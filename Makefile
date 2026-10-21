CC       ?= cc
CFLAGS   := -std=c11 -Wall -Wextra -Werror -pedantic -pthread -g -O0 -Isrc -D_DEFAULT_SOURCE -D_DARWIN_C_SOURCE
LDLIBS   := -pthread -lsqlite3
BUILD    := build

LIB_SRC  := $(filter-out src/server.c,$(wildcard src/*.c))
LIB_OBJ  := $(patsubst src/%.c,$(BUILD)/%.o,$(LIB_SRC))
HEADERS  := $(wildcard src/*.h)

TEST_SRC := $(wildcard tests/unit/test_*.c)
TEST_BIN := $(patsubst tests/unit/%.c,$(BUILD)/%,$(TEST_SRC))

VALGRIND := valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes --error-exitcode=99

.PHONY: all test itest check valgrind clean

all: server

server: $(LIB_OBJ) $(BUILD)/server.o
	$(CC) $(CFLAGS) -o $@ $^ $(LDLIBS)

$(BUILD)/%.o: src/%.c $(HEADERS) | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/test_%: tests/unit/test_%.c tests/unit/unit.h $(LIB_OBJ) | $(BUILD)
	$(CC) $(CFLAGS) -Itests/unit -o $@ $< $(LIB_OBJ) $(LDLIBS)

$(BUILD):
	mkdir -p $(BUILD)

test: $(TEST_BIN)
	@set -e; for t in $(TEST_BIN); do echo "== $$t"; ./$$t; done

itest: server
	PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/integration -p 'test_*.py' -v

check: test itest

valgrind: server $(TEST_BIN)
	@set -e; for t in $(TEST_BIN); do echo "== valgrind $$t"; $(VALGRIND) ./$$t; done
	SERVER_WRAPPER="$(VALGRIND)" PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests/integration -p 'test_*.py'

clean:
	rm -rf $(BUILD) server
