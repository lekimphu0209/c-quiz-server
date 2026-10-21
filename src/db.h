#ifndef DB_H
#define DB_H

#include "common.h"

#define DB_OK 0
#define DB_ERROR -1
#define DB_EXISTS -2

#define USERNAME_MAX 20
#define ROLE_MAX 8

typedef struct {
    int  id;
    char username[USERNAME_MAX + 1];
    char pass_hash[HASH_HEX_LEN + 1];
    char salt[SALT_HEX_LEN + 1];
    char role[ROLE_MAX];
} user_t;

typedef struct {
    const char *content;
    const char *opts[4];
    int         correct;
    const char *difficulty;
    const char *topic;
    const char *explanation;
} question_t;

int db_open(const char *path);
void db_close(void);
int db_begin(void);
int db_commit(void);
void db_rollback(void);
int db_seed_defaults(void);

int db_user_create(const char *username, const char *pass_hash, const char *salt, const char *role);
int db_user_find(const char *username, user_t *out);

long long db_question_add(const question_t *question);
int db_question_delete(int qid);
int db_question_list(strbuf_t *sb);
int db_question_count(const char *difficulty, const char *topic);
int db_topic_exists(const char *topic);

#endif
