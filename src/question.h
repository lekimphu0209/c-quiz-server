#ifndef QUESTION_H
#define QUESTION_H

#include "db.h"
#include "protocol.h"

#define CSV_FIELDS 9
#define CSV_LINE_MAX 4096

const char *question_validate(const question_t *question);
int question_parse_csv_line(char *line, question_t *out);

int handle_list_questions(request_t *req);
int handle_add_question(request_t *req);
int handle_del_question(request_t *req);
int handle_import_csv(request_t *req);

#endif
