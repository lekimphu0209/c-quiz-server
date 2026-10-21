import struct
import urllib.parse

ERR_MESSAGES = {
    "BAD_CREDENTIALS": "Sai tài khoản hoặc mật khẩu",
    "USER_EXISTS": "Tên đăng nhập đã tồn tại",
    "ALREADY_LOGGED_IN": "Tài khoản đang đăng nhập ở nơi khác",
    "NOT_AUTHENTICATED": "Phiên hết hạn — vui lòng đăng nhập lại",
    "FORBIDDEN": "Bạn không đủ quyền thực hiện thao tác này",
    "BAD_STATE": "Thao tác không hợp lệ ở trạng thái hiện tại",
    "NO_ROOM": "Phòng không tồn tại",
    "ROOM_STARTED": "Phòng đã bắt đầu",
    "ALREADY_JOINED": "Bạn đã ở trong phòng này",
    "ROOM_FULL": "Phòng đã đủ số lượng thí sinh",
    "ROOM_NOT_FINISHED": "Phòng chưa kết thúc — chưa có kết quả",
    "EXAM_ENDED": "Đã hết giờ làm bài",
    "ALREADY_SUBMITTED": "Bài đã được nộp",
    "NOT_ENOUGH_QUESTIONS": "Ngân hàng không đủ câu hỏi theo cấu hình",
    "NOTFOUND": "Đối tượng yêu cầu không tồn tại",
    "BAD_ARGS": "Dữ liệu nhập không hợp lệ",
    "UNKNOWN_CMD": "Lệnh không hợp lệ",
    "LINE_TOO_LONG": "Gói tin quá dài",
    "INTERNAL": "Lỗi hệ thống — thử lại sau",
}

ESCAPE_MAP = {
    "%": "%25",
    "|": "%7C",
    "\n": "%0A",
    "\r": "%0D",
    ":": "%3A",
    ",": "%2C",
}


def escape_field(val) -> str:
    """Escape protocol special characters in field text."""
    if val is None:
        return ""
    s = str(val)
    # Escape % first
    s = s.replace("%", "%25")
    s = s.replace("|", "%7C")
    s = s.replace("\n", "%0A")
    s = s.replace("\r", "%0D")
    s = s.replace(":", "%3A")
    s = s.replace(",", "%2C")
    return s


def unescape_field(val: str) -> str:
    """Unescape special characters decoded from server wire."""
    if not val:
        return ""
    return urllib.parse.unquote(val)


def build_frame(payload: str) -> bytes:
    """Pack payload with 4-byte big-endian length prefix."""
    raw = payload.encode("utf-8")
    return struct.pack("!I", len(raw)) + raw


def build_cmd(cmd: str, *args) -> str:
    """Construct a protocol command string with escaped arguments."""
    parts = [cmd]
    for arg in args:
        parts.append(escape_field(arg))
    return "|".join(parts)


def parse_frame(payload: str):
    """Split wire payload into fields."""
    if not payload:
        return []
    return payload.split("|")


def parse_qrec(qrec_str: str) -> dict:
    """Parse a single question record: qid:content:optA:optB:optC:optD:difficulty."""
    parts = qrec_str.split(":")
    if len(parts) < 7:
        return {}
    return {
        "qid": int(parts[0]) if parts[0].isdigit() else 0,
        "content": unescape_field(parts[1]),
        "opt_a": unescape_field(parts[2]),
        "opt_b": unescape_field(parts[3]),
        "opt_c": unescape_field(parts[4]),
        "opt_d": unescape_field(parts[5]),
        "difficulty": unescape_field(parts[6]),
    }


def parse_exam_body(parts: list, start_idx: int = 5) -> list:
    """Parse list of question records from raw split payload parts."""
    questions = []
    for qstr in parts[start_idx:]:
        if not qstr:
            continue
        q = parse_qrec(qstr)
        if q and q.get("qid"):
            questions.append(q)
    return questions


def parse_err(payload: str) -> tuple[str, str]:
    """Parse ERR|code|message into (code, user_friendly_msg)."""
    parts = payload.split("|", 2)
    code = parts[1] if len(parts) > 1 else "INTERNAL"
    raw_desc = unescape_field(parts[2]) if len(parts) > 2 else ""
    friendly = ERR_MESSAGES.get(code, raw_desc or code)
    if raw_desc and code not in ("BAD_CREDENTIALS", "USER_EXISTS", "ALREADY_LOGGED_IN"):
        friendly = f"{friendly} ({raw_desc})"
    return code, friendly
