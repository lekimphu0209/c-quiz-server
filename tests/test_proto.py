import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gui")))
from proto import (
    escape_field,
    unescape_field,
    build_frame,
    build_cmd,
    parse_frame,
    parse_qrec,
    parse_exam_body,
    parse_err,
)


class TestProto(unittest.TestCase):
    def test_escaping_roundtrip(self):
        original = "Hello | World : 100% test, ok?\nSecond line."
        escaped = escape_field(original)
        self.assertNotIn("|", escaped)
        self.assertNotIn(":", escaped)
        self.assertNotIn("\n", escaped)
        unescaped = unescape_field(escaped)
        self.assertEqual(unescaped, original)

    def test_build_frame(self):
        payload = "PING"
        data = build_frame(payload)
        self.assertEqual(len(data), 8)
        self.assertEqual(data[:4], b"\x00\x00\x00\x04")
        self.assertEqual(data[4:], b"PING")

    def test_build_cmd(self):
        cmd = build_cmd("LOGIN", "user", "pass|word")
        self.assertEqual(cmd, "LOGIN|user|pass%7Cword")

    def test_parse_qrec(self):
        record = "7:TCP%3A dam bao gi?:A:B:C:D:medium"
        q = parse_qrec(record)
        self.assertEqual(q["qid"], 7)
        self.assertEqual(q["content"], "TCP: dam bao gi?")
        self.assertEqual(q["opt_a"], "A")
        self.assertEqual(q["difficulty"], "medium")

    def test_parse_exam_body(self):
        parts = ["OK", "STARTED", "1", "2", "1800", "1:Cau 1:A:B:C:D:easy", "2:Cau 2:X:Y:Z:W:hard"]
        questions = parse_exam_body(parts, start_idx=5)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0]["qid"], 1)
        self.assertEqual(questions[0]["content"], "Cau 1")
        self.assertEqual(questions[1]["qid"], 2)
        self.assertEqual(questions[1]["difficulty"], "hard")

    def test_parse_err(self):
        code, msg = parse_err("ERR|BAD_CREDENTIALS|invalid pass")
        self.assertEqual(code, "BAD_CREDENTIALS")
        self.assertEqual(msg, "Sai tài khoản hoặc mật khẩu")


if __name__ == "__main__":
    unittest.main()
