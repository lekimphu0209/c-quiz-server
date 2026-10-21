#include <stdio.h>
#include <string.h>

#include "common.h"
#include "db.h"
#include "protocol.h"
#include "question.h"

static int valid_difficulty(const char *difficulty)
{
    if (!difficulty) return 0;
    return strcmp(difficulty, "easy") == 0 || strcmp(difficulty, "medium") == 0 || strcmp(difficulty, "hard") == 0;
}

static int filled(const char *text)
{
    return text && *text;
}

const char *question_validate(const question_t *question)
{
    int i = 0;

    if (!filled(question->content)) return "content required";
    for (i = 0; i < 4; i++) {
        if (!filled(question->opts[i])) return "all four options required";
    }
    if (question->correct < 0 || question->correct > 3) return "correct must be 0-3";
    if (!valid_difficulty(question->difficulty)) return "difficulty must be easy|medium|hard";
    if (!filled(question->topic)) return "topic required";
    return NULL;
}

static int split_on(char *line, char separator, char **fields, int max_fields)
{
    char *cursor = line;
    int count = 0;

    fields[count++] = cursor;
    while ((cursor = strchr(cursor, separator)) != NULL) {
        if (count >= max_fields) return -1;
        *cursor++ = '\0';
        fields[count++] = cursor;
    }
    return count;
}

static void fill_question(question_t *out, char **fields)
{
    out->content = fields[0];
    out->opts[0] = fields[1];
    out->opts[1] = fields[2];
    out->opts[2] = fields[3];
    out->opts[3] = fields[4];
    out->difficulty = fields[6];
    out->topic = fields[7];
    out->explanation = fields[8];
}

int question_parse_csv_line(char *line, question_t *out)
{
    char *fields[CSV_FIELDS];
    int i = 0;

    line[strcspn(line, "\r\n")] = '\0';
    if (split_on(line, ';', fields, CSV_FIELDS) != CSV_FIELDS) return -1;

    // allow %3B inside cells since raw semicolons split columns
    for (i = 0; i < CSV_FIELDS; i++) unescape_inplace(fields[i]);
    if (parse_int(fields[5], &out->correct) != 0) return -1;
    fill_question(out, fields);
    return question_validate(out) ? -1 : 0;
}

int handle_list_questions(request_t *req)
{
    strbuf_t *reply = reply_begin(req);

    if (db_question_list(reply) != DB_OK) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

int handle_add_question(request_t *req)
{
    question_t question;
    const char *problem = NULL;
    long long qid = 0;

    memset(&question, 0, sizeof(question));
    question.content = req->argv[2];
    memcpy(question.opts, &req->argv[3], sizeof(question.opts));
    question.difficulty = req->argv[8];
    question.topic = req->argv[9];
    question.explanation = req->argc > 10 ? req->argv[10] : "";
    if (parse_int(req->argv[7], &question.correct) != 0) return reply_err(req, "BAD_ARGS", "correct must be 0-3");
    problem = question_validate(&question);
    if (problem) return reply_err(req, "BAD_ARGS", problem);

    qid = db_question_add(&question);
    if (qid < 0) return reply_err(req, "INTERNAL", "database error");
    log_msg(LOG_INFO, "fd=%d admin=%s added qid=%lld", req->sess->fd, req->sess->username, qid);
    sb_appendf(reply_begin(req), "|%lld", qid);
    return 0;
}

int handle_del_question(request_t *req)
{
    int qid = 0;
    int changed = 0;

    if (parse_int(req->argv[2], &qid) != 0 || qid <= 0) return reply_err(req, "BAD_ARGS", "qid must be a positive integer");
    changed = db_question_delete(qid);
    if (changed < 0) return reply_err(req, "INTERNAL", "database error");
    if (changed == 0) return reply_err(req, "NOTFOUND", "question not found");

    log_msg(LOG_INFO, "fd=%d admin=%s deleted qid=%d", req->sess->fd, req->sess->username, qid);
    return reply_ok(req, NULL);
}

static int import_lines(FILE *file)
{
    char line[CSV_LINE_MAX];
    question_t question;
    int imported = 0;
    int line_no = 0;

    while (fgets(line, sizeof(line), file)) {
        line_no++;
        if (line[strspn(line, " \t\r\n")] == '\0') continue;
        memset(&question, 0, sizeof(question));
        if (question_parse_csv_line(line, &question) != 0) {
            log_msg(LOG_WARN, "import skipped malformed line %d", line_no);
            continue;
        }
        if (db_question_add(&question) < 0) return -1;
        imported++;
    }
    return imported;
}

int handle_import_csv(request_t *req)
{
    FILE *file = fopen(req->argv[2], "r");
    int imported = 0;

    if (!file) return reply_err(req, "NOTFOUND", "file not found");
    if (db_begin() != DB_OK) {
        fclose(file);
        return reply_err(req, "INTERNAL", "database busy");
    }
    imported = import_lines(file);
    fclose(file);

    // rollback on zero rows so a junk file leaves the bank untouched
    if (imported <= 0) {
        db_rollback();
        return imported < 0 ? reply_err(req, "INTERNAL", "database error") : reply_err(req, "BAD_ARGS", "no valid rows");
    }
    if (db_commit() != DB_OK) return reply_err(req, "INTERNAL", "commit failed");
    log_msg(LOG_INFO, "fd=%d admin=%s imported %d questions", req->sess->fd, req->sess->username, imported);
    sb_appendf(reply_begin(req), "|%d", imported);
    return 0;
}
