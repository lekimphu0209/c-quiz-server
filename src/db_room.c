#include <time.h>

#include <sqlite3.h>

#include "common.h"
#include "db.h"
#include "db_internal.h"
#include "db_room.h"

long long db_room_insert(const room_spec_t *spec)
{
    long long now = (long long)time(NULL);
    long long rid = 0;
    const char *status = spec->is_practice ? "RUNNING" : "WAITING";
    int rc = db_execute("INSERT INTO rooms (name, owner_id, num_q, duration_sec, difficulty_cfg, topic, status, is_practice, start_ts, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", "siiisssizl", spec->name, spec->owner_id, spec->num_q, spec->duration, spec->difficulty, spec->topic, status, spec->is_practice, spec->is_practice ? now : 0LL, now);

    if (rc < 0) return DB_ERROR;
    rid = db_last_insert_id();
    if (db_attempt_add((int)rid, spec->owner_id) != DB_OK) return DB_ERROR;
    return rid;
}

int db_room_get(int rid, room_t *out)
{
    sqlite3_stmt *stmt = db_prepare("SELECT r.rid, r.name, r.owner_id, u.username, r.num_q, r.duration_sec, r.difficulty_cfg, r.topic, r.status, r.is_practice, COALESCE(r.start_ts, 0) FROM rooms r JOIN users u ON u.id = r.owner_id WHERE r.rid = ?", "i", rid);
    int found = 0;

    if (!stmt) return DB_ERROR;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        out->rid = sqlite3_column_int(stmt, 0);
        db_column_copy(stmt, 1, out->name, sizeof(out->name));
        out->owner_id = sqlite3_column_int(stmt, 2);
        db_column_copy(stmt, 3, out->owner, sizeof(out->owner));
        out->num_q = sqlite3_column_int(stmt, 4);
        out->duration = sqlite3_column_int(stmt, 5);
        db_column_copy(stmt, 6, out->difficulty, sizeof(out->difficulty));
        db_column_copy(stmt, 7, out->topic, sizeof(out->topic));
        db_column_copy(stmt, 8, out->status, sizeof(out->status));
        out->is_practice = sqlite3_column_int(stmt, 9);
        out->start_ts = sqlite3_column_int64(stmt, 10);
        found = 1;
    }
    sqlite3_finalize(stmt);
    return found;
}

int db_room_list(strbuf_t *sb, const char *status)
{
    sqlite3_stmt *stmt = db_prepare("SELECT r.rid, r.name, u.username, r.status, r.num_q, r.duration_sec, (SELECT COUNT(*) FROM attempts a WHERE a.rid = r.rid) FROM rooms r JOIN users u ON u.id = r.owner_id WHERE r.is_practice = 0 AND (? = 'ALL' OR r.status = ?) ORDER BY r.rid", "ss", status, status);

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        sb_appendf(sb, "|%d:", sqlite3_column_int(stmt, 0));
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 1));
        sb_appendf(sb, ":%s:%s:%d:%d:%d", (const char *)sqlite3_column_text(stmt, 2), (const char *)sqlite3_column_text(stmt, 3), sqlite3_column_int(stmt, 4), sqlite3_column_int(stmt, 5), sqlite3_column_int(stmt, 6));
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : DB_OK;
}

int db_room_delete(int rid)
{
    if (db_execute("DELETE FROM attempt_answers WHERE att_id IN (SELECT att_id FROM attempts WHERE rid = ?)", "i", rid) < 0) return DB_ERROR;
    if (db_execute("DELETE FROM attempts WHERE rid = ?", "i", rid) < 0) return DB_ERROR;
    if (db_execute("DELETE FROM room_questions WHERE rid = ?", "i", rid) < 0) return DB_ERROR;
    return db_execute("DELETE FROM rooms WHERE rid = ?", "i", rid) < 0 ? DB_ERROR : DB_OK;
}

// drop lobby rooms left by a crash since their sessions no longer exist
int db_room_reset_waiting(void)
{
    if (db_execute("DELETE FROM attempts WHERE rid IN (SELECT rid FROM rooms WHERE status = 'WAITING')", "") < 0) return DB_ERROR;
    return db_execute("DELETE FROM rooms WHERE status = 'WAITING'", "");
}

int db_room_member_ids(int rid, int *ids, int max_ids)
{
    sqlite3_stmt *stmt = db_prepare("SELECT user_id FROM attempts WHERE rid = ? ORDER BY att_id", "i", rid);
    int count = 0;

    if (!stmt) return DB_ERROR;
    while (count < max_ids && sqlite3_step(stmt) == SQLITE_ROW) ids[count++] = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return count;
}

int db_room_member_names(int rid, strbuf_t *sb)
{
    sqlite3_stmt *stmt = db_prepare("SELECT u.username FROM attempts a JOIN users u ON u.id = a.user_id WHERE a.rid = ? ORDER BY a.att_id", "i", rid);
    int count = 0;

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        if (count++ > 0) sb_append(sb, ",");
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 0));
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : count;
}

int db_room_member_count(int rid)
{
    return db_query_int("SELECT COUNT(*) FROM attempts WHERE rid = ?", DB_ERROR, "i", rid);
}

int db_user_busy_room(int user_id)
{
    return db_query_int("SELECT a.rid FROM attempts a JOIN rooms r ON r.rid = a.rid WHERE a.user_id = ? AND a.status = 'IN_PROGRESS' AND r.status IN ('WAITING', 'RUNNING') ORDER BY a.att_id DESC LIMIT 1", 0, "i", user_id);
}

int db_attempt_add(int rid, int user_id)
{
    int rc = db_execute("INSERT INTO attempts (rid, user_id, joined_at) VALUES (?, ?, ?)", "iil", rid, user_id, (long long)time(NULL));

    if (rc < 0) return rc;
    return DB_OK;
}

int db_attempt_remove(int rid, int user_id)
{
    return db_execute("DELETE FROM attempts WHERE rid = ? AND user_id = ?", "ii", rid, user_id);
}

int db_attempt_exists(int rid, int user_id)
{
    return db_query_int("SELECT EXISTS (SELECT 1 FROM attempts WHERE rid = ? AND user_id = ?)", DB_ERROR, "ii", rid, user_id);
}
