import time

from quiz import TIMEOUT, QuizTestCase


class ResumeTest(QuizTestCase):
    def started(self):
        host = self.user("rh")
        member = self.user("rm")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        host.call("START_ROOM|%s|%d" % (host.token, rid))
        member.wait_event("EVT|EXAM|%d|" % rid)
        return host, member, rid

    def relogin(self, client):
        client.close()
        return self.login(client.username)

    def raw_login(self, username):
        client = self.connect()
        deadline = time.time() + TIMEOUT
        reply = client.call("LOGIN|%s|123456" % username)
        while reply.startswith("ERR|ALREADY_LOGGED_IN|") and time.time() < deadline:
            time.sleep(0.05)
            reply = client.call("LOGIN|%s|123456" % username)
        client.token = reply.split("|")[1]
        return client, reply

    def test_c01_login_reports_resume(self):
        host, member, rid = self.started()
        member.call("ANSWER|%s|%d|1|0" % (member.token, rid))
        member.call("ANSWER|%s|%d|2|1" % (member.token, rid))
        member.close()
        client, reply = self.raw_login(member.username)
        self.assertRegex(reply, r"^OK\|[0-9a-f]{32}\|user\|RESUME\|%d$" % rid)

    def test_c02_resume_returns_exam_mask_and_time(self):
        host, member, rid = self.started()
        started = member.call("GET_QUESTIONS|%s|%d" % (member.token, rid))
        member.call("ANSWER|%s|%d|1|0" % (member.token, rid))
        member.call("ANSWER|%s|%d|2|1" % (member.token, rid))
        again = self.relogin(member)
        reply = again.call("RESUME|%s|%d" % (again.token, rid)).split("|")
        self.assertEqual(reply[:4], ["OK", "RESUME", str(rid), "3"])
        self.assertTrue(0 < int(reply[4]) <= 120, reply[4])
        self.assertEqual(reply[5], "110")
        self.assertEqual(reply[6:], started.split("|")[3:])
        self.assertEqual(again.call("ANSWER|%s|%d|3|2" % (again.token, rid)), "OK")

    def test_c03_room_finished_while_offline(self):
        host, member, rid = self.started()
        member.close()
        self.server.execute("UPDATE rooms SET start_ts = start_ts - 100000 WHERE rid = ?", (rid,))
        host.wait_event("EVT|RESULT|%d|" % rid)
        client, reply = self.raw_login(member.username)
        self.assertRegex(reply, r"^OK\|[0-9a-f]{32}\|user$")
        self.assertErr(client.call("RESUME|%s|%d" % (client.token, rid)), "EXAM_ENDED")
        self.assertTrue(client.call("ROOM_RESULT|%s|%d" % (client.token, rid)).startswith("OK|3|"))

    def test_resume_errors(self):
        host, member, rid = self.started()
        outsider = self.user("ro")
        self.assertErr(outsider.call("RESUME|%s|%d" % (outsider.token, rid)), "FORBIDDEN")
        self.assertErr(outsider.call("RESUME|%s|999999" % outsider.token), "NO_ROOM")
        member.call("SUBMIT|%s|%d" % (member.token, rid))
        self.assertErr(member.call("RESUME|%s|%d" % (member.token, rid)), "ALREADY_SUBMITTED")
        waiting_host = self.user("rw")
        waiting = self.create_room(waiting_host)
        self.assertErr(waiting_host.call("RESUME|%s|%d" % (waiting_host.token, waiting)), "BAD_STATE")

    def test_practice_resume_after_disconnect(self):
        client = self.user("rp")
        reply = client.call("PRACTICE|%s|3|300|mixed|all" % client.token)
        rid = int(reply.split("|")[2])
        client.close()
        again, login = self.raw_login(client.username)
        self.assertTrue(login.endswith("|RESUME|%d" % rid), login)
        self.assertTrue(again.call("RESUME|%s|%d" % (again.token, rid)).startswith("OK|RESUME|%d|3|" % rid))


if __name__ == "__main__":
    import unittest
    unittest.main()
