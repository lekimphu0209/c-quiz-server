#ifndef STATS_H
#define STATS_H

#include "protocol.h"

int handle_history(request_t *req);
int handle_history_detail(request_t *req);
int handle_stats(request_t *req);

#endif
