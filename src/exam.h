#ifndef EXAM_H
#define EXAM_H

#include "db_exam.h"
#include "db_room.h"
#include "protocol.h"
#include "room.h"

int exam_take_snapshot(int rid, const exam_mix_t *mix, const char *topic, int num_q);
int exam_finalize(outbox_t *out, const room_t *room);
int exam_load_member(request_t *req, room_t *room, attempt_t *attempt);
int exam_check_active(request_t *req, const room_t *room, const attempt_t *attempt);

int exam_ticker_start(void);
void exam_ticker_stop(void);

int handle_start_room(request_t *req);
int handle_answer(request_t *req);
int handle_submit(request_t *req);
int handle_end_room(request_t *req);
int handle_get_questions(request_t *req);
int handle_room_result(request_t *req);

#endif
