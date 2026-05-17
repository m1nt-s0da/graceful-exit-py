import signal
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graceful_exit import GracefulExit


@pytest.fixture(autouse=True)
def restore_signal_handlers():
    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)


def test_first_sigint_sets_flag_and_second_sigint_raises_keyboard_interrupt():
    should_stop = False
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.default_int_handler)

    def on_sigint(signum, frame):
        nonlocal should_stop
        should_stop = True

    try:
        with GracefulExit(sigint=True, handler=on_sigint) as graceful_exit:
            graceful_exit._signal_handler(signal.SIGINT, None)

            assert should_stop is True
            assert graceful_exit.signals == [signal.SIGINT]
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler

            with pytest.raises(KeyboardInterrupt):
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)


def test_persist_keeps_custom_handler_installed_for_following_sigint():
    handled = 0

    def on_sigint(signum, frame):
        nonlocal handled
        handled += 1
        return "persist"

    with GracefulExit(sigint=True, handler=on_sigint) as graceful_exit:
        graceful_exit._signal_handler(signal.SIGINT, None)
        graceful_exit._signal_handler(signal.SIGINT, None)

        assert handled == 2
        assert graceful_exit.signals == [signal.SIGINT, signal.SIGINT]
        assert signal.getsignal(signal.SIGINT) == graceful_exit._signal_handler


def test_handler_exception_still_restores_previous_sigint_handler():
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.default_int_handler)

    def on_sigint(signum, frame):
        raise RuntimeError("save failed")

    try:
        with GracefulExit(sigint=True, handler=on_sigint) as graceful_exit:
            with pytest.raises(RuntimeError, match="save failed"):
                graceful_exit._signal_handler(signal.SIGINT, None)

            assert graceful_exit.signals == [signal.SIGINT]
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)


def test_shared_handler_handles_sigterm_once_then_restores_previous_handler():
    received = []
    original_sigterm_handler = signal.getsignal(signal.SIGTERM)

    def on_signal(signum, frame):
        received.append(signum)

    try:
        with GracefulExit(
            sigint=False, sigterm=True, handler=on_signal
        ) as graceful_exit:
            graceful_exit._signal_handler(signal.SIGTERM, None)

            assert received == [signal.SIGTERM]
            assert graceful_exit.signals == [signal.SIGTERM]
            assert signal.getsignal(signal.SIGTERM) is original_sigterm_handler
    finally:
        signal.signal(signal.SIGTERM, original_sigterm_handler)


def test_init_rejects_when_no_signal_is_enabled():
    with pytest.raises(
        ValueError, match="At least one of sigint or sigterm must be True"
    ):
        GracefulExit(sigint=False, sigterm=False)


def test_first_sigint_without_custom_handler_marks_signal_and_second_raises():
    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.default_int_handler)

    try:
        with GracefulExit(sigint=True) as graceful_exit:
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

            assert graceful_exit.signals == [signal.SIGINT]
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler

            with pytest.raises(KeyboardInterrupt):
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)


def test_instance_cannot_be_reused_after_stop():
    graceful_exit = GracefulExit(sigint=True)

    graceful_exit.start()
    graceful_exit.stop()

    with pytest.raises(RuntimeError, match="cannot be reused"):
        graceful_exit.start()
