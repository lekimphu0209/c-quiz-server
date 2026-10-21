import os
import tempfile

from quiz import QuizTestCase

VALID_ADD = "ADD_QUESTION|%s|Noi dung?|A|B|C|D|1|easy|net|giai thich"


class QuestionTest(QuizTestCase):
    def write_csv(self, text):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_q01_seeded_bank_listed(self):
        admin = self.admin()
        reply = admin.call("LIST_QUESTIONS|" + admin.token)
        rows = reply.split("|")[1:]
        self.assertEqual(reply.split("|")[0], "OK")
        self.assertGreaterEqual(len(rows), 30)
        self.assertEqual(len(rows[0].split(":")), 5)
        self.assertIn("seeded 30 questions", self.server.log_text())

    def test_q02_admin_adds_question(self):
        admin = self.admin()
        reply = admin.call(VALID_ADD % admin.token)
        self.assertRegex(reply, r"^OK\|\d+$")
        qid = int(reply.split("|")[1])
        rows = self.server.query("SELECT content, correct_opt, difficulty, topic, explanation FROM questions WHERE qid = ?", (qid,))
        self.assertEqual(rows, [("Noi dung?", 1, "easy", "net", "giai thich")])

    def test_add_without_explanation(self):
        admin = self.admin()
        self.assertRegex(admin.call("ADD_QUESTION|%s|Q?|A|B|C|D|0|hard|os|" % admin.token), r"^OK\|\d+$")
        self.assertRegex(admin.call("ADD_QUESTION|%s|Q?|A|B|C|D|0|hard|os" % admin.token), r"^OK\|\d+$")

    def test_add_rejects_invalid_fields(self):
        admin = self.admin()
        self.assertErr(admin.call("ADD_QUESTION|%s|Q?|A|B|C|D|5|easy|net|x" % admin.token), "BAD_ARGS")
        self.assertErr(admin.call("ADD_QUESTION|%s|Q?|A|B|C|D|1|insane|net|x" % admin.token), "BAD_ARGS")
        self.assertErr(admin.call("ADD_QUESTION|%s||A|B|C|D|1|easy|net|x" % admin.token), "BAD_ARGS")
        self.assertErr(admin.call("ADD_QUESTION|%s|Q?|A||C|D|1|easy|net|x" % admin.token), "BAD_ARGS")
        self.assertErr(admin.call("ADD_QUESTION|%s|Q?|A|B|C|D|x|easy|net|x" % admin.token), "BAD_ARGS")
        self.assertErr(admin.call("ADD_QUESTION|%s|Q?|A|B" % admin.token), "BAD_ARGS")

    def test_q03_admin_deletes_question(self):
        admin = self.admin()
        qid = admin.call(VALID_ADD % admin.token).split("|")[1]
        self.assertEqual(admin.call("DEL_QUESTION|%s|%s" % (admin.token, qid)), "OK")
        self.assertEqual(self.server.query("SELECT COUNT(*) FROM questions WHERE qid = ?", (qid,)), [(0,)])
        self.assertErr(admin.call("DEL_QUESTION|%s|%s" % (admin.token, qid)), "NOTFOUND")
        self.assertErr(admin.call("DEL_QUESTION|%s|abc" % admin.token), "BAD_ARGS")

    def test_q04_import_csv(self):
        admin = self.admin()
        path = self.write_csv("Cau 1?;A;B;C;D;0;easy;csv;giai thich\r\n\nbad line\nCau 2?;A;B;C;D;3;hard;csv;\n")
        self.assertEqual(admin.call("IMPORT_CSV|%s|%s" % (admin.token, path)), "OK|2")
        self.assertEqual(self.server.query("SELECT COUNT(*) FROM questions WHERE topic = 'csv'"), [(2,)])

    def test_import_missing_file(self):
        admin = self.admin()
        self.assertErr(admin.call("IMPORT_CSV|%s|/no/such/file.csv" % admin.token), "NOTFOUND")

    def test_import_all_invalid(self):
        admin = self.admin()
        path = self.write_csv("not;enough;fields\nQ;A;B;C;D;9;easy;x;y\n")
        self.assertErr(admin.call("IMPORT_CSV|%s|%s" % (admin.token, path)), "BAD_ARGS")

    def test_q05_escaped_content_decoded(self):
        admin = self.admin()
        reply = admin.call("ADD_QUESTION|%s|2%%7C2=?%%0Adong 2|A%%7Cx|B|C|D|2|medium|net|" % admin.token)
        qid = int(reply.split("|")[1])
        rows = self.server.query("SELECT content, opt_a FROM questions WHERE qid = ?", (qid,))
        self.assertEqual(rows, [("2|2=?\ndong 2", "A|x")])
        listing = admin.call("LIST_QUESTIONS|" + admin.token)
        self.assertIn("%d:2%%7C2=?%%0Adong 2:2:medium:net" % qid, listing)

    def test_a10_user_cannot_use_admin_commands(self):
        user = self.user("plain")
        self.assertErr(user.call(VALID_ADD % user.token), "FORBIDDEN")
        self.assertErr(user.call("LIST_QUESTIONS|" + user.token), "FORBIDDEN")
        self.assertErr(user.call("DEL_QUESTION|%s|1" % user.token), "FORBIDDEN")
        self.assertErr(user.call("IMPORT_CSV|%s|/tmp/x.csv" % user.token), "FORBIDDEN")

    def test_admin_command_needs_token(self):
        self.assertErr(self.connect().call("LIST_QUESTIONS|" + "f" * 32), "NOT_AUTHENTICATED")


if __name__ == "__main__":
    import unittest
    unittest.main()
