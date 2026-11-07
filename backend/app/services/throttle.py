"""Failed-login counter with a temporary lockout.

In memory and per process on purpose (fine for this single-process app): it resets when the
server restarts and is not shared between workers. A real deployment would keep this in Redis
or the database. Two counters are kept:
  - per (email, IP): stops guessing one account's password, without letting a stranger lock
    the real user out from a different IP;
  - per IP: slows down trying many emails from one address.
"""
import threading
import time
from dataclasses import dataclass, field

from app import config


@dataclass
class _Entry:
    failures: list[float] = field(default_factory=list)  # timestamps inside the window
    locked_until: float = 0.0


class LoginThrottle:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

    @staticmethod
    def _keys(email: str, ip: str) -> list[tuple[str, int]]:
        return [(f"acct:{email}|{ip}", config.LOGIN_MAX_FAILURES),
                (f"ip:{ip}", config.LOGIN_MAX_FAILURES_PER_IP)]

    def retry_after(self, email: str, ip: str) -> int:
        """Seconds until a login may be attempted again (0 = allowed now)."""
        now = self._clock()
        with self._lock:
            waits = [self._entries[k].locked_until - now for k, _ in self._keys(email, ip)
                     if k in self._entries]
        return max([0, *[int(w) + 1 for w in waits if w > 0]])

    def record_failure(self, email: str, ip: str) -> None:
        now = self._clock()
        with self._lock:
            for key, limit in self._keys(email, ip):
                entry = self._entries.setdefault(key, _Entry())
                entry.failures = [t for t in entry.failures if now - t < config.LOGIN_WINDOW_SECONDS]
                entry.failures.append(now)
                if len(entry.failures) >= limit:
                    entry.locked_until = now + config.LOGIN_LOCKOUT_SECONDS
                    entry.failures.clear()

    def record_success(self, email: str, ip: str) -> None:
        with self._lock:
            self._entries.pop(f"acct:{email}|{ip}", None)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()


login_throttle = LoginThrottle()
