# KẾ HOẠCH KIỂM THỬ (TEST PLAN) — exam\_app

Mục tiêu: kiểm chứng từng chức năng trong 01\_USECASES\_FLOWS.md theo input/output ở mức message socket, đồng thời checklist kiểm thử GUI.

**Môi trường test**: server build make chạy trên WSL2 Ubuntu 127.0.0.1:5000; client test \= client CLI ./client hoặc script python gửi frame thủ công; GUI PyQt5 trên Windows kết nối vào IP WSL2.

**Ghi chú input**: mọi "Input" là payload text; trên dây truyền luôn kèm 4-byte length prefix (big-endian) trước payload — test công cụ phải đóng frame đúng send\_frame/recv\_frame.

**PASS** \= response đúng format \+ đúng nội dung \+ trạng thái server (log/CSV) khớp. **FAIL** \= sai mã lỗi, sai format, mất kết nối, treo.

---

## 1\. Test tiện ích & framing (F01)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-F01 | Nhiều lệnh dính gói (gửi 3 frame liền trong 1 lần write) | PING PING PING back-to-back | 3 × OK|PONG, đúng thứ tự |  |
| T-F02 | 1 lệnh bị xé gói (gửi payload chia 3 chunk, sleep 200ms) | LOGIN|alice|123456 cắt 3 | OK|\<token\>|user sau khi đủ frame |  |
| T-F03 | Payload lớn (đề 20 câu \~2-3KB) | START\_ROOM phòng 20 câu | Client nhận đủ OK|STARTED|... không cắt |  |
| T-F04 | Payload rỗng / lệnh trống | frame "" | bỏ qua, không crash |  |

## 2\. Xác thực & phân quyền (UC01-UC06, F03-F06)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-A01 | Đăng ký hợp lệ | REGISTER|alice|123456 | OK|REGISTERED; users.txt có alice:\<salt\>:\<hash\>:user (không plaintext) |  |
| T-A02 | Trùng username | REGISTER|alice|x lần 2 | ERR|USER\_EXISTS|... |  |
| T-A03 | Username quá ngắn / ký tự lạ | REGISTER|ab|123456 ; REGISTER|a b|123456 | ERR|BAD\_ARGS |  |
| T-A04 | Password \< 6 ký tự | REGISTER|bob|123 | ERR|BAD\_ARGS |  |
| T-A05 | Login đúng | LOGIN|alice|123456 | OK|\<32hex\>|user |  |
| T-A06 | Sai mật khẩu | LOGIN|alice|sai | ERR|BAD\_CREDENTIALS (không lộ sai field nào) |  |
| T-A07 | User không tồn tại | LOGIN|nobody|x | ERR|BAD\_CREDENTIALS |  |
| T-A08 | Login kép (cùng user, 2 kết nối) | conn1 login alice rồi conn2 LOGIN|alice|123456 | conn2: ERR|ALREADY\_LOGGED\_IN |  |
| T-A09 | Lệnh khi chưa login | LIST\_ROOMS|badtoken | ERR|NOT\_AUTHENTICATED |  |
| T-A10 | User gọi lệnh admin | ADD\_QUESTION|tokenUser|... | ERR|FORBIDDEN |  |
| T-A11 | User thường gọi START\_ROOM phòng người khác | START\_ROOM|tokenB|1 | ERR|FORBIDDEN |  |
| T-A12 | Lệnh không tồn tại | FOO|x | ERR|UNKNOWN\_CMD |  |
| T-A13 | LOGOUT rồi dùng lại token | LOGOUT|t → LIST\_ROOMS|t | OK|BYE rồi ERR|NOT\_AUTHENTICATED |  |
| T-A14 | PING | PING | OK|PONG |  |
| T-A15 | Log không chứa password | sau REGISTER/LOGIN xem server.log | password thay bằng \*\*\* |  |

## 3\. Ngân hàng câu hỏi & Admin (UC21-24, F17)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-Q01 | Server khởi động nạp questions.csv | khởi động server | log số câu nạp được; qbank dùng được |  |
| T-Q02 | Admin thêm câu hỏi | ADD\_QUESTION|tokenAdmin|Noi dung?|A|B|C|D|1|easy|net|giai thich | OK|\<qid\>; questions.csv có dòng mới |  |
| T-Q03 | Admin xóa câu hỏi | DEL\_QUESTION|tokenAdmin|\<qid\> | OK; qid biến mất khỏi qbank |  |
| T-Q04 | Import CSV | IMPORT\_CSV|tokenAdmin|/path/q.csv | OK|\<số câu\>; file lỗi → ERR|BAD\_ARGS |  |
| T-Q05 | Nội dung chứa | và xuống dòng | ADD\_QUESTION|t|2%7C2=?|...%0A... | decode đúng trong DB |  |
| T-Q06 | Thiếu câu cho mức khó | tạo phòng hard:10 khi chỉ có 3 câu hard | ERR|NOT\_ENOUGH\_QUESTIONS |  |
| T-Q07 | Admin xem stats toàn hệ thống | STATS|tokenAdmin|ALL | OK|... dữ liệu tổng hợp |  |

## 4\. Quản lý phòng (UC11-UC13, F08-F10)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-R01 | Tạo phòng hợp lệ | CREATE\_ROOM|t|Thi giua ky|3|120|easy:1,medium:1,hard:1|all | OK|\<rid\>; owner tự là member |  |
| T-R02 | Tỷ lệ độ khó không khớp n | CREATE\_ROOM|t|X|3|120|easy:1,medium:1,hard:1|all với n=3 nhưng 1+1+1=3 ✓; case sai: easy:2,medium:2,hard:2 (tổng 6 ≠ 3\) | ERR|BAD\_ARGS |  |
| T-R03 | Thời gian ngoài khoảng | giây \= 10 (\<60) hoặc 99999 | ERR|BAD\_ARGS |  |
| T-R04 | LIST\_ROOMS đủ field | LIST\_ROOMS|t | OK|rid:name:owner:WAITING:n:sec:mem |  |
| T-R05 | JOIN phòng WAITING | JOIN|tB|1 | OK|JOINED|1; client A nhận EVT|MEMBER\_JOINED|1|b |  |
| T-R06 | JOIN phòng RUNNING/FINISHED | sau khi start: JOIN|tC|1 | ERR|ROOM\_STARTED |  |
| T-R07 | JOIN lại phòng đã join | JOIN|tB|1 lần 2 | ERR|ALREADY\_JOINED |  |
| T-R08 | JOIN phòng không tồn tại | JOIN|t|999 | ERR|NO\_ROOM |  |
| T-R09 | Rời phòng khi WAITING | LEAVE\_ROOM|tB|1 | OK|LEFT |  |
| T-R10 | Chủ phòng rời → hủy phòng | LEAVE\_ROOM|tHost|1 | OK|LEFT; member nhận EVT|ROOM\_CLOSED|1; LIST\_ROOMS không còn phòng 1 |  |
| T-R11 | Rời phòng khi RUNNING | LEAVE\_ROOM|tB|1 lúc đang thi | ERR|BAD\_STATE |  |
| T-R12 | User đang ở phòng khác JOIN tiếp | B join phòng 1 rồi JOIN|tB|2 | ERR|BAD\_STATE |  |

## 5\. Luồng thi (UC14-UC16, UC19-20, F11-F16)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-E01 | Host start, cả phòng nhận đề | START\_ROOM|tH|1 | Host: OK|STARTED|đề; member B: EVT|EXAM|1|3|120|đề (cùng đề) |  |
| T-E02 | Đề không kèm đáp án đúng | kiểm tra chuỗi đề | chỉ có qid:content:opt0-3, không có field correct |  |
| T-E03 | Trả lời \+ đổi đáp án | ANSWER|tB|1|0|1 rồi ANSWER|tB|1|0|3 | 2 × OK; log ghi opt=1 rồi opt=3; chấm theo opt=3 |  |
| T-E04 | Trả lời idx ngoài đề | ANSWER|tB|1|99|0 | ERR|NOTFOUND (hoặc BAD\_ARGS) |  |
| T-E05 | Trả lời opt ≠ 0-3 | ANSWER|tB|1|0|7 | ERR|BAD\_ARGS |  |
| T-E06 | Nộp bài sớm → lộ điểm ngay | SUBMIT|tB|1 | OK|\<đúng\>|\<n\> |  |
| T-E07 | Nộp lần 2 | SUBMIT|tB|1 lần nữa | ERR|ALREADY\_SUBMITTED |  |
| T-E08 | ANSWER sau khi nộp | ANSWER sau SUBMIT | ERR|ALREADY\_SUBMITTED |  |
| T-E09 | Hết giờ auto-submit \+ EVT RESULT | trả lời vài câu, không nộp, chờ hết giờ | EVT|RESULT|1|x/n|hạng; log AUTO\_SUBMIT, ROOM\_FINISHED |  |
| T-E10 | Tất cả nộp sớm → phòng kết thúc sớm | cả 2 member SUBMIT trước giờ | phòng FINISHED ngay, EVT|RESULT cho cả hai |  |
| T-E11 | END\_ROOM của host giữa chừng | END\_ROOM|tH|1 lúc RUNNING | OK|ENDED; mọi bài dở được chấm; EVT|RESULT |  |
| T-E12 | ANSWER sau hết giờ | gửi ANSWER khi đã FINISHED | ERR|EXAM\_ENDED (hoặc BAD\_STATE) |  |
| T-E13 | ANSWER user không trong phòng | ANSWER|tC|1|0|0 | ERR|FORBIDDEN |  |
| T-E14 | ROOM\_RESULT xếp hạng | ROOM\_RESULT|t|1 | OK|n|rank1:user:score:ts|... điểm giảm dần, đồng điểm xét nộp sớm |  |
| T-E15 | ROOM\_RESULT phòng chưa xong | ROOM\_RESULT lúc RUNNING | ERR|ROOM\_NOT\_FINISHED |  |
| T-E16 | (Tùy chọn) EVT TICK | quan sát trong lúc thi | EVT|TICK|1|\<giây còn\> mỗi \~10-30s |  |

## 6\. Luyện tập (UC10, F07)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-P01 | Luyện tập hợp lệ | PRACTICE|t|5|300|mixed|all | OK|PRACTICE|rid|5|300|đề |  |
| T-P02 | Lọc theo độ khó | PRACTICE|t|3|120|hard|all | đề chỉ gồm câu difficulty=hard |  |
| T-P03 | Lọc theo chủ đề | PRACTICE|t|3|120|mixed|net | đề chỉ gồm topic=net |  |
| T-P04 | Không đủ câu | PRACTICE|t|50|60|hard|all | ERR|NOT\_ENOUGH\_QUESTIONS |  |
| T-P05 | Trả lời \+ nộp | ANSWER rồi PRACTICE\_SUBMIT|t|rid | OK|\<đúng\>|5 |  |
| T-P06 | Hết giờ tự chấm | không nộp, chờ | EVT|RESULT với điểm |  |
| T-P07 | Đang luyện tập gọi JOIN | JOIN|t|1 khi IN\_PRACTICE | ERR|BAD\_STATE |  |

## 7\. Lịch sử & thống kê (UC17, F18)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-H01 | HISTORY sau khi thi xong | HISTORY|tB | OK|ts,room,ThiGK,x,n|ts,practice,-,y,m |  |
| T-H02 | HISTORY lọc mode | HISTORY|tB|practice | chỉ bản ghi practice |  |
| T-H03 | HISTORY user khác không lộ | HISTORY|tB không chứa bài của A | chỉ dữ liệu của B |  |
| T-H04 | HISTORY\_DETAIL | HISTORY\_DETAIL|tB|\<att\> | OK|qid:chose:correct:expl|... |  |
| T-H05 | STATS dữ liệu đồ thị | STATS|tB | OK|... đủ: điểm theo thời gian, đúng theo độ khó, theo chủ đề, số bài theo chế độ |  |
| T-H06 | CSV ghi đủ schema | mở exam\_history.csv | attempt\_id,user,mode,room\_id,room\_name,score,total,submitted\_at |  |

## 8\. Kết nối lại (UC05, nâng cao)

| TC | Mục đích | Input | Output kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-C01 | Disconnect giữa bài thi, đáp án còn giữ | B đang thi (đã ANSWER 2 câu) → rớt mạng → LOGIN lại | OK|token|role|RESUME|1 |  |
| T-C02 | RESUME trả đề \+ đáp án cũ \+ giờ còn lại | RESUME|tB2|1 | OK|đề|đáp án đã chọn|\<giây còn\> |  |
| T-C03 | Phòng kết thúc trong lúc offline | offline quá hết giờ → login lại | ROOM\_RESULT xem được điểm |  |

## 9\. Tải & đồng thời

| TC | Mục đích | Cách test | Kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- | :---- |
| T-L01 | 10 client login đồng thời | script Python 10 thread gửi LOGIN cùng lúc | tất cả OK, token khác nhau |  |
| T-L02 | 2 user đăng ký cùng 1 username | 2 conn REGISTER dup đồng thời | 1 × OK, 1 × ERR|USER\_EXISTS |  |
| T-L03 | 20 user join cùng phòng tới ngưỡng | vòng lặp join | đúng MAX\_PARTICIPANTS, sau đó ERR |  |
| T-L04 | Timer nhiều phòng song song | 3 phòng RUNNING cùng lúc, duration khác nhau | mỗi phòng FINISHED đúng giờ của nó |  |

## 10\. Checklist kiểm thử GUI (PyQt5)

| TC | Điểm kiểm | Kỳ vọng | Kết quả |
| :---- | :---- | :---- | :---- |
| G-01 | Login lỗi | hiển thị "Sai tài khoản hoặc mật khẩu", không crash |  |
| G-02 | Điều hướng theo role | admin thấy tab Quản trị; user thường không thấy |  |
| G-03 | Lobby refresh | bảng phòng cập nhật trạng thái/màu đúng |  |
| G-04 | Waiting realtime | member mới join xuất hiện ngay không cần reload |  |
| G-05 | Nút host | chỉ owner thấy "BẮT ĐẦU THI"; thí sinh thấy "đang chờ..." |  |
| G-06 | EVT EXAM | thí sinh tự chuyển sang màn làm bài khi host start |  |
| G-07 | Ma trận câu | đổi màu xám→xanh khi chọn đáp án; click nhảy câu |  |
| G-08 | Đổi đáp án | chọn lại radio → server ghi đè (kiểm chứng bằng điểm cuối) |  |
| G-09 | Countdown | đếm ngược đúng; hết giờ khoá input \+ popup EVT RESULT |  |
| G-10 | Bảng xếp hạng | S6 hiển thị đúng thứ hạng/điểm |  |
| G-11 | Đồ thị lịch sử | line chart \+ bar/pie render đúng dữ liệu STATS |  |
| G-12 | Mất kết nối | banner lỗi \+ cho phép login lại/RESUME |  |
| G-13 | Admin CRUD | thêm/xóa/import câu hỏi phản ánh ngay trong bảng |  |
| G-14 | Không đơ UI | trong lúc chờ EVT, GUI vẫn thao tác được |  |

## 11\. Quy trình chạy test

*\# WSL2: build \+ chạy server*  
cd exam\_app && make && ./server

*\# Terminal khác (WSL2): test nhanh bằng client CLI*  
./client 127.0.0.1 5000  
*\# hoặc script gửi frame thủ công (python) cho EVT/multi-client*

*\# Windows: chạy GUI*  
cd gui && python main.py   *\# nhập IP của WSL2 (wsl hostname \-I) \+ port 5000*

* Mỗi TC ghi vào BAO\_CAO\_KE\_HOACH.md: input, output mong đợi, output thực tế, PASS/FAIL (theo quy ước mục 9 của đặc tả).  
* Regression: sau mỗi thay đổi server, chạy lại bộ TC cũ (13 TC hiện có \+ các TC mới ở file này).

