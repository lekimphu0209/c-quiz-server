from dataclasses import dataclass, field


@dataclass
class AppState:
    """Shared application state passed to all screen components."""

    token: str = ""
    username: str = ""
    role: str = "user"
    room_id: int = None
    room_name: str = ""
    room_owner: str = ""
    room_meta: dict = field(default_factory=dict)
    exam: dict = field(default_factory=dict)
    last_result: dict = field(default_factory=dict)

    def clear(self):
        self.token = ""
        self.username = ""
        self.role = "user"
        self.room_id = None
        self.room_name = ""
        self.room_owner = ""
        self.room_meta.clear()
        self.exam.clear()
        self.last_result.clear()
