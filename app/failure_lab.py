import threading
import time

from pydantic import BaseModel


class FailureLabToggle(BaseModel):
    enabled: bool


class FailureLab:
    """Process-local lost-response injector for the first booking of a key.

    The calendar commit and event timeline stay outside this class. After a
    first matching booking succeeds, `claim_delay` marks that idempotency key
    so only that attempt sleeps past the configured Retell timeout. A retry
    for the same key returns immediately because it never claims the delay.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float,
        delay_seconds: float,
        enabled: bool = False,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self._enabled = enabled
        self._delayed_keys: set[str] = set()
        self._lock = threading.Lock()

    def snapshot(self) -> dict[str, bool | float]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "timeout_seconds": self.timeout_seconds,
                "delay_seconds": self.delay_seconds,
            }

    def set_enabled(self, enabled: bool) -> dict[str, bool | float]:
        with self._lock:
            self._enabled = enabled
            return {
                "enabled": self._enabled,
                "timeout_seconds": self.timeout_seconds,
                "delay_seconds": self.delay_seconds,
            }

    def reset_attempts(self) -> None:
        """Forget delayed keys so a restored demo can inject the timeout again."""
        with self._lock:
            self._delayed_keys.clear()

    def claim_delay(self, idempotency_key: str | None) -> bool:
        """Reserve the artificial delay for this key's first successful create."""
        if not idempotency_key:
            return False
        with self._lock:
            if not self._enabled or idempotency_key in self._delayed_keys:
                return False
            self._delayed_keys.add(idempotency_key)
            return True

    def wait_if_delayed(self, delayed: bool) -> None:
        if delayed:
            time.sleep(self.delay_seconds)
