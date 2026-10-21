#ifndef DB_INTERNAL_H
#define DB_INTERNAL_H

#include <stddef.h>

#include <sqlite3.h>

sqlite3_stmt *db_prepare(const char *sql, const char *types, ...);
int db_execute(const char *sql, const char *types, ...);
int db_query_int(const char *sql, int fallback, const char *types, ...);
long long db_last_insert_id(void);
void db_column_copy(sqlite3_stmt *stmt, int col, char *dst, size_t dst_size);

#endif
