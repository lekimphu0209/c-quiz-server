#ifndef AUTH_H
#define AUTH_H

#include "protocol.h"

#define PASSWORD_MIN 6
#define PASSWORD_MAX 64
#define USERNAME_MIN 3

int handle_ping(request_t *req);
int handle_register(request_t *req);
int handle_login(request_t *req);
int handle_logout(request_t *req);

#endif
