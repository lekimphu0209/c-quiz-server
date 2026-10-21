from quiz import QuizTestCase


class HistoryTest(QuizTestCase):
    def correct(self, rid):
        return dict(self.server.query("SELECT qidx, correct_opt FROM room_questions WHERE rid = ?", (rid,)))

    def practice_done(self, client, n=3, difficulty="hard", topic="all", right=None):
        reply = client.call("PRACTICE|%s|%d|300|%s|%s" % (client.token, n, difficulty, topic))
        rid = int(reply.split("|")[2])
        answers = self.correct(rid)
        for qidx in range(1, (n if right is None else right) + 1):
            client.call("ANSWER|%s|%d|%d|%d" % (client.token, rid, qidx, answers[qidx]))
        client.call("PRACTICE_SUBMIT|%s|%d" % (client.token, rid))
        client.wait_event("EVT|RESULT|%d|" % rid)
        return rid

    def room_done(self, host, member):
        rid = self.create_room(host, name="Thi GK")
        member.call("JOIN|%s|%d" % (member.token, rid))
        host.call("START_ROOM|%s|%d" % (host.token, rid))
        member.wait_event("EVT|EXAM|%d|" % rid)
        member.call("ANSWER|%s|%d|1|%d" % (member.token, rid, self.correct(rid)[1]))
        host.call("SUBMIT|%s|%d" % (host.token, rid))
        member.call("SUBMIT|%s|%d" % (member.token, rid))
        member.wait_event("EVT|RESULT|%d|" % rid)
        return rid

    def history(self, client, flt=None):
        reply = client.call("HISTORY|" + client.token + ("|" + flt if flt else ""))
        self.assertTrue(reply == "OK" or reply.startswith("OK|"), reply)
        return [item.split(":") for item in reply.split("|")[1:]]

    def test_h01_history_newest_first(self):
        host = self.user("hh")
        member = self.user("hm")
        self.room_done(host, member)
        self.server.execute("UPDATE attempts SET submit_ts = submit_ts - 100 WHERE status = 'SUBMITTED'")
        self.practice_done(member, right=2)
        rows = self.history(member)
        self.assertEqual(len(rows), 2)
        self.assertEqual([r[2] for r in rows], ["practice", "room"])
        self.assertEqual(rows[0][3:], ["practice%3A" + member.username, "2", "3"])
        self.assertEqual(rows[1][3:], ["Thi GK", "1", "3"])
        self.assertGreater(int(rows[0][1]), int(rows[1][1]))

    def test_h02_history_filter(self):
        host = self.user("fh")
        member = self.user("fm")
        self.room_done(host, member)
        self.practice_done(member)
        self.assertEqual([r[2] for r in self.history(member, "practice")], ["practice"])
        self.assertEqual([r[2] for r in self.history(member, "room")], ["room"])
        self.assertErr(member.call("HISTORY|%s|weird" % member.token), "BAD_ARGS")

    def test_h03_history_private(self):
        alice = self.user("ha")
        bob = self.user("hb")
        self.practice_done(alice)
        self.assertEqual(self.history(bob), [])
        self.assertEqual(len(self.history(alice)), 1)

    def test_h04_history_detail(self):
        client = self.user("hd")
        rid = self.practice_done(client, right=1)
        att = self.history(client)[0][0]
        reply = client.call("HISTORY_DETAIL|%s|%s" % (client.token, att)).split("|")
        self.assertEqual(reply[0], "OK")
        details = [d.split(":") for d in reply[1:]]
        answers = self.correct(rid)
        self.assertEqual([d[0] for d in details], ["1", "2", "3"])
        self.assertEqual(details[0][1:3], [str(answers[1]), str(answers[1])])
        self.assertEqual(details[1][1:3], ["-1", str(answers[2])])
        self.assertEqual(len(details[0]), 4)

    def test_history_detail_errors(self):
        owner = self.user("ho")
        other = self.user("hx")
        self.practice_done(owner)
        att = self.history(owner)[0][0]
        self.assertErr(other.call("HISTORY_DETAIL|%s|%s" % (other.token, att)), "FORBIDDEN")
        self.assertErr(owner.call("HISTORY_DETAIL|%s|999999" % owner.token), "NOTFOUND")
        self.assertErr(owner.call("HISTORY_DETAIL|%s|abc" % owner.token), "BAD_ARGS")
        reply = other.call("PRACTICE|%s|3|300|mixed|all" % other.token)
        rid = int(reply.split("|")[2])
        live = self.server.query("SELECT a.att_id FROM attempts a WHERE a.rid = ?", (rid,))[0][0]
        self.assertErr(other.call("HISTORY_DETAIL|%s|%d" % (other.token, live)), "BAD_STATE")

    def test_h05_personal_stats(self):
        client = self.user("hs")
        self.assertEqual(client.call("STATS|" + client.token), "OK|0|0|0|0|0|0|0|0|")
        self.practice_done(client, n=3, difficulty="hard", topic="net", right=3)
        self.practice_done(client, n=2, difficulty="easy", topic="net", right=1)
        reply = client.call("STATS|" + client.token).split("|")
        self.assertEqual(reply[:9], ["OK", "2", "200", "1", "2", "0", "0", "3", "3"])
        self.assertEqual(reply[9], "net:4/5")

    def test_q07_admin_global_stats(self):
        client = self.user("hg")
        self.practice_done(client)
        self.assertErr(client.call("STATS|%s|ALL" % client.token), "FORBIDDEN")
        self.assertErr(client.call("STATS|%s|bogus" % client.token), "BAD_ARGS")
        admin = self.admin()
        reply = admin.call("STATS|%s|ALL" % admin.token).split("|")
        self.assertEqual(reply[0], "OK")
        self.assertGreaterEqual(int(reply[1]), 1)
        self.assertEqual(len(reply), 10)
        admin.close()


if __name__ == "__main__":
    import unittest
    unittest.main()
