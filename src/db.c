#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include <sqlite3.h>

#include "common.h"
#include "db.h"
#include "db_internal.h"
#include "seed.h"

#define ADMIN_USERNAME "admin"
#define ADMIN_PASSWORD "admin123"

static sqlite3 *g_db = NULL;

static const char *const SCHEMA_SQL =
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);"
    "CREATE TABLE IF NOT EXISTS users ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,"
    " pass_hash TEXT NOT NULL, salt TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',"
    " created_at INTEGER NOT NULL);"
    "CREATE TABLE IF NOT EXISTS questions ("
    " qid INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL,"
    " opt_a TEXT NOT NULL, opt_b TEXT NOT NULL, opt_c TEXT NOT NULL, opt_d TEXT NOT NULL,"
    " correct_opt INTEGER NOT NULL CHECK (correct_opt BETWEEN 0 AND 3),"
    " difficulty TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),"
    " topic TEXT NOT NULL DEFAULT 'all', explanation TEXT NOT NULL DEFAULT '',"
    " created_at INTEGER NOT NULL);"
    "CREATE INDEX IF NOT EXISTS idx_q_diff_topic ON questions(difficulty, topic);"
    "CREATE TABLE IF NOT EXISTS rooms ("
    " rid INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,"
    " owner_id INTEGER NOT NULL REFERENCES users(id), num_q INTEGER NOT NULL,"
    " duration_sec INTEGER NOT NULL, difficulty_cfg TEXT NOT NULL DEFAULT 'mixed',"
    " topic TEXT NOT NULL DEFAULT 'all', status TEXT NOT NULL DEFAULT 'WAITING'"
    " CHECK (status IN ('WAITING','RUNNING','FINISHED')),"
    " is_practice INTEGER NOT NULL DEFAULT 0, start_ts INTEGER, created_at INTEGER NOT NULL);"
    "CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status, is_practice);"
    "CREATE TABLE IF NOT EXISTS room_questions ("
    " rid INTEGER NOT NULL REFERENCES rooms(rid), qidx INTEGER NOT NULL, qid INTEGER,"
    " content TEXT NOT NULL, opt_a TEXT NOT NULL, opt_b TEXT NOT NULL, opt_c TEXT NOT NULL,"
    " opt_d TEXT NOT NULL, correct_opt INTEGER NOT NULL, difficulty TEXT NOT NULL,"
    " topic TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '', PRIMARY KEY (rid, qidx));"
    "CREATE TABLE IF NOT EXISTS attempts ("
    " att_id INTEGER PRIMARY KEY AUTOINCREMENT, rid INTEGER NOT NULL REFERENCES rooms(rid),"
    " user_id INTEGER NOT NULL REFERENCES users(id), status TEXT NOT NULL DEFAULT 'IN_PROGRESS'"
    " CHECK (status IN ('IN_PROGRESS','SUBMITTED')), score INTEGER, submit_ts INTEGER,"
    " joined_at INTEGER NOT NULL, UNIQUE (rid, user_id));"
    "CREATE INDEX IF NOT EXISTS idx_att_user ON attempts(user_id, status);"
    "CREATE INDEX IF NOT EXISTS idx_att_room ON attempts(rid, status);"
    "CREATE TABLE IF NOT EXISTS attempt_answers ("
    " att_id INTEGER NOT NULL REFERENCES attempts(att_id), qidx INTEGER NOT NULL,"
    " chosen_opt INTEGER NOT NULL CHECK (chosen_opt BETWEEN 0 AND 3),"
    " PRIMARY KEY (att_id, qidx));";

static int bind_one(sqlite3_stmt *stmt, int index, char type, va_list *args)
{
    long long wide = 0;

    switch (type) {
    case 'i': return sqlite3_bind_int(stmt, index, va_arg(*args, int));
    case 'l': return sqlite3_bind_int64(stmt, index, va_arg(*args, long long));
    case 's': return sqlite3_bind_text(stmt, index, va_arg(*args, const char *), -1, SQLITE_TRANSIENT);
    case 'z':
        wide = va_arg(*args, long long);
        return wide ? sqlite3_bind_int64(stmt, index, wide) : sqlite3_bind_null(stmt, index);
    default: return SQLITE_MISUSE;
    }
}

static sqlite3_stmt *prepare_va(const char *sql, const char *types, va_list *args)
{
    sqlite3_stmt *stmt = NULL;
    const char *cursor = types ? types : "";
    int index = 1;

    if (!g_db) return NULL;
    if (sqlite3_prepare_v2(g_db, sql, -1, &stmt, NULL) != SQLITE_OK) {
        log_msg(LOG_ERROR, "sqlite prepare failed: %s", sqlite3_errmsg(g_db));
        return NULL;
    }
    for (; *cursor; cursor++, index++) {
        if (bind_one(stmt, index, *cursor, args) == SQLITE_OK) continue;
        log_msg(LOG_ERROR, "sqlite bind failed: %s", sqlite3_errmsg(g_db));
        sqlite3_finalize(stmt);
        return NULL;
    }
    return stmt;
}

sqlite3_stmt *db_prepare(const char *sql, const char *types, ...)
{
    va_list args;
    sqlite3_stmt *stmt = NULL;

    va_start(args, types);
    stmt = prepare_va(sql, types, &args);
    va_end(args);
    return stmt;
}

int db_execute(const char *sql, const char *types, ...)
{
    va_list args;
    sqlite3_stmt *stmt = NULL;
    int rc = 0;

    va_start(args, types);
    stmt = prepare_va(sql, types, &args);
    va_end(args);
    if (!stmt) return DB_ERROR;
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    if (rc == SQLITE_DONE) return sqlite3_changes(g_db);

    // map UNIQUE violation to a domain code, everything else is internal
    if (rc == SQLITE_CONSTRAINT) return DB_EXISTS;
    log_msg(LOG_ERROR, "sqlite step failed: %s", sqlite3_errmsg(g_db));
    return DB_ERROR;
}

int db_query_int(const char *sql, int fallback, const char *types, ...)
{
    va_list args;
    sqlite3_stmt *stmt = NULL;
    int value = fallback;

    va_start(args, types);
    stmt = prepare_va(sql, types, &args);
    va_end(args);
    if (!stmt) return fallback;
    if (sqlite3_step(stmt) == SQLITE_ROW && sqlite3_column_type(stmt, 0) != SQLITE_NULL) value = sqlite3_column_int(stmt, 0);
    sqlite3_finalize(stmt);
    return value;
}

long long db_last_insert_id(void)
{
    return g_db ? (long long)sqlite3_last_insert_rowid(g_db) : -1;
}

void db_column_copy(sqlite3_stmt *stmt, int col, char *dst, size_t dst_size)
{
    const unsigned char *text = sqlite3_column_text(stmt, col);

    snprintf(dst, dst_size, "%s", text ? (const char *)text : "");
}

int db_open(const char *path)
{
    char *error = NULL;

    if (sqlite3_open(path, &g_db) != SQLITE_OK) {
        log_msg(LOG_ERROR, "sqlite open %s failed: %s", path, sqlite3_errmsg(g_db));
        db_close();
        return DB_ERROR;
    }
    sqlite3_busy_timeout(g_db, 3000);
    sqlite3_exec(g_db, "PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;", NULL, NULL, NULL);
    if (sqlite3_exec(g_db, SCHEMA_SQL, NULL, NULL, &error) != SQLITE_OK) {
        log_msg(LOG_ERROR, "sqlite schema failed: %s", error ? error : "?");
        sqlite3_free(error);
        db_close();
        return DB_ERROR;
    }
    log_msg(LOG_INFO, "database ready at %s", path);
    return DB_OK;
}

void db_close(void)
{
    if (g_db) sqlite3_close(g_db);
    g_db = NULL;
}

int db_begin(void)
{
    return db_execute("BEGIN IMMEDIATE", "") >= 0 ? DB_OK : DB_ERROR;
}

int db_commit(void)
{
    return db_execute("COMMIT", "") >= 0 ? DB_OK : DB_ERROR;
}

void db_rollback(void)
{
    db_execute("ROLLBACK", "");
}

static int seed_admin(void)
{
    char salt[SALT_HEX_LEN + 1];
    char hash[HASH_HEX_LEN + 1];
    int rc = 0;

    if (db_query_int("SELECT COUNT(*) FROM users WHERE role = 'admin'", 0, "") > 0) return DB_OK;
    if (random_hex(salt, SALT_HEX_LEN) != 0) return DB_ERROR;
    hash_password(salt, ADMIN_PASSWORD, hash);
    rc = db_user_create(ADMIN_USERNAME, hash, salt, "admin");
    if (rc == DB_OK) log_msg(LOG_INFO, "seeded default admin user=%s pass=***", ADMIN_USERNAME);
    return rc == DB_EXISTS ? DB_OK : rc;
}

static int seed_questions(void)
{
    size_t i = 0;

    for (i = 0; i < SEED_QUESTION_COUNT; i++) {
        const seed_question_t *seed = &SEED_QUESTIONS[i];
        question_t question = { seed->content, { seed->opts[0], seed->opts[1], seed->opts[2], seed->opts[3] }, seed->correct, seed->difficulty, seed->topic, seed->explanation };

        if (db_question_add(&question) < 0) return DB_ERROR;
    }
    return db_execute("INSERT INTO meta (key, value) VALUES ('seeded', '1')", "") >= 0 ? DB_OK : DB_ERROR;
}

int db_seed_defaults(void)
{
    if (seed_admin() != DB_OK) return DB_ERROR;
    if (db_query_int("SELECT COUNT(*) FROM meta WHERE key = 'seeded'", 0, "") > 0) return DB_OK;
    if (db_begin() != DB_OK) return DB_ERROR;

    // rollback whole seed so a half-filled bank never survives a crash
    if (seed_questions() != DB_OK) {
        db_rollback();
        return DB_ERROR;
    }
    log_msg(LOG_INFO, "seeded %d questions", (int)SEED_QUESTION_COUNT);
    return db_commit();
}

int db_user_create(const char *username, const char *pass_hash, const char *salt, const char *role)
{
    int rc = db_execute("INSERT INTO users (username, pass_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)", "ssssl", username, pass_hash, salt, role, (long long)time(NULL));

    if (rc == DB_EXISTS || rc == DB_ERROR) return rc;
    return DB_OK;
}

int db_user_find(const char *username, user_t *out)
{
    sqlite3_stmt *stmt = db_prepare("SELECT id, username, pass_hash, salt, role FROM users WHERE username = ?", "s", username);
    int found = 0;

    if (!stmt) return DB_ERROR;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        out->id = sqlite3_column_int(stmt, 0);
        db_column_copy(stmt, 1, out->username, sizeof(out->username));
        db_column_copy(stmt, 2, out->pass_hash, sizeof(out->pass_hash));
        db_column_copy(stmt, 3, out->salt, sizeof(out->salt));
        db_column_copy(stmt, 4, out->role, sizeof(out->role));
        found = 1;
    }
    sqlite3_finalize(stmt);
    return found;
}

long long db_question_add(const question_t *q)
{
    int rc = db_execute("INSERT INTO questions (content, opt_a, opt_b, opt_c, opt_d, correct_opt, difficulty, topic, explanation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", "sssssisssl", q->content, q->opts[0], q->opts[1], q->opts[2], q->opts[3], q->correct, q->difficulty, q->topic, q->explanation ? q->explanation : "", (long long)time(NULL));

    if (rc < 0) return DB_ERROR;
    return db_last_insert_id();
}

int db_question_delete(int qid)
{
    return db_execute("DELETE FROM questions WHERE qid = ?", "i", qid);
}

int db_question_list(strbuf_t *sb)
{
    sqlite3_stmt *stmt = db_prepare("SELECT qid, content, correct_opt, difficulty, topic FROM questions ORDER BY qid", "");

    if (!stmt) return DB_ERROR;
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        sb_appendf(sb, "|%d:", sqlite3_column_int(stmt, 0));
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 1));
        sb_appendf(sb, ":%d:%s:", sqlite3_column_int(stmt, 2), (const char *)sqlite3_column_text(stmt, 3));
        sb_append_escaped(sb, (const char *)sqlite3_column_text(stmt, 4));
    }
    sqlite3_finalize(stmt);
    return sb->failed ? DB_ERROR : DB_OK;
}

int db_question_count(const char *difficulty, const char *topic)
{
    return db_query_int("SELECT COUNT(*) FROM questions WHERE (? = 'mixed' OR difficulty = ?) AND (? = 'all' OR topic = ?)", 0, "ssss", difficulty, difficulty, topic, topic);
}

int db_topic_exists(const char *topic)
{
    return db_query_int("SELECT EXISTS (SELECT 1 FROM questions WHERE topic = ?)", 0, "s", topic);
}
