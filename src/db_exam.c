#include <string.h>

#include <sqlite3.h>

#include "common.h"
#include "db.h"
#include "db_exam.h"
#include "db_internal.h"

#define FINISH_BATCH 64

// copy full question rows so later bank edits never alter this exam
int db_snapshot_take(int rid, const char *difficulty, const char *topic, int count, int base)
{
    if (count <= 0) return 0;
    return db_execute("INSERT INTO room_questions (rid, qidx, qid, content, opt_a, opt_b, opt_c, opt_d, correct_opt, difficulty, topic, explanation) SELECT ?, ? + ROW_NUMBER() OVER (), qid, content, opt_a, opt_b, opt_c, opt_d, correct_opt, difficulty, topic, explanation FROM (SELECT * FROM questions WHERE (? = 'mixed' OR difficulty = ?) AND (? = 'all' OR topic = ?) ORDER BY RANDOM() LIMIT ?)", "iissssi", rid, base, difficulty, difficulty, topic, topic, count);
}

int db_snapshot_append(int rid, strbuf_t *sb)
{
    sqlite3_stmt *stmt = db_prepare("SELECT COALESCE(qid, 0), content, opt_a, opt_b, opt_c, opt_d, difficulty FROM room_questions WHERE rid = ? ORDER BY qidx", "i", rid);
    int count = 0;
    int col = 0;

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        sb_appendf(sb, "|%d", sqlite3_column_int(stmt, 0));
        for (col = 1; col <= 6; col++) {
            sb_append(sb, ":");
            sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, col));
        }
        count++;
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : count;
}

int db_room_start(int rid, long long now)
{
    return db_execute("UPDATE rooms SET status = 'RUNNING', start_ts = ? WHERE rid = ? AND status = 'WAITING'", "li", now, rid) == 1 ? DB_OK : DB_ERROR;
}

int db_room_next_expired(long long now)
{
    sqlite3_stmt *stmt = db_prepare("SELECT rid FROM rooms WHERE status = 'RUNNING' AND start_ts + duration_sec <= ? ORDER BY rid LIMIT 1", "l", now);
    int rid = 0;

    if (!stmt) return DB_ERROR;
    if (sqlite3_step(stmt) == SQLITE_ROW) rid = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return rid;
}

int db_attempt_get(int rid, int user_id, attempt_t *out)
{
    sqlite3_stmt *stmt = db_prepare("SELECT att_id, user_id, status = 'SUBMITTED' FROM attempts WHERE rid = ? AND user_id = ?", "ii", rid, user_id);
    int found = 0;

    if (!stmt) return DB_ERROR;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        out->att_id = sqlite3_column_int(stmt, 0);
        out->user_id = sqlite3_column_int(stmt, 1);
        out->submitted = sqlite3_column_int(stmt, 2);
        found = 1;
    }
    sqlite3_finalize(stmt);
    return found;
}

int db_answer_save(int att_id, int qidx, int opt)
{
    return db_execute("INSERT OR REPLACE INTO attempt_answers (att_id, qidx, chosen_opt) VALUES (?, ?, ?)", "iii", att_id, qidx, opt) < 0 ? DB_ERROR : DB_OK;
}

int db_attempt_submit(int att_id, long long submit_ts)
{
    int rc = db_execute("UPDATE attempts SET status = 'SUBMITTED', submit_ts = ?, score = (SELECT COUNT(*) FROM attempt_answers aa JOIN room_questions rq ON rq.rid = attempts.rid AND rq.qidx = aa.qidx WHERE aa.att_id = attempts.att_id AND aa.chosen_opt = rq.correct_opt) WHERE att_id = ? AND status = 'IN_PROGRESS'", "li", submit_ts, att_id);

    if (rc != 1) return DB_ERROR;
    return db_query_int("SELECT score FROM attempts WHERE att_id = ?", DB_ERROR, "i", att_id);
}

int db_room_pending(int rid)
{
    return db_query_int("SELECT COUNT(*) FROM attempts WHERE rid = ? AND status = 'IN_PROGRESS'", DB_ERROR, "i", rid);
}

static int pending_attempts(int rid, int *att_ids, int max_ids)
{
    sqlite3_stmt *stmt = db_prepare("SELECT att_id FROM attempts WHERE rid = ? AND status = 'IN_PROGRESS' ORDER BY att_id", "i", rid);
    int count = 0;

    if (!stmt) return DB_ERROR;
    while (count < max_ids && sqlite3_step(stmt) == SQLITE_ROW) att_ids[count++] = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return count;
}

int db_room_finish(int rid)
{
    int att_ids[FINISH_BATCH];
    int count = pending_attempts(rid, att_ids, FINISH_BATCH);
    int i = 0;
    int score = 0;

    if (count < 0) return DB_ERROR;

    // grade unsubmitted work with submit_ts 0 to mark auto-submit
    for (i = 0; i < count; i++) {
        score = db_attempt_submit(att_ids[i], 0);
        if (score < 0) return DB_ERROR;
        log_msg(LOG_INFO, "AUTO_SUBMIT room=%d att=%d score=%d", rid, att_ids[i], score);
    }
    if (db_execute("UPDATE rooms SET status = 'FINISHED' WHERE rid = ?", "i", rid) != 1) return DB_ERROR;
    return count;
}

int db_room_results(int rid, result_row_t *rows, int max_rows)
{
    sqlite3_stmt *stmt = db_prepare("SELECT a.user_id, u.username, COALESCE(a.score, 0), COALESCE(a.submit_ts, 0) FROM attempts a JOIN users u ON u.id = a.user_id WHERE a.rid = ? ORDER BY COALESCE(a.score, 0) DESC, COALESCE(a.submit_ts, 0) = 0, a.submit_ts, a.att_id", "i", rid);
    int count = 0;

    if (!stmt) return DB_ERROR;
    while (count < max_rows && sqlite3_step(stmt) == SQLITE_ROW) {
        rows[count].user_id = sqlite3_column_int(stmt, 0);
        db_column_copy(stmt, 1, rows[count].username, sizeof(rows[count].username));
        rows[count].score = sqlite3_column_int(stmt, 2);
        rows[count].submit_ts = sqlite3_column_int64(stmt, 3);
        count++;
    }
    sqlite3_finalize(stmt);
    return count;
}

int db_answer_mask(int att_id, char *mask, int num_q)
{
    sqlite3_stmt *stmt = db_prepare("SELECT qidx FROM attempt_answers WHERE att_id = ?", "i", att_id);
    int qidx = 0;

    if (!stmt) return DB_ERROR;
    memset(mask, '0', (size_t)num_q);
    mask[num_q] = '\0';
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        qidx = sqlite3_column_int(stmt, 0);
        if (qidx >= 1 && qidx <= num_q) mask[qidx - 1] = '1';
    }
    sqlite3_finalize(stmt);
    return DB_OK;
}

int db_resumable_room(int user_id, long long now)
{
    return db_query_int("SELECT a.rid FROM attempts a JOIN rooms r ON r.rid = a.rid WHERE a.user_id = ? AND a.status = 'IN_PROGRESS' AND r.status = 'RUNNING' AND r.start_ts + r.duration_sec > ? ORDER BY a.att_id DESC LIMIT 1", 0, "il", user_id, now);
}
