# ĐẶC TẢ USE CASE & LUỒNG HOẠT ĐỘNG — Ứng dụng thi trắc nghiệm trực tuyến

Tài liệu thiết kế cho lập trình viên: use case của từng chức năng, luồng hoạt động, đầu vào/đầu ra ở mức message socket, biểu đồ use case / sequence / flow (Mermaid).

**Quyết định đã chốt**: framing length-prefix 4 byte; có role admin; GUI PyQt5; server chạy WSL2 Ubuntu, GUI chạy Windows.

---

## 1\. Actors (vai trò)

| Actor | Mô tả | Quyền |
| :---- | :---- | :---- |
| **Guest** | Client chưa đăng nhập | PING, REGISTER, LOGIN |
| **User** | Đã đăng nhập (role=user) | Luyện tập, tạo/tham gia/rời phòng, thi, xem kết quả, lịch sử, thống kê |
| **Host** | User đã tạo phòng (quyền theo đối tượng, chỉ với phòng của mình) | START\_ROOM, END\_ROOM |
| **Admin** | Đã đăng nhập (role=admin) | Toàn bộ quyền User \+ ADD\_QUESTION, DEL\_QUESTION, IMPORT\_CSV, xem stats toàn hệ thống |

Trạng thái session: CONNECTED → AUTHENTICATED → IN\_ROOM / IN\_PRACTICE / IN\_EXAM → AUTHENTICATED → đóng. Trạng thái phòng: WAITING → RUNNING → FINISHED. Trạng thái bài làm: IN\_PROGRESS → SUBMITTED.

---

## 2\. Giao thức tầng ứng dụng (chuẩn chung)

### 2.1. Framing (xử lý truyền dòng) — ĐÃ CHỐT

* \[4 byte độ dài payload, big-endian / network byte order\]\[payload: chuỗi text\]  
    
* send\_frame(sock, payload, len): ghi 4 byte htonl(len) rồi ghi đủ len byte (lặp send đến khi hết).  
* recv\_frame(sock, buf): lặp recv đến khi đủ 4 byte → ntohl ra len → lặp recv đến đủ len byte. len \> 4096 → lỗi.  
* Giải quyết "dính gói/xé gói" của TCP stream. Triển khai sẵn trong src/common.c (send\_frame, recv\_frame, read\_n\_bytes, write\_n\_bytes).

  ### 2.2. Cú pháp payload

* **Request**: CMD|arg1|arg2|... — tối đa 4096 byte.  
* **Response thành công**: OK|...  
* **Response lỗi**: ERR|\<ma\_loi\>|\<mo\_ta\>  
* **Sự kiện server chủ động đẩy (push)**: EVT|\<loai\>|... — client GUI dùng thread nghe socket nhận bất kỳ lúc nào.  
* Ký tự | trong nội dung: mã hóa %7C; xuống dòng: %0A.  
* Mọi lệnh cần đăng nhập đặt token ở arg1.

  ### 2.3. Bảng mã lỗi

BAD\_ARGS | UNKNOWN\_CMD | LINE\_TOO\_LONG | NOT\_AUTHENTICATED | FORBIDDEN | BAD\_STATE | USER\_EXISTS | BAD\_CREDENTIALS | ALREADY\_LOGGED\_IN | NO\_ROOM | ROOM\_STARTED | ALREADY\_JOINED | ROOM\_NOT\_FINISHED | EXAM\_ENDED | ALREADY\_SUBMITTED | NOT\_ENOUGH\_QUESTIONS | INTERNAL

---

## 3\. Biểu đồ Use Case tổng quan

* flowchart LR  
*     Guest(\[Guest\]) \--\> UC\_REG\[UC01 Đăng ký\]  
*     Guest \--\> UC\_LOGIN\[UC02 Đăng nhập\]  
*     Guest \--\> UC\_PING\[UC03 PING\]  
*   
*     User(\[User\]) \--\> UC\_PRAC\[UC10 Luyện tập\]  
*     User \--\> UC\_CREATE\[UC11 Tạo phòng thi\]  
*     User \--\> UC\_LIST\[UC12 Xem danh sách phòng\]  
*     User \--\> UC\_JOIN\[UC13 Tham gia / Rời phòng\]  
*     User \--\> UC\_ANS\[UC14 Trả lời / đổi đáp án\]  
*     User \--\> UC\_SUB\[UC15 Nộp bài sớm\]  
*     User \--\> UC\_RES\[UC16 Xem kết quả phòng\]  
*     User \--\> UC\_HIS\[UC17 Lịch sử & thống kê\]  
*     User \--\> UC\_OUT\[UC18 Đăng xuất\]  
*   
*     Host(\[Host \= User tạo phòng\]) \--\> UC\_START\[UC19 Bắt đầu thi\]  
*     Host \--\> UC\_END\[UC20 Kết thúc phòng sớm\]  
*     Host \-.kế thừa.-\> User  
*   
*     Admin(\[Admin\]) \--\> UC\_ADD\[UC21 Thêm câu hỏi\]  
*     Admin \--\> UC\_DEL\[UC22 Xóa câu hỏi\]  
*     Admin \--\> UC\_IMP\[UC23 Import CSV câu hỏi\]  
*     Admin \--\> UC\_STA\[UC24 Thống kê hệ thống\]  
*     Admin \-.kế thừa.-\> User  
*   
*     Server(\[Server tự động\]) \--\> UC\_TIME\[UC25 Hết giờ: tự nộp \+ broadcast kết quả\]  
    
  ---

  ## 4\. Đặc tả chi tiết từng Use Case

Ký hiệu đọc nhanh trong mọi UC:

* **Tiền ĐK** \= tiền điều kiện state của session/phòng lúc gọi lệnh.  
* **Luồng chính** đánh số bước: C\> client gửi, S\# bước server xử lý, S\> server trả/đẩy.  
* Cột **Lỗi** trong bảng field \= ERR trả nếu field vi phạm (kiểm theo thứ tự từ trên xuống).  
* t, tB, tH, tA \= token của user hiện tại, thí sinh B, host, admin.

  ## 4A. Nhóm Xác thực & Phiên

  ### UC01 — Đăng ký tài khoản

|  |  |
| :---- | :---- |
| **Actor** | Guest (session CONNECTED) |
| **Kích hoạt GUI** | S1 Login — nút ĐĂNG KÝ |
| **Tiền ĐK** | socket đã kết nối server |
| **Hậu ĐK** | user mới role=user được ghi users.txt; session vẫn CONNECTED (phải LOGIN riêng) |

**Input**: REGISTER|\<username\>|\<password\>

| Field | Ràng buộc | Lỗi |
| :---- | :---- | :---- |
| username | 3–20 ký tự \[a-zA-Z0-9\_\], duy nhất | BAD\_ARGS / USER\_EXISTS |
| password | ≥ 6 ký tự | BAD\_ARGS |

**Luồng chính**:

1. C\> REGISTER|alice|123456.  
2. S1 split\_fields → đúng 3 field → handle\_register.  
3. S2 Validate định dạng username/password (bảng trên).  
4. S3 Khóa g\_lock → quét danh sách user nạp từ users.txt.  
5. S4 Chưa trùng → sinh salt (8-16 hex ngẫu nhiên) → hash \= SHA256(salt \+ password) → append dòng alice:\<salt\>:\<hash\>:user.  
6. S\> OK|REGISTERED \+ log("REGISTER user=alice ok") (password che \*\*\*).

| Nhánh | Điều kiện | Kết quả |
| :---- | :---- | :---- |
| Lỗi tham số | thiếu field / username, password sai quy tắc | ERR|BAD\_ARGS|\<msg\> |
| Trùng tên | username đã có | ERR|USER\_EXISTS|username da ton tai |
| Lỗi IO | không ghi được users.txt | ERR|INTERNAL |

**EVT**: không. **Ghi dữ liệu**: users.txt. **Log**: REGISTER user=\<u\>.

---

### UC02 — Đăng nhập / quản lý phiên

|  |  |
| :---- | :---- |
| **Actor** | Guest |
| **Kích hoạt GUI** | S1 — nút ĐĂNG NHẬP |
| **Tiền ĐK** | session CONNECTED; user chưa login ở phiên khác |
| **Hậu ĐK** | session → AUTHENTICATED, ClientEntry{token, username, role}; GUI nhận token \+ role để phân quyền màn hình |

**Input**: LOGIN|\<username\>|\<password\>

**Luồng chính**:

1. C\> LOGIN|alice|123456.  
2. S1 Tra user theo username → salt → tính SHA256(salt+password) so với hash lưu.  
3. S2 Khớp → kiểm tra user chưa có session sống (g\_lock).  
4. S3 Sinh token 32-hex (rand()//dev/urandom), lưu ClientEntry{token, "alice", "user"}.  
5. S4 Quét attempts: nếu alice có bài IN\_PROGRESS trong phòng còn RUNNING → trả OK|\<token\>|user|RESUME|\<room\_id\>.  
6. S\> Ngược lại OK|\<token\>|user (admin → OK|\<token\>|admin).

| Nhánh | Điều kiện | Kết quả |
| :---- | :---- | :---- |
| Sai credential | username không tồn tại HOẶC hash không khớp | ERR|BAD\_CREDENTIALS (1 thông báo chung, không lộ sai field nào) |
| Đã login | user có session sống | ERR|ALREADY\_LOGGED\_IN |
| Resume | có attempt IN\_PROGRESS \+ phòng RUNNING | OK|token|role|RESUME|rid → GUI mở dialog vào lại phòng (xem UC05) |

**EVT**: không. **Ghi dữ liệu**: ClientEntry (RAM). **Log**: LOGIN user=\<u\> (che password). **Màn hình**: S1 → S2.

---

### UC03 — PING / kiểm tra kết nối

|  |  |
| :---- | :---- |
| **Actor** | Guest / bất kỳ |
| **Kích hoạt GUI** | S1 — nút Connect / auto trước LOGIN |

**Input → Output**: PING → OK|PONG. Không cần auth, không đổi state. GUI dùng để bật badge "● Đã kết nối" và chẩn đoán khi LOGIN timeout.

---

### UC04 — Kiểm soát quyền & trạng thái (cross-cutting, F06)

Không phải 1 lệnh — là **pipeline kiểm tra trong dispatcher** client\_thread, áp dụng trước mọi handler:

* recv\_frame → split\_fields  
*   1\. Lệnh có trong bảng CMD?        không → ERR|UNKNOWN\_CMD  
*   2\. Lệnh cần auth mà chưa login?   không → ERR|NOT\_AUTHENTICATED  
*   3\. Lệnh yêu cầu role cao hơn?     thiếu → ERR|FORBIDDEN  
*      (admin commands: ADD/DEL/IMPORT/LIST\_QUESTIONS, STATS|ALL;  
*       host commands: START/END\_ROOM — check owner trong handler)  
*   4\. Trạng thái session hợp lệ?     sai → ERR|BAD\_STATE  
*      (vd. ANSWER khi không IN\_EXAM, JOIN khi đang IN\_PRACTICE)  
*   5\. → handle\_\*()


Bảng quyền tối thiểu theo lệnh xem mục 10\. Mọi ERR đều đi kèm |mo\_ta và được log WARN kèm fd \+ user.

---

### UC05 — Kết nối lại bài thi (RESUME, nâng cao)

|  |  |
| :---- | :---- |
| **Actor** | User vừa login lại |
| **Kích hoạt GUI** | S1 nhận \`OK |
| **Tiền ĐK** | user có attempt IN\_PROGRESS thuộc phòng còn RUNNING |

**Input**: RESUME|\<token\>|\<room\_id\>

**Luồng chính**:

1. C\> RESUME|t|1.  
2. S1 Xác thực token \+ user là member có attempt IN\_PROGRESS của room 1\.  
3. S2 Tính giây\_còn \= end\_at \- now; giây\_còn \<= 0 → bài đã auto-submit → trả ERR|EXAM\_ENDED.  
4. S\> OK|\<n\>|\<giây\_còn\>|\<đề\>|\<ans\_mask: idx:opt,...\> — đề giống phát lúc start \+ các đáp án đã chọn.  
5. GUI S5 nạp lại đề, tô xanh ma trận theo ans\_mask, set countdown \= giây\_còn.

| Nhánh | Kết quả |
| :---- | :---- |
| Phòng đã FINISHED trong lúc offline | ERR|ROOM\_NOT\_FINISHED? — KHÔNG: trả ERR|EXAM\_ENDED, user tra điểm bằng ROOM\_RESULT |
| Không có attempt IN\_PROGRESS | ERR|BAD\_STATE |

**EVT**: không (kéo về bằng pull).

---

## 4B. Nhóm Luyện tập

### UC10 — Luyện tập một mình

|  |  |
| :---- | :---- |
| **Actor** | User (state AUTHENTICATED, không đang trong phòng/bài khác) |
| **Kích hoạt GUI** | S2 Dashboard — nút LUYỆN TẬP → form cấu hình |
| **Hậu ĐK** | Room đặc biệt owner=user, is\_practice=1 \+ attempt IN\_PROGRESS; session → IN\_PRACTICE |

**Input**: PRACTICE|\<token\>|\<n\>|\<giay\>|\<do\_kho\>|\<chu\_de\>

| Field | Ràng buộc | Lỗi |
| :---- | :---- | :---- |
| n | 1 ≤ n ≤ 100 và ≤ số câu phù hợp filter | BAD\_ARGS / NOT\_ENOUGH\_QUESTIONS |
| giay | \> 0 | BAD\_ARGS |
| do\_kho | easy|medium|hard|mixed | BAD\_ARGS |
| chu\_de | all hoặc tên topic có trong qbank | BAD\_ARGS |

**Luồng chính**:

1. C\> PRACTICE|t|5|300|mixed|all.  
2. S1 Auth \+ state OK → handle\_practice.  
3. S2 Picker: lọc qbank theo do\_kho/chu\_de → xáo trộn → lấy n câu không trùng.  
4. S3 Tạo room practice (không hiện trong LIST\_ROOMS), ghi question\_ids, end\_at \= now \+ giay, attempt IN\_PROGRESS.  
5. S\> OK|PRACTICE|\<rid\>|\<n\>|\<giay\>|\<qid:content:o0:o1:o2:o3|...\> — **không kèm đáp án đúng**.  
6. Trong bài: ANSWER (xem UC14) — ghi đè đến khi now ≤ end\_at.  
7. Nộp: PRACTICE\_SUBMIT|t|\<rid\> → chấm → S\> OK|\<đúng\>|\<n\> (+ tùy chọn |qid:correct:expl|...).  
8. Hết giờ không nộp → auto-submit (UC25) → EVT|RESULT|\<rid\>|\<đúng\>/\<n\>|- → ghi exam\_history.csv mode=practice.

| Nhánh | Kết quả |
| :---- | :---- |
| Đang trong phòng thi / bài khác gọi PRACTICE | ERR|BAD\_STATE |
| idx/opt sai khi ANSWER | ERR|BAD\_ARGS hoặc ERR|NOTFOUND |
| ANSWER sau end\_at | ERR|EXAM\_ENDED |

**EVT**: EVT|RESULT khi hết giờ. **Ghi dữ liệu**: exam\_history.csv. **Màn hình**: S2 → S5 → S6 (ẩn bảng xếp hạng).

---

## 4C. Nhóm Phòng thi

### UC11 — Tạo phòng thi (trở thành Host)

|  |  |
| :---- | :---- |
| **Actor** | User → trở thành Host của phòng vừa tạo |
| **Kích hoạt GUI** | S3 Lobby — nút \+ TẠO PHÒNG MỚI → dialog |
| **Hậu ĐK** | Room mới WAITING, owner là member đầu tiên; session owner → IN\_ROOM; GUI → S4 (view Host) |

**Input**: CREATE\_ROOM|\<token\>|\<ten\>|\<n\>|\<giay\>|\<easy:a,medium:b,hard:c\>|\<chu\_de\>

* Ví dụ: CREATE\_ROOM|t|Thi%20giua%20ky|20|1800|easy:5,medium:10,hard:5|all (tên có space → encode %20 hoặc chuẩn %7C/%0A cho ký tự đặc biệt).

| Field | Ràng buộc | Lỗi |
| :---- | :---- | :---- |
| ten | 1–50 ký tự | BAD\_ARGS |
| n | 1–100 | BAD\_ARGS |
| giay | 60–14400 | BAD\_ARGS |
| cấu hình độ khó | a+b+c \== n | BAD\_ARGS |
| chu\_de | all hoặc topic hợp lệ | BAD\_ARGS |
| qbank | đủ câu từng mức theo topic | NOT\_ENOUGH\_QUESTIONS |

**Luồng chính**:

1. C\> CREATE\_ROOM|t|Thi giua ky|20|1800|easy:5,medium:10,hard:5|all.  
2. S1 Auth \+ user không ở phòng nào → handle\_create\_room.  
3. S2 Validate toàn bộ field; kiểm tra user không đang IN\_EXAM/IN\_PRACTICE.  
4. S3 g\_lock: cấp id tăng dần → khởi tạo Room{id, name, owner, WAITING, cfg\_n, cfg\_giay, cfg\_ratio, cfg\_topic, participants=\[owner\]}.  
5. S\> OK|\<rid\> → GUI tự chuyển S4 Host view.

**EVT**: không (phòng chưa có ai để push). **Màn hình**: S3 → S4.

---

### UC12 — Xem danh sách phòng

|  |  |
| :---- | :---- |
| **Actor** | User |
| **Kích hoạt GUI** | S3 Lobby — load trang \+ nút Làm mới \+ QTimer 5s |

**Input**: LIST\_ROOMS|\<token\>\[|\<filter\>\] — filter ∈ WAITING|RUNNING|FINISHED, mặc định tất cả.

**Luồng chính**:

1. C\> LIST\_ROOMS|t.  
2. S1 Auth → duyệt g\_rooms (bỏ practice room is\_practice=1 và used=0).  
3. S\> OK|\<r1\>|\<r2\>|..., mỗi \<r\> \= id:name:owner:status:n:giay:mem.  
   * Ví dụ: OK|1:Thi giua ky:bob:WAITING:20:1800:3|2:Luyen tap:ann:RUNNING:10:600:1  
4. GUI parse từng item → đổ vào bảng \+ tô màu StatusBadge.

**Output khi rỗng**: OK (không item). **EVT**: không.

---

### UC13 — Tham gia / rời phòng

#### UC13a — JOIN

|  |  |
| :---- | :---- |
| **Actor** | User (không trong phòng/bài nào) |
| **Kích hoạt GUI** | S3 — chọn dòng WAITING → THAM GIA |

**Input**: JOIN|\<token\>|\<room\_id\>

**Luồng chính**:

1. C\> JOIN|tB|1.  
2. S1 Tìm room 1: tồn tại? WAITING? chưa đầy? user chưa là member? user không ở room khác / đang thi?  
3. S2 g\_lock: thêm user vào participants, mem++.  
4. S\> Trả joiner OK|JOINED|1; **push** EVT|MEMBER\_JOINED|1|b tới mọi member online khác.  
5. GUI S4: joiner chuyển trang; các member còn lại append tên vào list realtime.

| Nhánh | Kết quả |
| :---- | :---- |
| room không tồn tại / used=0 | ERR|NO\_ROOM |
| room RUNNING/FINISHED | ERR|ROOM\_STARTED |
| đã là member | ERR|ALREADY\_JOINED |
| đang ở room/bài khác | ERR|BAD\_STATE |
| phòng đầy MAX\_PARTICIPANTS | ERR|BAD\_STATE (hoặc ROOM\_FULL) |

   #### UC13b — LEAVE\_ROOM

**Input**: LEAVE\_ROOM|\<token\>|\<room\_id\> — chỉ khi phòng WAITING.

| Trường hợp | Luồng | Kết quả |
| :---- | :---- | :---- |
| Member thường rời | xóa khỏi participants, mem-- | OK|LEFT (+ tùy chọn EVT|MEMBER\_LEFT cho phòng) |
| **Owner rời** | phòng bị HỦY (đã chốt) | OK|LEFT cho owner \+ EVT|ROOM\_CLOSED|1 cho member còn lại → GUI về S3 |
| Rời khi RUNNING | — | ERR|BAD\_STATE (đang thi không được rời — chờ nộp/hết giờ) |

**EVT**: EVT|MEMBER\_JOINED, EVT|ROOM\_CLOSED (và tùy chọn EVT|MEMBER\_LEFT). **Màn hình**: S3 ↔ S4.

---

## 4D. Nhóm Làm bài thi

### UC14 — Trả lời / đổi đáp án

|  |  |
| :---- | :---- |
| **Actor** | User trong phòng RUNNING, attempt IN\_PROGRESS |
| **Kích hoạt GUI** | S5 — chọn radio A–D (auto gửi) |

**Input**: ANSWER|\<token\>|\<room\_id\>|\<idx\>|\<opt\>

| Field | Ràng buộc | Lỗi |
| :---- | :---- | :---- |
| idx | 0 ≤ idx \< n của đề | NOTFOUND/BAD\_ARGS |
| opt | 0–3 | BAD\_ARGS |

**Luồng chính**:

1. C\> ANSWER|tB|1|0|3.  
2. S1 Auth → session IN\_EXAM, room 1 RUNNING, user là member, attempt IN\_PROGRESS, now ≤ end\_at.  
3. S2 g\_lock: answers\[idx\] \= opt (**ghi đè** — đổi bao nhiêu lần cũng được).  
4. S\> OK; GUI tô xanh nút câu idx.

| Nhánh | Kết quả |
| :---- | :---- |
| Đã SUBMIT | ERR|ALREADY\_SUBMITTED |
| now \> end\_at | ERR|EXAM\_ENDED → GUI khoá input, chờ EVT|RESULT |
| User không phải member | ERR|FORBIDDEN |

**EVT**: không. **Ghi dữ liệu**: participants\[\].answers\[\] (RAM). **Log**: ANSWER user=\<u\> room=\<r\> idx=\<i\> opt=\<o\>.

---

### UC15 — Nộp bài sớm

|  |  |
| :---- | :---- |
| **Actor** | User IN\_EXAM, attempt IN\_PROGRESS |
| **Kích hoạt GUI** | S5 — nút ⚑ NỘP BÀI SỚM \+ confirm dialog |

**Input**: SUBMIT|\<token\>|\<room\_id\>

**Luồng chính**:

1. C\> SUBMIT|tB|1.  
2. S1 Check attempt IN\_PROGRESS \+ room RUNNING.  
3. S2 grade\_participant: so answers\[\] với correct của đề → score.  
4. S3 submitted\_at \= now, submitted \= 1, ghi exam\_history.csv (mode=room, room\_name).  
5. S\> OK|\<đúng\>|\<n\> — **lộ điểm ngay** (đã chốt).  
6. S4 Nếu MỌI member submitted → kích UC20: phòng FINISHED \+ EVT|RESULT tới mọi member online.

| Nhánh | Kết quả |
| :---- | :---- |
| SUBMIT lần 2 | ERR|ALREADY\_SUBMITTED |
| Không trong bài | ERR|BAD\_STATE |

**EVT**: EVT|RESULT nếu phòng kết thúc sớm. **Màn hình**: S5 → S6.

---

### UC16 — Xem kết quả phòng

|  |  |
| :---- | :---- |
| **Actor** | User |
| **Kích hoạt GUI** | S3 — chọn phòng FINISHED → XEM KẾT QUẢ; hoặc S6 refresh |

**Input**: ROOM\_RESULT|\<token\>|\<room\_id\>

**Luồng chính**:

1. C\> ROOM\_RESULT|t|1.  
2. S1 Room tồn tại \+ status \== FINISHED → duyệt participants.  
3. S2 Sort: score giảm dần; đồng điểm → submitted\_at tăng dần (nộp sớm xếp trước).  
4. S\> OK|\<n\>|\<rank1:user:score:ts\>|\<rank2:user:score:ts\>|...  
   * Ví dụ: OK|10|1:bob:9:1729300000|2:alice:9:1729300040|3:lee:5:1729300099

| Nhánh | Kết quả |
| :---- | :---- |
| Phòng còn WAITING/RUNNING | ERR|ROOM\_NOT\_FINISHED |
| Phòng không tồn tại | ERR|NO\_ROOM |

**Màn hình**: S6 (bảng xếp hạng).

---

## 4E. Nhóm Lịch sử & Thống kê

### UC17 — Lịch sử & thống kê cá nhân

|  |  |
| :---- | :---- |
| **Actor** | User (chỉ dữ liệu của mình) |
| **Kích hoạt GUI** | S7 History — load trang / đổi tab / bấm Chi tiết |

**Inputs**:

* HISTORY|\<token\>\[|practice|room\]  
* HISTORY\_DETAIL|\<token\>|\<attempt\_id\>  
* STATS|\<token\>

**Luồng chính**:

1. C\> HISTORY|tB|room → S\> OK|\<ts,room,\<room\_name\>,\<score\>,\<n\>\>|... (mới nhất trước).  
2. C\> HISTORY\_DETAIL|tB|\<att\> → S\> OK|\<qid:chose:correct:expl\>|... → GUI dialog từng câu (xanh đúng/đỏ sai).  
3. C\> STATS|tB → server tổng hợp từ exam\_history.csv \+ qbank → OK|\<series...\> gồm:  
   * điểm theo thời gian (line chart), tỷ lệ đúng theo easy/medium/hard (bar),  
   * tỷ lệ đúng theo chủ đề (bar/pie), số bài theo chế độ practice/room.

| Nhánh | Kết quả |
| :---- | :---- |
| Chưa từng thi | OK rỗng → GUI hiển thị "Chưa có dữ liệu" |
| att không thuộc user | ERR|FORBIDDEN |

**Màn hình**: S7 (bảng \+ Matplotlib FigureCanvasQTAgg).

---

### UC18 — Đăng xuất

**Input**: LOGOUT|\<token\> → OK|BYE. Xóa ClientEntry, session → CONNECTED. Attempt IN\_PROGRESS **giữ nguyên** — vẫn auto-submit khi hết giờ; login lại được RESUME (UC05). GUI về S1.

---

## 4F. Nhóm Host điều khiển phòng

### UC19 — Bắt đầu thi

|  |  |
| :---- | :---- |
| **Actor** | Host — chỉ owner của phòng đó |
| **Kích hoạt GUI** | S4 Host view — nút ▶ BẮT ĐẦU THI |
| **Tiền ĐK** | room WAITING, ≥ 2 member, qbank đủ câu |

**Input**: START\_ROOM|\<token\>|\<room\_id\>

**Luồng chính**:

1. C\> START\_ROOM|tH|1.  
2. S1 Auth → user \== room.owner → room WAITING → mem ≥ 2.  
3. S2 g\_lock: picker ra đề CHUNG theo cfg\_ratio\+cfg\_topic → ghi question\_ids\[\].  
4. S3 Mỗi member → attempt IN\_PROGRESS, answers\[\] \= \-1; start\_at \= now, end\_at \= now \+ giay; status \= RUNNING.  
5. S4 Spawn room\_timer\_thread (UC25) với {room\_id, end\_at}.  
6. S\> Owner: OK|STARTED|\<n\>|\<giay\>|\<đề\>.  
7. S\> Mọi member online khác: EVT|EXAM|1|\<n\>|\<giay\>|\<đề\> — GUI thí sinh tự nhảy S4→S5.

| Nhánh | Kết quả |
| :---- | :---- |
| Không phải owner | ERR|FORBIDDEN |
| Phòng RUNNING/FINISHED | ERR|BAD\_STATE |
| Chỉ 1 member | ERR|BAD\_STATE (cần ≥ 2 — luyện tập dùng PRACTICE) |
| Đề không đủ câu | ERR|NOT\_ENOUGH\_QUESTIONS |

**EVT**: EVT|EXAM. **Màn hình**: S4 → S5 (cả host lẫn member).

---

### UC20 — Kết thúc phòng

|  |  |
| :---- | :---- |
| **Actor** | Host (END\_ROOM) hoặc tự động |
| **Kích hoạt GUI** | S4/S5 Host — nút ✖ KẾT THÚC PHÒNG |

**Input**: END\_ROOM|\<token\>|\<room\_id\>

**Luồng chính** (dùng chung cho 3 trigger: host bấm / hết giờ UC25 / mọi member đã nộp):

1. S1 Owner \+ room RUNNING → finalize\_room(r):  
   * Với mọi attempt IN\_PROGRESS: chấm điểm phần đã trả lời → submitted\_at → ghi history.  
2. S2 status \= FINISHED.  
3. S\> Requester (nếu là lệnh): OK|ENDED.  
4. S\> Mỗi member online: EVT|RESULT|\<rid\>|\<đúng\>/\<n\>|\<hạng\> — GUI → S6.  
5. S5 Log ROOM\_FINISHED room=\<id\>.

| Nhánh | Kết quả |
| :---- | :---- |
| Không phải owner / phòng không RUNNING | ERR|FORBIDDEN / ERR|BAD\_STATE |

   ---

   ## 4G. Nhóm Admin

   ### UC21 — Thêm câu hỏi

**Input**: ADD\_QUESTION|\<token\>|\<content\>|\<A\>|\<B\>|\<C\>|\<D\>|\<correct 0-3\>|\<difficulty\>|\<topic\>|\<explanation\>

* Ký tự |/xuống dòng trong nội dung → encode %7C/%0A.

**Luồng chính**:

1. C\> ADD\_QUESTION|tA|2+2=?|3|4|5|6|1|easy|toan|phep cong.  
2. S1 Role admin → validate: 11 field, correct ∈ 0-3, difficulty ∈ easy|medium|hard, content/4 options không rỗng.  
3. S2 g\_lock: cấp qid mới → append struct qbank \+ ghi 1 dòng vào questions.csv.  
4. S\> OK|\<qid\> → GUI S8 refresh bảng.

**Lỗi**: FORBIDDEN (không phải admin), BAD\_ARGS (sai field/format).

### UC22 — Xóa câu hỏi

DEL\_QUESTION|\<token\>|\<qid\> → tìm qid trong qbank → xóa khỏi RAM \+ ghi lại questions.csv → OK. qid không tồn tại → ERR|NOTFOUND. (Câu hỏi đã phát cho phòng đang chạy vẫn an toàn vì đề lưu bản sao question\_ids.)

### UC23 — Import CSV

IMPORT\_CSV|\<token\>|\<path\_trên\_server\> → đọc file theo schema content,A,B,C,D,correct,difficulty,topic,explanation → bỏ dòng lỗi (đếm skip) → OK|\<số câu import\>\[|\<số dòng lỗi\>\]. File không đọc được → ERR|BAD\_ARGS.

### UC24 — Thống kê toàn hệ thống

STATS|\<token\>|ALL (chỉ admin) → OK|\<tổng lượt thi\>:\<điểm TB\>:\<đúng% theo độ khó\>:\<đúng% theo chủ đề\> → GUI S8 vẽ.

---

## 4H. Tự động hóa server

### UC25 — Hết giờ tự động nộp

|  |  |
| :---- | :---- |
| **Actor** | Server (timer) |
| **Trigger** | now ≥ room.end\_at |

**Luồng chính** (room\_timer\_thread):

1. Thread sleep tới end\_at (hoặc vòng lặp kiểm tra mỗi giây, có flag finished để END\_ROOM dừng sớm).  
2. g\_lock: với mọi member submitted \== 0 → score \= grade(answers\[\]) → submitted=1 → save\_history → log AUTO\_SUBMIT user=\<u\> room=\<r\>.  
3. status \= FINISHED → push EVT|RESULT|\<rid\>|\<đúng\>/\<n\>|\<hạng\> tới mọi member online → log ROOM\_FINISHED.  
4. Member offline: bài đã chấm, xem lại bằng ROOM\_RESULT/HISTORY khi login lại.

**EVT**: EVT|RESULT; tùy chọn EVT|TICK|\<rid\>|\<giây\_còn\> mỗi 10–30s để GUI resync đồng hồ.

---

## 5\. Sequence diagram — Luồng thi đầy đủ (1 phòng)

* sequenceDiagram  
*     autonumber  
*     participant H as Host (GUI)  
*     participant S as Server C  
*     participant B as Thí sinh B (GUI)  
*   
*     H-\>\>S: LOGIN|host|pw  
*     S--\>\>H: OK|tokenH|user  
*     B-\>\>S: LOGIN|b|pw2  
*     S--\>\>B: OK|tokenB|user  
*   
*     H-\>\>S: CREATE\_ROOM|tokenH|Thi giua ky|3|120|easy:1,medium:1,hard:1|all  
*     S--\>\>H: OK|1   (phòng WAITING, host \= member \#1)  
*   
*     B-\>\>S: LIST\_ROOMS|tokenB  
*     S--\>\>B: OK|1:Thi giua ky:host:WAITING:3:120:1  
*     B-\>\>S: JOIN|tokenB|1  
*     S--\>\>B: OK|JOINED|1  
*     S--\>\>H: EVT|MEMBER\_JOINED|1|b  
*   
*     H-\>\>S: START\_ROOM|tokenH|1  
*     Note over S: phòng RUNNING, ra đề chung,\<br/\>tạo attempt, spawn timer  
*     S--\>\>H: OK|STARTED|đề  
*     S--\>\>B: EVT|EXAM|1|3|120|đề  
*   
*     par Làm bài  
*         H-\>\>S: ANSWER|tokenH|1|0|2  
*         S--\>\>H: OK  
*         B-\>\>S: ANSWER|tokenB|1|0|1  
*         S--\>\>B: OK  
*         B-\>\>S: ANSWER|tokenB|1|0|3  (đổi đáp án \- ghi đè)  
*         S--\>\>B: OK  
*     end  
*   
*     H-\>\>S: SUBMIT|tokenH|1  
*     S--\>\>H: OK|2|3   (điểm lộ ngay)  
*   
*     Note over S: hết 120s → auto-submit bài B,\<br/\>chấm điểm, phòng FINISHED  
*     S--\>\>B: EVT|RESULT|1|1/3|2  
*     S--\>\>H: EVT|RESULT|1|2/3|1  
*   
*     B-\>\>S: ROOM\_RESULT|tokenB|1  
*     S--\>\>B: OK|3|1:host:2:ts|2:b:1:ts


  ## 6\. Sequence diagram — Luyện tập

* sequenceDiagram  
*     participant U as User  
*     participant S as Server  
*     U-\>\>S: PRACTICE|token|5|300|mixed|all  
*     S--\>\>U: OK|PRACTICE|7|5|300|đề 5 câu  
*     loop mỗi câu  
*         U-\>\>S: ANSWER|token|7|idx|opt  
*         S--\>\>U: OK  
*     end  
*     U-\>\>S: PRACTICE\_SUBMIT|token|7  
*     S--\>\>U: OK|4|5 (+đáp án đúng)  
*     U-\>\>S: HISTORY|token  
*     S--\>\>U: OK|ts,practice,-,4,5|...  
*     U-\>\>S: STATS|token  
*     S--\>\>U: OK|...(dữ liệu đồ thị)


  ## 7\. Flowchart — Vòng đời 1 kết nối trên server

* flowchart TD  
*     A\[accept kết nối\] \--\> B\[Tạo ClientEntry \+ session CONNECTED\]  
*     B \--\> C\[recv\_frame: đọc 4-byte len \+ payload\]  
*     C \--\>|đóng/lỗi| Z\[Cleanup: hủy session, giữ attempt\]  
*     C \--\> D\[split\_fields theo ký tự '|'\]  
*     D \--\> E{Lệnh hợp lệ?}  
*     E \--\>|không| R1\[ERR UNKNOWN\_CMD\] \--\> C  
*     E \--\>|có| F{Cần login?}  
*     F \--\>|có, chưa auth| R2\[ERR NOT\_AUTHENTICATED\] \--\> C  
*     F \--\>|ok| G{Đủ role?\<br/\>admin/host?}  
*     G \--\>|không| R3\[ERR FORBIDDEN\] \--\> C  
*     G \--\>|ok| H{Trạng thái hợp lệ?}  
*     H \--\>|không| R4\[ERR BAD\_STATE\] \--\> C  
*     H \--\>|ok| I\[handle\_XXX với g\_lock\]  
*     I \--\> J\[send\_to\_client reply\]  
*     J \--\> C


  ## 8\. Flowchart — Trạng thái phòng thi

* stateDiagram-v2  
*     \[\*\] \--\> WAITING : CREATE\_ROOM  
*     WAITING \--\> WAITING : JOIN / LEAVE\_ROOM\<br/\>EVT MEMBER\_JOINED  
*     WAITING \--\> \[\*\] : Host LEAVE\_ROOM (hủy phòng)  
*     WAITING \--\> RUNNING : START\_ROOM (host)\<br/\>EVT EXAM \+ timer thread  
*     RUNNING \--\> RUNNING : ANSWER (ghi đè) / SUBMIT  
*     RUNNING \--\> FINISHED : hết giờ (timer) /\<br/\>tất cả SUBMIT / END\_ROOM  
*     FINISHED \--\> \[\*\] : ROOM\_RESULT xem lại


  ## 9\. Flowchart — Xử lý 1 câu hỏi trong màn hình thi (client GUI)

* flowchart TD  
*     A\[Nhận EVT EXAM / OK STARTED kèm đề\] \--\> B\[Parse đề: list câu hỏi\]  
*     B \--\> C\[Hiển thị câu 1 \+ start QTimer countdown\]  
*     C \--\> D{User chọn radio A-D?}  
*     D \--\>|có| E\[ANSWER token room idx opt\]  
*     E \--\> F{OK?}  
*     F \--\>|OK| G\[Tô xanh nút câu idx trong ma trận\]  
*     F \--\>|ERR EXAM\_ENDED| H\[Khoá input, chờ EVT RESULT\]  
*     G \--\> D  
*     D \--\>|Nộp bài sớm| I\[SUBMIT\] \--\> J\[Hiện OK đúng/n\]  
*     D \--\>|countdown \= 0 / nhận EVT RESULT| J  
*     J \--\> K\[Chuyển màn hình Result\]


  ## 9B. Sequence — Đăng ký / Đăng nhập / Đăng xuất

* sequenceDiagram  
*     participant C as Client (S1 Login)  
*     participant S as Server C  
*     participant F as users.txt  
*   
*     C-\>\>S: REGISTER|alice|123456  
*     S-\>\>F: append alice:salt:hash:user  
*     S--\>\>C: OK|REGISTERED  
*   
*     C-\>\>S: LOGIN|alice|123456  
*     S-\>\>F: đọc salt → SHA256(salt+pw)  
*     S--\>\>C: OK|token32|user   (hoặc ...|RESUME|rid)  
*   
*     C-\>\>S: LOGOUT|token  
*     S--\>\>C: OK|BYE  
*     Note over S: xóa ClientEntry;\<br/\>attempt IN\_PROGRESS giữ nguyên


  ## 9C. Sequence — JOIN \+ EVT MEMBER\_JOINED \+ ROOM\_CLOSED

* sequenceDiagram  
*     participant A as Host  
*     participant S as Server  
*     participant B as Thí sinh B  
*   
*     B-\>\>S: JOIN|tB|1  
*     S--\>\>B: OK|JOINED|1  
*     S--\>\>A: EVT|MEMBER\_JOINED|1|b  
*   
*     A-\>\>S: LEAVE\_ROOM|tA|1   (owner rời → hủy phòng)  
*     S--\>\>A: OK|LEFT  
*     S--\>\>B: EVT|ROOM\_CLOSED|1


  ## 9D. State — Vòng đời một bài làm (attempt)

* stateDiagram-v2  
*     \[\*\] \--\> IN\_PROGRESS : START\_ROOM / PRACTICE / RESUME  
*     IN\_PROGRESS \--\> IN\_PROGRESS : ANSWER (ghi đè đáp án)  
*     IN\_PROGRESS \--\> SUBMITTED : SUBMIT / PRACTICE\_SUBMIT (lộ điểm ngay)  
*     IN\_PROGRESS \--\> SUBMITTED : hết giờ → AUTO\_SUBMIT (EVT RESULT)  
*     SUBMITTED \--\> \[\*\] : ROOM\_RESULT / HISTORY xem lại


  ## 9E. Flow — Phía client GUI phân luồng message nhận được

* flowchart TD  
*     A\[NetThread: recv\_frame xong 1 frame\] \--\> B{payload bắt đầu bằng?}  
*     B \--\>|OK| C\[emit response(payload)\<br/\>→ màn hình đang chờ xử lý\]  
*     B \--\>|ERR| D\[emit response(payload)\<br/\>→ màn hình hiện lỗi\]  
*     B \--\>|EVT|E\[emit event(payload)\<br/\>→ MainWindow.route\_event\]  
*     E \--\> F{EVT type}  
*     F \--\>|MEMBER\_JOINED| G\[S4: append danh sách\]  
*     F \--\>|EXAM| H\[parse đề → goto S5\]  
*     F \--\>|RESULT| I\[S5: khoá input → popup → S6\]  
*     F \--\>|ROOM\_CLOSED| J\[S4: popup → về S3\]  
*     F \--\>|TICK| K\[S5: resync countdown\]


  ## 10\. Bảng tra nhanh: lệnh ↔ quyền ↔ module

| Lệnh | Quyền tối thiểu | Phản hồi | EVT kèm theo |
| :---- | :---- | :---- | :---- |
| PING | guest | OK|PONG | — |
| REGISTER|u|p | guest | OK|REGISTERED | — |
| LOGIN|u|p | guest | OK|token|role\[|RESUME|id\] | — |
| LOGOUT|token | user | OK|BYE | — |
| PRACTICE|token|n|s|d|t | user | OK|PRACTICE|rid|n|s|đề | EVT|RESULT khi hết giờ |
| CREATE\_ROOM|token|name|n|s|cfg|topic | user | OK|rid | — |
| LIST\_ROOMS|token\[|filter\] | user | OK|r1|r2|... | — |
| JOIN|token|rid | user | OK|JOINED|rid | EVT|MEMBER\_JOINED |
| LEAVE\_ROOM|token|rid | user | OK|LEFT | EVT|ROOM\_CLOSED nếu host rời |
| START\_ROOM|token|rid | **host** | OK|STARTED|đề | EVT|EXAM cho members |
| END\_ROOM|token|rid | **host** | OK|ENDED | EVT|RESULT |
| ANSWER|token|rid|idx|opt | user (đang thi) | OK | — |
| SUBMIT|token|rid | user (đang thi) | OK|đúng|n | EVT|RESULT nếu phòng xong sớm |
| ROOM\_RESULT|token|rid | user | OK|n|rank:user:đúng:ts|... | — |
| HISTORY|token\[|mode\] | user | OK|att1|att2|... | — |
| HISTORY\_DETAIL|token|att | user | OK|q:chose:correct:expl|... | — |
| STATS|token\[|ALL\] | user (ALL: admin) | OK|... | — |
| RESUME|token|rid | user | OK|đề|đáp án cũ|giây còn | — |
| ADD\_QUESTION|token|... | **admin** | OK|qid | — |
| DEL\_QUESTION|token|qid | **admin** | OK | — |
| IMPORT\_CSV|token|path | **admin** | OK|count | — |

  ## 11\. Dữ liệu lưu trữ (file)

| File | Schema | Ghi khi |
| :---- | :---- | :---- |
| users.txt | username:salt:hash:role | REGISTER |
| questions.csv | qid,content,A,B,C,D,correct,difficulty,topic,explanation | server khởi động (load), ADD/DEL/IMPORT (save) |
| exam\_history.csv | attempt\_id,username,mode,room\_id,room\_name,score,total,submitted\_at | SUBMIT / auto-submit |
| server.log | \`timestamp | LEVEL |

* 

