#ifndef DB_STATS_H
#define DB_STATS_H

#include "common.h"

typedef struct {
    int correct;
    int total;
} tally_t;

typedef struct {
    int     attempts;
    int     avg_x100;
    tally_t easy;
    tally_t medium;
    tally_t hard;
} stats_t;

int db_history_list(int user_id, const char *mode, strbuf_t *sb);
int db_attempt_owner(int att_id, int *user_id, int *finished);
int db_history_detail(int att_id, strbuf_t *sb);
int db_stats_collect(int user_id, stats_t *out);
int db_stats_topics(int user_id, strbuf_t *sb);

#endif
