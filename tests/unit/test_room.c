#include <string.h>

#include "room.h"
#include "unit.h"

static void test_utf8_length_counts_code_points(void)
{
    CHECK(utf8_length("") == 0);
    CHECK(utf8_length("abc") == 3);
    CHECK(utf8_length("Đề thi") == 6);
}

static void test_parse_mixed_and_single(void)
{
    exam_mix_t mix;

    CHECK(parse_exam_mix("mixed", 7, &mix) == 0);
    CHECK(mix.mixed == 7 && mix.easy == 0);
    CHECK(parse_exam_mix("hard", 4, &mix) == 0);
    CHECK(mix.hard == 4 && mix.mixed == 0);
}

static void test_parse_ratio(void)
{
    exam_mix_t mix;

    CHECK(parse_exam_mix("easy:5,medium:10,hard:5", 20, &mix) == 0);
    CHECK(mix.easy == 5 && mix.medium == 10 && mix.hard == 5);
    CHECK(parse_exam_mix("hard:2,easy:1", 3, &mix) == 0);
    CHECK(mix.easy == 1 && mix.medium == 0 && mix.hard == 2);
}

static void test_parse_rejects_bad_ratio(void)
{
    exam_mix_t mix;

    CHECK(parse_exam_mix("easy:2,medium:2,hard:2", 3, &mix) == -1);
    CHECK(parse_exam_mix("easy:1,easy:2", 3, &mix) == -1);
    CHECK(parse_exam_mix("easy:-1,hard:4", 3, &mix) == -1);
    CHECK(parse_exam_mix("easy:x", 3, &mix) == -1);
    CHECK(parse_exam_mix("weird", 3, &mix) == -1);
    CHECK(parse_exam_mix("", 3, &mix) == -1);
    CHECK(parse_exam_mix(NULL, 3, &mix) == -1);
}

int main(void)
{
    RUN(test_utf8_length_counts_code_points);
    RUN(test_parse_mixed_and_single);
    RUN(test_parse_ratio);
    RUN(test_parse_rejects_bad_ratio);
    return UNIT_REPORT();
}
