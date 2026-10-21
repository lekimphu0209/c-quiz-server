#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#include "common.h"
#include "unit.h"

typedef struct {
    int         fd;
    const char *wire;
    size_t      cuts[4];
    int         cut_count;
} chunk_writer_t;

static void make_pair(int fds[2])
{
    int rc = socketpair(AF_UNIX, SOCK_STREAM, 0, fds);

    CHECK(rc == 0);
}

static size_t build_frame(const char *payload, char *out)
{
    uint32_t len = (uint32_t)strlen(payload);
    uint32_t net_len = htonl(len);

    memcpy(out, &net_len, 4);
    memcpy(out + 4, payload, len);
    return len + 4;
}

static void *write_chunks(void *arg)
{
    chunk_writer_t *writer = arg;
    size_t start = 0;
    int i = 0;

    for (i = 0; i < writer->cut_count; i++) {
        write_n_bytes(writer->fd, writer->wire + start, writer->cuts[i] - start);
        start = writer->cuts[i];
        usleep(200000);
    }
    return NULL;
}

static void test_send_then_recv_roundtrip(void)
{
    int fds[2];
    char buf[MAX_PAYLOAD + 1];
    uint32_t len = 0;

    make_pair(fds);
    CHECK(send_text(fds[0], "PING") == 0);
    CHECK(recv_frame(fds[1], buf, sizeof(buf), &len) == FRAME_OK);
    CHECK(len == 4);
    CHECK_STR(buf, "PING");
    close(fds[0]);
    close(fds[1]);
}

static void test_sticky_frames_in_one_write(void)
{
    int fds[2];
    char wire[64];
    char buf[MAX_PAYLOAD + 1];
    size_t total = 0;
    uint32_t len = 0;
    int i = 0;

    make_pair(fds);
    for (i = 0; i < 3; i++) total += build_frame("PING", wire + total);
    CHECK(write_n_bytes(fds[0], wire, total) == 0);

    // drain three frames glued by a single TCP write
    for (i = 0; i < 3; i++) {
        CHECK(recv_frame(fds[1], buf, sizeof(buf), &len) == FRAME_OK);
        CHECK_STR(buf, "PING");
    }
    close(fds[0]);
    close(fds[1]);
}

static void test_split_frame_across_chunks(void)
{
    int fds[2];
    char wire[64];
    char buf[MAX_PAYLOAD + 1];
    uint32_t len = 0;
    pthread_t thread;
    chunk_writer_t writer;

    make_pair(fds);
    writer.fd = fds[0];
    writer.wire = wire;
    writer.cuts[0] = 2;
    writer.cuts[1] = 11;
    writer.cuts[2] = build_frame("LOGIN|alice|123456", wire);
    writer.cut_count = 3;

    // cut inside the 4-byte header and inside the payload
    pthread_create(&thread, NULL, write_chunks, &writer);
    CHECK(recv_frame(fds[1], buf, sizeof(buf), &len) == FRAME_OK);
    CHECK(len == 18);
    CHECK_STR(buf, "LOGIN|alice|123456");
    pthread_join(thread, NULL);
    close(fds[0]);
    close(fds[1]);
}

static void test_reject_oversized_and_empty_frames(void)
{
    int fds[2];
    char buf[MAX_PAYLOAD + 1];
    uint32_t len = 0;
    uint32_t net_len = htonl(MAX_PAYLOAD + 1);
    uint32_t zero = 0;

    make_pair(fds);
    write_n_bytes(fds[0], &net_len, 4);
    CHECK(recv_frame(fds[1], buf, sizeof(buf), &len) == FRAME_TOO_LONG);
    write_n_bytes(fds[0], &zero, 4);
    CHECK(recv_frame(fds[1], buf, sizeof(buf), &len) == FRAME_EMPTY);
    CHECK(send_frame(fds[0], "x", 0) == -1);
    close(fds[0]);
    CHECK(recv_frame(fds[1], buf, sizeof(buf), &len) == FRAME_CLOSED);
    close(fds[1]);
}

static void test_reject_frame_larger_than_buffer(void)
{
    int fds[2];
    char small[8];
    uint32_t len = 0;

    make_pair(fds);
    send_text(fds[0], "LONGER_THAN_SMALL");
    CHECK(recv_frame(fds[1], small, sizeof(small), &len) == FRAME_TOO_LONG);
    close(fds[0]);
    close(fds[1]);
}

static void test_escape_and_unescape_roundtrip(void)
{
    strbuf_t sb;
    char copy[128];

    sb_init(&sb);
    CHECK(sb_append_escaped(&sb, "a|b\nc:d,e%f") == 0);
    CHECK_STR(sb_str(&sb), "a%7Cb%0Ac%3Ad%2Ce%25f");
    snprintf(copy, sizeof(copy), "%s", sb_str(&sb));
    unescape_inplace(copy);
    CHECK_STR(copy, "a|b\nc:d,e%f");
    sb_free(&sb);
}

static void test_unescape_keeps_invalid_sequences(void)
{
    char text[32];

    snprintf(text, sizeof(text), "%s", "100%|%zz|%4");
    unescape_inplace(text);
    CHECK_STR(text, "100%|%zz|%4");
    snprintf(text, sizeof(text), "%s", "Thi%20giua%20ky");
    unescape_inplace(text);
    CHECK_STR(text, "Thi giua ky");
}

static void test_split_fields_counts_empty_fields(void)
{
    char line[64];
    char *fields[MAX_FIELDS];

    snprintf(line, sizeof(line), "%s", "ADD|a||c|");
    CHECK(split_fields(line, fields, MAX_FIELDS) == 5);
    CHECK_STR(fields[0], "ADD");
    CHECK_STR(fields[2], "");
    CHECK_STR(fields[4], "");
    snprintf(line, sizeof(line), "%s", "a|b|c");
    CHECK(split_fields(line, fields, 2) == -1);
}

static void test_strbuf_formats_and_caps_size(void)
{
    strbuf_t sb;
    char *big = malloc(MAX_SEND_PAYLOAD + 2);

    sb_init(&sb);
    CHECK(sb_appendf(&sb, "OK|%d|%s", 7, "PONG") == 0);
    CHECK_STR(sb_str(&sb), "OK|7|PONG");
    sb_reset(&sb);
    CHECK_STR(sb_str(&sb), "");
    memset(big, 'x', MAX_SEND_PAYLOAD + 1);
    big[MAX_SEND_PAYLOAD + 1] = '\0';
    CHECK(sb_append(&sb, big) == -1);
    CHECK(sb.failed == 1);
    free(big);
    sb_free(&sb);
}

static void test_parse_int_is_strict(void)
{
    int value = 0;

    CHECK(parse_int("42", &value) == 0 && value == 42);
    CHECK(parse_int("-1", &value) == 0 && value == -1);
    CHECK(parse_int("", &value) == -1);
    CHECK(parse_int("4x", &value) == -1);
    CHECK(parse_int("99999999999", &value) == -1);
}

int main(void)
{
    RUN(test_send_then_recv_roundtrip);
    RUN(test_sticky_frames_in_one_write);
    RUN(test_split_frame_across_chunks);
    RUN(test_reject_oversized_and_empty_frames);
    RUN(test_reject_frame_larger_than_buffer);
    RUN(test_escape_and_unescape_roundtrip);
    RUN(test_unescape_keeps_invalid_sequences);
    RUN(test_split_fields_counts_empty_fields);
    RUN(test_strbuf_formats_and_caps_size);
    RUN(test_parse_int_is_strict);
    return UNIT_REPORT();
}
