#include <string.h>

#include "question.h"
#include "unit.h"

static void test_validate_accepts_complete_question(void)
{
    question_t question = { "Q?", { "A", "B", "C", "D" }, 2, "medium", "net", "" };

    CHECK(question_validate(&question) == NULL);
}

static void test_validate_rejects_bad_fields(void)
{
    question_t question = { "Q?", { "A", "B", "C", "D" }, 4, "medium", "net", "" };

    CHECK(question_validate(&question) != NULL);
    question.correct = 0;
    question.difficulty = "mixed";
    CHECK(question_validate(&question) != NULL);
    question.difficulty = "hard";
    question.opts[3] = "";
    CHECK(question_validate(&question) != NULL);
    question.opts[3] = "D";
    question.topic = "";
    CHECK(question_validate(&question) != NULL);
}

static void test_parse_csv_line_success(void)
{
    char line[] = "TCP%3B UDP?;A;B;C;D;3;hard;net;why\r\n";
    question_t question;

    memset(&question, 0, sizeof(question));
    CHECK(question_parse_csv_line(line, &question) == 0);
    CHECK_STR(question.content, "TCP; UDP?");
    CHECK_STR(question.opts[3], "D");
    CHECK(question.correct == 3);
    CHECK_STR(question.difficulty, "hard");
    CHECK_STR(question.topic, "net");
    CHECK_STR(question.explanation, "why");
}

static void test_parse_csv_line_rejects_wrong_shape(void)
{
    char short_line[] = "Q;A;B;C;D;1;easy;net";
    char long_line[] = "Q;A;B;C;D;1;easy;net;x;extra";
    char bad_correct[] = "Q;A;B;C;D;one;easy;net;x";
    question_t question;

    CHECK(question_parse_csv_line(short_line, &question) == -1);
    CHECK(question_parse_csv_line(long_line, &question) == -1);
    CHECK(question_parse_csv_line(bad_correct, &question) == -1);
}

int main(void)
{
    RUN(test_validate_accepts_complete_question);
    RUN(test_validate_rejects_bad_fields);
    RUN(test_parse_csv_line_success);
    RUN(test_parse_csv_line_rejects_wrong_shape);
    return UNIT_REPORT();
}
