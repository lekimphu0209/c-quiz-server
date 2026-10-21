#include <stdio.h>
#include <string.h>

#include "common.h"
#include "sha256.h"
#include "unit.h"

static void test_sha256_known_vectors(void)
{
    char hex[SHA256_HEX_LEN + 1];
    const char *long_input = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";

    sha256_hex((const unsigned char *)"", 0, hex);
    CHECK_STR(hex, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    sha256_hex((const unsigned char *)"abc", 3, hex);
    CHECK_STR(hex, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    sha256_hex((const unsigned char *)long_input, strlen(long_input), hex);
    CHECK_STR(hex, "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
}

static void test_sha256_million_a_crosses_many_blocks(void)
{
    sha256_ctx_t ctx;
    unsigned char chunk[1000];
    unsigned char digest[32];
    char hex[SHA256_HEX_LEN + 1];
    int i = 0;

    memset(chunk, 'a', sizeof(chunk));
    sha256_init(&ctx);
    for (i = 0; i < 1000; i++) sha256_update(&ctx, chunk, sizeof(chunk));
    sha256_final(&ctx, digest);
    for (i = 0; i < 32; i++) snprintf(hex + i * 2, 3, "%02x", digest[i]);
    CHECK_STR(hex, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
}

static void test_hash_password_uses_salt_prefix(void)
{
    char expected[SHA256_HEX_LEN + 1];
    char actual[HASH_HEX_LEN + 1];
    char other[HASH_HEX_LEN + 1];

    sha256_hex((const unsigned char *)"00ff00ff00ff00ff123456", 22, expected);
    hash_password("00ff00ff00ff00ff", "123456", actual);
    CHECK_STR(actual, expected);
    hash_password("1111111111111111", "123456", other);
    CHECK(strcmp(actual, other) != 0);
}

static void test_random_hex_is_lowercase_and_unique(void)
{
    char first[TOKEN_HEX_LEN + 1];
    char second[TOKEN_HEX_LEN + 1];
    size_t i = 0;

    CHECK(random_hex(first, TOKEN_HEX_LEN) == 0);
    CHECK(random_hex(second, TOKEN_HEX_LEN) == 0);
    CHECK(strlen(first) == TOKEN_HEX_LEN);
    CHECK(strcmp(first, second) != 0);
    for (i = 0; i < TOKEN_HEX_LEN; i++) CHECK((first[i] >= '0' && first[i] <= '9') || (first[i] >= 'a' && first[i] <= 'f'));
    CHECK(random_hex(first, 7) == -1);
}

static void test_secure_equals(void)
{
    CHECK(secure_equals("abc", "abc") == 1);
    CHECK(secure_equals("abc", "abd") == 0);
    CHECK(secure_equals("abc", "abcd") == 0);
    CHECK(secure_equals(NULL, "abc") == 0);
}

int main(void)
{
    RUN(test_sha256_known_vectors);
    RUN(test_sha256_million_a_crosses_many_blocks);
    RUN(test_hash_password_uses_salt_prefix);
    RUN(test_random_hex_is_lowercase_and_unique);
    RUN(test_secure_equals);
    return UNIT_REPORT();
}
