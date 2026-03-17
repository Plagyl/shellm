from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

try:
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.key_binding import KeyBindings
except ImportError:
    WordCompleter = None
    KeyBindings = None

ENV_FILE = Path(".env")
PROVIDERS = ("openai", "anthropic", "google")
ENV_KEYS = (
    "PROVIDER",
    "MODEL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
)
MODEL_OPTIONS = {
    "openai": ("gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"),
    "anthropic": ("claude-3-5-haiku-latest", "claude-3-7-sonnet-latest", "claude-sonnet-4-0"),
    "google": ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-flash-latest"),
}
DEFAULT_MODELS = {provider: models[0] for provider, models in MODEL_OPTIONS.items()}
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
    existing_provider, existing_key = _existing_provider_and_key(config)
    api_key, provider = _prompt_api_key(session, existing_key, existing_provider)
    model_default = _default_model(config, provider)
    model = _prompt_model(session, provider, model_default)

    updated = dict(config)
    updated["PROVIDER"] = provider
    updated["MODEL"] = model
    updated[API_KEY_BY_PROVIDER[provider]] = api_key
    save_config(updated, env_file)
    load_dotenv(env_file, override=True)
    return updated


def _existing_provider_and_key(config: dict[str, str]) -> tuple[str | None, str]:
    provider = config.get("PROVIDER", "").strip().lower()
    if provider in PROVIDERS:
        key = config.get(API_KEY_BY_PROVIDER[provider], "").strip()
        if key:
            return provider, key

    for candidate in PROVIDERS:
        key = config.get(API_KEY_BY_PROVIDER[candidate], "").strip()
        if key:
            return candidate, key

    return None, ""


def _prompt_api_key(session, existing_key: str, existing_provider: str | None) -> tuple[str, str]:
    while True:
        prompt = f"API key [{'keep current' if existing_key else 'required'}]: "
        api_key = session.prompt(prompt, is_password=True).strip()
        if not api_key:
            if existing_key:
                api_key = existing_key
            else:
                print("API key is required.")
                continue

        provider = _detect_provider_from_api_key(api_key)
        if provider:
            print(f"Detected provider: {provider}")
            return api_key, provider

        provider_default = existing_provider or "openai"
        print("Could not detect the provider from this key.")
        return api_key, _prompt_provider(session, provider_default)


def _default_model(config: dict[str, str], provider: str) -> str:
    current_provider = config.get("PROVIDER", "").strip().lower()
    current_model = config.get("MODEL", "").strip()
    if current_provider == provider and current_model:
        return current_model
    return DEFAULT_MODELS[provider]


def _prompt_model(session, provider: str, default: str) -> str:
    options = _model_options(provider, default)
    print(f"Suggested {provider} models: {', '.join(options)}")
    print("Press Tab to cycle through the suggested models.")
    return _prompt_with_choices(session, f"Model [{default}]: ", default, options)


def _model_options(provider: str, current_model: str) -> tuple[str, ...]:
    options = list(MODEL_OPTIONS[provider])
    if current_model and current_model not in options:
        options.insert(0, current_model)
    return tuple(options)


def _detect_provider_from_api_key(api_key: str) -> str | None:
    if api_key.startswith("sk-ant-"):
        return "anthropic"
    if api_key.startswith("AIza"):
        return "google"
    if api_key.startswith("sk-proj-") or api_key.startswith("sk-"):
        return "openai"
    return None


def _prompt_provider(session, default: str) -> str:
    while True:
        value = _prompt_with_choices(session, f"Provider [{default}]: ", default, PROVIDERS).lower()
        if value in PROVIDERS:
            return value
        print("Choose one of: openai, anthropic, google")


def _prompt_with_choices(session, prompt: str, default: str, choices: tuple[str, ...]) -> str:
    value = session.prompt(prompt, is_password=False, **_choice_prompt_kwargs(choices)).strip()
    return value or default


def _choice_prompt_kwargs(choices: tuple[str, ...]) -> dict:
    if WordCompleter is None or KeyBindings is None:
        return {}

    bindings = KeyBindings()

    @bindings.add("tab")
    def _next_choice(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state:
            buffer.complete_next()
        else:
            buffer.start_completion(select_first=True)

    @bindings.add("s-tab")
    def _previous_choice(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state:
            buffer.complete_previous()

    return {
        "completer": WordCompleter(list(choices), ignore_case=True, sentence=True, match_middle=True),
        "complete_while_typing": False,
        "key_bindings": bindings,
    }
