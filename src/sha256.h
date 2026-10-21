#ifndef SHA256_H
#define SHA256_H

#include <stddef.h>
#include <stdint.h>

#define SHA256_DIGEST_LEN 32
#define SHA256_HEX_LEN 64

typedef struct {
    uint32_t state[8];
    uint64_t bit_len;
    uint8_t  block[64];
    size_t   block_len;
} sha256_ctx_t;

void sha256_init(sha256_ctx_t *ctx);
void sha256_update(sha256_ctx_t *ctx, const unsigned char *data, size_t len);
void sha256_final(sha256_ctx_t *ctx, unsigned char digest[SHA256_DIGEST_LEN]);
void sha256_hex(const unsigned char *data, size_t len, char out[SHA256_HEX_LEN + 1]);

#endif
