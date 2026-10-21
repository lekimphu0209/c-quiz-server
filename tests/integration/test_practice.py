from quiz import QuizTestCase


def qrecs(payload, skip):
    return payload.split("|")[skip:]


class PracticeTest(QuizTestCase):
    def practice(self, client, n=5, sec=300, difficulty="mixed", topic="all"):
        reply = client.call("PRACTICE|%s|%d|%d|%s|%s" % (client.token, n, sec, difficulty, topic))
        self.assertTrue(reply.startswith("OK|PRACTICE|"), reply)
        return int(reply.split("|")[2]), reply

    def correct(self, rid):
        return dict(self.server.query("SELECT qidx, correct_opt FROM room_questions WHERE rid = ?", (rid,)))

    def test_p01_practice_hidden_room(self):
        client = self.user("p1")
        rid, reply = self.practice(client)
        self.assertEqual(reply.split("|")[2:5], [str(rid), "5", "300"])
        self.assertEqual(len(qrecs(reply, 5)), 5)
        rows = self.server.query("SELECT is_practice, status, name FROM rooms WHERE rid = ?", (rid,))
        self.assertEqual(rows, [(1, "RUNNING", "practice:" + client.username)])
        listing = client.call("LIST_ROOMS|" + client.token)
        self.assertNotIn("|%d:" % rid, listing + ":")

    def test_p02_filter_difficulty(self):
        client = self.user("p2")
        rid, reply = self.practice(client, n=3, sec=120, difficulty="hard")
        self.assertEqual({record.split(":")[6] for record in qrecs(reply, 5)}, {"hard"})

    def test_p03_filter_topic(self):
        client = self.user("p3")
        rid, reply = self.practice(client, n=3, sec=120, topic="net")
        self.assertEqual({row[0] for row in self.server.query("SELECT topic FROM room_questions WHERE rid = ?", (rid,))}, {"net"})

    def test_p04_not_enough_and_bad_args(self):
        client = self.user("p4")
        self.assertErr(client.call("PRACTICE|%s|50|60|hard|all" % client.token), "NOT_ENOUGH_QUESTIONS")
        self.assertErr(client.call("PRACTICE|%s|0|60|hard|all" % client.token), "BAD_ARGS")
        self.assertErr(client.call("PRACTICE|%s|3|0|hard|all" % client.token), "BAD_ARGS")
        self.assertErr(client.call("PRACTICE|%s|3|60|insane|all" % client.token), "BAD_ARGS")
        self.assertErr(client.call("PRACTICE|%s|3|60|hard" % client.token), "BAD_ARGS")

    def test_p05_answer_and_submit(self):
        client = self.user("p5")
        rid, _ = self.practice(client)
        for qidx, opt in self.correct(rid).items():
            self.assertEqual(client.call("ANSWER|%s|%d|%d|%d" % (client.token, rid, qidx, opt)), "OK")
        self.assertEqual(client.call("PRACTICE_SUBMIT|%s|%d" % (client.token, rid)), "OK|5|5")
        self.assertEqual(client.wait_event("EVT|RESULT|%d|" % rid), "EVT|RESULT|%d|5/5|-" % rid)
        self.assertErr(client.call("PRACTICE_SUBMIT|%s|%d" % (client.token, rid)), "EXAM_ENDED")

    def test_p06_timeout_grades_practice(self):
        client = self.user("p6")
        rid, _ = self.practice(client, n=3, sec=60)
        client.call("ANSWER|%s|%d|2|%d" % (client.token, rid, self.correct(rid)[2]))
        self.server.execute("UPDATE rooms SET start_ts = start_ts - 1000 WHERE rid = ?", (rid,))
        self.assertEqual(client.wait_event("EVT|RESULT|%d|" % rid), "EVT|RESULT|%d|1/3|-" % rid)

    def test_p07_busy_while_practicing(self):
        host = self.user("p7h")
        room = self.create_room(host)
        client = self.user("p7")
        self.practice(client)
        self.assertErr(client.call("JOIN|%s|%d" % (client.token, room)), "BAD_STATE")
        self.assertErr(client.call("PRACTICE|%s|3|60|mixed|all" % client.token), "BAD_STATE")
        self.assertErr(host.call("PRACTICE|%s|3|60|mixed|all" % host.token), "BAD_STATE")

    def test_practice_room_private(self):
        owner = self.user("p8")
        other = self.user("p9")
        rid, _ = self.practice(owner)
        self.assertErr(other.call("ANSWER|%s|%d|1|0" % (other.token, rid)), "NO_ROOM")
        self.assertErr(other.call("JOIN|%s|%d" % (other.token, rid)), "NO_ROOM")


if __name__ == "__main__":
    import unittest
    unittest.main()
