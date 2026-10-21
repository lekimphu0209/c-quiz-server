#include <stdio.h>
#include <string.h>

#include "common.h"
#include "db.h"
#include "db_room.h"
#include "protocol.h"
#include "room.h"

size_t utf8_length(const char *text)
{
    size_t count = 0;

    for (; *text; text++) count += ((unsigned char)*text & 0xC0) != 0x80;
    return count;
}

static int *mix_slot(exam_mix_t *mix, const char *key, int *bit)
{
    if (strcmp(key, "easy") == 0) return (*bit = 1, &mix->easy);
    if (strcmp(key, "medium") == 0) return (*bit = 2, &mix->medium);
    if (strcmp(key, "hard") == 0) return (*bit = 4, &mix->hard);
    return NULL;
}

static int apply_mix_item(char *item, exam_mix_t *mix, int *seen)
{
    char *colon = strchr(item, ':');
    int *slot = NULL;
    int bit = 0;
    int value = 0;

    if (!colon) return -1;
    *colon = '\0';
    slot = mix_slot(mix, item, &bit);
    if (!slot || (*seen & bit) || parse_int(colon + 1, &value) != 0 || value < 0) return -1;
    *slot = value;
    *seen |= bit;
    return 0;
}

int parse_exam_mix(const char *text, int num_q, exam_mix_t *out)
{
    char copy[ROOM_CFG_MAX];
    char *item = copy;
    char *next = NULL;
    int seen = 0;
    int bit = 0;
    int *single = NULL;

    memset(out, 0, sizeof(*out));
    if (!text || strlen(text) >= sizeof(copy)) return -1;
    if (strcmp(text, "mixed") == 0) return (out->mixed = num_q, 0);
    snprintf(copy, sizeof(copy), "%s", text);
    single = mix_slot(out, copy, &bit);
    if (single) return (*single = num_q, 0);

    // walk comma list; each difficulty key may appear only once
    for (; item; item = next) {
        next = strchr(item, ',');
        if (next) *next++ = '\0';
        if (apply_mix_item(item, out, &seen) != 0) return -1;
    }
    return out->easy + out->medium + out->hard == num_q ? 0 : -1;
}

int exam_mix_available(const exam_mix_t *mix, const char *topic)
{
    if (mix->mixed > 0) return db_question_count("mixed", topic) >= mix->mixed;
    if (db_question_count("easy", topic) < mix->easy) return 0;
    if (db_question_count("medium", topic) < mix->medium) return 0;
    return db_question_count("hard", topic) >= mix->hard;
}

int room_load(request_t *req, room_t *room)
{
    int rid = 0;
    int found = 0;

    if (parse_int(req->argv[2], &rid) != 0 || rid <= 0) return reply_err(req, "BAD_ARGS", "room id must be a positive integer");
    found = db_room_get(rid, room);
    if (found < 0) return reply_err(req, "INTERNAL", "database error");

    // hide other users' practice rooms behind NO_ROOM
    if (!found || (room->is_practice && room->owner_id != req->sess->user_id)) return reply_err(req, "NO_ROOM", "room not found");
    return 0;
}

int room_broadcast(outbox_t *out, int rid, int skip_user, const char *payload)
{
    int ids[MAX_PARTICIPANTS + 1];
    int count = db_room_member_ids(rid, ids, MAX_PARTICIPANTS + 1);
    int i = 0;

    for (i = 0; i < count; i++) {
        if (ids[i] != skip_user) outbox_push(out, ids[i], payload);
    }
    return count < 0 ? -1 : 0;
}

static int leave_waiting(outbox_t *out, const room_t *room, int user_id, const char *username)
{
    char event[128];
    int rc = 0;

    if (room->owner_id != user_id) {
        if (db_attempt_remove(room->rid, user_id) < 0) return -1;
        snprintf(event, sizeof(event), "EVT|MEMBER_LEFT|%d|%s", room->rid, username);
        log_msg(LOG_INFO, "user=%s left room=%d", username, room->rid);
        return room_broadcast(out, room->rid, user_id, event);
    }

    // owner leaving a lobby cancels the room for everyone
    snprintf(event, sizeof(event), "EVT|ROOM_CLOSED|%d", room->rid);
    room_broadcast(out, room->rid, user_id, event);
    if (db_begin() != DB_OK) return -1;
    rc = db_room_delete(room->rid);
    if (rc != DB_OK) {
        db_rollback();
        return -1;
    }
    log_msg(LOG_INFO, "owner=%s closed room=%d", username, room->rid);
    return db_commit();
}

void room_on_signout(outbox_t *out, int user_id, const char *username)
{
    room_t room;
    int rid = db_user_busy_room(user_id);

    if (rid <= 0 || db_room_get(rid, &room) != 1) return;
    if (strcmp(room.status, "WAITING") == 0) leave_waiting(out, &room, user_id, username);
}

static const char *validate_create(request_t *req, room_spec_t *spec, exam_mix_t *mix)
{
    size_t name_chars = utf8_length(req->argv[2]);

    spec->name = req->argv[2];
    spec->owner_id = req->sess->user_id;
    spec->difficulty = req->argv[5];
    spec->topic = req->argv[6];
    if (name_chars < 1 || name_chars > ROOM_NAME_CHARS) return "room name must be 1-50 characters";
    if (parse_int(req->argv[3], &spec->num_q) != 0 || spec->num_q < ROOM_N_MIN || spec->num_q > ROOM_N_MAX) return "n must be 1-100";
    if (parse_int(req->argv[4], &spec->duration) != 0 || spec->duration < ROOM_SEC_MIN || spec->duration > ROOM_SEC_MAX) return "sec must be 60-14400";
    if (parse_exam_mix(spec->difficulty, spec->num_q, mix) != 0) return "difficulty must be mixed or easy:a,medium:b,hard:c summing to n";
    if (!*spec->topic || strlen(spec->topic) >= TOPIC_MAX) return "topic must be 1-63 bytes";
    return NULL;
}

static long long create_room_tx(const room_spec_t *spec)
{
    long long rid = 0;

    if (db_begin() != DB_OK) return DB_ERROR;
    rid = db_room_insert(spec);
    if (rid < 0) {
        db_rollback();
        return DB_ERROR;
    }
    return db_commit() == DB_OK ? rid : DB_ERROR;
}

int handle_create_room(request_t *req)
{
    room_spec_t spec;
    exam_mix_t mix;
    const char *problem = NULL;
    long long rid = 0;
    int busy = 0;

    memset(&spec, 0, sizeof(spec));
    problem = validate_create(req, &spec, &mix);
    if (problem) return reply_err(req, "BAD_ARGS", problem);
    busy = db_user_busy_room(req->sess->user_id);
    if (busy != 0) return reply_err(req, busy < 0 ? "INTERNAL" : "BAD_STATE", "already in another room or exam");
    if (!exam_mix_available(&mix, spec.topic)) return reply_err(req, "NOT_ENOUGH_QUESTIONS", "question bank too small for this config");

    rid = create_room_tx(&spec);
    if (rid < 0) return reply_err(req, "INTERNAL", "database error");
    log_msg(LOG_INFO, "fd=%d user=%s created room=%lld n=%d sec=%d", req->sess->fd, req->sess->username, rid, spec.num_q, spec.duration);
    sb_appendf(reply_begin(req), "|%lld", rid);
    return 0;
}

int handle_list_rooms(request_t *req)
{
    const char *filter = req->argc > 2 ? req->argv[2] : "ALL";
    const char *allowed[] = { "ALL", "WAITING", "RUNNING", "FINISHED" };
    size_t i = 0;

    for (i = 0; i < sizeof(allowed) / sizeof(allowed[0]); i++) {
        if (strcmp(filter, allowed[i]) == 0) break;
    }
    if (i == sizeof(allowed) / sizeof(allowed[0])) return reply_err(req, "BAD_ARGS", "filter must be ALL|WAITING|RUNNING|FINISHED");
    if (db_room_list(reply_begin(req), filter) != DB_OK) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

static int check_joinable(request_t *req, const room_t *room)
{
    int uid = req->sess->user_id;
    int member = db_attempt_exists(room->rid, uid);
    int busy = 0;

    if (room->is_practice) return reply_err(req, "NO_ROOM", "room not found");
    if (member != 0) return reply_err(req, member < 0 ? "INTERNAL" : "ALREADY_JOINED", "already a member");
    if (strcmp(room->status, "WAITING") != 0) return reply_err(req, "ROOM_STARTED", "room already started");
    busy = db_user_busy_room(uid);
    if (busy != 0) return reply_err(req, busy < 0 ? "INTERNAL" : "BAD_STATE", "already in another room or exam");
    if (db_room_member_count(room->rid) >= MAX_PARTICIPANTS) return reply_err(req, "ROOM_FULL", "room is full");
    return 0;
}

static int reply_joined(request_t *req, const room_t *room)
{
    strbuf_t *reply = reply_begin(req);

    sb_appendf(reply, "|JOINED|%d|", room->rid);
    sb_append_escaped(reply, room->name);
    sb_appendf(reply, "|%s|%d|%d|%s|", room->owner, room->num_q, room->duration, room->difficulty);
    if (db_room_member_names(room->rid, reply) < 0) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

int handle_join(request_t *req)
{
    room_t room;
    char event[128];

    if (room_load(req, &room) != 0) return -1;
    if (check_joinable(req, &room) != 0) return -1;
    snprintf(event, sizeof(event), "EVT|MEMBER_JOINED|%d|%s", room.rid, req->sess->username);
    if (room_broadcast(req->out, room.rid, req->sess->user_id, event) != 0) return reply_err(req, "INTERNAL", "database error");
    if (db_attempt_add(room.rid, req->sess->user_id) != DB_OK) return reply_err(req, "INTERNAL", "database error");

    log_msg(LOG_INFO, "fd=%d user=%s joined room=%d", req->sess->fd, req->sess->username, room.rid);
    return reply_joined(req, &room);
}

int handle_leave_room(request_t *req)
{
    room_t room;
    int member = 0;

    if (room_load(req, &room) != 0) return -1;
    member = db_attempt_exists(room.rid, req->sess->user_id);
    if (member < 0) return reply_err(req, "INTERNAL", "database error");
    if (!member) return reply_err(req, "BAD_STATE", "not a member of this room");
    if (strcmp(room.status, "WAITING") != 0) return reply_err(req, "BAD_STATE", "room already started");
    if (leave_waiting(req->out, &room, req->sess->user_id, req->sess->username) != 0) return reply_err(req, "INTERNAL", "database error");
    return reply_ok(req, "LEFT");
}
