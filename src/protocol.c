#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

#include "auth.h"
#include "common.h"
#include "exam.h"
#include "practice.h"
#include "protocol.h"
#include "question.h"
#include "room.h"
#include "session.h"

typedef struct {
    const char *name;
    int         min_args;
    int         max_args;
    int         need_auth;
    int         admin_only;
    handler_fn  handler;
} command_t;

static const command_t COMMANDS[] = {
    { "PING", 1, 2, 0, 0, handle_ping },
    { "REGISTER", 3, 3, 0, 0, handle_register },
    { "LOGIN", 3, 3, 0, 0, handle_login },
    { "LOGOUT", 2, 2, 1, 0, handle_logout },
    { "LIST_QUESTIONS", 2, 2, 1, 1, handle_list_questions },
    { "ADD_QUESTION", 10, 11, 1, 1, handle_add_question },
    { "DEL_QUESTION", 3, 3, 1, 1, handle_del_question },
    { "IMPORT_CSV", 3, 3, 1, 1, handle_import_csv },
    { "CREATE_ROOM", 7, 7, 1, 0, handle_create_room },
    { "LIST_ROOMS", 2, 3, 1, 0, handle_list_rooms },
    { "JOIN", 3, 3, 1, 0, handle_join },
    { "LEAVE_ROOM", 3, 3, 1, 0, handle_leave_room },
    { "START_ROOM", 3, 3, 1, 0, handle_start_room },
    { "ANSWER", 5, 5, 1, 0, handle_answer },
    { "SUBMIT", 3, 3, 1, 0, handle_submit },
    { "END_ROOM", 3, 3, 1, 0, handle_end_room },
    { "GET_QUESTIONS", 3, 3, 1, 0, handle_get_questions },
    { "ROOM_RESULT", 3, 3, 1, 0, handle_room_result },
    { "PRACTICE", 6, 6, 1, 0, handle_practice },
    { "PRACTICE_SUBMIT", 3, 3, 1, 0, handle_submit },
    { "RESUME", 3, 3, 1, 0, handle_resume },
};

static pthread_mutex_t g_core_lock = PTHREAD_MUTEX_INITIALIZER;

void core_lock(void)
{
    pthread_mutex_lock(&g_core_lock);
}

void core_unlock(void)
{
    pthread_mutex_unlock(&g_core_lock);
}

void outbox_init(outbox_t *out)
{
    memset(out, 0, sizeof(*out));
    sb_init(&out->reply);
}

void outbox_free(outbox_t *out)
{
    int i = 0;

    for (i = 0; i < out->push_count; i++) free(out->pushes[i].payload);
    out->push_count = 0;
    sb_free(&out->reply);
}

int outbox_push(outbox_t *out, int user_id, const char *payload)
{
    char *copy = NULL;

    if (out->push_count >= MAX_PUSHES) {
        log_msg(LOG_WARN, "push queue full, dropped event for user_id=%d", user_id);
        return -1;
    }
    copy = strdup(payload);
    if (!copy) return -1;
    out->pushes[out->push_count].user_id = user_id;
    out->pushes[out->push_count++].payload = copy;
    return 0;
}

void outbox_flush(outbox_t *out, session_t *sess)
{
    int i = 0;

    // send reply first so the requester sees OK before its own events
    if (sess && out->reply.len > 0) session_send(sess, sb_str(&out->reply));
    for (i = 0; i < out->push_count; i++) session_push(out->pushes[i].user_id, out->pushes[i].payload);
}

strbuf_t *reply_begin(request_t *req)
{
    sb_reset(&req->out->reply);
    sb_append(&req->out->reply, "OK");
    return &req->out->reply;
}

int reply_ok(request_t *req, const char *tail)
{
    strbuf_t *reply = reply_begin(req);

    if (tail) sb_appendf(reply, "|%s", tail);
    return 0;
}

int reply_err(request_t *req, const char *code, const char *message)
{
    const char *cmd = req->argc > 0 ? req->argv[0] : "?";

    sb_reset(&req->out->reply);
    sb_appendf(&req->out->reply, "ERR|%s|", code);
    sb_append_escaped(&req->out->reply, message);
    log_msg(LOG_WARN, "fd=%d user=%s cmd=%s err=%s", req->sess->fd, req->sess->username, cmd, code);
    return -1;
}

static const command_t *find_command(const char *name)
{
    size_t i = 0;

    for (i = 0; i < sizeof(COMMANDS) / sizeof(COMMANDS[0]); i++) {
        if (strcmp(COMMANDS[i].name, name) == 0) return &COMMANDS[i];
    }
    return NULL;
}

static int check_access(request_t *req, const command_t *cmd)
{
    if (!cmd) return reply_err(req, "UNKNOWN_CMD", "unknown command");
    if (cmd->need_auth && (req->argc < 2 || !session_is_authenticated(req->sess, req->argv[1]))) return reply_err(req, "NOT_AUTHENTICATED", "invalid or expired token");
    if (cmd->admin_only && !session_is_admin(req->sess)) return reply_err(req, "FORBIDDEN", "admin only");
    if (req->argc < cmd->min_args || req->argc > cmd->max_args) return reply_err(req, "BAD_ARGS", "wrong field count");
    return 0;
}

static void log_request(const request_t *req)
{
    const char *cmd = req->argv[0];

    // mask credentials so passwords never reach console or log file
    if (strcmp(cmd, "REGISTER") == 0 || strcmp(cmd, "LOGIN") == 0) {
        log_msg(LOG_INFO, "fd=%d cmd=%s user=%s pass=***", req->sess->fd, cmd, req->argv[1]);
        return;
    }
    log_msg(LOG_INFO, "fd=%d user=%s cmd=%s argc=%d", req->sess->fd, req->sess->username, cmd, req->argc);
}

static void dispatch(request_t *req)
{
    const command_t *cmd = find_command(req->argv[0]);
    int i = 0;

    if (check_access(req, cmd) != 0) return;
    log_request(req);
    for (i = 1; i < req->argc; i++) unescape_inplace(req->argv[i]);

    // serialize core state; network flush happens after unlock
    core_lock();
    cmd->handler(req);
    core_unlock();
    if (req->out->reply.failed) reply_err(req, "INTERNAL", "reply too large");
}

void protocol_handle(session_t *sess, char *payload)
{
    char *argv[MAX_FIELDS];
    outbox_t out;
    request_t req = { sess, argv, 0, &out };

    outbox_init(&out);
    req.argc = split_fields(payload, argv, MAX_FIELDS);
    if (req.argc < 0) {
        req.argc = 1;
        reply_err(&req, "BAD_ARGS", "too many fields");
    } else {
        dispatch(&req);
    }
    outbox_flush(&out, sess);
    outbox_free(&out);
}

void protocol_disconnect(session_t *sess)
{
    outbox_t out;

    outbox_init(&out);
    log_msg(LOG_INFO, "fd=%d disconnected user=%s", sess->fd, sess->user_id ? sess->username : "-");

    // leave lobby rooms first so peers get MEMBER_LEFT or ROOM_CLOSED
    core_lock();
    if (sess->user_id) room_on_signout(&out, sess->user_id, sess->username);
    core_unlock();
    session_close(sess);
    outbox_flush(&out, NULL);
    outbox_free(&out);
}
