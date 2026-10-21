#include <stdio.h>
#include <string.h>
#include <time.h>

#include "common.h"
#include "db.h"
#include "db_exam.h"
#include "db_room.h"
#include "exam.h"
#include "practice.h"
#include "protocol.h"
#include "room.h"

static int valid_practice_difficulty(const char *difficulty)
{
    const char *allowed[] = { "easy", "medium", "hard", "mixed" };
    size_t i = 0;

    for (i = 0; i < sizeof(allowed) / sizeof(allowed[0]); i++) {
        if (strcmp(difficulty, allowed[i]) == 0) return 1;
    }
    return 0;
}

static const char *validate_practice(request_t *req, room_spec_t *spec, exam_mix_t *mix)
{
    spec->owner_id = req->sess->user_id;
    spec->difficulty = req->argv[4];
    spec->topic = req->argv[5];
    spec->is_practice = 1;
    if (parse_int(req->argv[2], &spec->num_q) != 0 || spec->num_q < ROOM_N_MIN || spec->num_q > ROOM_N_MAX) return "n must be 1-100";
    if (parse_int(req->argv[3], &spec->duration) != 0 || spec->duration < PRACTICE_SEC_MIN || spec->duration > ROOM_SEC_MAX) return "sec must be 1-14400";
    if (!valid_practice_difficulty(spec->difficulty)) return "difficulty must be easy|medium|hard|mixed";
    if (!*spec->topic || strlen(spec->topic) >= TOPIC_MAX) return "topic must be 1-63 bytes";
    return parse_exam_mix(spec->difficulty, spec->num_q, mix) == 0 ? NULL : "invalid difficulty";
}

static long long create_practice_tx(const room_spec_t *spec, const exam_mix_t *mix)
{
    long long rid = 0;

    if (db_begin() != DB_OK) return DB_ERROR;
    rid = db_room_insert(spec);

    // room, attempt and snapshot commit together or not at all
    if (rid < 0 || exam_take_snapshot((int)rid, mix, spec->topic, spec->num_q) != DB_OK) {
        db_rollback();
        return DB_ERROR;
    }
    return db_commit() == DB_OK ? rid : DB_ERROR;
}

int handle_practice(request_t *req)
{
    room_spec_t spec;
    exam_mix_t mix;
    char name[ROOM_NAME_BYTES];
    const char *problem = NULL;
    long long rid = 0;
    int busy = 0;

    memset(&spec, 0, sizeof(spec));
    problem = validate_practice(req, &spec, &mix);
    if (problem) return reply_err(req, "BAD_ARGS", problem);
    busy = db_user_busy_room(req->sess->user_id);
    if (busy != 0) return reply_err(req, busy < 0 ? "INTERNAL" : "BAD_STATE", "already in another room or exam");
    if (!exam_mix_available(&mix, spec.topic)) return reply_err(req, "NOT_ENOUGH_QUESTIONS", "question bank too small for this filter");

    snprintf(name, sizeof(name), "practice:%s", req->sess->username);
    spec.name = name;
    rid = create_practice_tx(&spec, &mix);
    if (rid < 0) return reply_err(req, "INTERNAL", "database error");
    log_msg(LOG_INFO, "fd=%d user=%s practice room=%lld n=%d sec=%d", req->sess->fd, req->sess->username, rid, spec.num_q, spec.duration);

    sb_appendf(reply_begin(req), "|PRACTICE|%lld|%d|%d", rid, spec.num_q, spec.duration);
    if (db_snapshot_append((int)rid, &req->out->reply) < 0) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

int handle_resume(request_t *req)
{
    room_t room;
    attempt_t attempt;
    char mask[ROOM_N_MAX + 1];
    long long remaining = 0;

    if (exam_load_member(req, &room, &attempt) != 0) return -1;
    if (exam_check_active(req, &room, &attempt) != 0) return -1;
    if (db_answer_mask(attempt.att_id, mask, room.num_q) != DB_OK) return reply_err(req, "INTERNAL", "database error");

    remaining = room.start_ts + room.duration - (long long)time(NULL);
    log_msg(LOG_INFO, "fd=%d user=%s resumed room=%d remaining=%lld", req->sess->fd, req->sess->username, room.rid, remaining);
    sb_appendf(reply_begin(req), "|RESUME|%d|%d|%lld|%s", room.rid, room.num_q, remaining, mask);
    if (db_snapshot_append(room.rid, &req->out->reply) < 0) return reply_err(req, "INTERNAL", "database error");
    return 0;
}
