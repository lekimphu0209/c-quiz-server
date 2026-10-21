# Thiết kế Database — SQLite (phương án B)

Thay thế users.txt, history.csv, ngân hàng câu hỏi hardcode và các mảng struct trong RAM. DB là 1 file exam.db cạnh binary server (WSL2). Lập trình bằng **SQLite C API** (sqlite3.h, link \-lsqlite3). Phần tạo bảng/seed/migrate chạy 1 lần trong main() trước khi listen().

---

## 1\. Quyết định kiến trúc dữ liệu

| Dữ liệu | Lưu ở đâu | Lý do |
| :---- | :---- | :---- |
| users, questions, rooms, attempts, answers | **SQLite exam.db** | cần persist, query, quan hệ |
| **sessions (token → user)** | **RAM** (mảng g\_sessions như hiện tại) | ephemeral — server restart thì login lại; không cần persist |
| connfd của từng client online | RAM (g\_clients) | để push EVT |
| Timer phòng đang chạy | RAM (timer thread hiện tại) | runtime state |

**Snapshot đề thi**: room\_questions lưu **bản sao đầy đủ** nội dung câu hỏi lúc tạo đề — để DEL\_QUESTION/HISTORY\_DETAIL không bị ảnh hưởng khi ngân hàng thay đổi.

## 2\. ERD

erDiagram  
    USERS ||--o{ ROOMS : "owner\_id (host tạo)"  
    USERS ||--o{ ATTEMPTS : "user\_id (1 user nhiều bài)"  
    ROOMS ||--o{ ATTEMPTS : "rid"  
    ROOMS ||--o{ ROOM\_QUESTIONS : "đề (snapshot)"  
    QUESTIONS ||--o{ ROOM\_QUESTIONS : "qid (tham chiếu gốc)"  
    ATTEMPTS ||--o{ ATTEMPT\_ANSWERS : "đáp án từng câu"

    USERS {  
        int id PK  
        text username UK  
        text pass\_hash  
        text salt  
        text role  
        int created\_at  
    }  
    QUESTIONS {  
        int qid PK  
        text content  
        text opt\_a  
        text opt\_b  
        text opt\_c  
        text opt\_d  
        int correct\_opt  
        text difficulty  
        text topic  
        text explanation  
        int created\_at  
    }  
    ROOMS {  
        int rid PK  
        text name  
        int owner\_id FK  
        int num\_q  
        int duration\_sec  
        text difficulty\_cfg  
        text topic  
        text status  
        int is\_practice  
        int start\_ts  
        int created\_at  
    }  
    ROOM\_QUESTIONS {  
        int rid FK  
        int qidx  
        int qid  
        text content  
        text opt\_a  
        text opt\_b  
        text opt\_c  
        text opt\_d  
        int correct\_opt  
        text difficulty  
        text topic  
        text explanation  
    }  
    ATTEMPTS {  
        int att\_id PK  
        int rid FK  
        int user\_id FK  
        text status  
        int score  
        int submit\_ts  
        int joined\_at  
    }  
    ATTEMPT\_ANSWERS {  
        int att\_id FK  
        int qidx  
        int chosen\_opt  
    }

## 3\. Schema chi tiết (DDL)

PRAGMA journal\_mode \= WAL;  
PRAGMA foreign\_keys \= ON;

CREATE TABLE IF NOT EXISTS users (  
    id         INTEGER PRIMARY KEY AUTOINCREMENT,  
    username   TEXT NOT NULL UNIQUE,            *\-- 3-20 ký tự \[a-zA-Z0-9\_\]*  
    pass\_hash  TEXT NOT NULL,                   *\-- SHA-256 hex (64 ký tự)*  
    salt       TEXT NOT NULL,                   *\-- 16 hex ngẫu nhiên*  
    role       TEXT NOT NULL DEFAULT 'user',    *\-- 'user' | 'admin'*  
    created\_at INTEGER NOT NULL                 *\-- unix ts*  
);

CREATE TABLE IF NOT EXISTS questions (  
    qid         INTEGER PRIMARY KEY AUTOINCREMENT,  
    content     TEXT NOT NULL,  
    opt\_a       TEXT NOT NULL,  
    opt\_b       TEXT NOT NULL,  
    opt\_c       TEXT NOT NULL,  
    opt\_d       TEXT NOT NULL,  
    correct\_opt INTEGER NOT NULL CHECK (correct\_opt BETWEEN 0 AND 3),  
    difficulty  TEXT NOT NULL CHECK (difficulty IN ('easy','medium','hard')),  
    topic       TEXT NOT NULL DEFAULT 'all',  
    explanation TEXT NOT NULL DEFAULT '',  
    created\_at  INTEGER NOT NULL  
);  
CREATE INDEX IF NOT EXISTS idx\_q\_diff\_topic ON questions(difficulty, topic);

CREATE TABLE IF NOT EXISTS rooms (  
    rid            INTEGER PRIMARY KEY AUTOINCREMENT,  
    name           TEXT NOT NULL,               *\-- 1-50 ký tự; phòng practice: "practice:\<user\>"*  
    owner\_id       INTEGER NOT NULL REFERENCES users(id),  
    num\_q          INTEGER NOT NULL,  
    duration\_sec   INTEGER NOT NULL,  
    difficulty\_cfg TEXT NOT NULL DEFAULT 'mixed', *\-- 'mixed' hoặc 'easy:a,medium:b,hard:c'*  
    topic          TEXT NOT NULL DEFAULT 'all',  
    status         TEXT NOT NULL DEFAULT 'WAITING'  
                   CHECK (status IN ('WAITING','RUNNING','FINISHED')),  
    is\_practice    INTEGER NOT NULL DEFAULT 0,  
    start\_ts       INTEGER,                     *\-- NULL khi WAITING*  
    created\_at     INTEGER NOT NULL  
);  
CREATE INDEX IF NOT EXISTS idx\_rooms\_status ON rooms(status, is\_practice);

*\-- Snapshot câu hỏi của đề: độc lập với bảng questions*  
CREATE TABLE IF NOT EXISTS room\_questions (  
    rid         INTEGER NOT NULL REFERENCES rooms(rid),  
    qidx        INTEGER NOT NULL,               *\-- vị trí câu 1..num\_q (khớp ANSWER|..|qidx|..)*  
    qid         INTEGER,                        *\-- tham chiếu gốc (NULL được nếu câu gốc bị xóa)*  
    content     TEXT NOT NULL,  
    opt\_a       TEXT NOT NULL,  
    opt\_b       TEXT NOT NULL,  
    opt\_c       TEXT NOT NULL,  
    opt\_d       TEXT NOT NULL,  
    correct\_opt INTEGER NOT NULL,  
    difficulty  TEXT NOT NULL,  
    topic       TEXT NOT NULL,  
    explanation TEXT NOT NULL DEFAULT '',  
    PRIMARY KEY (rid, qidx)  
);

CREATE TABLE IF NOT EXISTS attempts (  
    att\_id    INTEGER PRIMARY KEY AUTOINCREMENT,  
    rid       INTEGER NOT NULL REFERENCES rooms(rid),  
    user\_id   INTEGER NOT NULL REFERENCES users(id),  
    status    TEXT NOT NULL DEFAULT 'IN\_PROGRESS'  
              CHECK (status IN ('IN\_PROGRESS','SUBMITTED')),  
    score     INTEGER,                          *\-- NULL khi chưa chấm*  
    submit\_ts INTEGER,                          *\-- NULL khi chưa nộp; dùng xếp hạng*  
    joined\_at INTEGER NOT NULL,  
    UNIQUE (rid, user\_id)                       *\-- 1 user chỉ 1 attempt/phòng*  
);  
CREATE INDEX IF NOT EXISTS idx\_att\_user   ON attempts(user\_id, status);  
CREATE INDEX IF NOT EXISTS idx\_att\_room   ON attempts(rid, status);

CREATE TABLE IF NOT EXISTS attempt\_answers (  
    att\_id     INTEGER NOT NULL REFERENCES attempts(att\_id),  
    qidx       INTEGER NOT NULL,  
    chosen\_opt INTEGER NOT NULL CHECK (chosen\_opt BETWEEN 0 AND 3),  
    PRIMARY KEY (att\_id, qidx)                  *\-- ANSWER \= INSERT OR REPLACE (ghi đè)*  
);

## 4\. Mapping lệnh protocol → thao tác DB

| Lệnh | Đọc | Ghi |
| :---- | :---- | :---- |
| REGISTER | users (check trùng username) | INSERT users (salt+SHA256(pass)) |
| LOGIN | users (verify hash), attempts×rooms (tìm attempt IN\_PROGRESS của phòng RUNNING → cờ RESUME) | — |
| LOGOUT | — | session RAM (không đụng DB; attempt giữ IN\_PROGRESS) |
| RESUME | room\_questions (đề), attempt\_answers (mask), rooms.start\_ts\+duration\_sec (giây còn) | — |
| PING | — | — |
| PRACTICE | questions (lọc difficulty/topic, ORDER BY RANDOM() LIMIT n) | INSERT rooms (is\_practice=1, status=RUNNING, start\_ts=now), INSERT room\_questions (snapshot), INSERT attempts |
| LIST\_ROOMS | rooms (status ≠ practice) \+ attempts count member | — |
| CREATE\_ROOM | questions (check đủ câu theo difficulty\_cfg/topic) | INSERT rooms, INSERT attempts (owner) |
| JOIN | rooms (status), attempts (member list) | INSERT attempts (status=IN\_PROGRESS) |
| LEAVE\_ROOM | rooms.owner\_id, attempts | DELETE attempts (WAITING) hoặc giữ (RUNNING); owner rời lúc WAITING → UPDATE rooms SET status='FINISHED'? **Không** → đánh dấu đóng: status='FINISHED' \+ push EVT|ROOM\_CLOSED |
| START\_ROOM | rooms (owner, status), attempts (≥2 member), questions (chọn đề) | UPDATE rooms status=RUNNING, start\_ts, INSERT room\_questions (snapshot) |
| END\_ROOM | attempts IN\_PROGRESS \+ room\_questions (chấm) | UPDATE attempts score/submit\_ts/status, UPDATE rooms status=FINISHED |
| GET\_QUESTIONS | room\_questions (đề), attempts (check member) | — |
| ANSWER | attempts (check member, status, hạn giờ qua rooms) | INSERT OR REPLACE attempt\_answers |
| SUBMIT / PRACTICE\_SUBMIT | attempt\_answers × room\_questions (chấm) | UPDATE attempts score, submit\_ts=now, status=SUBMITTED |
| ROOM\_RESULT | attempts × users của rid | — |
| HISTORY | attempts × rooms của user | — |
| HISTORY\_DETAIL | attempt\_answers × room\_questions theo att\_id | — |
| STATS | attempts \+ attempt\_answers × room\_questions | — |
| STATS|t|ALL | như trên, không lọc user | — |
| LIST\_QUESTIONS | questions | — |
| ADD\_QUESTION | — | INSERT questions |
| DEL\_QUESTION | questions | DELETE questions (snapshot trong room\_questions không đổi) |
| IMPORT\_CSV | — | nhiều INSERT questions trong 1 transaction |

### Timer thread (giữ nguyên cơ chế, đổi backend)

* Timer thread ngủ đến start\_ts \+ duration\_sec → thức dậy:  
  1. UPDATE attempts ... status='SUBMITTED', score=\<chấm\>, submit\_ts=NULL cho attempt IN\_PROGRESS.  
  2. UPDATE rooms SET status='FINISHED'.  
  3. Push EVT|RESULT tới từng member online.  
* submit\_ts \= NULL với auto-submit → rank tie-break xếp sau người nộp tay (xem query §5).

## 5\. SQL mẫu cho các query phức tạp

### 5.1 Bảng xếp hạng (ROOM\_RESULT)

SELECT u.username, a.score,  
       COALESCE(a.submit\_ts, 0) AS ts  
FROM   attempts a JOIN users u ON u.id \= a.user\_id  
WHERE  a.rid \= ? AND a.status \= 'SUBMITTED'  
ORDER  BY a.score DESC,  
          (a.submit\_ts IS NULL) ASC,   *\-- nộp tay trước, auto-submit sau*  
          a.submit\_ts ASC;

### 5.2 Chấm điểm (SUBMIT / auto-submit)

SELECT COUNT(\*) FROM attempt\_answers aa  
JOIN room\_questions rq ON rq.rid \= ? AND rq.qidx \= aa.qidx  
WHERE aa.att\_id \= ? AND aa.chosen\_opt \= rq.correct\_opt;

### 5.3 RESUME — kiểm tra \+ lấy mask

*\-- attempt còn dở của user trong phòng đang chạy*  
SELECT a.att\_id, r.rid, r.num\_q,  
       r.duration\_sec \- (strftime('%s','now') \- r.start\_ts) AS remain  
FROM   attempts a JOIN rooms r ON r.rid \= a.rid  
WHERE  a.user\_id \= ? AND a.status \= 'IN\_PROGRESS' AND r.status \= 'RUNNING';

*\-- mask đáp án*  
SELECT qidx, chosen\_opt FROM attempt\_answers WHERE att\_id \= ? ORDER BY qidx;

### 5.4 STATS cá nhân / ALL

SELECT COUNT(DISTINCT a.att\_id)                                   AS attempts,  
       CAST(AVG(100.0\*a.score/r.num\_q) AS INTEGER)                AS avg\_x100,  
       SUM(CASE WHEN rq.difficulty='easy'   AND aa.chosen\_opt=rq.correct\_opt THEN 1 ELSE 0 END) AS easy\_ok,  
       SUM(CASE WHEN rq.difficulty='easy'   THEN 1 ELSE 0 END)    AS easy\_total,  
       */\* tương tự medium, hard \*/*  
       rq.topic                                                   AS topic\_group  
FROM   attempts a  
JOIN   rooms r            ON r.rid \= a.rid  
LEFT JOIN attempt\_answers aa ON aa.att\_id \= a.att\_id  
LEFT JOIN room\_questions  rq ON rq.rid \= a.rid AND rq.qidx \= aa.qidx  
WHERE  a.status \= 'SUBMITTED'  
  AND  (? IS NULL OR a.user\_id \= ?)    *\-- NULL \=\> ALL (admin)*  
GROUP  BY rq.topic;

### 5.5 HISTORY

SELECT a.att\_id, a.submit\_ts, CASE WHEN r.is\_practice THEN 'practice' ELSE 'room' END AS mode,  
       r.name, a.score, r.num\_q  
FROM   attempts a JOIN rooms r ON r.rid \= a.rid  
WHERE  a.user\_id \= ? AND a.status \= 'SUBMITTED'  
  AND  (? \= 'all' OR (? \= 'practice' AND r.is\_practice \= 1) OR (? \= 'room' AND r.is\_practice \= 0))  
ORDER  BY a.submit\_ts DESC;

### 5.6 HISTORY\_DETAIL

SELECT aa.qidx, aa.chosen\_opt, rq.correct\_opt, rq.explanation,  
       rq.content, rq.opt\_a, rq.opt\_b, rq.opt\_c, rq.opt\_d  
FROM   attempt\_answers aa  
JOIN   room\_questions rq ON rq.rid \= ? AND rq.qidx \= aa.qidx  
WHERE  aa.att\_id \= ?  
UNION ALL  
SELECT rq.qidx, \-1, rq.correct\_opt, rq.explanation,  
       rq.content, rq.opt\_a, rq.opt\_b, rq.opt\_c, rq.opt\_d  
FROM   room\_questions rq  
WHERE  rq.rid \= ? AND rq.qidx NOT IN (SELECT qidx FROM attempt\_answers WHERE att\_id \= ?)  
ORDER  BY qidx;

### 5.7 Chọn đề theo difficulty\_cfg (START\_ROOM / PRACTICE)

*\-- cfg \= 'mixed':     SELECT ... ORDER BY RANDOM() LIMIT n*  
*\-- cfg \= 'easy:a,...': chạy 3 query, mỗi độ khó LIMIT tương ứng*  
SELECT qid, content, opt\_a, opt\_b, opt\_c, opt\_d, correct\_opt, difficulty, topic, explanation  
FROM   questions  
WHERE  difficulty \= ? AND ( ? \= 'all' OR topic \= ? )  
ORDER  BY RANDOM() LIMIT ?;  
*\-- đếm được \< cần → ERR|NOT\_ENOUGH\_QUESTIONS*

## 6\. Concurrency & thread-safety

* Server đã có g\_lock (mutex toàn cục) — **giữ nguyên**: mọi hàm handler gọi sqlite3\_\* **bên trong critical section** như hiện nay → 1 connection sqlite3\* dùng chung là đủ, không cần serialize mode.  
* PRAGMA journal\_mode=WAL \+ busy\_timeout=3000 phòng trường hợp sau này bỏ g\_lock.  
* **Transaction**: PRACTICE/START\_ROOM/IMPORT\_CSV/END\_ROOM ghi nhiều bảng → bọc BEGIN IMMEDIATE … COMMIT.  
* Không lưu username lặp lại trong attempts — join users khi cần hiển thị.

## 7\. Migrate dữ liệu cũ → exam.db

Chạy 1 lần khi main() khởi động (idempotent — check marker bảng meta):

| Nguồn cũ | Đích | Cách |
| :---- | :---- | :---- |
| users.txt (user:pass plaintext) | users | đọc từng dòng → sinh salt ngẫu nhiên, pass\_hash \= sha256(salt \+ pass), role='user'; tạo sẵn 1 admin admin/admin123 nếu chưa có |
| qbank hardcode g\_qbank\[\] trong server.c | questions | INSERT toàn bộ, difficulty='medium', topic='all' (mặc định), seed thêm CSV nếu có |
| history.csv (user,room,score,total) | attempts | tạo rooms giả status=FINISHED,is\_practice=0,name='imported' nếu rid không còn; submit\_ts \= ts của file |
| sessions RAM | — | không migrate (login lại) |

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);  
*\-- marker: INSERT INTO meta VALUES('migrated','1')*

## 8\. Vai trò file .csv sau khi có DB

* questions.csv chỉ còn là **định dạng input của IMPORT\_CSV** — không phải storage.  
* history.csv ngừng ghi — HISTORY đọc từ attempts.  
* users.txt ngừng dùng — giữ file cũ làm nguồn migrate lần đầu.

## 9\. Build & môi trường

* WSL2: sudo apt install libsqlite3-dev; Makefile server thêm \-lsqlite3.  
* Header mới: include/db.h khai báo db\_init(), db\_migrate(), và các hàm db\_\* cho từng handler (giữ SQL tập trung 1 file src/db.c — handler chỉ gọi hàm, không rải SQL).

