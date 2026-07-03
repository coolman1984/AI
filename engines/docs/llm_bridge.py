"""LLM bridge with configured fallback chain (MASTER_PLAN F.4)."""

from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Protocol

from gov.ledger import log_external_call
from gov.privacy import Tier, assert_can_send_external

_ANSI_RE = __import__("re").compile(r"\x1b\[[0-9;]*m")


class LLMBridge(Protocol):
    def generate(self, prompt: str) -> str: ...


class ProviderError(RuntimeError):
    """Raised when a configured provider fails."""


class OpencodeLLM:
    """Calls the 'opencode' CLI — never used in tests."""

    def __init__(
        self,
        exe: str | None = None,
        model: str | None = None,
        variant: str | None = None,
    ):
        self.exe = exe or os.environ.get("OPENCODE_EXE", "opencode")
        self.model = model or os.environ.get("OPENCODE_MODEL", "deepseek-v4-flash")
        self.variant = variant or os.environ.get("OPENCODE_VARIANT", "default")
        self.provider_name = f"opencode:{self.model}"

    def generate(self, prompt: str) -> str:
        result = subprocess.run(
            [self.exe, "run", "-m", self.model, "--variant", self.variant],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            stderr_excerpt = (
                result.stderr.strip()[-500:] if result.stderr.strip() else "(no stderr)"
            )
            raise ProviderError(
                f"opencode exited with code {result.returncode}: {stderr_excerpt}"
            )
        cleaned = _ANSI_RE.sub("", result.stdout)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        return "\n".join(lines)


class CallableLLM:
    """Test-friendly provider backed by a callable."""

    def __init__(self, fn, *, name: str = "callable"):
        self._fn = fn
        self.provider_name = name

    def generate(self, prompt: str) -> str:
        return self._fn(prompt)


class FailingLLM:
    """Provider that always fails — used to test fallback."""

    def __init__(self, message: str = "provider unavailable"):
        self.provider_name = "failing"
        self.message = message

    def generate(self, prompt: str) -> str:
        raise ProviderError(self.message)


class FallbackLLMBridge:
    """Try providers in order; privacy tier gate and ledger run once per successful call."""

    def __init__(
        self,
        providers: list[LLMBridge],
        *,
        tier: Tier = Tier.TIER_2,
        document: str = "",
        ledger_path: str = ".brain/external_call_ledger.jsonl",
        external_send: bool = True,
    ):
        self.providers = providers
        self.tier = tier
        self.document = document
        self.ledger_path = ledger_path
        self.external_send = external_send
        self.last_provider: str | None = None
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        if self.external_send:
            assert_can_send_external(self.tier)
        errors: list[str] = []
        for provider in self.providers:
            try:
                result = provider.generate(prompt)
                self.last_provider = getattr(provider, "provider_name", provider.__class__.__name__)
                self.call_count += 1
                if self.external_send:
                    model_name = getattr(provider, "model", self.last_provider)
                    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
                    log_external_call(
                        document=self.document,
                        tier=self.tier,
                        model=str(model_name),
                        prompt_hash=prompt_hash,
                        path=self.ledger_path,
                    )
                return result
            except (ProviderError, RuntimeError, OSError) as exc:
                errors.append(f"{provider.__class__.__name__}: {exc}")
        raise ProviderError("all providers failed: " + "; ".join(errors))


def build_fallback_bridge(cfg: dict | None = None) -> FallbackLLMBridge:
    """Build fallback chain from config ai.fallback_models list."""
    cfg = cfg or {}
    models = cfg.get("ai", {}).get("fallback_models", [])
    providers: list[LLMBridge] = []
    for entry in models:
        provider = entry.get("provider", "callable")
        if provider == "opencode":
            providers.append(
                OpencodeLLM(model=entry.get("model"), variant=entry.get("variant"))
            )
    if not providers:
        providers.append(OpencodeLLM())
    return FallbackLLMBridge(providers)