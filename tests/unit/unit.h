#ifndef UNIT_H
#define UNIT_H

#include <stdio.h>
#include <string.h>

static int g_unit_checks = 0;
static int g_unit_failures = 0;

#define CHECK(cond) do { g_unit_checks++; if (!(cond)) { g_unit_failures++; fprintf(stderr, "  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); } } while (0)

#define CHECK_STR(actual, expected) CHECK(strcmp((actual), (expected)) == 0)

#define RUN(test_fn) do { printf("  %s\n", #test_fn); test_fn(); } while (0)

#define UNIT_REPORT() (printf("  %d checks, %d failures\n", g_unit_checks, g_unit_failures), g_unit_failures == 0 ? 0 : 1)

#endif
