# graceful-exit

graceful-exit is a small utility for handling SIGINT and SIGTERM in long-running loops.

The main use case is work that should not be interrupted in the middle of a step, such as training loops, batch processing, or checkpointed computation.

A typical flow looks like this:

- the first signal marks that the current run should stop gracefully
- the current step is allowed to finish
- the program saves state or writes a checkpoint
- the loop exits cleanly
- if the same signal arrives again before the step completes, the original signal handler is restored and the process is interrupted immediately

## Installation

```bash
pip install git+https://github.com/m1nt-s0da/graceful-exit-py.git
```

## Why this package exists

In long-running loops, immediate interruption is often the wrong behavior.

For example, in a machine learning training loop you may want to:

1. receive a signal during a step
2. finish the current step without corrupting state
3. save a checkpoint
4. exit after the step boundary

At the same time, if the user or process manager sends the signal again, the program should stop immediately instead of waiting again.

graceful-exit is built around that one-shot pattern.

## Basic usage

```python
from graceful_exit import GracefulExit

with GracefulExit(sigint=True) as graceful_exit:
    for epoch in range(100):
        run_training_step(epoch)

        if graceful_exit.signals:
            save_checkpoint(epoch)
            break
```

In this example:

- the first SIGINT is recorded in graceful_exit.signals
- the current step is allowed to finish
- at the step boundary, the loop checks whether a signal has been received
- if so, the program saves state and exits the loop
- a second SIGINT during the same step uses the restored original handler and interrupts immediately

## Persisting the custom handler

If your handler returns "persist", graceful-exit keeps its own signal handler installed.

```python
from graceful_exit import GracefulExit

received = 0


def on_signal(signum, frame):
    global received
    received += 1
    return "persist"


with GracefulExit(sigint=True, handler=on_signal):
    do_work()
```

Use this only if you want repeated signals to continue going through the custom handler instead of falling back to the original handler.

## Handling SIGTERM

SIGINT is the most common choice for interactive interruption such as Ctrl+C.

SIGTERM is useful when the process is managed externally, for example by:

- containers
- service managers
- job schedulers
- supervisors

You can enable either signal or both:

```python
from graceful_exit import GracefulExit


def on_signal(signum, frame):
    request_shutdown()


with GracefulExit(sigint=True, sigterm=True, handler=on_signal):
    run_one_step()
```

The same handler receives the signal number, so the caller can still branch on SIGINT and SIGTERM when needed.

## API

### GracefulExit

```python
GracefulExit(*, sigint=True, sigterm=False, handler=...)
```

Arguments:

- sigint: enable SIGINT handling
- sigterm: enable SIGTERM handling
- handler: called as handler(signum, frame)

Each instance is single-use. Create a new GracefulExit for each loop or run.

Handler behavior:

- returning None means the package restores the previous handler after the signal
- returning "persist" keeps the package handler installed
- if the handler raises an exception, the previous handler is still restored unless persistence was requested before the exception

### signals

The signals property returns a copy of the received signal numbers.

```python
from graceful_exit import GracefulExit

with GracefulExit(sigint=True) as graceful_exit:
    do_work()

print(graceful_exit.signals)
```

## Constraints

- signal handlers are installed only from the main thread
- signal handlers are removed only from the main thread
- each GracefulExit instance is intended for one start/stop lifecycle only
- this package is aimed at step-based graceful shutdown, not arbitrary cross-thread signaling

## Recommended pattern

Use GracefulExit around a loop whose iteration boundary is safe for checkpointing or cleanup.

Examples:

- a training loop with one step per iteration
- a batch processing loop
- a data processing loop with explicit chunk boundaries
- a long-running job with periodic checkpoint points

That lets each iteration finish cleanly, keeps the shutdown check at a predictable boundary, and still allows a second signal to interrupt immediately.
