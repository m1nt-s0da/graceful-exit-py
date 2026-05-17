import signal
import pytest
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
        with GracefulExit(sigint=True, sigint_handler=on_sigint) as graceful_exit:
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

    with GracefulExit(sigint=True, sigint_handler=on_sigint) as graceful_exit:
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
        with GracefulExit(sigint=True, sigint_handler=on_sigint) as graceful_exit:
            with pytest.raises(RuntimeError, match="save failed"):
                graceful_exit._signal_handler(signal.SIGINT, None)

            assert graceful_exit.signals == [signal.SIGINT]
            assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)
