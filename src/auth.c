#include <ctype.h>
#include <string.h>
#include <time.h>

#include "auth.h"
#include "common.h"
#include "db.h"
#include "db_exam.h"
#include "room.h"
#include "session.h"

static const char *const DUMMY_SALT = "0000000000000000";

static int valid_username(const char *name)
{
    size_t len = strlen(name);
    size_t i = 0;

    if (len < USERNAME_MIN || len > USERNAME_MAX) return 0;
    for (i = 0; i < len; i++) {
        if (!isalnum((unsigned char)name[i]) && name[i] != '_') return 0;
    }
    return 1;
}

static int valid_password(const char *password)
{
    size_t len = strlen(password);

    return len >= PASSWORD_MIN && len <= PASSWORD_MAX;
}

int handle_ping(request_t *req)
{
    return reply_ok(req, "PONG");
}

int handle_register(request_t *req)
{
    const char *username = req->argv[1];
    const char *password = req->argv[2];
    char salt[SALT_HEX_LEN + 1];
    char hash[HASH_HEX_LEN + 1];
    int rc = 0;

    if (!valid_username(username)) return reply_err(req, "BAD_ARGS", "username 3-20 chars [A-Za-z0-9_]");
    if (!valid_password(password)) return reply_err(req, "BAD_ARGS", "password 6-64 chars");
    if (random_hex(salt, SALT_HEX_LEN) != 0) return reply_err(req, "INTERNAL", "entropy unavailable");

    hash_password(salt, password, hash);
    rc = db_user_create(username, hash, salt, "user");
    if (rc == DB_EXISTS) return reply_err(req, "USER_EXISTS", "username taken");
    if (rc != DB_OK) return reply_err(req, "INTERNAL", "database error");

    log_msg(LOG_INFO, "fd=%d registered user=%s", req->sess->fd, username);
    return reply_ok(req, "REGISTERED");
}

static int verify_credentials(const char *username, const char *password, user_t *user)
{
    char hash[HASH_HEX_LEN + 1];
    int found = valid_username(username) ? db_user_find(username, user) : 0;

    if (found < 0) return -1;

    // hash even for unknown users so timing never reveals which field failed
    hash_password(found ? user->salt : DUMMY_SALT, password, hash);
    return found && secure_equals(hash, user->pass_hash);
}

int handle_login(request_t *req)
{
    user_t user;
    char token[TOKEN_LEN];
    strbuf_t *reply = NULL;
    int verified = 0;
    int resume_rid = 0;

    if (req->sess->user_id != 0) return reply_err(req, "ALREADY_LOGGED_IN", "connection already authenticated");
    memset(&user, 0, sizeof(user));
    verified = verify_credentials(req->argv[1], req->argv[2], &user);
    if (verified < 0) return reply_err(req, "INTERNAL", "database error");
    if (!verified) return reply_err(req, "BAD_CREDENTIALS", "invalid username or password");
    if (random_hex(token, TOKEN_HEX_LEN) != 0) return reply_err(req, "INTERNAL", "entropy unavailable");
    if (session_login(req->sess, &user, token) != 0) return reply_err(req, "ALREADY_LOGGED_IN", "account has an active session");

    log_msg(LOG_INFO, "fd=%d login user=%s role=%s", req->sess->fd, user.username, user.role);
    reply = reply_begin(req);
    sb_appendf(reply, "|%s|%s", token, user.role);

    // flag unfinished attempts so the client can offer RESUME
    resume_rid = db_resumable_room(user.id, (long long)time(NULL));
    if (resume_rid > 0) sb_appendf(reply, "|RESUME|%d", resume_rid);
    return 0;
}

int handle_logout(request_t *req)
{
    log_msg(LOG_INFO, "fd=%d logout user=%s", req->sess->fd, req->sess->username);
    room_on_signout(req->out, req->sess->user_id, req->sess->username);
    session_logout(req->sess);
    return reply_ok(req, "BYE");
}
