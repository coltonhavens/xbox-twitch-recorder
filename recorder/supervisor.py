"""Bound the complete worker process group; systemd ExecStopPost powers off the VM."""
import os
import signal
import subprocess
import sys
from .events import emit

MAX_SECONDS = 19800  # 5h30; systemd and native GCE stop have additional margin.


def terminate_group(child):
    # A departed leader can leave FFmpeg/yt-dlp descendants in the same group.
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        child.wait(timeout=10)
        return
    try:
        child.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait(timeout=10)


def supervise(command, seconds=MAX_SECONDS):
    if not 0 < seconds <= MAX_SECONDS:
        raise ValueError('Invalid runtime limit')
    child = None
    def interrupted(*_):
        raise InterruptedError('Supervisor termination')
    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        emit('run_started')
        child = subprocess.Popen(command, start_new_session=True, stdin=subprocess.DEVNULL)
        status = child.wait(timeout=seconds)
        emit('run_finished' if status == 0 else 'run_failed', 'INFO' if status == 0 else 'ERROR', exit_status=status)
        return status
    except subprocess.TimeoutExpired:
        terminate_group(child)
        emit('runtime_limit', 'ERROR', seconds=seconds)
        return 124
    except Exception as exc:
        emit('supervisor_failed', 'ERROR', error_type=type(exc).__name__)
        return 1
    finally:
        # Stop children before guest poweroff; preserve already committed state/media.
        if child:
            terminate_group(child)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    raise SystemExit(supervise([sys.executable, '-m', 'recorder.worker']))


if __name__ == '__main__':
    main()
