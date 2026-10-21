from quiz import QuizTestCase


class RoomTest(QuizTestCase):
    def rooms(self, client, flt=None):
        reply = client.call("LIST_ROOMS|" + client.token + ("|" + flt if flt else ""))
        self.assertTrue(reply == "OK" or reply.startswith("OK|"), reply)
        return [item.split(":") for item in reply.split("|")[1:]]

    def find(self, client, rid):
        return next((r for r in self.rooms(client) if r[0] == str(rid)), None)

    def test_r01_create_room_owner_is_member(self):
        host = self.user("host")
        rid = self.create_room(host, n=3, sec=120, cfg="easy:1,medium:1,hard:1", name="Thi giua ky")
        rows = self.server.query("SELECT name, num_q, duration_sec, difficulty_cfg, status, is_practice FROM rooms WHERE rid = ?", (rid,))
        self.assertEqual(rows, [("Thi giua ky", 3, 120, "easy:1,medium:1,hard:1", "WAITING", 0)])
        self.assertEqual(self.server.query("SELECT COUNT(*) FROM attempts WHERE rid = ?", (rid,)), [(1,)])

    def test_r02_ratio_must_match_n(self):
        host = self.user("ratio")
        self.assertErr(host.call("CREATE_ROOM|%s|X|3|120|easy:2,medium:2,hard:2|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s|X|3|120|easy:1,easy:2|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s|X|3|120|weird|all" % host.token), "BAD_ARGS")

    def test_r03_duration_and_size_bounds(self):
        host = self.user("bound")
        self.assertErr(host.call("CREATE_ROOM|%s|X|3|10|mixed|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s|X|3|99999|mixed|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s|X|0|120|mixed|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s|X|101|120|mixed|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s||3|120|mixed|all" % host.token), "BAD_ARGS")
        self.assertErr(host.call("CREATE_ROOM|%s|%s|3|120|mixed|all" % (host.token, "n" * 51)), "BAD_ARGS")

    def test_create_room_unicode_name_counts_characters(self):
        host = self.user("uni")
        self.create_room(host, name="Đề thi cuối kỳ " + "ạ" * 30)

    def test_q06_not_enough_questions(self):
        host = self.user("few")
        self.assertErr(host.call("CREATE_ROOM|%s|X|20|120|easy:0,medium:0,hard:20|all" % host.token), "NOT_ENOUGH_QUESTIONS")
        self.assertErr(host.call("CREATE_ROOM|%s|X|3|120|mixed|no_such_topic" % host.token), "NOT_ENOUGH_QUESTIONS")

    def test_r04_list_rooms_fields(self):
        host = self.user("lst")
        rid = self.create_room(host, n=2, sec=90, name="A%7CB:C")
        row = self.find(host, rid)
        self.assertEqual(row, [str(rid), "A%7CB%3AC", host.username, "WAITING", "2", "90", "1"])
        self.assertIsNone(next((r for r in self.rooms(host, "RUNNING") if r[0] == str(rid)), None))
        self.assertIsNotNone(next((r for r in self.rooms(host, "WAITING") if r[0] == str(rid)), None))
        self.assertErr(host.call("LIST_ROOMS|%s|BOGUS" % host.token), "BAD_ARGS")

    def test_a09_list_rooms_requires_token(self):
        self.assertErr(self.connect().call("LIST_ROOMS|badtoken"), "NOT_AUTHENTICATED")

    def test_r05_join_broadcasts_member_joined(self):
        host = self.user("jh")
        member = self.user("jm")
        rid = self.create_room(host, n=3, sec=120, cfg="easy:1,medium:1,hard:1")
        reply = member.call("JOIN|%s|%d" % (member.token, rid))
        self.assertEqual(reply, "OK|JOINED|%d|Phong thi|%s|3|120|easy:1,medium:1,hard:1|%s,%s" % (rid, host.username, host.username, member.username))
        self.assertEqual(host.wait_event("EVT|MEMBER_JOINED"), "EVT|MEMBER_JOINED|%d|%s" % (rid, member.username))
        self.assertTrue(member.no_event("EVT|MEMBER_JOINED"))
        self.assertEqual(self.find(host, rid)[6], "2")

    def test_r06_join_started_room(self):
        host = self.user("sh")
        late = self.user("sl")
        rid = self.create_room(host)
        self.server.execute("UPDATE rooms SET status = 'RUNNING', start_ts = strftime('%s','now') WHERE rid = ?", (rid,))
        self.assertErr(late.call("JOIN|%s|%d" % (late.token, rid)), "ROOM_STARTED")
        self.server.execute("UPDATE rooms SET status = 'FINISHED' WHERE rid = ?", (rid,))
        self.assertErr(late.call("JOIN|%s|%d" % (late.token, rid)), "ROOM_STARTED")

    def test_r07_join_twice(self):
        host = self.user("th")
        member = self.user("tm")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        self.assertErr(member.call("JOIN|%s|%d" % (member.token, rid)), "ALREADY_JOINED")
        self.assertErr(host.call("JOIN|%s|%d" % (host.token, rid)), "ALREADY_JOINED")

    def test_r08_join_missing_room(self):
        member = self.user("nr")
        self.assertErr(member.call("JOIN|%s|999999" % member.token), "NO_ROOM")
        self.assertErr(member.call("JOIN|%s|abc" % member.token), "BAD_ARGS")

    def test_r09_member_leaves_waiting_room(self):
        host = self.user("lh")
        member = self.user("lm")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        host.wait_event("EVT|MEMBER_JOINED")
        self.assertEqual(member.call("LEAVE_ROOM|%s|%d" % (member.token, rid)), "OK|LEFT")
        self.assertEqual(host.wait_event("EVT|MEMBER_LEFT"), "EVT|MEMBER_LEFT|%d|%s" % (rid, member.username))
        self.assertEqual(self.find(host, rid)[6], "1")
        self.assertErr(member.call("LEAVE_ROOM|%s|%d" % (member.token, rid)), "BAD_STATE")

    def test_r10_owner_leave_closes_room(self):
        host = self.user("ch")
        member = self.user("cm")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        self.assertEqual(host.call("LEAVE_ROOM|%s|%d" % (host.token, rid)), "OK|LEFT")
        self.assertEqual(member.wait_event("EVT|ROOM_CLOSED"), "EVT|ROOM_CLOSED|%d" % rid)
        self.assertIsNone(self.find(member, rid))
        self.assertErr(member.call("JOIN|%s|%d" % (member.token, rid)), "NO_ROOM")
        self.create_room(member)

    def test_r11_leave_running_room(self):
        host = self.user("rh")
        member = self.user("rm")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        self.server.execute("UPDATE rooms SET status = 'RUNNING', start_ts = strftime('%s','now') WHERE rid = ?", (rid,))
        self.assertErr(member.call("LEAVE_ROOM|%s|%d" % (member.token, rid)), "BAD_STATE")

    def test_r12_busy_user_cannot_join_or_create(self):
        host_a = self.user("ba")
        host_b = self.user("bb")
        member = self.user("bm")
        rid_a = self.create_room(host_a)
        rid_b = self.create_room(host_b)
        member.call("JOIN|%s|%d" % (member.token, rid_a))
        self.assertErr(member.call("JOIN|%s|%d" % (member.token, rid_b)), "BAD_STATE")
        self.assertErr(member.call("CREATE_ROOM|%s|X|3|120|mixed|all" % member.token), "BAD_STATE")
        self.assertErr(host_a.call("CREATE_ROOM|%s|X|3|120|mixed|all" % host_a.token), "BAD_STATE")

    def test_disconnect_leaves_waiting_room(self):
        host = self.user("dh")
        member = self.user("dm")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        member.close()
        self.assertEqual(host.wait_event("EVT|MEMBER_LEFT"), "EVT|MEMBER_LEFT|%d|%s" % (rid, member.username))

    def test_owner_logout_closes_room(self):
        host = self.user("oh")
        member = self.user("om")
        rid = self.create_room(host)
        member.call("JOIN|%s|%d" % (member.token, rid))
        self.assertEqual(host.call("LOGOUT|" + host.token), "OK|BYE")
        self.assertEqual(member.wait_event("EVT|ROOM_CLOSED"), "EVT|ROOM_CLOSED|%d" % rid)

    def test_l03_room_full(self):
        host = self.user("fh")
        rid = self.create_room(host)
        for _ in range(19):
            joiner = self.user("fj")
            self.assertTrue(joiner.call("JOIN|%s|%d" % (joiner.token, rid)).startswith("OK|JOINED|"))
        extra = self.user("fx")
        self.assertErr(extra.call("JOIN|%s|%d" % (extra.token, rid)), "ROOM_FULL")
        self.assertEqual(self.find(host, rid)[6], "20")


if __name__ == "__main__":
    import unittest
    unittest.main()
