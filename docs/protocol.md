# Đặc tả Protocol / API — Exam App (source of truth cho wire format)

Tài liệu này là **chuẩn duy nhất** về những gì đi trên dây mạng. 01\_USECASES\_FLOWS.md mô tả *khi nào* gọi lệnh; file này mô tả *byte nào* được truyền. Nếu server.c hiện tại khác với spec này → **spec này là mục tiêu cần sửa server theo** (xem mục 9 — bảng đối chiếu).

---

## 1\. Tầng framing (đã chốt — giữ nguyên từ code hiện có)

┌──────────────────────────────┬─────────────────────────────────┐  
│  4 byte length (uint32,      │  payload: len byte, chuỗi text  │  
│  network byte order / BE)    │  "TRUONG1|TRUONG2|..."          │  
└──────────────────────────────┴─────────────────────────────────┘

* **Hàm nền tảng**: send\_frame(sockfd, payload, len) / recv\_frame(sockfd, buf, size, \&len) (common.h). recv\_frame lặp đọc đến khi đủ 4 byte header rồi đủ len byte payload — chống dính gói/xé gói.  
* **Giới hạn**: len ≤ MAX\_LINE \= 1024. len \= 0 hoặc len \> 1024 → frame lỗi, đóng kết nối.  
* **Payload KHÔNG có null-terminator** trên dây; phía nhận tự thêm '\\0' sau khi recv.  
* **Trả về của recv\_frame**: 1 ok / 0 đối phương đóng / \-1 lỗi socket.

## 2\. Quy ước payload

| Quy tắc | Chi tiết |
| :---- | :---- |
| Phân cách trường | \` |
| Escape trong nội dung text | \` |
| Trường con (sub-field) trong 1 field | : (vd. rank:user:score), nhóm lặp key:val,key:val (vd. easy:5,medium:10) |
| Số | ASCII decimal, không leading zero |
| Token phiên | 32 ký tự hex, chữ thường |
| Đáp án opt | 0\=A, 1\=B, 2\=C, 3\=D; \-1 \= chưa chọn |
| Độ khó | easy / medium / hard / mixed (khi là tham số lọc) |
| Trạng thái phòng | WAITING / RUNNING / FINISHED (chữ hoa, trên dây) |

### Cấu trúc bản ghi câu hỏi (qrec)

Dùng chung trong EVT|EXAM, OK|STARTED, OK|PRACTICE, OK|RESUME, GET\_QUESTIONS:

qid:content:optA:optB:optC:optD:difficulty

* Các qrec nối nhau bằng | → đề n câu \= n qrec.  
* **Không chứa đáp án đúng** (chốt xem trước). Đáp án đúng chỉ xuất hiện trong ROOM\_RESULT/HISTORY\_DETAIL.  
* Ví dụ 1 qrec: 7:TCP đảm bảo điều gì?:Tốc độ cao nhất:Tin cậy%7C đúng thứ tự:Ít overhead:Broadcast:medium

## 3\. Vai trò & trạng thái phiên

| Role | Lệnh được phép |
| :---- | :---- |
| **guest** (chưa login) | PING, REGISTER, LOGIN |
| **user** | tất cả lệnh user \+ host |
| **host** (owner của phòng cụ thể) | START\_ROOM, END\_ROOM trên phòng mình tạo |
| **admin** | toàn bộ \+ LIST\_QUESTIONS, ADD\_QUESTION, DEL\_QUESTION, IMPORT\_CSV, \`STATS |

Mọi lệnh sau login đều mang token ở **field 1** (trừ REGISTER/LOGIN/PING).

---

## 4\. Từ điển lệnh

Cột **TT** (trạng thái): ✔ đã có trong server.c · ✏ có nhưng **đổi tên/format** · ✚ lệnh mới phải viết.

### 4A. Phiên & xác thực

#### PING — ✚

* **Request**: PING  
* **OK**: OK|PONG  
* **Dùng**: kiểm tra kết nối ngay sau connect() (S1), hoặc định kỳ.  
* **Lỗi**: không.

#### REGISTER — ✏ (đã có; đổi payload OK)

* **Request**: REGISTER|username|password  
* **Validate server**: username 3–20 ký tự \[a-zA-Z0-9\_\]; password ≥ 6 ký tự; username chưa tồn tại.  
* **OK**: OK|REGISTERED *(hiện tại: OK|dang ky thanh cong → đổi)*  
* **ERR**: USER\_EXISTS · BAD\_ARGS  
* **Ghi**: append users.txt; hash password SHA-256+salt *(hiện tại lưu plaintext → nâng cấp)*.

#### LOGIN — ✏ (đổi payload OK: thêm role \+ RESUME)

* **Request**: LOGIN|username|password  
* **OK**: OK|token|role — hoặc OK|token|role|RESUME|room\_id nếu user còn attempt IN\_PROGRESS.  
* **ERR**: BAD\_CREDENTIALS · ALREADY\_LOGGED\_IN · BAD\_ARGS  
* *(hiện tại server trả OK|token — thiếu role và nhánh RESUME).*

#### LOGOUT — ✔

* **Request**: LOGOUT|token  
* **OK**: OK|BYE — hủy session; giữ nguyên attempt IN\_PROGRESS để RESUME sau.  
* **ERR**: NOT\_AUTHENTICATED

#### RESUME — ✚

* **Request**: RESUME|token|room\_id  
* **OK**: OK|RESUME|rid|n|giây\_còn|ans\_mask|qrec|qrec|...  
  * giây\_còn \= duration \- (now \- start\_time), tính phía server.  
  * ans\_mask \= n ký tự 0/1 theo thứ tự câu (đã trả lời).  
* **ERR**: NOT\_AUTHENTICATED · NO\_ROOM · BAD\_STATE (phòng FINISHED → EXAM\_ENDED)

### 4B. Luyện tập

#### PRACTICE — ✚ (thay PRACTICE\_START)

* **Request**: PRACTICE|token|n|sec|difficulty|topic  
  * difficulty: easy|medium|hard|mixed; topic: tên chủ đề hoặc all.  
* **OK**: OK|PRACTICE|rid|n|sec|qrec|qrec|... — rid là phòng ẩn is\_practice=1, không hiện trong LIST\_ROOMS.  
* **ERR**: BAD\_ARGS · NOT\_ENOUGH\_QUESTIONS · BAD\_STATE (đang ở phòng/bài khác)

#### ANSWER (dùng chung cho practice) — ✔

* Practice room dùng chung ANSWER/SUBMIT với rid của phòng practice.  
* *(hiện tại: PRACTICE\_ANSWER|token|room\_id|qid|opt đổi tên nội bộ thành ANSWER — target: client gọi ANSWER trực tiếp).*

#### PRACTICE\_SUBMIT — ✔ (giữ làm alias của SUBMIT)

* **Request**: PRACTICE\_SUBMIT|token|rid  
* **OK**: OK|score|n — giống SUBMIT, cộng thêm lịch sử với mode=practice.

### 4C. Quản lý phòng

#### LIST\_ROOMS — ✏ (đổi format item \+ thêm filter)

* **Request**: LIST\_ROOMS|token\[|filter\] — filter ∈ ALL|WAITING|RUNNING|FINISHED (mặc định ALL).  
* **OK**: OK|room|room|... với room \= rid:name:owner:status:n:sec:member\_count  
  * Không có phòng → OK (trần).  
  * Không trả phòng is\_practice.  
* *(hiện tại item \= id:owner:status:num\_q/duration — thiếu name, member\_count).*

#### CREATE\_ROOM — ✏ (đổi tham số)

* **Request**: CREATE\_ROOM|token|name|n|sec|difficulty|topic  
  * difficulty: mixed hoặc easy:a,medium:b,hard:c với a+b+c \== n.  
* **OK**: OK|rid — creator tự vào phòng, trạng thái WAITING, role host.  
* **ERR**: BAD\_ARGS (n ∉ \[1,100\], sec ∉ \[60,14400\], a+b+c ≠ n, tên rỗng/\>50 ký tự) · BAD\_STATE (đang ở phòng khác) · NOT\_ENOUGH\_QUESTIONS  
* *(hiện tại: CREATE\_ROOM|token|num\_q|duration — thêm name/difficulty/topic).*

#### JOIN — ✏ (đổi tên từ JOIN\_ROOM, đổi OK, thêm EVT)

* **Request**: JOIN|token|rid  
* **OK**: OK|JOINED|rid|name|owner|n|sec|difficulty|mem1,mem2,... — trả member list để S4 khởi tạo lstMembers.  
* **EVT phát**: EVT|MEMBER\_JOINED|rid|username → tất cả member khác trong phòng.  
* **ERR**: NO\_ROOM · ROOM\_STARTED (status ≠ WAITING) · ALREADY\_JOINED · BAD\_STATE (đang ở phòng khác) · ROOM\_FULL (\> MAX\_PARTICIPANTS)  
* *(hiện tại OK|tham gia phong thanh cong — thiếu metadata, chưa broadcast EVT).*

#### LEAVE\_ROOM — ✚

* **Request**: LEAVE\_ROOM|token|rid  
* **OK**: OK|LEFT  
* **EVT phát**:  
  * member thường rời → EVT|MEMBER\_LEFT|rid|username cho member còn lại.  
  * **owner rời khi phòng WAITING** → hủy phòng, EVT|ROOM\_CLOSED|rid cho mọi member.  
  * owner rời khi RUNNING → phòng vẫn tiếp tục (bài đã phát rồi).  
* **ERR**: NO\_ROOM · BAD\_STATE (không ở phòng này)

#### START\_ROOM — ✏ (đổi tên từ START\_EXAM, thêm broadcast)

* **Request**: START\_ROOM|token|rid  
* **Quyền**: chỉ owner.  
* **Điều kiện**: room WAITING; ≥ 2 member (kể cả host); ngân hàng đủ câu.  
* **OK**: OK|STARTED|rid|n|sec|qrec|... (trả cho host).  
* **EVT phát**: EVT|EXAM|rid|n|sec|qrec|... → mọi member khác.  
* **ERR**: FORBIDDEN · NO\_ROOM · BAD\_STATE (đã RUNNING / \< 2 member) · NOT\_ENOUGH\_QUESTIONS  
* *(hiện tại: chỉ trả đề cho host, member phải tự GET\_QUESTIONS — target: push EVT|EXAM).*

#### END\_ROOM — ✚

* **Request**: END\_ROOM|token|rid  
* **Quyền**: chỉ owner; room RUNNING.  
* **Tác động**: auto-submit mọi attempt IN\_PROGRESS, chấm điểm, ghi history, phòng → FINISHED.  
* **OK**: OK|ENDED  
* **EVT phát**: EVT|RESULT|rid|score/n|rank → từng member (payload riêng theo user).  
* **ERR**: FORBIDDEN · NO\_ROOM · BAD\_STATE

#### GET\_QUESTIONS — ✔ (giữ làm fallback)

* **Request**: GET\_QUESTIONS|token|rid — cho member lỡ EVT|EXAM (reconnect, join trễ edge-case).  
* **OK**: OK|n|sec|qrec|... — chỉ khi room RUNNING và requester là member.  
* **ERR**: NO\_ROOM · BAD\_STATE · FORBIDDEN

#### ROOM\_RESULT — ✏ (đổi tên từ RESULT, format mới)

* **Request**: ROOM\_RESULT|token|rid  
* **Điều kiện**: room FINISHED.  
* **OK**: OK|n|entry|entry|... với entry \= rank:username:score:submit\_ts  
  * Sắp xếp: score giảm dần → submit\_ts tăng dần (nộp sớm thắng).  
  * submit\_ts: unix timestamp, hoặc 0 nếu auto-submit do hết giờ.  
* **ERR**: NO\_ROOM · ROOM\_NOT\_FINISHED

### 4D. Làm bài

#### ANSWER — ✔

* **Request**: ANSWER|token|rid|qidx|opt  
  * qidx: **vị trí câu trong đề, 1-based** (khớp ma trận nút ở S5). Server map qidx → question\_ids\[qidx-1\].  
  * opt: 0..3; gửi lại ghi đè đáp án cũ.  
* **OK**: OK *(hiện tại OK|da ghi nhan dap an — có thể giữ, client chỉ check prefix OK).*  
* **ERR**: NO\_ROOM · BAD\_STATE (room chưa RUNNING / đã FINISHED) · FORBIDDEN (không phải member) · EXAM\_ENDED (hết giờ / đã quá hạn) · ALREADY\_SUBMITTED · BAD\_ARGS (qidx/opt ngoài khoảng)  
* *(hiện tại server nhận question\_id; target đổi sang qidx — hoặc giữ question\_id nếu muốn ít sửa server, khi đó UI phải truyền qid từ qrec. **Chốt trong spec này: dùng qidx**.)*

#### SUBMIT — ✔

* **Request**: SUBMIT|token|rid  
* **OK**: OK|score|n — chấm ngay, ghi history mode=room, attempt → SUBMITTED.  
* **EVT phát** (khi là người cuối cùng nộp trong room): EVT|RESULT|... cho tất cả \+ phòng → FINISHED.  
* **ERR**: NO\_ROOM · FORBIDDEN · EXAM\_ENDED · ALREADY\_SUBMITTED

### 4E. Lịch sử & thống kê

#### HISTORY — ✚

* **Request**: HISTORY|token\[|filter\] — filter ∈ all|room|practice (mặc định all).  
* **OK**: OK|att|att|... với att \= att\_id:unix\_ts:mode:room\_name:score:n, mới nhất trước.  
  * mode ∈ room|practice.  
* **ERR**: NOT\_AUTHENTICATED

#### HISTORY\_DETAIL — ✚

* **Request**: HISTORY\_DETAIL|token|att\_id  
* **OK**: OK|detail|detail|... với detail \= qidx:chosen\_opt:correct\_opt:explanation  
  * chosen\_opt \= \-1 nếu bỏ trống. Cho phép hiển thị đáp án đúng \+ giải thích (bài đã kết thúc).  
* **ERR**: NOTFOUND · FORBIDDEN (att của người khác)

#### STATS — ✚

* **Request**: STATS|token → thống kê của chính mình; STATS|token|ALL → toàn hệ thống (**admin only**).  
* **OK cá nhân**: OK|attempts|avg\_score\_x100|easy\_correct|easy\_total|medium\_correct|medium\_total|hard\_correct|hard\_total|topic:correct/total,topic:correct/total,...  
  * avg\_score\_x100: điểm TB × 100 (tránh số thực).  
* **OK ALL**: OK|total\_attempts|avg\_score\_x100|easy\_correct|easy\_total|... (cùng format).  
* **ERR**: FORBIDDEN (ALL với non-admin) · BAD\_ARGS

### 4F. Admin — ngân hàng câu hỏi

#### LIST\_QUESTIONS — ✚ (admin)

* **Request**: LIST\_QUESTIONS|token  
* **OK**: OK|qrow|qrow|... với qrow \= qid:content:correct\_opt:difficulty:topic  
* **ERR**: FORBIDDEN

#### ADD\_QUESTION — ✚ (admin)

* **Request**: ADD\_QUESTION|token|content|optA|optB|optC|optD|correct|difficulty|topic|explanation  
  * correct ∈ 0..3; mọi field text escape %7C/%0A; explanation có thể rỗng.  
* **OK**: OK|qid — append questions.csv.  
* **ERR**: FORBIDDEN · BAD\_ARGS (field rỗng, correct ∉ \[0,3\], difficulty sai)

#### DEL\_QUESTION — ✚ (admin)

* **Request**: DEL\_QUESTION|token|qid  
* **OK**: OK — xóa khỏi questions.csv (ghi đè file). Câu đã phát trong đề cũ vẫn giữ snapshot.  
* **ERR**: FORBIDDEN · NOTFOUND

#### IMPORT\_CSV — ✚ (admin)

* **Request**: IMPORT\_CSV|token|path — path là đường dẫn file **trên máy server** (WSL2), format mỗi dòng: content;optA;optB;optC;optD;correct;difficulty;topic;explanation.  
* **OK**: OK|count — số dòng import thành công; dòng lỗi bỏ qua và log.  
* **ERR**: FORBIDDEN · NOTFOUND (file không tồn tại) · BAD\_ARGS (file sai format toàn bộ)

---

## 5\. Bảng EVT (server push — không theo request)

| EVT | Payload | Gửi tới | Phát khi |
| :---- | :---- | :---- | :---- |
| \`EVT | MEMBER\_JOINED | rid | username\` |
| \`EVT | MEMBER\_LEFT | rid | username\` |
| \`EVT | ROOM\_CLOSED | rid\` | rid |
| \`EVT | EXAM | rid | n |
| \`EVT | RESULT | rid | score/n |
| \`EVT | TICK | rid | giây\_còn\` |

**Quy tắc push**: ghi trực tiếp send\_frame vào fd của member đang online (session còn hiệu lực). Member offline không nhận — khi login lại dùng RESUME/ROOM\_RESULT để lấy lại trạng thái.

*(Hiện tại server chỉ có PUSH\_AUTO\_SUBMIT|room\_id|score|total → đổi thành EVT|RESULT; và chưa có broadcast EVT|EXAM/EVT|MEMBER\_\*.)*

## 6\. Bảng mã lỗi (ERR|code|mô tả)

| Code | Nghĩa | HTTP-tương-đương |
| :---- | :---- | :---- |
| BAD\_CREDENTIALS | sai username/password | 401 |
| USER\_EXISTS | username đã đăng ký | 409 |
| ALREADY\_LOGGED\_IN | tài khoản đang có session | 409 |
| NOT\_AUTHENTICATED | token sai/hết hạn | 401 |
| FORBIDDEN | đã login nhưng thiếu quyền (non-owner, non-admin, non-member) | 403 |
| BAD\_STATE | đúng quyền nhưng sai trạng thái (join phòng RUNNING, start phòng FINISHED, đang ở phòng khác...) | 409 |
| NO\_ROOM | room\_id không tồn tại | 404 |
| ROOM\_STARTED | phòng không còn WAITING (join) | 409 |
| ALREADY\_JOINED | đã là member phòng | 409 |
| ROOM\_FULL | phòng đủ MAX\_PARTICIPANTS | 409 |
| ROOM\_NOT\_FINISHED | lấy kết quả phòng chưa xong | 409 |
| EXAM\_ENDED | thao tác sau khi hết giờ/phòng đóng | 410 |
| ALREADY\_SUBMITTED | nộp/answer sau khi đã submitted | 409 |
| NOT\_ENOUGH\_QUESTIONS | ngân hàng thiếu câu theo cấu hình đề | 422 |
| NOTFOUND | đối tượng khác không tồn tại (qid, att\_id, file) | 404 |
| BAD\_ARGS | sai số field / field không hợp lệ | 400 |
| BADREQ | lệnh không tồn tại | 400 |
| INTERNAL | lỗi hệ thống | 500 |

**Mapping từ code hiện tại** (server.c dùng AUTH/PERM/NOTFOUND/STATE/DUP/BADREQ): AUTH→NOT\_AUTHENTICATED · PERM→FORBIDDEN · STATE→BAD\_STATE (chi tiết hoá thành ROOM\_STARTED, ALREADY\_JOINED... nơi client cần phân biệt) · DUP→USER\_EXISTS/ALREADY\_JOINED/ALREADY\_LOGGED\_IN · BADREQ giữ nguyên.

## 7\. Ví dụ frame raw

### PING → OK|PONG

→ 00 00 00 04 | 50 49 4E 47              ("PING")  
← 00 00 00 07 | 4F 4B 7C 50 4F 4E 47     ("OK|PONG")

### LOGIN|bob|secret123 → OK|\<token\>|user

→ 00 00 00 15 | "LOGIN|bob|secret123"          (21 byte)  
← 00 00 00 27 | "OK|a1b2...f9(32hex)|user"     (39 byte)

### JOIN|tok|r3 lúc phòng đã chạy

→ "JOIN|a1b2...f9|3"  
← "ERR|ROOM\_STARTED|phong da bat dau"

## 8\. Giới hạn hệ thống (đồng bộ common.h)

| Hằng | Giá trị | Ý nghĩa |
| :---- | :---- | :---- |
| MAX\_LINE | 1024 | payload tối đa 1 frame |
| MAX\_USERS | 100 | tài khoản tối đa |
| MAX\_CLIENTS | 50 | socket đồng thời |
| MAX\_ROOMS | 20 | phòng tồn tại |
| MAX\_PARTICIPANTS | 20 | thí sinh/phòng |
| MAX\_QROOM | 10 | câu/đề hiện tại — **cần nâng** nếu cho phép n=100 |
| TOKEN\_LEN | 33 | 32 hex \+ \\0 |

⚠ Lưu ý triển khai: với MAX\_LINE=1024, đề 10 câu dài có thể vượt → **nâng MAX\_LINE lên 8192** hoặc chia đề thành nhiều frame. Chốt: nâng lên **8192**, cập nhật cả client.

## 9\. Đối chiếu server.c hiện tại → spec mục tiêu

| server.c hiện tại | Spec mục tiêu | Việc phải làm |
| :---- | :---- | :---- |
| REGISTER → \`OK | dang ky thanh cong\` | \`OK |
| LOGIN → \`OK | token\` | \`OK |
| JOIN\_ROOM | JOIN | đổi tên \+ trả metadata \+ broadcast \`EVT |
| START\_EXAM | START\_ROOM | đổi tên \+ broadcast \`EVT |
| RESULT | ROOM\_RESULT | đổi tên \+ format entry rank:user:score:ts |
| PRACTICE\_START | PRACTICE | đổi tên \+ tham số difficulty/topic |
| PRACTICE\_ANSWER | ANSWER (dùng chung) | bỏ lệnh riêng |
| PUSH\_AUTO\_SUBMIT | \`EVT | RESULT\` |
| — | PING, RESUME, LEAVE\_ROOM, END\_ROOM, HISTORY, HISTORY\_DETAIL, STATS, LIST\_QUESTIONS, ADD\_QUESTION, DEL\_QUESTION, IMPORT\_CSV, \`EVT | MEMBER\_LEFT, EVT |
| \`ERR | AUTH/PERM/STATE/DUP\` | bảng mã mục 6 |
| users.txt plaintext | hash \+ role | đổi schema username:hash:role |

## 10\. Checklist parse phía client (Python)

def on\_frame(payload: str):  
    if payload.startswith("EVT|"):  route\_event(payload)  
    elif payload.startswith("OK|") or payload \== "OK": handle\_ok(payload)  
    elif payload.startswith("ERR|"):                   handle\_err(payload)  
    *\# field tách bằng '|' sau khi kiểm tra prefix;*  
    *\# nội dung text: unescape %7C \-\> '|', %0A \-\> '\\n' SAU KHI split*  
