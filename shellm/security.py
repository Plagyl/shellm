from __future__ import annotations

import re
import shlex

SENSITIVE_COMMANDS = {
    "rm",
    "sudo",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "chown",
    "chmod",
}
PIPE_PATTERNS = (
    re.compile(r"\bcurl\b[^\n|]*\|\s*(bash|sh)\b"),
    re.compile(r"\bwget\b[^\n|]*\|\s*(bash|sh)\b"),
)


def is_sensitive(command: str) -> bool:
    lowered = command.lower()
    if any(pattern.search(lowered) for pattern in PIPE_PATTERNS):
        return True

    for name in SENSITIVE_COMMANDS:
        if re.search(rf"(^|[;&|])\s*{re.escape(name)}\b", lowered):
            return True

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    return bool(tokens and tokens[0].lower() in SENSITIVE_COMMANDS)
