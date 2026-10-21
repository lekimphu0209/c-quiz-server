#ifndef SEED_H
#define SEED_H

#include <stddef.h>

typedef struct {
    const char *content;
    const char *opts[4];
    int         correct;
    const char *difficulty;
    const char *topic;
    const char *explanation;
} seed_question_t;

extern const seed_question_t SEED_QUESTIONS[];
extern const size_t SEED_QUESTION_COUNT;

#endif
