#include <stdio.h>
#include <string.h>

#include "sha256.h"

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

static const uint32_t INITIAL_STATE[8] = {
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
};

static void sha256_schedule(const uint8_t block[64], uint32_t w[64])
{
    int i = 0;

    for (i = 0; i < 16; i++) {
        w[i] = ((uint32_t)block[i * 4] << 24) | ((uint32_t)block[i * 4 + 1] << 16) | ((uint32_t)block[i * 4 + 2] << 8) | (uint32_t)block[i * 4 + 3];
    }
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ROTR(w[i - 15], 7) ^ ROTR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ROTR(w[i - 2], 17) ^ ROTR(w[i - 2], 19) ^ (w[i - 2] >> 10);

        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
}

static void sha256_transform(sha256_ctx_t *ctx, const uint8_t block[64])
{
    uint32_t w[64];
    uint32_t v[8];
    int i = 0;

    sha256_schedule(block, w);
    memcpy(v, ctx->state, sizeof(v));
    for (i = 0; i < 64; i++) {
        uint32_t s1 = ROTR(v[4], 6) ^ ROTR(v[4], 11) ^ ROTR(v[4], 25);
        uint32_t ch = (v[4] & v[5]) ^ (~v[4] & v[6]);
        uint32_t t1 = v[7] + s1 + ch + K[i] + w[i];
        uint32_t s0 = ROTR(v[0], 2) ^ ROTR(v[0], 13) ^ ROTR(v[0], 22);
        uint32_t maj = (v[0] & v[1]) ^ (v[0] & v[2]) ^ (v[1] & v[2]);

        // rotate working variables h..a, then fold t1 into e and a
        memmove(&v[1], &v[0], 7 * sizeof(uint32_t));
        v[4] += t1;
        v[0] = t1 + s0 + maj;
    }
    for (i = 0; i < 8; i++) ctx->state[i] += v[i];
}

void sha256_init(sha256_ctx_t *ctx)
{
    memcpy(ctx->state, INITIAL_STATE, sizeof(INITIAL_STATE));
    ctx->bit_len = 0;
    ctx->block_len = 0;
}

void sha256_update(sha256_ctx_t *ctx, const unsigned char *data, size_t len)
{
    size_t i = 0;

    for (i = 0; i < len; i++) {
        ctx->block[ctx->block_len++] = data[i];
        if (ctx->block_len < 64) continue;
        sha256_transform(ctx, ctx->block);
        ctx->bit_len += 512;
        ctx->block_len = 0;
    }
}

void sha256_final(sha256_ctx_t *ctx, unsigned char digest[SHA256_DIGEST_LEN])
{
    uint64_t total_bits = ctx->bit_len + (uint64_t)ctx->block_len * 8;
    int i = 0;

    ctx->block[ctx->block_len++] = 0x80;

    // spill padding into an extra block when length field no longer fits
    if (ctx->block_len > 56) {
        memset(ctx->block + ctx->block_len, 0, 64 - ctx->block_len);
        sha256_transform(ctx, ctx->block);
        ctx->block_len = 0;
    }
    memset(ctx->block + ctx->block_len, 0, 56 - ctx->block_len);
    for (i = 0; i < 8; i++) ctx->block[63 - i] = (uint8_t)(total_bits >> (i * 8));
    sha256_transform(ctx, ctx->block);
    for (i = 0; i < SHA256_DIGEST_LEN; i++) digest[i] = (uint8_t)(ctx->state[i / 4] >> (24 - (i % 4) * 8));
}

void sha256_hex(const unsigned char *data, size_t len, char out[SHA256_HEX_LEN + 1])
{
    sha256_ctx_t ctx;
    unsigned char digest[SHA256_DIGEST_LEN];
    int i = 0;

    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, digest);
    for (i = 0; i < SHA256_DIGEST_LEN; i++) snprintf(out + i * 2, 3, "%02x", digest[i]);
}
