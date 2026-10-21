"""Socket test harness: spawns ./server on a free port with a throw-away exam.db."""

import os
import shlex
import shutil
import signal
import socket
import sqlite3
import struct
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRAPPER = shlex.split(os.environ.get("SERVER_WRAPPER", ""))
TIMEOUT = float(os.environ.get("QUIZ_TIMEOUT", "30" if WRAPPER else "5"))
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def frame(payload):
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    return struct.pack("!I", len(data)) + data


class ServerProcess:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="quiz_it_")
        self.db_path = os.path.join(self.tmp, "exam.db")
        self.log_path = os.path.join(self.tmp, "server.log")
        self.err_path = os.path.join(self.tmp, "stderr.log")
        self.port = free_port()
        self.proc = None
        self.err_file = None

    def start(self):
        env = dict(os.environ, DB_PATH=self.db_path, LOG_PATH=self.log_path, PORT=str(self.port))
        self.err_file = open(self.err_path, "wb")
        cmd = WRAPPER + [os.path.join(ROOT, "server")]
        self.proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=self.err_file)
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("server exited early: " + self.stderr())
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.5).close()
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("server did not start")

    def stop(self):
        self.proc.send_signal(signal.SIGTERM)
        code = self.proc.wait(timeout=TIMEOUT * 2)
        self.err_file.close()
        report = self.stderr()
        log_dir = os.environ.get("VALGRIND_LOG_DIR")
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            shutil.copy(self.err_path, os.path.join(log_dir, "server_%d.log" % self.port))
        shutil.rmtree(self.tmp, ignore_errors=True)
        if code != 0:
            raise AssertionError("server exit code %d\n%s" % (code, report[-4000:]))

    def stderr(self):
        with open(self.err_path, "r", errors="replace") as handle:
            return handle.read()

    def log_text(self):
        with open(self.log_path, "r", errors="replace") as handle:
            return handle.read()

    def query(self, sql, params=()):
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            return conn.execute(sql, params).fetchall()

    def execute(self, sql, params=()):
        with sqlite3.connect(self.db_path, timeout=5) as conn:
            conn.execute(sql, params)
            conn.commit()


class Client:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT)
        self.events = []
        self.token = None
        self.username = None

    def send(self, payload):
        self.sock.sendall(frame(payload))

    def send_raw(self, data):
        self.sock.sendall(data)

    def _recv_exact(self, count):
        data = b""
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise ConnectionError("server closed connection")
            data += chunk
        return data

    def recv(self):
        (length,) = struct.unpack("!I", self._recv_exact(4))
        return self._recv_exact(length).decode("utf-8")

    def call(self, payload):
        self.send(payload)
        while True:
            reply = self.recv()
            if not reply.startswith("EVT|"):
                return reply
            self.events.append(reply)

    def wait_event(self, prefix, timeout=None):
        deadline = time.time() + (timeout or TIMEOUT)
        while True:
            for index, event in enumerate(self.events):
                if event.startswith(prefix):
                    return self.events.pop(index)
            remaining = deadline - time.time()
            if remaining <= 0:
                raise AssertionError("no event %s, got %r" % (prefix, self.events))
            self.sock.settimeout(remaining)
            try:
                self.events.append(self.recv())
            except socket.timeout:
                pass
            finally:
                self.sock.settimeout(TIMEOUT)

    def no_event(self, prefix, wait=0.4):
        self.sock.settimeout(wait)
        try:
            self.events.append(self.recv())
        except socket.timeout:
            pass
        finally:
            self.sock.settimeout(TIMEOUT)
        return not any(event.startswith(prefix) for event in self.events)

    def is_closed(self):
        try:
            return self.sock.recv(1) == b""
        except OSError:
            return True

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class QuizTestCase(unittest.TestCase):
    server = None
    _counter = 0
    _counter_lock = threading.Lock()

    @classmethod
    def setUpClass(cls):
        cls.server = ServerProcess()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()

    def connect(self):
        client = Client(self.server.port)
        self.clients.append(client)
        return client

    def unique(self, prefix="u"):
        with QuizTestCase._counter_lock:
            QuizTestCase._counter += 1
            return "%s%d" % (prefix, QuizTestCase._counter)

    def login(self, username, password="123456", client=None):
        client = client or self.connect()
        deadline = time.time() + TIMEOUT
        reply = client.call("LOGIN|%s|%s" % (username, password))
        while reply.startswith("ERR|ALREADY_LOGGED_IN|") and time.time() < deadline:
            time.sleep(0.05)
            reply = client.call("LOGIN|%s|%s" % (username, password))
        self.assertTrue(reply.startswith("OK|"), reply)
        client.token = reply.split("|")[1]
        client.username = username
        return client

    def user(self, prefix="u", password="123456"):
        username = self.unique(prefix)
        client = self.connect()
        self.assertEqual(client.call("REGISTER|%s|%s" % (username, password)), "OK|REGISTERED")
        return self.login(username, password, client)

    def create_room(self, host, n=3, sec=120, cfg="mixed", topic="all", name="Phong thi"):
        reply = host.call("CREATE_ROOM|%s|%s|%d|%d|%s|%s" % (host.token, name, n, sec, cfg, topic))
        self.assertRegex(reply, r"^OK\|\d+$")
        return int(reply.split("|")[1])

    def admin(self):
        return self.login(ADMIN_USER, ADMIN_PASS)

    def assertErr(self, reply, code):
        self.assertTrue(reply.startswith("ERR|%s|" % code), "expected ERR|%s, got %r" % (code, reply))
