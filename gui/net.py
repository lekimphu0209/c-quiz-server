import socket
import struct
import threading
from PyQt5.QtCore import QThread, pyqtSignal

from proto import build_frame


class NetThread(QThread):
    response = pyqtSignal(str)
    event = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, host="127.0.0.1", port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = None
        self._send_lock = threading.Lock()
        self._running = False

    def connect_server(self, host=None, port=None) -> bool:
        if host:
            self.host = host
        if port:
            self.port = int(port)
        self.close()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
            sock.settimeout(None)  # Blocking in thread
            self.sock = sock
            self._running = True
            if not self.isRunning():
                self.start()
            self.connected.emit()
            return True
        except Exception:
            self.sock = None
            self._running = False
            return False

    def is_connected(self) -> bool:
        return self.sock is not None and self._running

    def send(self, cmd: str) -> bool:
        if not self.is_connected():
            return False
        try:
            data = build_frame(cmd)
            with self._send_lock:
                self.sock.sendall(data)
            return True
        except Exception:
            self.close()
            self.disconnected.emit()
            return False

    def _recv_n(self, n: int) -> bytes:
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def run(self):
        while self._running and self.sock:
            try:
                hdr = self._recv_n(4)
                if not hdr:
                    break
                (length,) = struct.unpack("!I", hdr)
                if length == 0:
                    break
                payload_bytes = self._recv_n(length)
                if not payload_bytes:
                    break
                payload = payload_bytes.decode("utf-8", errors="replace")
                if payload.startswith("EVT|"):
                    self.event.emit(payload)
                else:
                    self.response.emit(payload)
            except Exception:
                break
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.disconnected.emit()

    def close(self):
        self._running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.isRunning():
            self.wait(1000)
