#ifndef COMMON_H
#define COMMON_H

#include <stddef.h>
#include <stdint.h>

#define MAX_PAYLOAD 8192
#define MAX_SEND_PAYLOAD 262144
#define MAX_FIELDS 32

#define SALT_HEX_LEN 16
#define HASH_HEX_LEN 64
#define TOKEN_HEX_LEN 32
#define TOKEN_LEN (TOKEN_HEX_LEN + 1)

#define FRAME_OK 1
#define FRAME_CLOSED 0
#define FRAME_ERROR -1
#define FRAME_TOO_LONG -2
#define FRAME_EMPTY -3

typedef struct {
    char   *data;
    size_t  len;
    size_t  cap;
    int     failed;
} strbuf_t;

typedef enum {
    LOG_DEBUG = 0,
    LOG_INFO,
    LOG_WARN,
    LOG_ERROR
} log_level_t;

int write_n_bytes(int sockfd, const void *buf, size_t len);
int read_n_bytes(int sockfd, void *buf, size_t len);
int send_frame(int sockfd, const char *payload, uint32_t len);
int send_text(int sockfd, const char *payload);
int recv_frame(int sockfd, char *buf, size_t buf_size, uint32_t *out_len);

void sb_init(strbuf_t *sb);
void sb_free(strbuf_t *sb);
void sb_reset(strbuf_t *sb);
int sb_append(strbuf_t *sb, const char *text);
int sb_appendf(strbuf_t *sb, const char *fmt, ...);
int sb_append_escaped(strbuf_t *sb, const char *text);
const char *sb_str(const strbuf_t *sb);

void unescape_inplace(char *text);
int split_fields(char *line, char **fields, int max_fields);
int parse_int(const char *text, int *out);

int random_hex(char *out, size_t hex_len);
void hash_password(const char *salt, const char *password, char out_hex[HASH_HEX_LEN + 1]);
int secure_equals(const char *left, const char *right);

void log_open(const char *path, int echo_stdout);
void log_close(void);
void log_msg(log_level_t level, const char *fmt, ...);

#endif
