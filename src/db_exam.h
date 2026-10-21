#ifndef DB_EXAM_H
#define DB_EXAM_H

#include "common.h"
#include "db.h"

typedef struct {
    int att_id;
    int user_id;
    int submitted;
} attempt_t;

typedef struct {
    int       user_id;
    char      username[USERNAME_MAX + 1];
    int       score;
    long long submit_ts;
} result_row_t;

int db_snapshot_take(int rid, const char *difficulty, const char *topic, int count, int base);
int db_snapshot_append(int rid, strbuf_t *sb);
int db_room_start(int rid, long long now);
int db_room_next_expired(long long now);

int db_attempt_get(int rid, int user_id, attempt_t *out);
int db_answer_save(int att_id, int qidx, int opt);
int db_attempt_submit(int att_id, long long submit_ts);
int db_room_pending(int rid);
int db_room_finish(int rid);
int db_room_results(int rid, result_row_t *rows, int max_rows);

#endif
