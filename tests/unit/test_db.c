#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "common.h"
#include "db.h"
#include "unit.h"

static char g_db_path[128];

static void open_fresh_db(void)
{
    snprintf(g_db_path, sizeof(g_db_path), "/tmp/quiz_unit_%d.db", (int)getpid());
    unlink(g_db_path);
    CHECK(db_open(g_db_path) == DB_OK);
    CHECK(db_seed_defaults() == DB_OK);
}

static void close_and_remove_db(void)
{
    char side[160];

    db_close();
    unlink(g_db_path);
    snprintf(side, sizeof(side), "%s-wal", g_db_path);
    unlink(side);
    snprintf(side, sizeof(side), "%s-shm", g_db_path);
    unlink(side);
}

static void test_seed_creates_admin_with_hashed_password(void)
{
    user_t admin;
    char expected[HASH_HEX_LEN + 1];

    open_fresh_db();
    CHECK(db_user_find("admin", &admin) == 1);
    CHECK_STR(admin.role, "admin");
    CHECK(strlen(admin.salt) == SALT_HEX_LEN);
    hash_password(admin.salt, "admin123", expected);
    CHECK_STR(admin.pass_hash, expected);
    CHECK(strstr(admin.pass_hash, "admin123") == NULL);
    close_and_remove_db();
}

static void test_seed_question_bank_is_balanced_and_idempotent(void)
{
    open_fresh_db();
    CHECK(db_question_count("mixed", "all") == 30);
    CHECK(db_question_count("easy", "all") == 10);
    CHECK(db_question_count("medium", "all") == 10);
    CHECK(db_question_count("hard", "all") == 10);
    CHECK(db_question_count("mixed", "net") == 10);
    CHECK(db_topic_exists("net") == 1);
    CHECK(db_topic_exists("nope") == 0);
    CHECK(db_seed_defaults() == DB_OK);
    CHECK(db_question_count("mixed", "all") == 30);
    close_and_remove_db();
}

static void test_user_create_rejects_duplicate_username(void)
{
    user_t found;

    open_fresh_db();
    CHECK(db_user_create("alice", "hash", "salt", "user") == DB_OK);
    CHECK(db_user_create("alice", "hash2", "salt2", "user") == DB_EXISTS);
    CHECK(db_user_find("alice", &found) == 1);
    CHECK_STR(found.pass_hash, "hash");
    CHECK(db_user_find("nobody", &found) == 0);
    close_and_remove_db();
}

static void test_question_add_list_delete(void)
{
    question_t q = { "2|2=?", { "3", "4", "5", "6" }, 1, "easy", "toan", "phep:cong" };
    strbuf_t sb;
    long long qid = 0;

    open_fresh_db();
    qid = db_question_add(&q);
    CHECK(qid > 30);
    CHECK(db_question_count("easy", "toan") == 1);
    sb_init(&sb);
    CHECK(db_question_list(&sb) == DB_OK);
    CHECK(strstr(sb_str(&sb), ":2%7C2=?:1:easy:toan") != NULL);
    sb_free(&sb);
    CHECK(db_question_delete((int)qid) == 1);
    CHECK(db_question_delete((int)qid) == 0);
    close_and_remove_db();
}

static void test_rollback_discards_writes(void)
{
    question_t q = { "x", { "a", "b", "c", "d" }, 0, "hard", "tmp", "" };

    open_fresh_db();
    CHECK(db_begin() == DB_OK);
    CHECK(db_question_add(&q) > 0);
    db_rollback();
    CHECK(db_question_count("hard", "tmp") == 0);
    close_and_remove_db();
}

static void test_data_persists_after_reopen(void)
{
    user_t found;

    open_fresh_db();
    CHECK(db_user_create("bob", "h", "s", "user") == DB_OK);
    db_close();
    CHECK(db_open(g_db_path) == DB_OK);
    CHECK(db_user_find("bob", &found) == 1);
    close_and_remove_db();
}

int main(void)
{
    log_open(NULL, 0);
    RUN(test_seed_creates_admin_with_hashed_password);
    RUN(test_seed_question_bank_is_balanced_and_idempotent);
    RUN(test_user_create_rejects_duplicate_username);
    RUN(test_question_add_list_delete);
    RUN(test_rollback_discards_writes);
    RUN(test_data_persists_after_reopen);
    return UNIT_REPORT();
}
