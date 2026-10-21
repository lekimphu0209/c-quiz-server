#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#include "common.h"

#ifdef MSG_NOSIGNAL
#define SEND_FLAGS MSG_NOSIGNAL
#else
#define SEND_FLAGS 0
#endif

#define LOG_LINE_MAX 1024

static pthread_mutex_t g_log_lock = PTHREAD_MUTEX_INITIALIZER;
static FILE *g_log_file = NULL;
static int g_log_echo = 1;

static const char *const LOG_LEVEL_NAMES[] = { "DEBUG", "INFO", "WARN", "ERROR" };

int write_n_bytes(int sockfd, const void *buf, size_t len)
{
    const char *cursor = buf;
    size_t left = len;

    while (left > 0) {
        ssize_t sent = send(sockfd, cursor, left, SEND_FLAGS);

        if (sent < 0 && errno == EINTR) continue;
        if (sent <= 0) return -1;
        cursor += sent;
        left -= (size_t)sent;
    }
    return 0;
}

int read_n_bytes(int sockfd, void *buf, size_t len)
{
    char *cursor = buf;
    size_t left = len;

    while (left > 0) {
        ssize_t got = recv(sockfd, cursor, left, 0);

        if (got < 0 && errno == EINTR) continue;
        if (got == 0) return FRAME_CLOSED;
        if (got < 0) return FRAME_ERROR;
        cursor += got;
        left -= (size_t)got;
    }
    return FRAME_OK;
}

int send_frame(int sockfd, const char *payload, uint32_t len)
{
    uint32_t net_len = htonl(len);

    if (!payload || len == 0 || len > MAX_SEND_PAYLOAD) return -1;
    if (write_n_bytes(sockfd, &net_len, sizeof(net_len)) < 0) return -1;
    return write_n_bytes(sockfd, payload, len);
}

int send_text(int sockfd, const char *payload)
{
    if (!payload) return -1;
    return send_frame(sockfd, payload, (uint32_t)strlen(payload));
}

int recv_frame(int sockfd, char *buf, size_t buf_size, uint32_t *out_len)
{
    uint32_t net_len = 0;
    uint32_t len = 0;
    int rc = 0;

    if (!buf || buf_size < 2 || !out_len) return FRAME_ERROR;
    rc = read_n_bytes(sockfd, &net_len, sizeof(net_len));
    if (rc != FRAME_OK) return rc;
    len = ntohl(net_len);
    if (len == 0) return FRAME_EMPTY;

    // reject oversized length before reading payload into fixed buffer
    if (len > MAX_PAYLOAD || len > buf_size - 1) return FRAME_TOO_LONG;
    rc = read_n_bytes(sockfd, buf, len);
    if (rc != FRAME_OK) return rc;
    buf[len] = '\0';
    *out_len = len;
    return FRAME_OK;
}

void sb_init(strbuf_t *sb)
{
    sb->data = NULL;
    sb->len = 0;
    sb->cap = 0;
    sb->failed = 0;
}

void sb_free(strbuf_t *sb)
{
    free(sb->data);
    sb_init(sb);
}

void sb_reset(strbuf_t *sb)
{
    sb->len = 0;
    sb->failed = 0;
    if (sb->data) sb->data[0] = '\0';
}

static int sb_reserve(strbuf_t *sb, size_t extra)
{
    size_t need = sb->len + extra + 1;
    size_t new_cap = sb->cap ? sb->cap : 256;
    char *grown = NULL;

    // cap total size so one reply never exceeds the send frame limit
    if (sb->failed || extra > MAX_SEND_PAYLOAD || need > MAX_SEND_PAYLOAD + 1) {
        sb->failed = 1;
        return -1;
    }
    if (need <= sb->cap) return 0;
    while (new_cap < need) new_cap *= 2;
    grown = realloc(sb->data, new_cap);
    if (!grown) {
        sb->failed = 1;
        return -1;
    }
    sb->data = grown;
    sb->cap = new_cap;
    return 0;
}

int sb_append(strbuf_t *sb, const char *text)
{
    size_t len = text ? strlen(text) : 0;

    if (sb_reserve(sb, len) < 0) return -1;
    memcpy(sb->data + sb->len, text ? text : "", len);
    sb->len += len;
    sb->data[sb->len] = '\0';
    return 0;
}

int sb_appendf(strbuf_t *sb, const char *fmt, ...)
{
    va_list args;
    va_list copy;
    int need = 0;

    va_start(args, fmt);
    va_copy(copy, args);
    need = vsnprintf(NULL, 0, fmt, copy);
    va_end(copy);
    if (need < 0 || sb_reserve(sb, (size_t)need) < 0) {
        va_end(args);
        sb->failed = 1;
        return -1;
    }
    vsnprintf(sb->data + sb->len, sb->cap - sb->len, fmt, args);
    va_end(args);
    sb->len += (size_t)need;
    return 0;
}

static const char *escape_code(char c)
{
    switch (c) {
    case '%': return "%25";
    case '|': return "%7C";
    case '\n': return "%0A";
    case '\r': return "%0D";
    case ':': return "%3A";
    case ',': return "%2C";
    default: return NULL;
    }
}

int sb_append_escaped(strbuf_t *sb, const char *text)
{
    char plain[2] = { 0, 0 };
    const char *cursor = text ? text : "";

    for (; *cursor; cursor++) {
        const char *code = escape_code(*cursor);

        plain[0] = *cursor;
        if (sb_append(sb, code ? code : plain) < 0) return -1;
    }
    return 0;
}

const char *sb_str(const strbuf_t *sb)
{
    return sb->data ? sb->data : "";
}

static int hex_value(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

void unescape_inplace(char *text)
{
    char *read = text;
    char *write = text;

    if (!text) return;
    while (*read) {
        int high = read[0] == '%' && read[1] ? hex_value(read[1]) : -1;
        int low = high >= 0 && read[2] ? hex_value(read[2]) : -1;

        // decode only complete %XX pairs, keep malformed sequences verbatim
        if (high >= 0 && low >= 0) {
            *write++ = (char)(high * 16 + low);
            read += 3;
            continue;
        }
        *write++ = *read++;
    }
    *write = '\0';
}

int split_fields(char *line, char **fields, int max_fields)
{
    char *cursor = line;
    int count = 0;

    if (!line || !fields || max_fields <= 0) return -1;
    fields[count++] = cursor;
    while ((cursor = strchr(cursor, '|')) != NULL) {
        if (count >= max_fields) return -1;
        *cursor++ = '\0';
        fields[count++] = cursor;
    }
    return count;
}

int parse_int(const char *text, int *out)
{
    char *end = NULL;
    long value = 0;

    if (!text || !*text || !out) return -1;
    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || *end != '\0') return -1;
    if (value < INT_MIN || value > INT_MAX) return -1;
    *out = (int)value;
    return 0;
}

void log_open(const char *path, int echo_stdout)
{
    pthread_mutex_lock(&g_log_lock);
    g_log_echo = echo_stdout;
    if (path && *path) g_log_file = fopen(path, "a");
    pthread_mutex_unlock(&g_log_lock);
}

void log_close(void)
{
    pthread_mutex_lock(&g_log_lock);
    if (g_log_file) fclose(g_log_file);
    g_log_file = NULL;
    pthread_mutex_unlock(&g_log_lock);
}

void log_msg(log_level_t level, const char *fmt, ...)
{
    char stamp[32];
    char line[LOG_LINE_MAX];
    time_t now = time(NULL);
    struct tm local;
    va_list args;

    localtime_r(&now, &local);
    strftime(stamp, sizeof(stamp), "%Y-%m-%d %H:%M:%S", &local);
    va_start(args, fmt);
    vsnprintf(line, sizeof(line), fmt, args);
    va_end(args);

    // serialize writers so multi-thread log lines never interleave
    pthread_mutex_lock(&g_log_lock);
    if (g_log_echo) fprintf(stdout, "%s [%s] %s\n", stamp, LOG_LEVEL_NAMES[level], line);
    if (g_log_echo) fflush(stdout);
    if (g_log_file) fprintf(g_log_file, "%s [%s] %s\n", stamp, LOG_LEVEL_NAMES[level], line);
    if (g_log_file) fflush(g_log_file);
    pthread_mutex_unlock(&g_log_lock);
}
