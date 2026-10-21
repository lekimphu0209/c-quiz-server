#include <stdio.h>
#include <string.h>
#include <time.h>
#include <pthread.h>

#include "common.h"
#include "db.h"
#include "db_exam.h"
#include "db_room.h"
#include "exam.h"
#include "protocol.h"
#include "room.h"

#define TICK_MAX_ROOMS 32

static pthread_t g_ticker;
static int g_ticker_started = 0;
static int g_ticker_stop = 0;
static pthread_mutex_t g_ticker_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_ticker_cond = PTHREAD_COND_INITIALIZER;

int exam_take_snapshot(int rid, const exam_mix_t *mix, const char *topic, int num_q)
{
    int taken = 0;

    if (mix->mixed > 0) taken = db_snapshot_take(rid, "mixed", topic, mix->mixed, 0);
    if (mix->mixed > 0) return taken == num_q ? DB_OK : DB_ERROR;

    // stack difficulty blocks so qidx stays contiguous 1..n
    taken = db_snapshot_take(rid, "easy", topic, mix->easy, 0);
    if (taken != mix->easy) return DB_ERROR;
    taken = db_snapshot_take(rid, "medium", topic, mix->medium, mix->easy);
    if (taken != mix->medium) return DB_ERROR;
    taken = db_snapshot_take(rid, "hard", topic, mix->hard, mix->easy + mix->medium);
    return taken == mix->hard ? DB_OK : DB_ERROR;
}

static int push_results(outbox_t *out, const room_t *room)
{
    result_row_t rows[MAX_PARTICIPANTS];
    char event[128];
    char rank[16];
    int count = db_room_results(room->rid, rows, MAX_PARTICIPANTS);
    int i = 0;

    for (i = 0; i < count; i++) {
        snprintf(rank, sizeof(rank), "%d", i + 1);
        snprintf(event, sizeof(event), "EVT|RESULT|%d|%d/%d|%s", room->rid, rows[i].score, room->num_q, room->is_practice ? "-" : rank);
        outbox_push(out, rows[i].user_id, event);
    }
    return count < 0 ? -1 : 0;
}

int exam_finalize(outbox_t *out, const room_t *room)
{
    if (db_begin() != DB_OK) return -1;

    // grade and close atomically so a crash never leaves half-graded rooms
    if (db_room_finish(room->rid) < 0) {
        db_rollback();
        return -1;
    }
    if (db_commit() != DB_OK) return -1;
    log_msg(LOG_INFO, "ROOM_FINISHED room=%d", room->rid);
    return push_results(out, room);
}

static int load_member(request_t *req, room_t *room, attempt_t *attempt)
{
    int found = 0;

    if (room_load(req, room) != 0) return -1;
    found = db_attempt_get(room->rid, req->sess->user_id, attempt);
    if (found < 0) return reply_err(req, "INTERNAL", "database error");
    if (!found) return reply_err(req, "FORBIDDEN", "not a member of this room");
    return 0;
}

static int check_active(request_t *req, const room_t *room, const attempt_t *attempt)
{
    long long now = (long long)time(NULL);

    if (strcmp(room->status, "WAITING") == 0) return reply_err(req, "BAD_STATE", "exam not started");
    if (strcmp(room->status, "FINISHED") == 0) return reply_err(req, "EXAM_ENDED", "exam finished");
    if (attempt->submitted) return reply_err(req, "ALREADY_SUBMITTED", "attempt already submitted");
    if (now >= room->start_ts + room->duration) return reply_err(req, "EXAM_ENDED", "time is up");
    return 0;
}

static int start_room_tx(const room_t *room, const exam_mix_t *mix)
{
    if (db_begin() != DB_OK) return -1;
    if (exam_take_snapshot(room->rid, mix, room->topic, room->num_q) != DB_OK || db_room_start(room->rid, (long long)time(NULL)) != DB_OK) {
        db_rollback();
        return -1;
    }
    return db_commit() == DB_OK ? 0 : -1;
}

static int announce_exam(request_t *req, const room_t *room)
{
    strbuf_t body;
    strbuf_t event;
    strbuf_t *reply = reply_begin(req);
    int rc = 0;

    sb_init(&body);
    sb_init(&event);
    if (db_snapshot_append(room->rid, &body) < 0) rc = reply_err(req, "INTERNAL", "database error");
    if (rc == 0) {
        sb_appendf(reply, "|STARTED|%d|%d|%d%s", room->rid, room->num_q, room->duration, sb_str(&body));
        sb_appendf(&event, "EVT|EXAM|%d|%d|%d%s", room->rid, room->num_q, room->duration, sb_str(&body));
        room_broadcast(req->out, room->rid, req->sess->user_id, sb_str(&event));
    }
    sb_free(&body);
    sb_free(&event);
    return rc;
}

int handle_start_room(request_t *req)
{
    room_t room;
    exam_mix_t mix;

    if (room_load(req, &room) != 0) return -1;
    if (room.owner_id != req->sess->user_id) return reply_err(req, "FORBIDDEN", "only the owner can start");
    if (strcmp(room.status, "WAITING") != 0) return reply_err(req, "BAD_STATE", "room is not waiting");
    if (db_room_member_count(room.rid) < 2) return reply_err(req, "BAD_STATE", "need at least 2 members");
    if (parse_exam_mix(room.difficulty, room.num_q, &mix) != 0 || !exam_mix_available(&mix, room.topic)) return reply_err(req, "NOT_ENOUGH_QUESTIONS", "question bank too small for this config");
    if (start_room_tx(&room, &mix) != 0) return reply_err(req, "INTERNAL", "database error");

    log_msg(LOG_INFO, "fd=%d owner=%s started room=%d", req->sess->fd, req->sess->username, room.rid);
    return announce_exam(req, &room);
}

int handle_answer(request_t *req)
{
    room_t room;
    attempt_t attempt;
    int qidx = 0;
    int opt = 0;

    if (load_member(req, &room, &attempt) != 0) return -1;
    if (check_active(req, &room, &attempt) != 0) return -1;
    if (parse_int(req->argv[3], &qidx) != 0 || qidx < 1 || qidx > room.num_q) return reply_err(req, "BAD_ARGS", "qidx out of range");
    if (parse_int(req->argv[4], &opt) != 0 || opt < 0 || opt > 3) return reply_err(req, "BAD_ARGS", "opt must be 0-3");
    if (db_answer_save(attempt.att_id, qidx, opt) != DB_OK) return reply_err(req, "INTERNAL", "database error");

    log_msg(LOG_INFO, "ANSWER user=%s room=%d idx=%d opt=%d", req->sess->username, room.rid, qidx, opt);
    return reply_ok(req, NULL);
}

int handle_submit(request_t *req)
{
    room_t room;
    attempt_t attempt;
    int score = 0;

    if (load_member(req, &room, &attempt) != 0) return -1;
    if (check_active(req, &room, &attempt) != 0) return -1;
    score = db_attempt_submit(attempt.att_id, (long long)time(NULL));
    if (score < 0) return reply_err(req, "INTERNAL", "database error");

    log_msg(LOG_INFO, "SUBMIT user=%s room=%d score=%d/%d", req->sess->username, room.rid, score, room.num_q);
    sb_appendf(reply_begin(req), "|%d|%d", score, room.num_q);

    // last submission closes the room early for everyone
    if (db_room_pending(room.rid) == 0) exam_finalize(req->out, &room);
    return 0;
}

int handle_end_room(request_t *req)
{
    room_t room;

    if (room_load(req, &room) != 0) return -1;
    if (room.owner_id != req->sess->user_id) return reply_err(req, "FORBIDDEN", "only the owner can end");
    if (strcmp(room.status, "RUNNING") != 0) return reply_err(req, "BAD_STATE", "room is not running");
    if (exam_finalize(req->out, &room) != 0) return reply_err(req, "INTERNAL", "database error");

    log_msg(LOG_INFO, "fd=%d owner=%s ended room=%d", req->sess->fd, req->sess->username, room.rid);
    return reply_ok(req, "ENDED");
}

int handle_get_questions(request_t *req)
{
    room_t room;
    attempt_t attempt;
    strbuf_t *reply = NULL;

    if (load_member(req, &room, &attempt) != 0) return -1;
    if (strcmp(room.status, "RUNNING") != 0) return reply_err(req, "BAD_STATE", "room is not running");
    reply = reply_begin(req);
    sb_appendf(reply, "|%d|%d", room.num_q, room.duration);
    if (db_snapshot_append(room.rid, reply) < 0) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

int handle_room_result(request_t *req)
{
    room_t room;
    result_row_t rows[MAX_PARTICIPANTS];
    strbuf_t *reply = NULL;
    int count = 0;
    int i = 0;

    if (room_load(req, &room) != 0) return -1;
    if (strcmp(room.status, "FINISHED") != 0) return reply_err(req, "ROOM_NOT_FINISHED", "room not finished");
    count = db_room_results(room.rid, rows, MAX_PARTICIPANTS);
    if (count < 0) return reply_err(req, "INTERNAL", "database error");

    reply = reply_begin(req);
    sb_appendf(reply, "|%d", room.num_q);
    for (i = 0; i < count; i++) sb_appendf(reply, "|%d:%s:%d:%lld", i + 1, rows[i].username, rows[i].score, rows[i].submit_ts);
    return 0;
}

static int finalize_one_expired(void)
{
    outbox_t out;
    room_t room;
    int rid = 0;

    outbox_init(&out);
    core_lock();
    rid = db_room_next_expired((long long)time(NULL));
    if (rid > 0 && db_room_get(rid, &room) == 1 && exam_finalize(&out, &room) != 0) rid = -1;
    core_unlock();

    // push RESULT events only after releasing the core lock
    outbox_flush(&out, NULL);
    outbox_free(&out);
    return rid;
}

static void *ticker_main(void *arg)
{
    struct timespec deadline;
    int i = 0;

    (void)arg;
    pthread_mutex_lock(&g_ticker_lock);
    while (!g_ticker_stop) {
        clock_gettime(CLOCK_REALTIME, &deadline);
        deadline.tv_sec += 1;
        pthread_cond_timedwait(&g_ticker_cond, &g_ticker_lock, &deadline);
        if (g_ticker_stop) break;
        pthread_mutex_unlock(&g_ticker_lock);
        for (i = 0; i < TICK_MAX_ROOMS && finalize_one_expired() > 0; i++) continue;
        pthread_mutex_lock(&g_ticker_lock);
    }
    pthread_mutex_unlock(&g_ticker_lock);
    return NULL;
}

int exam_ticker_start(void)
{
    g_ticker_stop = 0;
    if (pthread_create(&g_ticker, NULL, ticker_main, NULL) != 0) return -1;
    g_ticker_started = 1;
    return 0;
}

void exam_ticker_stop(void)
{
    if (!g_ticker_started) return;
    pthread_mutex_lock(&g_ticker_lock);
    g_ticker_stop = 1;
    pthread_cond_signal(&g_ticker_cond);
    pthread_mutex_unlock(&g_ticker_lock);
    pthread_join(g_ticker, NULL);
    g_ticker_started = 0;
}
