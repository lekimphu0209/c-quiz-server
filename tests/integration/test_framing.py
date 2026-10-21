import struct
import time

from quiz import QuizTestCase, frame


class FramingTest(QuizTestCase):
    def test_f01_sticky_frames_answered_in_order(self):
        client = self.connect()
        client.send_raw(frame("PING") + frame("PING") + frame("PING"))
        self.assertEqual([client.recv() for _ in range(3)], ["OK|PONG"] * 3)

    def test_f02_split_frame_reassembled(self):
        name = self.unique("split")
        self.assertEqual(self.connect().call("REGISTER|%s|123456" % name), "OK|REGISTERED")
        client = self.connect()
        data = frame("LOGIN|%s|123456" % name)
        for chunk in (data[:3], data[3:12], data[12:]):
            client.send_raw(chunk)
            time.sleep(0.2)
        reply = client.recv().split("|")
        self.assertEqual(reply[0], "OK")
        self.assertRegex(reply[1], r"^[0-9a-f]{32}$")
        self.assertEqual(reply[2], "user")

    def test_f04_empty_frame_closes_without_crash(self):
        client = self.connect()
        client.send_raw(struct.pack("!I", 0))
        self.assertTrue(client.is_closed())
        self.assertEqual(self.connect().call("PING"), "OK|PONG")

    def test_oversized_frame_rejected(self):
        client = self.connect()
        client.send_raw(struct.pack("!I", 9000) + b"A" * 16)
        self.assertErr(client.recv(), "LINE_TOO_LONG")
        self.assertTrue(client.is_closed())
        self.assertEqual(self.connect().call("PING"), "OK|PONG")

    def test_max_payload_accepted(self):
        client = self.connect()
        reply = client.call("PING|" + "x" * (8192 - 5))
        self.assertEqual(reply, "OK|PONG")

    def test_abrupt_disconnect_mid_frame(self):
        client = self.connect()
        client.send_raw(struct.pack("!I", 100) + b"PIN")
        client.close()
        self.assertEqual(self.connect().call("PING"), "OK|PONG")

    def test_utf8_payload_roundtrip(self):
        name = self.unique("utf")
        reply = self.connect().call("REGISTER|%s|mật khẩu" % name)
        self.assertEqual(reply, "OK|REGISTERED")
        self.login(name, "mật khẩu")


if __name__ == "__main__":
    import unittest
    unittest.main()
