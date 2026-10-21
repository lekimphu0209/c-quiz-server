#ifndef SESSION_H
#define SESSION_H

#include <pthread.h>

#include "common.h"
#include "db.h"

#define MAX_CLIENTS 50

#define SLOT_FREE 0
#define SLOT_ACTIVE 1
#define SLOT_DONE 2
#define SLOT_JOINING 3

typedef struct {
    int             state;
    pthread_t       thread;
    int             fd;
    unsigned        generation;
    int             user_id;
    char            username[USERNAME_MAX + 1];
    char            role[ROLE_MAX];
    char            token[TOKEN_LEN];
    pthread_mutex_t send_lock;
} session_t;

void sessions_init(void);
void sessions_destroy(void);
session_t *session_reserve(int fd);
void session_release_unstarted(session_t *sess);
void sessions_reap(void);
void sessions_shutdown_all(void);
int sessions_active_count(void);

int session_login(session_t *sess, const user_t *user, const char *token);
void session_logout(session_t *sess);
int session_is_authenticated(const session_t *sess, const char *token);
int session_is_admin(const session_t *sess);

int session_send(session_t *sess, const char *payload);
int session_push(int user_id, const char *payload);
void session_close(session_t *sess);

#endif
