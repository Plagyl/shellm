from __future__ import annotations

import json
from importlib.resources import files
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import httpx
except ImportError:
    httpx = None

PROMPT_TEMPLATE = files("shellm.prompts").joinpath("shell_command.txt").read_text(encoding="utf-8")


def get_shell_command(config: dict[str, str], cwd: str, user_input: str) -> str:
    prompt = PROMPT_TEMPLATE.format(cwd=cwd, user_input=user_input)
    provider = config.get("PROVIDER", "").strip().lower()
    model = config.get("MODEL", "").strip()

    if provider == "openai":
        text = _call_openai(model, config["OPENAI_API_KEY"], prompt)
    elif provider == "anthropic":
        text = _call_anthropic(model, config["ANTHROPIC_API_KEY"], prompt)
    elif provider == "google":
        text = _call_google(model, config["GOOGLE_API_KEY"], prompt)
    else:
        raise RuntimeError(f"Unsupported provider: {provider}")

    return _normalize_reply(text)


def _call_openai(model: str, api_key: str, prompt: str) -> str:
    data = _post_json(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json_body={
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    return data["choices"][0]["message"]["content"]


def _call_anthropic(model: str, api_key: str, prompt: str) -> str:
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json_body={
            "model": model,
            "max_tokens": 128,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    return data["content"][0]["text"]


def _call_google(model: str, api_key: str, prompt: str) -> str:
    data = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json_body={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        },
        timeout=60,
    )
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _post_json(
    url: str,
    headers: dict[str, str],
    json_body: dict,
    timeout: int,
    params: dict[str, str] | None = None,
) -> dict:
    if httpx is not None:
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=json_body,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Request failed: {exc}") from exc

    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(
        url,
        data=json.dumps(json_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Request failed: HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc


def _normalize_reply(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1]).strip()

    if cleaned == "#AMBIGUOUS":
        return cleaned

    for line in cleaned.splitlines():
        line = line.strip()
        if line:
            return line

    return "#AMBIGUOUS"
