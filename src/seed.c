#include "seed.h"

const seed_question_t SEED_QUESTIONS[] = {
    { "TCP hoạt động ở tầng nào của mô hình OSI?", { "Tầng 2 - Liên kết dữ liệu", "Tầng 3 - Mạng", "Tầng 4 - Giao vận", "Tầng 7 - Ứng dụng" }, 2, "easy", "net", "TCP và UDP thuộc tầng giao vận." },
    { "Cổng mặc định của giao thức HTTP là?", { "21", "25", "80", "443" }, 2, "easy", "net", "HTTP dùng cổng 80, HTTPS dùng 443." },
    { "Địa chỉ IPv4 dài bao nhiêu bit?", { "16", "32", "64", "128" }, 1, "easy", "net", "IPv4 32 bit, IPv6 128 bit." },
    { "Hàm nào tạo socket trong POSIX?", { "socket()", "bind()", "listen()", "accept()" }, 0, "easy", "net", "socket() trả về file descriptor mới." },
    { "Hàm htonl() dùng để làm gì?", { "Đổi số 32 bit sang network byte order", "Đổi chuỗi IP sang số", "Phân giải tên miền", "Đóng socket" }, 0, "medium", "net", "htonl = host to network long (big-endian)." },
    { "UDP khác TCP ở điểm nào?", { "UDP có bắt tay 3 bước", "UDP không đảm bảo thứ tự và độ tin cậy", "UDP chậm hơn vì có ACK", "UDP chỉ dùng cho IPv6" }, 1, "medium", "net", "UDP là giao thức không kết nối." },
    { "Tham số backlog của listen() nghĩa là gì?", { "Số byte tối đa nhận", "Độ dài hàng đợi kết nối chờ accept", "Số thread phục vụ", "Thời gian timeout" }, 1, "medium", "net", "backlog giới hạn hàng đợi kết nối đang chờ." },
    { "Vì sao cần length-prefix framing trên TCP?", { "TCP là stream nên không giữ ranh giới message", "TCP hay mất gói", "TCP không hỗ trợ text", "Để mã hóa dữ liệu" }, 0, "hard", "net", "Dính gói và xé gói xảy ra trên stream." },
    { "Trạng thái TIME_WAIT xuất hiện ở phía nào?", { "Phía nhận FIN trước", "Phía chủ động đóng kết nối", "Cả hai phía luôn luôn", "Chỉ ở server" }, 1, "hard", "net", "Bên chủ động close() vào TIME_WAIT 2*MSL." },
    { "recv() trả về 0 có nghĩa là gì?", { "Lỗi socket", "Chưa có dữ liệu, thử lại", "Đối phương đã đóng kết nối", "Buffer đầy" }, 2, "hard", "net", "Giá trị 0 báo EOF từ peer." },
    { "sizeof(char) trong C bằng bao nhiêu?", { "1", "2", "4", "Tùy trình biên dịch" }, 0, "easy", "c", "Chuẩn C quy định sizeof(char) == 1." },
    { "Hàm nào cấp phát bộ nhớ động?", { "free()", "malloc()", "sizeof()", "printf()" }, 1, "easy", "c", "malloc cấp phát vùng nhớ trên heap." },
    { "Ký tự kết thúc chuỗi trong C là?", { "Xuống dòng", "NUL (mã 0)", "Dấu cách", "Dấu $" }, 1, "easy", "c", "Chuỗi C kết thúc bằng byte 0." },
    { "Vì sao nên dùng snprintf thay sprintf?", { "Nhanh hơn", "Giới hạn kích thước, chống tràn bộ đệm", "Hỗ trợ Unicode", "Không cần include" }, 1, "medium", "c", "snprintf nhận kích thước buffer đích." },
    { "Dereference con trỏ NULL gây ra?", { "Trả về 0", "Hành vi không xác định, thường segfault", "Lỗi biên dịch", "Tự cấp phát bộ nhớ" }, 1, "medium", "c", "Đây là undefined behavior." },
    { "static trên biến toàn cục có tác dụng?", { "Giới hạn phạm vi trong file", "Cấp phát trên stack", "Biến chỉ đọc", "Chia sẻ giữa các tiến trình" }, 0, "medium", "c", "Internal linkage." },
    { "pthread_mutex_lock dùng để làm gì?", { "Tạo thread mới", "Bảo vệ vùng găng khỏi truy cập đồng thời", "Kết thúc thread", "Gửi tín hiệu" }, 1, "medium", "c", "Mutex đảm bảo loại trừ lẫn nhau." },
    { "Valgrind báo definitely lost nghĩa là?", { "Mất hết con trỏ tới vùng nhớ chưa free", "Vẫn còn con trỏ tới vùng nhớ", "Đọc ngoài vùng", "Thread deadlock" }, 0, "hard", "c", "Rò rỉ bộ nhớ chắc chắn." },
    { "Deadlock xảy ra khi nào?", { "Các thread chờ khóa của nhau vô hạn", "Thread chạy quá nhanh", "Thiếu heap", "Socket đóng sớm" }, 0, "hard", "c", "Chờ vòng tròn tài nguyên." },
    { "strncpy với nguồn dài hơn n thì sao?", { "Đích luôn có byte 0 cuối", "Đích có thể không kết thúc bằng byte 0", "Trả về NULL", "Lỗi biên dịch" }, 1, "hard", "c", "Phải tự gán dest[n-1] = 0." },
    { "Lệnh nào liệt kê tiến trình trên Linux?", { "ls", "ps", "cd", "cat" }, 1, "easy", "os", "ps hiển thị danh sách tiến trình." },
    { "File descriptor số 0 mặc định là?", { "stdout", "stderr", "stdin", "socket" }, 2, "easy", "os", "0 stdin, 1 stdout, 2 stderr." },
    { "Hàm fork() tạo ra?", { "Thread mới", "Tiến trình con", "Socket", "File" }, 1, "easy", "os", "fork() nhân bản tiến trình hiện tại." },
    { "Tín hiệu SIGPIPE phát sinh khi?", { "Ghi vào socket mà phía kia đã đóng", "Chia cho 0", "Hết bộ nhớ", "Nhấn Ctrl+Z" }, 0, "medium", "os", "Server mạng thường bỏ qua SIGPIPE." },
    { "Khác biệt chính giữa thread và process?", { "Thread dùng chung không gian địa chỉ", "Mỗi thread có PID riêng", "Process nhẹ hơn thread", "Không khác biệt" }, 0, "medium", "os", "Các thread chung bộ nhớ của tiến trình." },
    { "WSL2 chạy Linux theo cơ chế nào?", { "Giả lập system call", "Máy ảo nhẹ với kernel Linux thật", "Biên dịch chéo", "Container Docker" }, 1, "medium", "os", "WSL2 dùng kernel Linux trong VM nhẹ." },
    { "Race condition là gì?", { "Kết quả phụ thuộc thứ tự thực thi không kiểm soát", "Hai tiến trình chạy an toàn", "Lỗi cú pháp", "Tràn ngăn xếp" }, 0, "hard", "os", "Cần đồng bộ hóa để tránh race." },
    { "SO_REUSEADDR giúp gì cho server?", { "Bind lại cổng khi còn TIME_WAIT", "Tăng tốc độ gửi", "Mã hóa kết nối", "Giới hạn số client" }, 0, "hard", "os", "Cho phép restart server ngay." },
    { "WAL của SQLite mang lại lợi ích gì?", { "Đọc ghi đồng thời tốt hơn", "Nén dữ liệu", "Mã hóa file", "Không cần transaction" }, 0, "hard", "os", "Reader không chặn writer." },
    { "poll() hoặc select() dùng để làm gì?", { "Chờ nhiều file descriptor sẵn sàng I/O", "Tạo tiến trình", "Cấp phát bộ nhớ", "Băm mật khẩu" }, 0, "hard", "os", "I/O multiplexing." }
};

const size_t SEED_QUESTION_COUNT = sizeof(SEED_QUESTIONS) / sizeof(SEED_QUESTIONS[0]);
