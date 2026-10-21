import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "gui")))
from state import AppState
from proto import (
    build_cmd,
    parse_frame,
    parse_err,
    parse_qrec,
    parse_exam_body,
    escape_field,
    unescape_field,
    ERR_MESSAGES,
)


class TestGuiStateAndCommands(unittest.TestCase):
    def test_app_state_lifecycle(self):
        state = AppState()
        self.assertEqual(state.token, "")
        self.assertEqual(state.role, "user")
        self.assertIsNone(state.room_id)

        state.token = "a" * 32
        state.username = "testuser"
        state.role = "admin"
        state.room_id = 42
        state.room_name = "Giữa kỳ"
        state.exam = {"rid": 42, "n": 20}
        state.last_result = {"score": 18, "total": 20}

        self.assertEqual(state.token, "a" * 32)
        self.assertEqual(state.role, "admin")
        self.assertEqual(state.room_id, 42)

        state.clear()
        self.assertEqual(state.token, "")
        self.assertEqual(state.username, "")
        self.assertEqual(state.role, "user")
        self.assertIsNone(state.room_id)
        self.assertEqual(len(state.exam), 0)
        self.assertEqual(len(state.last_result), 0)

    def test_all_err_codes_mapped(self):
        codes = [
            "BAD_CREDENTIALS",
            "USER_EXISTS",
            "ALREADY_LOGGED_IN",
            "NOT_AUTHENTICATED",
            "FORBIDDEN",
            "BAD_STATE",
            "NO_ROOM",
            "ROOM_STARTED",
            "ALREADY_JOINED",
            "ROOM_FULL",
            "ROOM_NOT_FINISHED",
            "EXAM_ENDED",
            "ALREADY_SUBMITTED",
            "NOT_ENOUGH_QUESTIONS",
            "NOTFOUND",
            "BAD_ARGS",
            "UNKNOWN_CMD",
            "LINE_TOO_LONG",
            "INTERNAL",
        ]
        for c in codes:
            self.assertIn(c, ERR_MESSAGES)
            code, friendly = parse_err(f"ERR|{c}|error description")
            self.assertEqual(code, c)
            self.assertTrue(len(friendly) > 0)

    def test_command_builders(self):
        token = "tok123"
        # S1
        self.assertEqual(build_cmd("PING"), "PING")
        self.assertEqual(build_cmd("LOGIN", "user", "pass"), "LOGIN|user|pass")
        self.assertEqual(build_cmd("REGISTER", "u", "p"), "REGISTER|u|p")

        # S2 & S3
        self.assertEqual(build_cmd("LIST_ROOMS", token, "WAITING"), "LIST_ROOMS|tok123|WAITING")
        self.assertEqual(build_cmd("CREATE_ROOM", token, "Phòng 1", 20, 1800, "mixed", "mang"), "CREATE_ROOM|tok123|Phòng 1|20|1800|mixed|mang")
        self.assertEqual(build_cmd("JOIN", token, 5), "JOIN|tok123|5")

        # S4
        self.assertEqual(build_cmd("START_ROOM", token, 5), "START_ROOM|tok123|5")
        self.assertEqual(build_cmd("LEAVE_ROOM", token, 5), "LEAVE_ROOM|tok123|5")

        # S5
        self.assertEqual(build_cmd("ANSWER", token, 5, 1, 2), "ANSWER|tok123|5|1|2")
        self.assertEqual(build_cmd("SUBMIT", token, 5), "SUBMIT|tok123|5")
        self.assertEqual(build_cmd("PRACTICE", token, 10, 600, "easy:5,medium:5,hard:0", "mang"), "PRACTICE|tok123|10|600|easy%3A5%2Cmedium%3A5%2Chard%3A0|mang")
        self.assertEqual(build_cmd("PRACTICE_SUBMIT", token, 99), "PRACTICE_SUBMIT|tok123|99")

        # S6 & S7
        self.assertEqual(build_cmd("ROOM_RESULT", token, 5), "ROOM_RESULT|tok123|5")
        self.assertEqual(build_cmd("HISTORY", token, "all"), "HISTORY|tok123|all")
        self.assertEqual(build_cmd("HISTORY_DETAIL", token, 12), "HISTORY_DETAIL|tok123|12")
        self.assertEqual(build_cmd("STATS", token), "STATS|tok123")
        self.assertEqual(build_cmd("STATS", token, "ALL"), "STATS|tok123|ALL")

        # S8
        self.assertEqual(build_cmd("LIST_QUESTIONS", token), "LIST_QUESTIONS|tok123")
        self.assertEqual(build_cmd("DEL_QUESTION", token, 7), "DEL_QUESTION|tok123|7")
        self.assertEqual(build_cmd("IMPORT_CSV", token, "data/q.csv"), "IMPORT_CSV|tok123|data/q.csv")


if __name__ == "__main__":
    unittest.main()
