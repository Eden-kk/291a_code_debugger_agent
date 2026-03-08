"""Thin wrapper around the OpenAI-compatible chat completions API with token tracking.

Supports multiple backends:
  - tritonai : UCSD TritonAI API (Llama-4-Scout, GPT-OSS-120B, Mistral, Claude, …)
  - openai   : OpenAI official API (GPT-4o, GPT-4o-mini, …)
  - local    : Local vLLM / Ollama server exposing an OpenAI-compatible endpoint
  - deepseek : DeepSeek API
  - custom   : Any OpenAI-compatible endpoint (specify --base-url)
"""

import os
import time
from typing import Optional

from openai import OpenAI


# ---------------------------------------------------------------------------
# Backend presets
# ---------------------------------------------------------------------------

BACKENDS = {
    "tritonai": {
        "base_url": "https://tritonai-api.ucsd.edu/v1",
        "api_key_env": "TRITONAI_API_KEY",
        "default_model": "api-gpt-oss-120b",
    },
    "openai": {
        "base_url": None,              # uses the openai library default
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,            # not required
        "default_model": "llama3.1:8b",
    },
    "local": {
        "base_url": "http://localhost:8000/v1",
        "api_key_env": None,            # not required for local vLLM
        "default_model": "Qwen/Qwen2.5-Coder-32B-Instruct",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
}


# ---------------------------------------------------------------------------
# Approximate pricing per 1 M tokens (USD)
# ---------------------------------------------------------------------------

_PRICING = {
    # model_prefix: (input_per_M, output_per_M)
    "gpt-4o-mini":  (0.15,  0.60),
    "gpt-4o":       (2.50, 10.00),
    "gpt-4-turbo":  (10.00, 30.00),
    "deepseek-chat": (0.27,  1.10),
    "deepseek-coder": (0.14, 0.28),
    # Open-source / local / TritonAI models — cost is essentially 0
    "Qwen":         (0.0, 0.0),
    "qwen":         (0.0, 0.0),
    "llama":        (0.0, 0.0),
    "Llama":        (0.0, 0.0),
    "mistral":      (0.0, 0.0),
    "api-":         (0.0, 0.0),   # TritonAI models
    "us.":          (0.0, 0.0),   # TritonAI AWS Bedrock models
    "moonshotai.":  (0.0, 0.0),
    "minimax.":     (0.0, 0.0),
}


def _price_for_model(model: str):
    """Return (input_price, output_price) per 1 M tokens."""
    for prefix, prices in _PRICING.items():
        if model.startswith(prefix):
            return prices
    # fallback: 0 (assume local / unknown)
    return (0.0, 0.0)


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------


class LLMClient:
    """OpenAI-compatible ChatCompletion client with cumulative token & cost tracking.

    Parameters
    ----------
    model : str
        Model identifier (e.g. "gpt-4o-mini", "Qwen/Qwen2.5-Coder-32B-Instruct").
    backend : str
        One of "openai", "local", "deepseek", or "custom".
    base_url : str | None
        Override the API endpoint URL.  Takes precedence over the backend preset.
    api_key : str | None
        Override the API key.  Takes precedence over environment variables.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = 42,
        backend: str = "openai",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        # --- Resolve backend preset ----------------------------------------
        preset = BACKENDS.get(backend, {})
        resolved_base_url = base_url or preset.get("base_url")
        env_var = preset.get("api_key_env")

        # --- Resolve API key ------------------------------------------------
        if api_key is None and env_var:
            api_key = os.environ.get(env_var)
        if api_key is None and resolved_base_url is None:
            # OpenAI backend requires a key
            raise RuntimeError(
                f"API key not found.  Set the {env_var or 'OPENAI_API_KEY'} "
                "environment variable, or pass --api-key."
            )
        # Local backends don't need a real key
        if api_key is None:
            api_key = "not-needed"

        # --- Build client ---------------------------------------------------
        client_kwargs: dict = {"api_key": api_key, "timeout": 120.0}
        if resolved_base_url:
            client_kwargs["base_url"] = resolved_base_url

        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self.backend = backend
        self.base_url = resolved_base_url

        # Cumulative counters
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0

    # -- core API ------------------------------------------------------------

    def chat(self, messages: list, tools: Optional[list] = None):
        """Send a chat completion request and return the raw response."""
        kwargs: dict = dict(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        if self.seed is not None:
            kwargs["seed"] = self.seed
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # Simple retry with back-off for transient errors
        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break
            except Exception as exc:
                last_exc = exc
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(
                f"LLM API failed after 3 retries: {last_exc}"
            ) from last_exc

        # Track tokens
        if response.usage:
            self.total_input_tokens += response.usage.prompt_tokens
            self.total_output_tokens += response.usage.completion_tokens
        self.call_count += 1

        return response

    # -- helpers -------------------------------------------------------------

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def estimated_cost(self) -> float:
        """Return estimated cost in USD based on tracked token usage."""
        inp_price, out_price = _price_for_model(self.model)
        return (
            self.total_input_tokens * inp_price
            + self.total_output_tokens * out_price
        ) / 1_000_000
