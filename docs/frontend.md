# THIẾT KẾ GIAO DIỆN (UI) — exam\_app GUI client (PyQt5)

Bố cục từng màn hình (wireframe), bản đồ điều hướng giữa các màn hình, ánh xạ widget → lệnh socket, hiển thị theo role (Guest/User/Host/Admin).

**Stack**: Python 3 \+ PyQt5 \+ Matplotlib (nhúng FigureCanvasQTAgg). Chạy trên Windows, kết nối TCP tới server C trên WSL2 Ubuntu. Protocol \+ I/O chi tiết xem 01\_USECASES\_FLOWS.md.

---

## 1\. Kiến trúc chung của app GUI

gui/  
├── main.py            \# QApplication, MainWindow(QStackedWidget), session {token, role, username}  
├── net.py             \# NetThread(QThread): recv\_frame liên tục  
│                      \#   signals: response(str)  — frame OK/ERR trả lời lệnh  
│                      \#            event(str)     — frame EVT|... từ server đẩy  
│                      \#   api: send(cmd) ghi send\_frame  
├── proto.py           \# build\_cmd(), parse(), escape %7C / %0A  
├── widgets.py         \# widget dùng chung: StatusBadge, QuestionMatrix, CountdownLabel  
└── screens/           \# S1..S8, mỗi file 1 class QWidget

* **Quy tắc thread**: chỉ NetThread đọc socket; cập nhật UI **chỉ** trong slot của signal (main thread). Gửi lệnh từ main thread qua net.send(cmd) — frame ghi tuần tự, không race với thread đọc.  
* **Điều hướng**: MainWindow giữ QStackedWidget; goto(name) đổi trang. Mỗi screen implement on\_enter() (nạp dữ liệu) và on\_leave() (dừng QTimer tạm, hủy pending).

### AppState — object dùng chung (inject vào mọi screen)

| Field | Kiểu | Set lúc | Dùng ở |
| :---- | :---- | :---- | :---- |
| token | str (32-hex) | LOGIN ok | mọi lệnh cần auth |
| username | str | LOGIN ok | header S2, so owner ở S4 |
| role | user/admin | LOGIN ok | ẩn/hiện nút Admin ở S2, guard S8 |
| room\_id | int / None | CREATE/JOIN ok | S4, S5, lệnh phòng |
| exam | {rid, n, sec, questions\[{qid,content,opts\[4\],difficulty}\], answers\[n\]=-1, mode: 'room'|'practice'} | OK STARTED / EVT EXAM / OK PRACTICE / OK RESUME | S5 |
| last\_result | {score, n, rank, board\[{rank,user,score,ts}\]} | OK SUBMIT / EVT RESULT / ROOM\_RESULT | S6 |

### Hợp đồng signal của NetThread

| Signal | Payload | Bắn khi | Ai connect |
| :---- | :---- | :---- | :---- |
| response(str) | nguyên payload OK|... / ERR|... | frame không bắt đầu EVT| | screen đang active — mỗi screen giữ pending\_cmd; chỉ xử lý response cho lệnh mình gửi |
| event(str) | nguyên payload EVT|... | frame EVT| | MainWindow.route\_event() → phân tới screen theo bảng mục 4 |
| disconnected() | — | recv trả 0 / socket lỗi | MainWindow → banner mất kết nối |

* **Quy tắc định tuyến response**: screen trước khi send gán self.pending\_cmd \= 'JOIN'; slot on\_response bỏ qua nếu không có pending (response của màn hình khác).

## 2\. Bản đồ điều hướng (navigation map)

stateDiagram-v2  
    \[\*\] \--\> S1\_Login  
    S1\_Login \--\> S2\_Dashboard : LOGIN ok (OK|token|role)  
    S2\_Dashboard \--\> S3\_Lobby : "Chế độ thi"  
    S2\_Dashboard \--\> S5\_Exam : "Luyện tập" (PRACTICE → nhận đề)  
    S2\_Dashboard \--\> S7\_History : "Lịch sử & thống kê"  
    S2\_Dashboard \--\> S8\_Admin : tab Admin (chỉ role=admin)  
    S3\_Lobby \--\> S4\_Waiting : JOIN / CREATE\_ROOM ok  
    S3\_Lobby \--\> S6\_Result : "Xem kết quả" (phòng FINISHED)  
    S4\_Waiting \--\> S3\_Lobby : LEAVE\_ROOM / EVT ROOM\_CLOSED  
    S4\_Waiting \--\> S5\_Exam : EVT EXAM (đề đến)  
    S5\_Exam \--\> S6\_Result : SUBMIT ok / EVT RESULT / hết giờ  
    S6\_Result \--\> S3\_Lobby : "Về sảnh"  
    S6\_Result \--\> S2\_Dashboard : "Về trang chủ"  
    S7\_History \--\> S2\_Dashboard : Back  
    S8\_Admin \--\> S2\_Dashboard : Back  
    S2\_Dashboard \--\> S1\_Login : LOGOUT

## 2B. Bảng điều hướng chi tiết

| Màn hình | Vào từ | Điều kiện / lệnh kích hoạt | Ra tới |
| :---- | :---- | :---- | :---- |
| **S1** Login | mở app, LOGOUT, mất kết nối | — | S2 (OK|token|role); S5 (RESUME) |
| **S2** Dashboard | LOGIN ok; Back từ S3/S7/S8; "về trang chủ" từ S6 | — | S3, S5 (PRACTICE ok), S7, S8 (admin), S1 (LOGOUT) |
| **S3** Lobby | S2 "Chế độ thi"; "về sảnh" từ S6; rời phòng từ S4 | LIST\_ROOMS khi on\_enter | S4 (OK|JOINED/OK|rid); S6 (ROOM\_RESULT ok); S2 |
| **S4** Waiting | S3 | OK|JOINED / OK|rid (create) | S5 (EVT|EXAM / OK|STARTED); S3 (OK|LEFT / EVT|ROOM\_CLOSED) |
| **S5** Exam | S4, S2 (practice), S1 (RESUME) | AppState.exam đã nạp | S6 (OK|đúng|n / EVT|RESULT / hết giờ) |
| **S6** Result | S5, S3 (xem kết quả) | AppState.last\_result hoặc ROOM\_RESULT ok | S3, S2 |
| **S7** History | S2 | HISTORY khi on\_enter | S2 |
| **S8** Admin | S2, chỉ role=admin | LIST\_QUESTIONS \+ STATS|t|ALL khi on\_enter | S2 |

---

## 3\. Đặc tả chi tiết từng màn hình

Cấu trúc mỗi màn hình: **Meta** (mục đích, điều kiện vào, lệnh gửi, EVT xử lý, ra tới) → **wireframe** → **bảng widget** → **luồng xử lý/validate** → **bảng xử lý response**.

### S1 — Login / Register (screens/login.py)

| Meta | Giá trị |
| :---- | :---- |
| **Mục đích** | Kết nối server, xác thực, nhận token\+role, phát hiện RESUME |
| **Điều kiện vào** | Mở app / sau LOGOUT / sau mất kết nối |
| **Lệnh gửi** | PING, LOGIN|u|p, REGISTER|u|p |
| **EVT xử lý** | không |
| **Ra tới** | S2 (LOGIN ok); dialog RESUME → goto(S5) |

\+----------------------------------------------------------+  
|            THI TRẮC NGHIỆM TRỰC TUYẾN                    |  
|                                                          |  
|   Server IP   \[ 127.0.0.1        \]   Port \[ 5000  \]      |  
|   \---------------------------------------------------    |  
|   Username    \[                    \]                     |  
|   Password    \[                    \]  (echo \= ●)         |  
|                                                          |  
|        \[   ĐĂNG NHẬP   \]      \[   ĐĂNG KÝ   \]            |  
|                                                          |  
|   Trạng thái: ● Đã kết nối / ○ Chưa kết nối              |  
|   (label lỗi: sai mật khẩu / không kết nối được...)      |  
\+----------------------------------------------------------+

#### Widget chi tiết

| ID | Loại | Nội dung / mặc định | Sự kiện → hành động |
| :---- | :---- | :---- | :---- |
| edIp | QLineEdit | 127.0.0.1 | — |
| edPort | QLineEdit | 5000, QIntValidator | — |
| edUser | QLineEdit | placeholder "Tên đăng nhập" | ReturnPressed → focus edPass |
| edPass | QLineEdit | EchoMode=Password | ReturnPressed → btnLogin.click() |
| btnLogin | QPushButton | "ĐĂNG NHẬP" | click → do\_login() |
| btnRegister | QPushButton | "ĐĂNG KÝ" | click → do\_register() |
| lblStatus | QLabel | "○ Chưa kết nối" đỏ / "● Đã kết nối" xanh | cập nhật sau connect \+ PING |
| lblError | QLabel | đỏ, ẩn mặc định | set text theo ERR code |

#### Luồng do\_login()

1. Validate: IP/port/user/pass rỗng → lblError (không gọi socket).  
2. Chưa kết nối → socket.connect(ip, port) \+ send("PING") chờ OK\\|PONG; lỗi → "Không kết nối được server".  
3. send("LOGIN|u|p") → chờ response.  
4. OK\\|token\\|role: lưu AppState → goto(S2).  
5. OK\\|token\\|role\\|RESUME\\|rid: QMessageBox.question "Bạn có bài thi chưa xong (phòng \#rid). Vào lại?" — Yes → RESUME\\|token\\|rid → goto(S5); No → goto(S2).

#### Xử lý response

| Response | UI |
| :---- | :---- |
| OK|PONG | badge xanh; nếu đang trong luồng login → gửi LOGIN |
| OK|REGISTERED | popup "Đăng ký thành công — hãy đăng nhập" |
| ERR|BAD\_CREDENTIALS | lblError "Sai tài khoản hoặc mật khẩu" |
| ERR|USER\_EXISTS | lblError "Tên đăng nhập đã tồn tại" |
| ERR|ALREADY\_LOGGED\_IN | lblError "Tài khoản đang đăng nhập ở nơi khác" |
| ERR|BAD\_ARGS | lblError "Username 3–20 ký tự \[a-zA-Z0-9\_\], password ≥ 6" |
| socket lỗi / timeout | lblError "Không kết nối được server" |

### S2 — Dashboard (screens/dashboard.py)

| Meta | Giá trị |
| :---- | :---- |
| **Mục đích** | Trang chủ sau login — chọn chế độ \+ trung tâm điều hướng |
| **Lệnh gửi** | PRACTICE (qua dialog), LOGOUT |
| **EVT xử lý** | EVT|RESULT → toast nhẹ (bài cũ vừa kết thúc) |
| **Ra tới** | S3 / S5 (practice) / S7 / S8 (admin) / S1 |

\+----------------------------------------------------------+  
|  Xin chào, \<username\>        role: \[user|admin\]  \[Đăng xuất\] |  
|----------------------------------------------------------|  
|                                                          |  
|   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      |  
|   │  CHẾ ĐỘ THI │  │  LUYỆN TẬP  │  │ LỊCH SỬ &   │      |  
|   │  (phòng)    │  │             │  │ THỐNG KÊ    │      |  
|   └─────────────┘  └─────────────┘  └─────────────┘      |  
|                                                          |  
|   ┌─────────────────────────────┐  ← chỉ role=admin      |  
|   │  QUẢN TRỊ (ADMIN)           │                        |  
|   └─────────────────────────────┘                        |  
\+----------------------------------------------------------+

#### Widget chi tiết

| ID | Loại | Hiển thị theo role | Sự kiện → hành động |
| :---- | :---- | :---- | :---- |
| lblUser | QLabel | "Xin chào, {username} — role: {role}" | — |
| btnExam | QPushButton lớn "CHẾ ĐỘ THI" | mọi role | goto(S3) |
| btnPractice | QPushButton "LUYỆN TẬP" | mọi role | mở dialog cấu hình (dưới) |
| btnHistory | QPushButton "LỊCH SỬ & THỐNG KÊ" | mọi role | goto(S7) |
| btnAdmin | QPushButton "QUẢN TRỊ (ADMIN)" | role=admin; user thường setVisible(False) | goto(S8) |
| btnLogout | QPushButton "Đăng xuất" | mọi role | confirm → LOGOUT|t → OK|BYE → clear AppState → goto(S1) |

#### Dialog "Luyện tập" (QDialog)

\+-------------------------------------------+  
|  LUYỆN TẬP                                |  
|  Số câu \[10\]   Thời gian (giây) \[600\]     |  
|  Độ khó  \[ mixed ▼ \]   Chủ đề \[ all ▼ \]   |  
|           \[  BẮT ĐẦU  \]    \[  HỦY  \]      |  
\+-------------------------------------------+

* **Validate client**: 1 ≤ n ≤ 100, giây \> 0 trước khi gửi PRACTICE\\|t\\|n\\|s\\|do\_kho\\|chu\_de.  
* OK\\|PRACTICE\\|rid\\|n\\|s\\|đề → AppState.exam{mode:'practice'} → goto(S5).  
* ERR\\|NOT\_ENOUGH\_QUESTIONS → "Ngân hàng không đủ câu theo bộ lọc"; ERR\\|BAD\_STATE → "Bạn đang ở phòng/bài khác".

### S3 — Lobby phòng thi (screens/lobby.py)

| Meta | Giá trị |
| :---- | :---- |
| **Mục đích** | Danh sách phòng (refresh 5s), join / tạo phòng / xem kết quả phòng cũ |
| **Nạp khi vào** | on\_enter: LIST\_ROOMS|t \+ start QTimer(5000) refresh; on\_leave: timer.stop() |
| **Lệnh gửi** | LIST\_ROOMS, JOIN, CREATE\_ROOM, ROOM\_RESULT |
| **EVT xử lý** | EVT|EXAM (phòng vừa join bắt đầu), EVT|ROOM\_CLOSED |
| **Ra tới** | S4 (JOIN/CREATE ok); S6 (ROOM\_RESULT ok); S2 |

\+------------------------------------------------------------------+  
|  \< Trang chủ |  SẢNH PHÒNG THI              \[Làm mới\]            |  
|------------------------------------------------------------------|  
|  Lọc: ( Tất cả v)   \[████████ table phòng ████████\]              |  
|  ┌────┬──────────────┬───────┬───────────┬───────┬──────┬──────┐ |  
|  │ ID │ Tên phòng    │ Chủ   │ Trạng thái│ Số câu│ Giây │ TV   │ |  
|  ├────┼──────────────┼───────┼───────────┼───────┼──────┼──────┤ |  
|  │ 1  │ Thi giua ky  │ bob   │ ●WAITING  │  20   │ 1800 │ 3    │ |  
|  │ 2  │ Luyen tap    │ ann   │ ●RUNNING  │  10   │ 600  │ 1    │ |  
|  │ 3  │ Cuoi ky      │ lee   │ ●FINISHED │  15   │ 900  │ 5    │ |  
|  └────┴──────────────┴───────┴───────────┴───────┴──────┴──────┘ |  
|                                                                  |  
|  \[ \+ TẠO PHÒNG MỚI \]   \[ THAM GIA \]   \[ XEM KẾT QUẢ \]           |  
\+------------------------------------------------------------------+

#### Widget chi tiết

| ID | Loại | Sự kiện → hành động |
| :---- | :---- | :---- |
| tblRooms | QTableWidget 7 cột (ID/Tên/Chủ/Trạng thái/Số câu/Giây/TV), SelectRows, read-only | selectionChanged → enable nút theo status dòng chọn |
| cmbFilter | QComboBox \[Tất cả/WAITING/RUNNING/FINISHED\] | currentIndexChanged → LIST\_ROOMS|t|filter |
| btnRefresh | QPushButton "Làm mới" | LIST\_ROOMS|t |
| btnCreate | QPushButton "+ TẠO PHÒNG MỚI" | mở dialog (dưới) |
| btnJoin | QPushButton "THAM GIA" — enable chỉ khi chọn dòng **WAITING** | JOIN|t|id |
| btnResult | QPushButton "XEM KẾT QUẢ" — enable chỉ khi chọn **FINISHED** | ROOM\_RESULT|t|id → AppState.last\_result → goto(S6) |
| btnBack | QPushButton "\< Trang chủ" | goto(S2) |

* **Màu StatusBadge**: WAITING=xanh lá, RUNNING=vàng, FINISHED=xám (item background).  
* Server không trả phòng practice → bảng chỉ có phòng thi thật.

#### Xử lý response

| Response | UI |
| :---- | :---- |
| OK|r1|r2... | parse item id:name:owner:status:n:s:mem → đổ bảng \+ badge màu |
| OK|JOINED|rid | AppState.room\_id=rid → goto(S4) |
| OK|n|board... (ROOM\_RESULT) | AppState.last\_result → goto(S6) |
| ERR|ROOM\_STARTED | "Phòng đã bắt đầu" \+ LIST\_ROOMS refresh |
| ERR|ALREADY\_JOINED / ERR|BAD\_STATE | "Bạn đang ở trong phòng/bài khác" |
| ERR|NO\_ROOM | "Phòng không tồn tại" \+ refresh |
| ERR|ROOM\_NOT\_FINISHED | "Phòng chưa kết thúc" |

#### Dialog "Tạo phòng mới" (QDialog)

\+----------------------------------------------+  
|  TẠO PHÒNG THI                               |  
|  Tên phòng   \[                           \]   |  
|  Số câu hỏi  \[ 20 \]   Thời gian (giây) \[1800\]|  
|  Tỷ lệ độ khó:  Dễ \[5\] TB \[10\] Khó \[5\]       |  
|                 (label: tổng phải \= số câu)   |  
|  Chủ đề      \[ all ▼ \]                       |  
|              \[  TẠO  \]      \[  HỦY  \]        |  
\+----------------------------------------------+

→ CREATE\_ROOM|token|ten|n|giay|easy:a,medium:b,hard:c|topic.

#### Validate phía client (dialog tạo phòng)

| Check | Thông báo |
| :---- | :---- |
| tên 1–50 ký tự | "Tên phòng 1–50 ký tự" |
| 1 ≤ n ≤ 100 | "Số câu 1–100" |
| 60 ≤ giây ≤ 14400 | "Thời gian 60–14400 giây" |
| a+b+c \== n (label live khi gõ) | "Tổng Dễ+TB+Khó phải \= số câu" |

**Thành công** OK\\|rid → AppState.room\_id=rid → goto(S4) view Host. ERR\\|NOT\_ENOUGH\_QUESTIONS → "Ngân hàng không đủ câu theo cấu hình".

### S4 — Phòng chờ (screens/waiting.py) — 2 view theo role

| Meta | Giá trị |
| :---- | :---- |
| **Mục đích** | Chờ host bắt đầu; member list realtime; host có nút điều khiển phòng |
| **Chọn view** | AppState.username \== room.owner → **Host view**; ngược lại → **Participant view** |
| **Lệnh gửi** | START\_ROOM (host), LEAVE\_ROOM |
| **EVT xử lý** | MEMBER\_JOINED, MEMBER\_LEFT, EXAM, ROOM\_CLOSED |
| **Ra tới** | S5 (đề đến); S3 (rời / phòng bị hủy) |

View THÍ SINH (participant)              View CHỦ PHÒNG (host)  
\+------------------------------+         \+------------------------------+  
|  Phòng \#1: Thi giua ky       |         |  Phòng \#1: Thi giua ky       |  
|  20 câu \- 30 phút \- Chủ: bob |         |  20 câu \- 30 phút \- Chủ: bạn |  
|  Độ khó: 5D/10TB/5K \- all    |         |  Độ khó: 5D/10TB/5K \- all    |  
|------------------------------|         |------------------------------|  
|  Thí sinh trong phòng (3):   |         |  Thí sinh trong phòng (3):   |  
|   • bob (chủ phòng)          |         |   • bạn (chủ phòng)          |  
|   • ann                      |         |   • ann                      |  
|   • lee          ← realtime  |         |   • lee          ← realtime  |  
|------------------------------|         |------------------------------|  
|  "Đang chờ chủ phòng         |         |  \[ ▶ BẮT ĐẦU THI \]          |  
|   bắt đầu bài thi..."        |         |  \[ ✖ HỦY PHÒNG \]            |  
|         \[ RỜI PHÒNG \]        |         |  \[ RỜI PHÒNG \]              |  
\+------------------------------+         \+------------------------------+

#### Widget chi tiết

| ID | Loại | Host | Participant | Sự kiện → hành động |
| :---- | :---- | :---- | :---- | :---- |
| lblInfo | QLabel | hiện | hiện | "Phòng \#rid: name — n câu — giây — chủ: owner — tỷ lệ độ khó" |
| lstMembers | QListWidget | hiện | hiện | EVT|MEMBER\_JOINED → addItem(u); EVT|MEMBER\_LEFT → xóa item |
| btnStart | QPushButton "▶ BẮT ĐẦU THI" | hiện | **ẩn** | START\_ROOM|t|rid → OK|STARTED|đề → AppState.exam → goto(S5) |
| btnCancel | QPushButton "✖ HỦY PHÒNG" | hiện | **ẩn** | confirm → LEAVE\_ROOM (owner rời \= hủy phòng) |
| btnLeave | QPushButton "RỜI PHÒNG" | hiện | hiện | confirm → LEAVE\_ROOM|t|rid → OK|LEFT → goto(S3) |
| lblWait | QLabel "Đang chờ chủ phòng bắt đầu bài thi..." | ẩn | hiện | — |

#### Xử lý response / EVT

| Message | UI |
| :---- | :---- |
| EVT|MEMBER\_JOINED|rid|u | append u (bỏ qua nếu rid ≠ AppState.room\_id) |
| EVT|EXAM|rid|n|s|đề | parse đề → AppState.exam{mode:'room'} → goto(S5) |
| EVT|ROOM\_CLOSED|rid | QMessageBox "Chủ phòng đã hủy phòng" → goto(S3) |
| ERR|FORBIDDEN (START) | "Chỉ chủ phòng được bắt đầu" |
| ERR|BAD\_STATE (START) | "Cần ít nhất 2 thí sinh" / "Phòng không còn ở trạng thái chờ" |
| ERR|NOT\_ENOUGH\_QUESTIONS (START) | "Ngân hàng thiếu câu hỏi cho đề" |

### S5 — Làm bài (screens/exam.py) — dùng chung Thi & Luyện tập

| Meta | Giá trị |
| :---- | :---- |
| **Nguồn đề** | OK|STARTED (host), EVT|EXAM (member), OK|PRACTICE, OK|RESUME — parse vào AppState.exam |
| **Lệnh gửi** | ANSWER mỗi lần chọn/đổi đáp án; SUBMIT hoặc PRACTICE\_SUBMIT khi nộp |
| **EVT xử lý** | EVT|RESULT, EVT|TICK |
| **Ra tới** | S6 |
| **Chặn thoát** | đóng app khi đang thi → confirm "Bài vẫn được chấm khi hết giờ — thoát?" |

\+--------------------------------------------------------------------+  
|  BÀI THI  |  ⏱ 00:24:31   |  Phòng \#1 \- Thi giua ky               |  
|--------------------------------------------------------------------|  
|  Ma trận câu hỏi:            |  Câu 3/20        Độ khó: Trung bình |  
|  \[1\]\[2\]\[3\]\[4\]\[5\]             |  \---------------------------------  |  
|  \[6\]\[7\]\[8\]\[9\]\[10\]            |  TCP dam bao dieu gi?               |  
|  \[11\]\[12\]\[13\]\[14\]\[15\]        |                                     |  
|  \[16\]\[17\]\[18\]\[19\]\[20\]        |  ( ) A. Toc do cao nhat             |  
|   xám=chưa làm  xanh=đã chọn |  (•) B. Tin cay, dung thu tu        |  
|   ● \= đang xem               |  ( ) C. Khong ket noi               |  
|                              |  ( ) D. Broadcast                   |  
|                              |                                     |  
|                              |      \[◀ Câu trước\] \[Câu sau ▶\]     |  
|--------------------------------------------------------------------|  
|  Đã làm: 12/20                            \[  ⚑ NỘP BÀI SỚM  \]     |  
\+--------------------------------------------------------------------+

#### Widget chi tiết

| ID | Loại | Hành vi |
| :---- | :---- | :---- |
| lblTitle | QLabel | "BÀI THI — Phòng \#rid name" hoặc "LUYỆN TẬP" |
| lblTimer | CountdownLabel \+ QTimer(1000) | remain \= sec (RESUME: giây\_còn); tick → remain-- hiển thị mm:ss; remain ≤ 30 → đỏ nhấp; remain \== 0 → lock\_inputs() chờ EVT|RESULT |
| matrix | QuestionMatrix (QGridLayout n QPushButton) | click nút i → show\_question(i); xám \= answers\[i\]==-1, xanh \= đã chọn, viền đậm \= đang xem; RESUME: tô xanh theo ans\_mask |
| lblQ | QLabel | "Câu i/n — Độ khó: {difficulty}" |
| txtContent | QLabel word-wrap | nội dung câu hỏi |
| rdoA–rdoD | 4 QRadioButton \+ QButtonGroup | toggled → gửi ngay ANSWER|t|rid|i|opt (ghi đè); set lại checked theo answers\[i\] khi đổi câu |
| btnPrev/btnNext | QPushButton | show\_question(i±1) |
| lblProgress | QLabel | "Đã làm: k/n" — cập nhật sau mỗi OK của ANSWER |
| btnSubmit | QPushButton "⚑ NỘP BÀI SỚM" | confirm "Còn n-k câu chưa làm. Nộp?" → SUBMIT (practice: PRACTICE\_SUBMIT) |
| lblErr | QLabel đỏ | ERR của ANSWER/SUBMIT |

#### Xử lý response / EVT

| Message | UI |
| :---- | :---- |
| OK (ANSWER) | tô xanh nút câu i; lblProgress k/n |
| ERR|EXAM\_ENDED | lock\_inputs() \+ lblErr "Đã hết giờ" |
| ERR|ALREADY\_SUBMITTED | lock\_inputs() |
| ERR|BAD\_ARGS/NOTFOUND | lblErr (không đổi ma trận) |
| OK|đúng|n (SUBMIT) | AppState.last\_result → goto(S6) |
| EVT|RESULT|rid|x/n|rank | lock\_inputs() → AppState.last\_result → goto(S6) — xảy ra khi hết giờ / host END\_ROOM / mọi người nộp xong |
| EVT|TICK|rid|sec | lblTimer.remain \= sec (resync) |
| disconnected() | banner \+ hướng login lại → RESUME |

#### lock\_inputs()

Disable radio group \+ btnSubmit (vẫn cho xem lại câu), hiện "Chờ kết quả...". Luyện tập: giống hệt, mode='practice' → S6 ẩn bảng xếp hạng.

### S6 — Kết quả (screens/result.py)

| Meta | Giá trị |
| :---- | :---- |
| **Nguồn dữ liệu** | AppState.last\_result (từ SUBMIT/EVT|RESULT); ROOM\_RESULT pull lại cho bảng đầy đủ |
| **Lệnh gửi** | ROOM\_RESULT|t|rid, HISTORY\_DETAIL (practice) |
| **EVT xử lý** | không |
| **Ra tới** | S3 / S2 |

\+----------------------------------------------------------+  
|  KẾT QUẢ — Phòng \#1: Thi giua ky                         |  
|----------------------------------------------------------|  
|            🏆  Điểm của bạn:  8 / 10                     |  
|----------------------------------------------------------|  
|  Bảng xếp hạng:                                          |  
|  ┌──────┬───────────┬────────┬──────────────┐            |  
|  │ Hạng │ Thí sinh  │ Đúng   │ Nộp lúc      │            |  
|  │  1   │ bob       │ 9/10   │ 18:02:11     │            |  
|  │  2   │ bạn       │ 8/10   │ 18:02:45     │            |  
|  │  3   │ lee       │ 5/10   │ (hết giờ)    │            |  
|  └──────┴───────────┴────────┴──────────────┘            |  
|        \[ VỀ SẢNH \]          \[ VỀ TRANG CHỦ \]             |  
\+----------------------------------------------------------+

#### Widget chi tiết

| ID | Loại | Hành vi |
| :---- | :---- | :---- |
| lblScore | QLabel lớn | "🏆 Điểm của bạn: x/n" (+ "Hạng k" nếu có) |
| tblRank | QTableWidget (Hạng/Thí sinh/Đúng/Nộp lúc) | đổ board\[\]; tô vàng dòng của mình; mode=practice → setVisible(False) |
| btnDetail | QPushButton "Xem đáp án \+ giải thích" | chỉ practice → HISTORY\_DETAIL|t|att → dialog từng câu (xanh đúng / đỏ sai \+ explanation) |
| btnLobby | QPushButton "VỀ SẢNH" | goto(S3) |
| btnHome | QPushButton "VỀ TRANG CHỦ" | goto(S2) |

* Vào từ S3 "XEM KẾT QUẢ" (xem phòng cũ): ROOM\_RESULT đổ thẳng tblRank; lblScore hiện hạng của mình trong board.

### S7 — Lịch sử & thống kê (screens/history.py)

| Meta | Giá trị |
| :---- | :---- |
| **Nạp khi vào** | HISTORY|t đổ bảng tab 1 |
| **Lệnh gửi** | HISTORY, HISTORY\_DETAIL, STATS |
| **EVT xử lý** | không |
| **Ra tới** | S2 |

\+--------------------------------------------------------------------+  
| \< Trang chủ |  LỊCH SỬ & THỐNG KÊ                                  |  
|--------------------------------------------------------------------|  
| ┌ Tab: Lịch sử ────────────┬ Tab: Đồ thị ──────────────────────┐   |  
| │ Bảng:                    │  ┌─────────────────────────────┐  │   |  
| │ ngày | chế độ | phòng    │  │  Line chart: điểm theo      │  │   |  
| │      | đúng/n  | \[xem\]   │  │  thời gian (Matplotlib)     │  │   |  
| │ 18/10| thi    | ThiGK    │  ├─────────────────────────────┤  │   |  
| │      | 8/10   | \[chi tiết│  │  Bar/Pie: tỷ lệ đúng theo   │  │   |  
| │      |        | →dialog\] │  │  độ khó & chủ đề            │  │   |  
| │                          │  └─────────────────────────────┘  │   |  
| └──────────────────────────┴──────────────────────────────────┘   |  
\+--------------------------------------------------------------------+

#### Tab "Lịch sử"

| ID | Loại | Hành vi |
| :---- | :---- | :---- |
| tblHist | QTableWidget (Ngày/Chế độ/Phòng/Đúng-n/\[Chi tiết\]) | đổ từ OK|\<ts,mode,room\_name,score,n\>|...; mới nhất trên đầu |
| cmbMode | QComboBox \[Tất cả/Thi phòng/Luyện tập\] | → HISTORY|t / |room / |practice |
| nút "Chi tiết" mỗi dòng | QPushButton trong cell | → HISTORY\_DETAIL|t|att → dialog |
| Dialog chi tiết | QTableWidget (Câu/Bạn chọn/Đáp án đúng/Giải thích) | dòng đúng: xanh lá; sai: đỏ |

#### Tab "Đồ thị" (Matplotlib FigureCanvasQTAgg)

| Chart | Dữ liệu từ STATS|t | Loại |
| :---- | :---- | :---- |
| Điểm theo thời gian | series (ts, score/n) | line |
| Tỷ lệ đúng theo độ khó | easy/medium/hard % | bar |
| Tỷ lệ đúng theo chủ đề | topic % | bar/pie |
| Số bài theo chế độ | practice vs room | pie |

* OK rỗng → label "Chưa có dữ liệu — hãy làm bài đầu tiên\!".

### S8 — Tab Admin (screens/admin.py) — chỉ role=admin

| Meta | Giá trị |
| :---- | :---- |
| **Điều kiện vào** | AppState.role \== 'admin' — nút ẩn ở S2 với user; truy cập trực tiếp → về S2 |
| **Nạp khi vào** | LIST\_QUESTIONS|t \+ STATS|t|ALL |
| **Lệnh gửi** | LIST\_QUESTIONS, ADD\_QUESTION, DEL\_QUESTION, IMPORT\_CSV, STATS|t|ALL |
| **EVT xử lý** | không |
| **Ra tới** | S2 |

\+--------------------------------------------------------------------+  
| \< Trang chủ |  QUẢN TRỊ — NGÂN HÀNG CÂU HỎI                        |  
|--------------------------------------------------------------------|  
|  \[+ Thêm câu hỏi\] \[Xóa đã chọn\] \[Import CSV\]   Lọc độ khó: \[all ▼\] |  
| ┌────┬───────────────────────┬──────┬────────┬──────────┬────────┐ |  
| │ ID │ Nội dung              │ Đ.án │ Độ khó │ Chủ đề   │        │ |  
| │ 1  │ 2 \+ 2 \= ?             │  B   │ easy   │ toan     │        │ |  
| └────┴───────────────────────┴──────┴────────┴──────────┴────────┘ |  
|  ── Form thêm (dialog): nội dung | A|B|C|D | đáp án | độ khó |     |  
|     chủ đề | giải thích        → ADD\_QUESTION|token|...            |  
|--------------------------------------------------------------------|  
|  THỐNG KÊ HỆ THỐNG (STATS|token|ALL): tổng lượt thi, điểm TB,      |  
|  biểu đồ tỷ lệ đúng theo độ khó toàn hệ thống                      |  
\+--------------------------------------------------------------------+

#### Widget chi tiết

| ID | Loại | Hành vi |
| :---- | :---- | :---- |
| tblQ | QTableWidget (ID/Nội dung/Đ.án/Độ khó/Chủ đề) | đổ từ OK|qid:content:correct:diff:topic|... của LIST\_QUESTIONS |
| btnAdd | QPushButton "＋ Thêm câu hỏi" | dialog form (dưới) → ADD\_QUESTION → refresh bảng |
| btnDel | QPushButton "Xóa đã chọn" (enable khi chọn dòng) | confirm → DEL\_QUESTION|t|qid → refresh |
| btnImport | QPushButton "Import CSV" | QLineEdit path trên server → IMPORT\_CSV|t|path → OK|count |
| cmbDiff | QComboBox lọc độ khó | lọc client-side trên tblQ |
| chartSys | FigureCanvasQTAgg | STATS|t|ALL → bar tỷ lệ đúng theo độ khó toàn hệ thống \+ text "Tổng lượt thi / điểm TB" |

#### Dialog "Thêm câu hỏi" — validate client

| Field | Check trước khi gửi |
| :---- | :---- |
| Nội dung \+ 4 đáp án A–D | không rỗng |
| Đáp án đúng | radio A–D bắt buộc chọn → map 0-3 |
| Độ khó | QComboBox easy/medium/hard |
| Chủ đề | QComboBox topic có sẵn \+ nhập mới |
| Giải thích | có thể rỗng |

→ ADD\_QUESTION\\|t\\|content\\|A\\|B\\|C\\|D\\|correct\\|diff\\|topic\\|expl — escape %7C/%0A trong text.

#### Xử lý response

| Response | UI |
| :---- | :---- |
| OK|qid | refresh tblQ \+ toast "Đã thêm câu \#qid" |
| OK (DEL) | xóa dòng khỏi bảng |
| OK|count (IMPORT) | "Đã import count câu" \+ refresh |
| ERR|FORBIDDEN | "Không đủ quyền" |
| ERR|BAD\_ARGS / ERR|NOTFOUND | hiện mô tả lỗi từ server |

* Cần thêm lệnh LIST\_QUESTIONS\\|token (admin) — *bổ sung vào protocol khi code*.

---

## 4\. Ánh xạ sự kiện server (EVT) → hành động UI

| EVT | Parse | Trang đang đứng | Hành động UI | Server phát khi |
| :---- | :---- | :---- | :---- | :---- |
| EVT|MEMBER\_JOINED|rid|user | rid, user | S4 (cùng rid) | append user vào lstMembers | user khác JOIN |
| EVT|MEMBER\_LEFT|rid|user | rid, user | S4 | xóa khỏi list | member LEAVE\_ROOM (tùy chọn) |
| EVT|EXAM|rid|n|s|đề | rid, n, s, list câu | S4 | parse đề → AppState.exam{mode:'room'} → goto(S5) \+ start countdown | host START\_ROOM |
| EVT|RESULT|rid|x/n|rank | rid, x, n, rank | S5 | lock\_inputs() → AppState.last\_result → goto(S6) | hết giờ / END\_ROOM / mọi người nộp |
| EVT|RESULT|rid|x/n|rank | rid, x, n, rank | S2/S3/S7/S8 | toast "Phòng \#rid kết thúc — điểm x/n" | (như trên) |
| EVT|ROOM\_CLOSED|rid | rid | S4 | QMessageBox "Chủ phòng đã hủy phòng" → goto(S3) | owner LEAVE\_ROOM |
| EVT|TICK|rid|sec | rid, sec | S5 | lblTimer.remain \= sec | server định kỳ (tùy chọn) |

* **Quy tắc lọc rid**: EVT mang rid ≠ AppState.room\_id → chỉ toast, không đổi màn hình.  
* **EVT đến lúc đang ở S1** (chưa login): queue lại — sau LOGIN thành công, route\_event phát lại.

## 5\. Quy ước hiển thị lỗi

* **ERR sau hành động nút** → lblErr đỏ ngay dưới nút vừa bấm; lỗi nghiêm trọng/hệ thống → QMessageBox.warning.

### Bảng mapping ERR|code → thông báo người dùng

| Code | Thông báo |
| :---- | :---- |
| BAD\_CREDENTIALS | Sai tài khoản hoặc mật khẩu |
| USER\_EXISTS | Tên đăng nhập đã tồn tại |
| ALREADY\_LOGGED\_IN | Tài khoản đang đăng nhập ở nơi khác |
| NOT\_AUTHENTICATED | Phiên hết hạn — đăng nhập lại → goto(S1) |
| FORBIDDEN | Bạn không đủ quyền thực hiện thao tác này |
| BAD\_STATE | Thao tác không hợp lệ ở trạng thái hiện tại |
| NO\_ROOM | Phòng không tồn tại |
| ROOM\_STARTED | Phòng đã bắt đầu |
| ALREADY\_JOINED | Bạn đã ở trong phòng này |
| ROOM\_NOT\_FINISHED | Phòng chưa kết thúc — chưa có kết quả |
| EXAM\_ENDED | Đã hết giờ làm bài |
| ALREADY\_SUBMITTED | Bài đã được nộp |
| NOT\_ENOUGH\_QUESTIONS | Ngân hàng không đủ câu hỏi theo cấu hình |
| BAD\_ARGS | Dữ liệu nhập không hợp lệ (kèm mô tả server) |
| INTERNAL | Lỗi hệ thống — thử lại sau |

* **Mất kết nối** (disconnected()): banner đỏ full-width "Mất kết nối tới server" \+ nút Kết nối lại → goto(S1) → login lại → RESUME nếu đang thi (UC05).  
* **Chống đơ UI**: gửi lệnh → btn.setEnabled(False) \+ WaitCursor tới khi response về; timeout 5s → "Server không phản hồi".  
* **Toast** cho EVT không chặn màn hình: QToolTip.showText/QSystemTrayIcon.showMessage — không dùng modal.

