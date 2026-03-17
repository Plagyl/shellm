from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

ENV_FILE = Path(".env")
PROVIDERS = ("openai", "anthropic", "google")
ENV_KEYS = (
    "PROVIDER",
    "MODEL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
)
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "google": "gemini-1.5-flash",
}
API_KEY_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def load_config(env_file: Path = ENV_FILE) -> dict[str, str]:
    load_dotenv(env_file, override=False)
    return {key: os.getenv(key, "").strip() for key in ENV_KEYS}


def save_config(config: dict[str, str], env_file: Path = ENV_FILE) -> None:
    env_file.touch(exist_ok=True)
    for key in ENV_KEYS:
        set_key(str(env_file), key, config.get(key, ""))


def selected_api_key(config: dict[str, str]) -> str:
    provider = config.get("PROVIDER", "").strip().lower()
    key_name = API_KEY_BY_PROVIDER.get(provider, "")
    return config.get(key_name, "").strip()


def is_configured(config: dict[str, str]) -> bool:
    provider = config.get("PROVIDER", "").strip().lower()
    if provider not in PROVIDERS:
        return False
    if not config.get("MODEL", "").strip():
        return False
    return bool(selected_api_key(config))


def configure(session, config: dict[str, str], env_file: Path = ENV_FILE) -> dict[str, str]:
    provider_default = config.get("PROVIDER", "").strip().lower() or "openai"
    provider = _prompt_provider(session, provider_default)

    model_default = config.get("MODEL", "").strip()
    if not model_default or provider != provider_default:
        model_default = DEFAULT_MODELS[provider]
    model = session.prompt(f"Model [{model_default}]: ").strip() or model_default

    api_key_name = API_KEY_BY_PROVIDER[provider]
    existing_key = config.get(api_key_name, "").strip()
    while True:
        prompt = f"{api_key_name} [{'keep current' if existing_key else 'required'}]: "
        api_key = session.prompt(prompt, is_password=True).strip()
        if api_key:
            break
        if existing_key:
            api_key = existing_key
            break
        print(f"{api_key_name} is required.")

    updated = dict(config)
    updated["PROVIDER"] = provider
    updated["MODEL"] = model
    updated[api_key_name] = api_key
    save_config(updated, env_file)
    load_dotenv(env_file, override=True)
    return updated


def _prompt_provider(session, default: str) -> str:
    while True:
        value = session.prompt(f"Provider [{default}]: ").strip().lower() or default
        if value in PROVIDERS:
            return value
        print("Choose one of: openai, anthropic, google")
