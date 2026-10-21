#include <string.h>

#include <sqlite3.h>

#include "common.h"
#include "db.h"
#include "db_internal.h"
#include "db_stats.h"

#define ANSWER_JOIN "FROM attempts a JOIN room_questions rq ON rq.rid = a.rid LEFT JOIN attempt_answers aa ON aa.att_id = a.att_id AND aa.qidx = rq.qidx WHERE a.status = 'SUBMITTED' AND (? = 0 OR a.user_id = ?)"

// fall back to deadline when auto-submit stored submit_ts as 0
int db_history_list(int user_id, const char *mode, strbuf_t *sb)
{
    sqlite3_stmt *stmt = db_prepare("SELECT a.att_id, CASE WHEN a.submit_ts > 0 THEN a.submit_ts ELSE r.start_ts + r.duration_sec END AS ts, CASE WHEN r.is_practice = 1 THEN 'practice' ELSE 'room' END, r.name, COALESCE(a.score, 0), r.num_q FROM attempts a JOIN rooms r ON r.rid = a.rid WHERE a.user_id = ? AND a.status = 'SUBMITTED' AND (? = 'all' OR (? = 'practice' AND r.is_practice = 1) OR (? = 'room' AND r.is_practice = 0)) ORDER BY ts DESC, a.att_id DESC", "isss", user_id, mode, mode, mode);

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        sb_appendf(sb, "|%d:%lld:%s:", sqlite3_column_int(stmt, 0), (long long)sqlite3_column_int64(stmt, 1), (const char *)sqlite3_column_text(stmt, 2));
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 3));
        sb_appendf(sb, ":%d:%d", sqlite3_column_int(stmt, 4), sqlite3_column_int(stmt, 5));
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : DB_OK;
}

int db_attempt_owner(int att_id, int *user_id, int *finished)
{
    sqlite3_stmt *stmt = db_prepare("SELECT a.user_id, r.status = 'FINISHED' FROM attempts a JOIN rooms r ON r.rid = a.rid WHERE a.att_id = ?", "i", att_id);
    int found = 0;

    if (!stmt) return DB_ERROR;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        *user_id = sqlite3_column_int(stmt, 0);
        *finished = sqlite3_column_int(stmt, 1);
        found = 1;
    }
    sqlite3_finalize(stmt);
    return found;
}

int db_history_detail(int att_id, strbuf_t *sb)
{
    sqlite3_stmt *stmt = db_prepare("SELECT rq.qidx, COALESCE(aa.chosen_opt, -1), rq.correct_opt, rq.explanation FROM attempts a JOIN room_questions rq ON rq.rid = a.rid LEFT JOIN attempt_answers aa ON aa.att_id = a.att_id AND aa.qidx = rq.qidx WHERE a.att_id = ? ORDER BY rq.qidx", "i", att_id);

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        sb_appendf(sb, "|%d:%d:%d:", sqlite3_column_int(stmt, 0), sqlite3_column_int(stmt, 1), sqlite3_column_int(stmt, 2));
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 3));
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : DB_OK;
}

static tally_t *tally_for(stats_t *out, const char *difficulty)
{
    if (strcmp(difficulty, "easy") == 0) return &out->easy;
    if (strcmp(difficulty, "medium") == 0) return &out->medium;
    if (strcmp(difficulty, "hard") == 0) return &out->hard;
    return NULL;
}

static int collect_difficulty(int user_id, stats_t *out)
{
    sqlite3_stmt *stmt = db_prepare("SELECT rq.difficulty, COALESCE(SUM(aa.chosen_opt = rq.correct_opt), 0), COUNT(*) " ANSWER_JOIN " GROUP BY rq.difficulty", "ii", user_id, user_id);
    tally_t *tally = NULL;

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        tally = tally_for(out, (const char *)sqlite3_column_text(stmt, 0));
        if (!tally) continue;
        tally->correct = sqlite3_column_int(stmt, 1);
        tally->total = sqlite3_column_int(stmt, 2);
    }
    sqlite3_finalize(stmt);
    return DB_OK;
}

int db_stats_collect(int user_id, stats_t *out)
{
    memset(out, 0, sizeof(*out));
    out->attempts = db_query_int("SELECT COUNT(*) FROM attempts WHERE status = 'SUBMITTED' AND (? = 0 OR user_id = ?)", DB_ERROR, "ii", user_id, user_id);
    if (out->attempts < 0) return DB_ERROR;
    out->avg_x100 = db_query_int("SELECT CAST(ROUND(AVG(score) * 100) AS INTEGER) FROM attempts WHERE status = 'SUBMITTED' AND (? = 0 OR user_id = ?)", 0, "ii", user_id, user_id);
    return collect_difficulty(user_id, out);
}

int db_stats_topics(int user_id, strbuf_t *sb)
{
    sqlite3_stmt *stmt = db_prepare("SELECT rq.topic, COALESCE(SUM(aa.chosen_opt = rq.correct_opt), 0), COUNT(*) " ANSWER_JOIN " GROUP BY rq.topic ORDER BY rq.topic", "ii", user_id, user_id);
    int count = 0;

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        if (count++ > 0) sb_append(sb, ",");
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 0));
        sb_appendf(sb, ":%d/%d", sqlite3_column_int(stmt, 1), sqlite3_column_int(stmt, 2));
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : DB_OK;
}
