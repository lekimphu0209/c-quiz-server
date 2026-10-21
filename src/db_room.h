#ifndef DB_ROOM_H
#define DB_ROOM_H

#include "common.h"
#include "db.h"

#define ROOM_NAME_BYTES 256
#define ROOM_CFG_MAX 64
#define TOPIC_MAX 64
#define STATUS_MAX 16

typedef struct {
    int       rid;
    char      name[ROOM_NAME_BYTES];
    int       owner_id;
    char      owner[USERNAME_MAX + 1];
    int       num_q;
    int       duration;
    char      difficulty[ROOM_CFG_MAX];
    char      topic[TOPIC_MAX];
    char      status[STATUS_MAX];
    int       is_practice;
    long long start_ts;
} room_t;

typedef struct {
    const char *name;
    int         owner_id;
    int         num_q;
    int         duration;
    const char *difficulty;
    const char *topic;
    int         is_practice;
} room_spec_t;

long long db_room_insert(const room_spec_t *spec);
int db_room_get(int rid, room_t *out);
int db_room_list(strbuf_t *sb, const char *status);
int db_room_delete(int rid);
int db_room_reset_waiting(void);

int db_room_member_ids(int rid, int *ids, int max_ids);
int db_room_member_names(int rid, strbuf_t *sb);
int db_room_member_count(int rid);

int db_user_busy_room(int user_id);
int db_attempt_add(int rid, int user_id);
int db_attempt_remove(int rid, int user_id);
int db_attempt_exists(int rid, int user_id);

#endif
