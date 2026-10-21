#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "common.h"
#include "session.h"

#define MAX_PUSHES 64

typedef struct {
    int   user_id;
    char *payload;
} push_t;

typedef struct {
    strbuf_t reply;
    push_t   pushes[MAX_PUSHES];
    int      push_count;
} outbox_t;

typedef struct {
    session_t *sess;
    char     **argv;
    int        argc;
    outbox_t  *out;
} request_t;

typedef int (*handler_fn)(request_t *req);

void core_lock(void);
void core_unlock(void);

void outbox_init(outbox_t *out);
void outbox_free(outbox_t *out);
int outbox_push(outbox_t *out, int user_id, const char *payload);
void outbox_flush(outbox_t *out, session_t *sess);

strbuf_t *reply_begin(request_t *req);
int reply_ok(request_t *req, const char *tail);
int reply_err(request_t *req, const char *code, const char *message);

void protocol_handle(session_t *sess, char *payload);
void protocol_disconnect(session_t *sess);

#endif
