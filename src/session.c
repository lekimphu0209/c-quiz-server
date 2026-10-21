#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <pthread.h>

#include "common.h"
#include "session.h"

static session_t g_slots[MAX_CLIENTS];
static pthread_mutex_t g_sessions_lock = PTHREAD_MUTEX_INITIALIZER;

static void clear_identity(session_t *sess)
{
    sess->user_id = 0;
    sess->username[0] = '\0';
    sess->role[0] = '\0';
    memset(sess->token, 0, sizeof(sess->token));
}

void sessions_init(void)
{
    int i = 0;

    for (i = 0; i < MAX_CLIENTS; i++) {
        memset(&g_slots[i], 0, sizeof(g_slots[i]));
        g_slots[i].state = SLOT_FREE;
        g_slots[i].fd = -1;
        pthread_mutex_init(&g_slots[i].send_lock, NULL);
    }
}

void sessions_destroy(void)
{
    int i = 0;

    for (i = 0; i < MAX_CLIENTS; i++) pthread_mutex_destroy(&g_slots[i].send_lock);
}

session_t *session_reserve(int fd)
{
    session_t *found = NULL;
    int i = 0;

    pthread_mutex_lock(&g_sessions_lock);
    for (i = 0; i < MAX_CLIENTS && !found; i++) {
        if (g_slots[i].state == SLOT_FREE) found = &g_slots[i];
    }
    if (found) {
        found->state = SLOT_ACTIVE;
        clear_identity(found);
        pthread_mutex_lock(&found->send_lock);
        found->fd = fd;
        found->generation++;
        pthread_mutex_unlock(&found->send_lock);
    }
    pthread_mutex_unlock(&g_sessions_lock);
    return found;
}

void session_release_unstarted(session_t *sess)
{
    session_close(sess);
    pthread_mutex_lock(&g_sessions_lock);
    sess->state = SLOT_FREE;
    pthread_mutex_unlock(&g_sessions_lock);
}

static int collect_done(pthread_t *threads, int *indexes)
{
    int count = 0;
    int i = 0;

    pthread_mutex_lock(&g_sessions_lock);
    for (i = 0; i < MAX_CLIENTS; i++) {
        if (g_slots[i].state != SLOT_DONE) continue;
        g_slots[i].state = SLOT_JOINING;
        threads[count] = g_slots[i].thread;
        indexes[count++] = i;
    }
    pthread_mutex_unlock(&g_sessions_lock);
    return count;
}

void sessions_reap(void)
{
    pthread_t threads[MAX_CLIENTS];
    int indexes[MAX_CLIENTS];
    int count = collect_done(threads, indexes);
    int i = 0;

    // join outside the registry lock so finishing workers never block
    for (i = 0; i < count; i++) pthread_join(threads[i], NULL);
    pthread_mutex_lock(&g_sessions_lock);
    for (i = 0; i < count; i++) g_slots[indexes[i]].state = SLOT_FREE;
    pthread_mutex_unlock(&g_sessions_lock);
}

void sessions_shutdown_all(void)
{
    int i = 0;

    pthread_mutex_lock(&g_sessions_lock);
    for (i = 0; i < MAX_CLIENTS; i++) {
        if (g_slots[i].state != SLOT_ACTIVE) continue;
        pthread_mutex_lock(&g_slots[i].send_lock);
        if (g_slots[i].fd >= 0) shutdown(g_slots[i].fd, SHUT_RDWR);
        pthread_mutex_unlock(&g_slots[i].send_lock);
    }
    pthread_mutex_unlock(&g_sessions_lock);
}

int sessions_active_count(void)
{
    int count = 0;
    int i = 0;

    pthread_mutex_lock(&g_sessions_lock);
    for (i = 0; i < MAX_CLIENTS; i++) count += g_slots[i].state == SLOT_ACTIVE;
    pthread_mutex_unlock(&g_sessions_lock);
    return count;
}

static int user_online(const session_t *self, int user_id)
{
    int i = 0;

    for (i = 0; i < MAX_CLIENTS; i++) {
        if (&g_slots[i] == self || g_slots[i].state != SLOT_ACTIVE) continue;
        if (g_slots[i].user_id == user_id) return 1;
    }
    return 0;
}

int session_login(session_t *sess, const user_t *user, const char *token)
{
    int rc = -1;

    // check and claim under one lock so concurrent logins cannot both win
    pthread_mutex_lock(&g_sessions_lock);
    if (sess->user_id == 0 && !user_online(sess, user->id)) {
        sess->user_id = user->id;
        snprintf(sess->username, sizeof(sess->username), "%s", user->username);
        snprintf(sess->role, sizeof(sess->role), "%s", user->role);
        snprintf(sess->token, sizeof(sess->token), "%s", token);
        rc = 0;
    }
    pthread_mutex_unlock(&g_sessions_lock);
    return rc;
}

void session_logout(session_t *sess)
{
    pthread_mutex_lock(&g_sessions_lock);
    pthread_mutex_lock(&sess->send_lock);
    clear_identity(sess);
    sess->generation++;
    pthread_mutex_unlock(&sess->send_lock);
    pthread_mutex_unlock(&g_sessions_lock);
}

int session_is_authenticated(const session_t *sess, const char *token)
{
    if (!sess || !token || sess->user_id == 0) return 0;
    if (strlen(token) != TOKEN_HEX_LEN) return 0;
    return secure_equals(sess->token, token);
}

int session_is_admin(const session_t *sess)
{
    return sess && sess->user_id != 0 && strcmp(sess->role, "admin") == 0;
}

int session_send(session_t *sess, const char *payload)
{
    int rc = -1;

    // serialize writers per socket so replies and pushes never interleave
    pthread_mutex_lock(&sess->send_lock);
    if (sess->fd >= 0) rc = send_text(sess->fd, payload);
    pthread_mutex_unlock(&sess->send_lock);
    return rc;
}

static session_t *find_user(int user_id, unsigned *generation)
{
    int i = 0;

    for (i = 0; i < MAX_CLIENTS; i++) {
        if (g_slots[i].state != SLOT_ACTIVE || g_slots[i].user_id != user_id) continue;
        *generation = g_slots[i].generation;
        return &g_slots[i];
    }
    return NULL;
}

int session_push(int user_id, const char *payload)
{
    session_t *target = NULL;
    unsigned generation = 0;
    int rc = 0;

    if (user_id <= 0 || !payload) return -1;
    pthread_mutex_lock(&g_sessions_lock);
    target = find_user(user_id, &generation);
    pthread_mutex_unlock(&g_sessions_lock);
    if (!target) return 0;

    // drop push when the slot was logged out or recycled meanwhile
    pthread_mutex_lock(&target->send_lock);
    if (target->generation == generation && target->fd >= 0) rc = send_text(target->fd, payload);
    pthread_mutex_unlock(&target->send_lock);
    return rc;
}

void session_close(session_t *sess)
{
    pthread_mutex_lock(&g_sessions_lock);
    pthread_mutex_lock(&sess->send_lock);
    if (sess->fd >= 0) close(sess->fd);
    sess->fd = -1;
    sess->generation++;
    clear_identity(sess);
    sess->state = SLOT_DONE;
    pthread_mutex_unlock(&sess->send_lock);
    pthread_mutex_unlock(&g_sessions_lock);
}
