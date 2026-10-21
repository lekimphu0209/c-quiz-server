#ifndef ROOM_H
#define ROOM_H

#include <stddef.h>

#include "db_room.h"
#include "protocol.h"

#define MAX_PARTICIPANTS 20

#define ROOM_NAME_CHARS 50
#define ROOM_N_MIN 1
#define ROOM_N_MAX 100
#define ROOM_SEC_MIN 60
#define ROOM_SEC_MAX 14400

typedef struct {
    int mixed;
    int easy;
    int medium;
    int hard;
} exam_mix_t;

size_t utf8_length(const char *text);
int parse_exam_mix(const char *text, int num_q, exam_mix_t *out);
int exam_mix_available(const exam_mix_t *mix, const char *topic);

int room_load(request_t *req, room_t *room);
int room_broadcast(outbox_t *out, int rid, int skip_user, const char *payload);
void room_on_signout(outbox_t *out, int user_id, const char *username);

int handle_create_room(request_t *req);
int handle_list_rooms(request_t *req);
int handle_join(request_t *req);
int handle_leave_room(request_t *req);

#endif
