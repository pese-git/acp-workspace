from __future__ import annotations

import shlex
import sys
import time

from acp_client.tui.managers.terminal import LocalTerminalManager


def test_terminal_manager_create_output_wait_and_release() -> None:
    manager = LocalTerminalManager()
    command = f"{shlex.quote(sys.executable)} -c \"print('hello from terminal')\""

    terminal_id = manager.create_terminal(command)

    output = ""
    for _ in range(40):
        output += manager.get_output(terminal_id)
        wait_result = manager.wait_for_exit(terminal_id)
        if isinstance(wait_result, int):
            break
        time.sleep(0.02)

    assert "hello from terminal" in output
    wait_result = manager.wait_for_exit(terminal_id)
    assert wait_result == 0

    manager.release_terminal(terminal_id)


def test_terminal_manager_kill_running_process() -> None:
    manager = LocalTerminalManager()
    command = f'{shlex.quote(sys.executable)} -c "import time; time.sleep(5)"'

    terminal_id = manager.create_terminal(command)
    killed = manager.kill_terminal(terminal_id)

    assert killed is True
    wait_result = manager.wait_for_exit(terminal_id)
    assert isinstance(wait_result, int)
