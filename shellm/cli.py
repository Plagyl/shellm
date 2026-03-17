from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

try:
    from prompt_toolkit import PromptSession
except ImportError:
    import getpass

    class PromptSession:
        def prompt(self, message: str, is_password: bool = False) -> str:
            if is_password:
                return getpass.getpass(message)
            return input(message)

from shellm.config import configure, is_configured, load_config
from shellm.providers import get_shell_command
from shellm.security import is_sensitive

QUIT_COMMANDS = {"/exit", "/quit"}


def main() -> None:
    session = PromptSession()
    config = load_config()
    cwd = Path.cwd()
    previous_cwd: Path | None = None

    if not is_configured(config):
        print("Missing configuration. Let's set up your API key.")
        try:
            config = configure(session, config)
        except (EOFError, KeyboardInterrupt):
            print()
            return

    print_header(config, cwd)

    while True:
        try:
            user_input = session.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not user_input:
            continue
        if user_input in QUIT_COMMANDS:
            return
        if user_input == "/config":
            try:
                config = configure(session, config)
            except (EOFError, KeyboardInterrupt):
                print()
            print_header(config, cwd)
            continue

        try:
            command = get_shell_command(config, str(cwd), user_input)
        except Exception as exc:
            print(f"Provider error: {exc}", file=sys.stderr)
            continue

        print(command)

        if command == "#AMBIGUOUS":
            print("Ambiguous request.")
            continue

        if is_sensitive(command):
            print("Sensitive command detected.")
            answer = session.prompt("Confirm? [y/N] ").strip().lower()
            if answer not in {"y", "yes"}:
                print("Cancelled.")
                continue

        if _is_cd(command):
            cwd, previous_cwd = _change_directory(command, cwd, previous_cwd)
            continue

        _run(command, cwd, previous_cwd)


def print_header(config: dict[str, str], cwd: Path) -> None:
    provider = config.get("PROVIDER", "?") or "?"
    model = config.get("MODEL", "?") or "?"
    print(f"[provider: {provider} | model: {model} | cwd: {_display_path(cwd)}]")


def _display_path(path: Path) -> str:
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}" if path != home else "~"
    except ValueError:
        return str(path)


def _is_cd(command: str) -> bool:
    parts = _split_command(command)
    return bool(parts and parts[0] == "cd" and _cd_target(parts) is not None)


def _change_directory(command: str, cwd: Path, previous_cwd: Path | None) -> tuple[Path, Path | None]:
    parts = _split_command(command, report_errors=True)
    if not parts:
        return cwd, previous_cwd

    target_text = _cd_target(parts)
    if target_text is None:
        print("cd: too many arguments", file=sys.stderr)
        return cwd, previous_cwd
    if target_text == "":
        print("cd: empty path", file=sys.stderr)
        return cwd, previous_cwd

    if target_text == "-":
        if previous_cwd is None:
            print("cd: OLDPWD not set", file=sys.stderr)
            return cwd, previous_cwd
        target = previous_cwd
        label = "-"
    else:
        target = _expand_cd_target(target_text, cwd)
        label = target_text or "~"

    if not target.exists():
        print(f"cd: no such file or directory: {label}", file=sys.stderr)
        return cwd, previous_cwd
    if not target.is_dir():
        print(f"cd: not a directory: {label}", file=sys.stderr)
        return cwd, previous_cwd

    next_cwd = Path(os.path.abspath(str(target)))
    print(f"[cwd: {_display_path(next_cwd)}]")
    return next_cwd, cwd


def _run(command: str, cwd: Path, previous_cwd: Path | None) -> None:
    env = os.environ.copy()
    env["PWD"] = str(cwd)
    if previous_cwd is not None:
        env["OLDPWD"] = str(previous_cwd)

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            shell=True,
            executable="/bin/bash",
        )
    except KeyboardInterrupt:
        print()
        return

    if completed.returncode != 0:
        print(f"[exit: {completed.returncode}]")


def _split_command(command: str, report_errors: bool = False) -> list[str] | None:
    try:
        return shlex.split(command)
    except ValueError as exc:
        if report_errors:
            print(f"cd parse error: {exc}", file=sys.stderr)
        return None


def _cd_target(parts: list[str]) -> str | None:
    if len(parts) == 1:
        return str(Path.home())
    if len(parts) == 2:
        return str(Path.home()) if parts[1] == "--" else parts[1]
    if len(parts) == 3 and parts[1] == "--":
        return parts[2]
    return None


def _expand_cd_target(target: str, cwd: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(target))
    if not os.path.isabs(expanded):
        expanded = os.path.join(str(cwd), expanded)
    return Path(expanded)
