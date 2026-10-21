import threading

from quiz import QuizTestCase


class AuthTest(QuizTestCase):
    def test_a01_register_stores_salted_hash(self):
        name = self.unique("reg")
        self.assertEqual(self.connect().call("REGISTER|%s|123456" % name), "OK|REGISTERED")
        rows = self.server.query("SELECT pass_hash, salt, role FROM users WHERE username = ?", (name,))
        self.assertEqual(len(rows), 1)
        pass_hash, salt, role = rows[0]
        self.assertRegex(pass_hash, r"^[0-9a-f]{64}$")
        self.assertRegex(salt, r"^[0-9a-f]{16}$")
        self.assertEqual(role, "user")
        self.assertNotIn("123456", pass_hash)

    def test_a02_duplicate_username(self):
        name = self.unique("dup")
        client = self.connect()
        self.assertEqual(client.call("REGISTER|%s|123456" % name), "OK|REGISTERED")
        self.assertErr(client.call("REGISTER|%s|abcdef" % name), "USER_EXISTS")

    def test_a03_bad_username(self):
        client = self.connect()
        self.assertErr(client.call("REGISTER|ab|123456"), "BAD_ARGS")
        self.assertErr(client.call("REGISTER|a b|123456"), "BAD_ARGS")
        self.assertErr(client.call("REGISTER|%s|123456" % ("x" * 21)), "BAD_ARGS")

    def test_a04_short_password(self):
        self.assertErr(self.connect().call("REGISTER|%s|123" % self.unique("pw")), "BAD_ARGS")

    def test_a05_login_success(self):
        client = self.user("ok")
        self.assertRegex(client.token, r"^[0-9a-f]{32}$")

    def test_a06_wrong_password(self):
        name = self.unique("wp")
        self.connect().call("REGISTER|%s|123456" % name)
        self.assertErr(self.connect().call("LOGIN|%s|sai" % name), "BAD_CREDENTIALS")

    def test_a07_unknown_user(self):
        self.assertErr(self.connect().call("LOGIN|nobody_x|123456"), "BAD_CREDENTIALS")

    def test_a08_double_login(self):
        first = self.user("dbl")
        self.assertErr(self.connect().call("LOGIN|%s|123456" % first.username), "ALREADY_LOGGED_IN")

    def test_login_twice_same_connection(self):
        first = self.user("same")
        other = self.unique("same")
        self.connect().call("REGISTER|%s|123456" % other)
        self.assertErr(first.call("LOGIN|%s|123456" % other), "ALREADY_LOGGED_IN")

    def test_a12_unknown_command(self):
        self.assertErr(self.connect().call("FOO|x"), "UNKNOWN_CMD")

    def test_a13_logout_invalidates_token(self):
        client = self.user("out")
        self.assertEqual(client.call("LOGOUT|" + client.token), "OK|BYE")
        self.assertErr(client.call("LOGOUT|" + client.token), "NOT_AUTHENTICATED")

    def test_logout_bad_token(self):
        client = self.user("bad")
        self.assertErr(client.call("LOGOUT|" + "0" * 32), "NOT_AUTHENTICATED")
        self.assertErr(client.call("LOGOUT"), "NOT_AUTHENTICATED")

    def test_token_bound_to_connection(self):
        owner = self.user("own")
        thief = self.connect()
        self.assertErr(thief.call("LOGOUT|" + owner.token), "NOT_AUTHENTICATED")

    def test_a14_ping(self):
        self.assertEqual(self.connect().call("PING"), "OK|PONG")

    def test_bad_field_count(self):
        client = self.connect()
        self.assertErr(client.call("REGISTER|onlyname"), "BAD_ARGS")
        self.assertErr(client.call("LOGIN|a|b|c"), "BAD_ARGS")

    def test_a15_log_masks_password(self):
        name = self.unique("log")
        self.connect().call("REGISTER|%s|Sup3rSecretPw" % name)
        self.connect().call("LOGIN|%s|Sup3rSecretPw" % name)
        self.connect().call("LOGIN|%s|WrongSecretPw" % name)
        text = self.server.log_text()
        self.assertIn("user=%s pass=***" % name, text)
        self.assertNotIn("Sup3rSecretPw", text)
        self.assertNotIn("WrongSecretPw", text)

    def test_disconnect_releases_login(self):
        client = self.user("drop")
        client.close()
        for _ in range(50):
            reply = self.connect().call("LOGIN|%s|123456" % client.username)
            if reply.startswith("OK|"):
                return
        self.fail("login still locked after disconnect")

    def test_l01_concurrent_logins(self):
        names = [self.unique("conc") for _ in range(10)]
        for name in names:
            self.connect().call("REGISTER|%s|123456" % name)
        clients = [self.connect() for _ in names]
        replies = [None] * len(names)

        def worker(index):
            replies[index] = clients[index].call("LOGIN|%s|123456" % names[index])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(names))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertTrue(all(reply.startswith("OK|") for reply in replies), replies)
        self.assertEqual(len({reply.split("|")[1] for reply in replies}), len(names))

    def test_l02_concurrent_duplicate_register(self):
        name = self.unique("race")
        clients = [self.connect(), self.connect()]
        replies = [None, None]

        def worker(index):
            replies[index] = clients[index].call("REGISTER|%s|123456" % name)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(reply.split("|")[0] + reply.split("|")[1] for reply in replies), ["ERRUSER_EXISTS", "OKREGISTERED"])

    def test_admin_seeded(self):
        reply = self.connect().call("LOGIN|admin|admin123")
        self.assertTrue(reply.startswith("OK|") and reply.endswith("|admin"), reply)


if __name__ == "__main__":
    import unittest
    unittest.main()
