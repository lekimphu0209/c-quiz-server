import time

from quiz import QuizTestCase


def qrecs(payload, skip):
    return payload.split("|")[skip:]


class ExamTest(QuizTestCase):
    def room_with_member(self, n=3, cfg="easy:1,medium:1,hard:1", sec=120):
        host = self.user("eh")
        member = self.user("em")
        rid = self.create_room(host, n=n, sec=sec, cfg=cfg)
        self.assertTrue(member.call("JOIN|%s|%d" % (member.token, rid)).startswith("OK|JOINED|"))
        host.wait_event("EVT|MEMBER_JOINED")
        return host, member, rid

    def started(self, n=3, cfg="easy:1,medium:1,hard:1", sec=120):
        host, member, rid = self.room_with_member(n, cfg, sec)
        reply = host.call("START_ROOM|%s|%d" % (host.token, rid))
        self.assertTrue(reply.startswith("OK|STARTED|%d|%d|%d|" % (rid, n, sec)), reply)
        member.wait_event("EVT|EXAM|%d|" % rid)
        return host, member, rid

    def correct(self, rid):
        return dict(self.server.query("SELECT qidx, correct_opt FROM room_questions WHERE rid = ?", (rid,)))

    def expire(self, rid):
        self.server.execute("UPDATE rooms SET start_ts = start_ts - 100000 WHERE rid = ?", (rid,))

    def test_e01_start_pushes_same_exam(self):
        host, member, rid = self.room_with_member()
        reply = host.call("START_ROOM|%s|%d" % (host.token, rid))
        event = member.wait_event("EVT|EXAM|%d|" % rid)
        self.assertEqual(event.split("|")[2:5], [str(rid), "3", "120"])
        self.assertEqual(qrecs(reply, 5), qrecs(event, 5))
        self.assertEqual(self.server.query("SELECT status FROM rooms WHERE rid = ?", (rid,)), [("RUNNING",)])

    def test_e02_exam_hides_correct_answer(self):
        host, member, rid = self.room_with_member()
        reply = host.call("START_ROOM|%s|%d" % (host.token, rid))
        records = qrecs(reply, 5)
        self.assertEqual(len(records), 3)
        for record in records:
            fields = record.split(":")
            self.assertEqual(len(fields), 7, record)
            self.assertTrue(fields[0].isdigit())
            self.assertIn(fields[6], ("easy", "medium", "hard"))
        difficulties = sorted(r[0] for r in self.server.query("SELECT difficulty FROM room_questions WHERE rid = ?", (rid,)))
        self.assertEqual(difficulties, ["easy", "hard", "medium"])

    def test_a11_only_owner_starts(self):
        host, member, rid = self.room_with_member()
        self.assertErr(member.call("START_ROOM|%s|%d" % (member.token, rid)), "FORBIDDEN")
        self.assertErr(member.call("END_ROOM|%s|%d" % (member.token, rid)), "FORBIDDEN")

    def test_start_requires_two_members_and_waiting(self):
        host = self.user("solo")
        rid = self.create_room(host)
        self.assertErr(host.call("START_ROOM|%s|%d" % (host.token, rid)), "BAD_STATE")
        host, member, rid = self.started()
        self.assertErr(host.call("START_ROOM|%s|%d" % (host.token, rid)), "BAD_STATE")
        self.assertErr(host.call("START_ROOM|%s|999999" % host.token), "NO_ROOM")

    def test_e03_answer_and_change(self):
        host, member, rid = self.started()
        self.assertEqual(member.call("ANSWER|%s|%d|1|1" % (member.token, rid)), "OK")
        self.assertEqual(member.call("ANSWER|%s|%d|1|3" % (member.token, rid)), "OK")
        rows = self.server.query("SELECT aa.chosen_opt FROM attempt_answers aa JOIN attempts a ON a.att_id = aa.att_id JOIN users u ON u.id = a.user_id WHERE a.rid = ? AND u.username = ?", (rid, member.username))
        self.assertEqual(rows, [(3,)])
        log = self.server.log_text()
        self.assertIn("user=%s room=%d idx=1 opt=1" % (member.username, rid), log)
        self.assertIn("user=%s room=%d idx=1 opt=3" % (member.username, rid), log)

    def test_e04_e05_answer_out_of_range(self):
        host, member, rid = self.started()
        self.assertErr(member.call("ANSWER|%s|%d|99|0" % (member.token, rid)), "BAD_ARGS")
        self.assertErr(member.call("ANSWER|%s|%d|0|0" % (member.token, rid)), "BAD_ARGS")
        self.assertErr(member.call("ANSWER|%s|%d|1|7" % (member.token, rid)), "BAD_ARGS")
        self.assertErr(member.call("ANSWER|%s|%d|x|1" % (member.token, rid)), "BAD_ARGS")

    def test_e06_e07_e08_submit_scores_once(self):
        host, member, rid = self.started()
        for qidx, opt in self.correct(rid).items():
            self.assertEqual(member.call("ANSWER|%s|%d|%d|%d" % (member.token, rid, qidx, opt)), "OK")
        self.assertEqual(member.call("SUBMIT|%s|%d" % (member.token, rid)), "OK|3|3")
        self.assertErr(member.call("SUBMIT|%s|%d" % (member.token, rid)), "ALREADY_SUBMITTED")
        self.assertErr(member.call("ANSWER|%s|%d|1|0" % (member.token, rid)), "ALREADY_SUBMITTED")

    def test_e09_timeout_auto_submits(self):
        host, member, rid = self.started()
        first = self.correct(rid)[1]
        member.call("ANSWER|%s|%d|1|%d" % (member.token, rid, first))
        self.expire(rid)
        self.assertEqual(member.wait_event("EVT|RESULT|%d|" % rid), "EVT|RESULT|%d|1/3|1" % rid)
        self.assertEqual(host.wait_event("EVT|RESULT|%d|" % rid), "EVT|RESULT|%d|0/3|2" % rid)
        self.assertEqual(self.server.query("SELECT status FROM rooms WHERE rid = ?", (rid,)), [("FINISHED",)])
        self.assertEqual(self.server.query("SELECT COUNT(*) FROM attempts WHERE rid = ? AND status = 'SUBMITTED' AND submit_ts = 0", (rid,)), [(2,)])
        log = self.server.log_text()
        self.assertIn("AUTO_SUBMIT room=%d" % rid, log)
        self.assertIn("ROOM_FINISHED room=%d" % rid, log)

    def test_e10_all_submitted_finishes_room(self):
        host, member, rid = self.started()
        self.assertEqual(host.call("SUBMIT|%s|%d" % (host.token, rid)), "OK|0|3")
        self.assertTrue(host.no_event("EVT|RESULT"))
        self.assertEqual(member.call("SUBMIT|%s|%d" % (member.token, rid)), "OK|0|3")
        self.assertTrue(member.wait_event("EVT|RESULT|%d|0/3|" % rid))
        self.assertTrue(host.wait_event("EVT|RESULT|%d|0/3|" % rid))
        self.assertEqual(self.server.query("SELECT status FROM rooms WHERE rid = ?", (rid,)), [("FINISHED",)])

    def test_e11_host_ends_room(self):
        host, member, rid = self.started()
        member.call("ANSWER|%s|%d|2|%d" % (member.token, rid, self.correct(rid)[2]))
        self.assertEqual(host.call("END_ROOM|%s|%d" % (host.token, rid)), "OK|ENDED")
        self.assertEqual(member.wait_event("EVT|RESULT|%d|" % rid), "EVT|RESULT|%d|1/3|1" % rid)
        host.wait_event("EVT|RESULT|%d|" % rid)
        self.assertErr(host.call("END_ROOM|%s|%d" % (host.token, rid)), "BAD_STATE")

    def test_e12_answer_after_finish(self):
        host, member, rid = self.started()
        host.call("END_ROOM|%s|%d" % (host.token, rid))
        self.assertErr(member.call("ANSWER|%s|%d|1|0" % (member.token, rid)), "EXAM_ENDED")
        self.assertErr(member.call("SUBMIT|%s|%d" % (member.token, rid)), "EXAM_ENDED")

    def test_answer_after_deadline_before_ticker(self):
        host, member, rid = self.started()
        self.expire(rid)
        self.assertErr(member.call("ANSWER|%s|%d|1|0" % (member.token, rid)), "EXAM_ENDED")

    def test_e13_outsider_forbidden(self):
        host, member, rid = self.started()
        outsider = self.user("out")
        self.assertErr(outsider.call("ANSWER|%s|%d|1|0" % (outsider.token, rid)), "FORBIDDEN")
        self.assertErr(outsider.call("SUBMIT|%s|%d" % (outsider.token, rid)), "FORBIDDEN")
        self.assertErr(outsider.call("GET_QUESTIONS|%s|%d" % (outsider.token, rid)), "FORBIDDEN")

    def test_answer_in_waiting_room(self):
        host, member, rid = self.room_with_member()
        self.assertErr(member.call("ANSWER|%s|%d|1|0" % (member.token, rid)), "BAD_STATE")
        self.assertErr(member.call("GET_QUESTIONS|%s|%d" % (member.token, rid)), "BAD_STATE")

    def test_e14_room_result_ranking(self):
        host, member, rid = self.room_with_member()
        third = self.user("e3")
        third.call("JOIN|%s|%d" % (third.token, rid))
        host.call("START_ROOM|%s|%d" % (host.token, rid))
        answers = self.correct(rid)
        host.call("ANSWER|%s|%d|1|%d" % (host.token, rid, answers[1]))
        self.assertEqual(host.call("SUBMIT|%s|%d" % (host.token, rid)), "OK|1|3")
        for qidx, opt in answers.items():
            member.call("ANSWER|%s|%d|%d|%d" % (member.token, rid, qidx, opt))
        member.call("SUBMIT|%s|%d" % (member.token, rid))
        third.call("ANSWER|%s|%d|1|%d" % (third.token, rid, answers[1]))
        self.server.execute("UPDATE attempts SET submit_ts = submit_ts - 50 WHERE rid = ? AND status = 'SUBMITTED'", (rid,))
        third.call("SUBMIT|%s|%d" % (third.token, rid))
        reply = third.call("ROOM_RESULT|%s|%d" % (third.token, rid)).split("|")
        self.assertEqual(reply[:2], ["OK", "3"])
        entries = [entry.split(":") for entry in reply[2:]]
        self.assertEqual([e[:3] for e in entries], [["1", member.username, "3"], ["2", host.username, "1"], ["3", third.username, "1"]])
        self.assertTrue(all(int(e[3]) > 0 for e in entries))

    def test_e15_result_before_finish(self):
        host, member, rid = self.started()
        self.assertErr(member.call("ROOM_RESULT|%s|%d" % (member.token, rid)), "ROOM_NOT_FINISHED")
        self.assertErr(member.call("ROOM_RESULT|%s|999999" % member.token), "NO_ROOM")

    def test_get_questions_fallback(self):
        host, member, rid = self.room_with_member()
        started = host.call("START_ROOM|%s|%d" % (host.token, rid))
        reply = member.call("GET_QUESTIONS|%s|%d" % (member.token, rid))
        self.assertEqual(reply.split("|")[:3], ["OK", "3", "120"])
        self.assertEqual(qrecs(reply, 3), qrecs(started, 5))

    def test_snapshot_survives_question_delete(self):
        host, member, rid = self.room_with_member()
        started = host.call("START_ROOM|%s|%d" % (host.token, rid))
        qid = qrecs(started, 5)[0].split(":")[0]
        admin = self.admin()
        self.assertEqual(admin.call("DEL_QUESTION|%s|%s" % (admin.token, qid)), "OK")
        self.assertEqual(qrecs(member.call("GET_QUESTIONS|%s|%d" % (member.token, rid)), 3), qrecs(started, 5))
        admin.close()

    def test_f03_large_exam_payload(self):
        host, member, rid = self.room_with_member(n=20, cfg="mixed", sec=600)
        reply = host.call("START_ROOM|%s|%d" % (host.token, rid))
        self.assertEqual(len(qrecs(reply, 5)), 20)
        self.assertGreater(len(reply.encode("utf-8")), 1024)
        self.assertEqual(len(qrecs(member.wait_event("EVT|EXAM|%d|" % rid), 5)), 20)

    def test_submitted_user_is_free_again(self):
        host, member, rid = self.started()
        self.assertErr(member.call("CREATE_ROOM|%s|X|3|120|mixed|all" % member.token), "BAD_STATE")
        member.call("SUBMIT|%s|%d" % (member.token, rid))
        self.create_room(member)

    def test_l04_parallel_room_timers(self):
        rooms = [self.started() for _ in range(3)]
        self.expire(rooms[0][2])
        self.expire(rooms[1][2])
        rooms[0][1].wait_event("EVT|RESULT|%d|" % rooms[0][2])
        rooms[1][1].wait_event("EVT|RESULT|%d|" % rooms[1][2])
        time.sleep(1.2)
        self.assertEqual(self.server.query("SELECT status FROM rooms WHERE rid = ?", (rooms[2][2],)), [("RUNNING",)])
        self.expire(rooms[2][2])
        rooms[2][1].wait_event("EVT|RESULT|%d|" % rooms[2][2])


if __name__ == "__main__":
    import unittest
    unittest.main()
