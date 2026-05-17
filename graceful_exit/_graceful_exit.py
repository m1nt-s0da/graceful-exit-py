import signal
from typing import Protocol, Literal
import threading

__all__ = ["GracefulExit", "SignalHandler"]


class SignalHandler(Protocol):
    def __call__(self, signum: int, frame) -> None | Literal["persist"]: ...


class GracefulExit:
    def __init__(
        self,
        *,
        sigint=True,
        sigterm=False,
        sigint_handler: SignalHandler | None = None,
        sigterm_handler: SignalHandler | None = None,
    ):
        if sigint is False and sigint_handler is not None:
            raise ValueError("SIGINT handler provided but SIGINT handling is disabled.")
        if sigterm is False and sigterm_handler is not None:
            raise ValueError(
                "SIGTERM handler provided but SIGTERM handling is disabled."
            )

        self._sigint = sigint
        self._sigterm = sigterm
        self._old_sigint_handler = None
        self._old_sigterm_handler = None
        self._signals: list[int] = []
        self._sigint_handler = sigint_handler
        self._sigterm_handler = sigterm_handler
        self._signals_lock = threading.Lock()
        self._sigint_handler_set = False
        self._sigterm_handler_set = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    @property
    def signals(self):
        with self._signals_lock:
            return list(self._signals)

    def _signal_handler(self, signum, frame):
        with self._signals_lock:
            self._signals.append(signum)

        should_persist = False
        try:
            if signum == signal.SIGINT and self._sigint_handler is not None:
                should_persist = self._sigint_handler(signum, frame) == "persist"
            if signum == signal.SIGTERM and self._sigterm_handler is not None:
                should_persist = self._sigterm_handler(signum, frame) == "persist"
        finally:
            if not should_persist:
                self._remove_handler(signum)

    def start(self):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Signal handlers can only be set in the main thread.")

        installed_sigint = False
        installed_sigterm = False

        try:
            if self._sigint:
                if self._sigint_handler_set:
                    raise RuntimeError("SIGINT handler is already set.")

                self._old_sigint_handler = signal.signal(
                    signal.SIGINT, self._signal_handler
                )
                self._sigint_handler_set = True
                installed_sigint = True

            if self._sigterm:
                if self._sigterm_handler_set:
                    raise RuntimeError("SIGTERM handler is already set.")

                self._old_sigterm_handler = signal.signal(
                    signal.SIGTERM, self._signal_handler
                )
                self._sigterm_handler_set = True
                installed_sigterm = True
        except Exception:
            if installed_sigterm:
                self._remove_handler(signal.SIGTERM)
            if installed_sigint:
                self._remove_handler(signal.SIGINT)
            raise

    def stop(self):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError(
                "Signal handlers can only be removed in the main thread."
            )

        if self._sigint:
            self._remove_handler(signal.SIGINT)

        if self._sigterm:
            self._remove_handler(signal.SIGTERM)

    def _remove_handler(self, signum: int):
        if signum == signal.SIGINT and self._sigint_handler_set:
            signal.signal(signal.SIGINT, self._old_sigint_handler)
            self._old_sigint_handler = None
            self._sigint_handler_set = False

        elif signum == signal.SIGTERM and self._sigterm_handler_set:
            signal.signal(signal.SIGTERM, self._old_sigterm_handler)
            self._old_sigterm_handler = None
            self._sigterm_handler_set = False
