# shellm

`shellm` is a minimal conversational shell prototype.

It asks an LLM for exactly one shell command, prints it, and then runs it in the current working directory.

## Project tree

```text
shellm/
├── .env.example
├── pyproject.toml
├── README.md
└── shellm
    ├── __init__.py
    ├── cli.py
    ├── config.py
    ├── providers.py
    ├── prompts
    │   ├── __init__.py
    │   └── shell_command.txt
    └── security.py
```

## Install

Python 3.11+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configure

Copy the example file if you want to pre-fill values:

```bash
cp .env.example .env
```

Supported providers:

- `openai`
- `anthropic`
- `google`

Expected `.env` keys:

```env
PROVIDER=
MODEL=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
```

If the config is incomplete, `shellm` asks for the API key first, detects the provider when possible, then suggests a few models for that provider before saving everything to `.env`. When `prompt_toolkit` is available, you can use `Tab` to cycle through the suggested models.

Inside the REPL, use `/config` to update the provider, model, or API key again.

## Run

```bash
shellm
```

Example:

```text
[provider: openai | model: gpt-4o-mini | cwd: ~/project]

> list big files
find . -type f -printf "%s %p\n" | sort -nr | head -20
123456 ./data/big.bin

> go into src
cd src
[cwd: ~/project/src]

> go back
cd -
[cwd: ~/project]

> delete logs
rm -f *.log
Sensitive command detected.
Confirm? [y/N]
```

## Notes

- `cd` is handled locally and updates the current REPL directory.
- Supported local forms are `cd`, `cd <path>`, `cd -- <path>`, and `cd -`.
- `cd` expands `~` and environment variables such as `$HOME`.
- Other commands run through `/bin/bash` with live stdout and stderr.
- The client does the safety check, not the model.
- Sensitive commands require confirmation.
- `prompt_toolkit` and `httpx` are preferred, but the code keeps a small stdlib fallback for bare environments.

## Limits

- This is not a full POSIX shell.
- Quoting and shell edge cases are delegated to `bash`.
- The safety filter is intentionally simple and local.
- Provider API responses are normalized lightly, but this is still an MVP.
