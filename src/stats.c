#include <string.h>

#include "common.h"
#include "db.h"
#include "db_stats.h"
#include "protocol.h"
#include "session.h"
#include "stats.h"

int handle_history(request_t *req)
{
    const char *mode = req->argc > 2 ? req->argv[2] : "all";

    if (strcmp(mode, "all") != 0 && strcmp(mode, "room") != 0 && strcmp(mode, "practice") != 0) return reply_err(req, "BAD_ARGS", "filter must be all|room|practice");
    if (db_history_list(req->sess->user_id, mode, reply_begin(req)) != DB_OK) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

int handle_history_detail(request_t *req)
{
    int att_id = 0;
    int owner = 0;
    int finished = 0;
    int found = 0;

    if (parse_int(req->argv[2], &att_id) != 0 || att_id <= 0) return reply_err(req, "BAD_ARGS", "att_id must be a positive integer");
    found = db_attempt_owner(att_id, &owner, &finished);
    if (found < 0) return reply_err(req, "INTERNAL", "database error");
    if (!found) return reply_err(req, "NOTFOUND", "attempt not found");
    if (owner != req->sess->user_id) return reply_err(req, "FORBIDDEN", "attempt belongs to another user");

    // hide answer key until the whole room is finished
    if (!finished) return reply_err(req, "BAD_STATE", "exam still running");
    if (db_history_detail(att_id, reply_begin(req)) != DB_OK) return reply_err(req, "INTERNAL", "database error");
    return 0;
}

static void append_tally(strbuf_t *sb, const tally_t *tally)
{
    sb_appendf(sb, "|%d|%d", tally->correct, tally->total);
}

int handle_stats(request_t *req)
{
    stats_t stats;
    strbuf_t *reply = NULL;
    int scope = req->sess->user_id;

    if (req->argc > 2 && strcmp(req->argv[2], "ALL") != 0) return reply_err(req, "BAD_ARGS", "scope must be ALL");
    if (req->argc > 2 && !session_is_admin(req->sess)) return reply_err(req, "FORBIDDEN", "admin only");
    if (req->argc > 2) scope = 0;
    if (db_stats_collect(scope, &stats) != DB_OK) return reply_err(req, "INTERNAL", "database error");

    reply = reply_begin(req);
    sb_appendf(reply, "|%d|%d", stats.attempts, stats.avg_x100);
    append_tally(reply, &stats.easy);
    append_tally(reply, &stats.medium);
    append_tally(reply, &stats.hard);
    sb_append(reply, "|");
    if (db_stats_topics(scope, reply) != DB_OK) return reply_err(req, "INTERNAL", "database error");
    return 0;
}
