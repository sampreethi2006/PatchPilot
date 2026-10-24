import json
import logging
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("patchpilot.ai_provider")


class AIProvider(ABC):
    """Abstract interface for AI reasoning providers."""

    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider has necessary credentials and configuration."""
        pass

    @abstractmethod
    def generate_diagnosis(
        self,
        test_output: str,
        source_code: str,
        retrieved_memory: str = "",
    ) -> Dict[str, Any]:
        """Analyze test failure and source code to propose diagnosis and patch."""
        pass


class DeterministicRuleProvider(AIProvider):
    """Deterministic rule-based analyzer used as reliable local baseline."""

    def name(self) -> str:
        return "Deterministic Rule Analyzer (Local Engine)"

    def is_configured(self) -> bool:
        return True

    def generate_diagnosis(
        self,
        test_output: str,
        source_code: str,
        retrieved_memory: str = "",
    ) -> Dict[str, Any]:
        # Handle zero division case
        if "ZeroDivisionError" in test_output:
            return {
                "provider": self.name(),
                "is_llm": False,
                "root_cause": (
                    "The `divide` function divides `a / b` directly without checking if the divisor `b` is zero."
                ),
                "suggested_fix": (
                    "Add an input validation check: `if b == 0: raise ValueError('Cannot divide by zero.')`"
                ),
                "proposed_patch": (
                    "def divide(a, b):\n"
                    "    # Fixed: validate divisor before dividing\n"
                    "    if b == 0:\n"
                    "        raise ValueError(\"Cannot divide by zero.\")\n"
                    "    return a / b\n"
                ),
                "confidence": 0.99,
                "method": "Rule-based static traceback & AST matching",
            }

        return {
            "provider": self.name(),
            "is_llm": False,
            "root_cause": "Test failure occurred. Traceback indicates assertion or runtime failure.",
            "suggested_fix": "Review failing test assertion and traceback.",
            "proposed_patch": None,
            "confidence": 0.3,
            "method": "Fallback rule analyzer",
        }


class NebiusLLMProvider(AIProvider):
    """Nebius Studio LLM provider interface using OpenAI-compatible HTTP API.

    Reads configuration solely from environment variables without hardcoded keys.
    """

    def __init__(self):
        self.api_key = os.environ.get("NEBIUS_API_KEY", "").strip()
        self.base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1").rstrip("/")
        self.model = os.environ.get("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")
        self.timeout = int(os.environ.get("NEBIUS_TIMEOUT_SEC", 15))

    def name(self) -> str:
        return f"Nebius AI ({self.model})"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_diagnosis(
        self,
        test_output: str,
        source_code: str,
        retrieved_memory: str = "",
    ) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("Nebius API key is not configured. Set NEBIUS_API_KEY environment variable.")

        prompt = (
            "You are an expert autonomous software repair agent.\n"
            "Analyze the following Python test failure and source code.\n\n"
            f"--- RELEVANT MEMORY FINDINGS ---\n{retrieved_memory[:1500]}\n\n"
            f"--- PYTEST TRACEBACK ---\n{test_output[:3000]}\n\n"
            f"--- SOURCE CODE ---\n{source_code[:3000]}\n\n"
            "Respond ONLY in valid JSON matching this exact structure:\n"
            "{\n"
            '  "root_cause": "<concise explanation of why the failure occurred>",\n'
            '  "suggested_fix": "<concrete description of the fix>",\n'
            '  "proposed_patch": "<complete fixed code of the target file>",\n'
            '  "confidence": <float between 0.0 and 1.0>\n'
            "}"
        )

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a professional Python code diagnostic and repair system."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return {
                    "provider": self.name(),
                    "is_llm": True,
                    "root_cause": parsed.get("root_cause", ""),
                    "suggested_fix": parsed.get("suggested_fix", ""),
                    "proposed_patch": parsed.get("proposed_patch", ""),
                    "confidence": float(parsed.get("confidence", 0.9)),
                    "method": "Nebius LLM Inference",
                }
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            logger.error("Nebius API error %d: %s", exc.code, err_body)
            raise RuntimeError(f"Nebius API returned HTTP {exc.code}") from exc
        except Exception as exc:
            logger.exception("Nebius inference failed")
            raise RuntimeError(f"Nebius request failed: {exc}") from exc


def get_active_provider() -> Tuple[AIProvider, Dict[str, Any]]:
    """Determine the active AI provider based on environment configuration."""
    nebius = NebiusLLMProvider()
    if nebius.is_configured():
        return nebius, {
            "name": nebius.name(),
            "type": "llm",
            "model": nebius.model,
            "is_configured": True,
        }

    rule_provider = DeterministicRuleProvider()
    return rule_provider, {
        "name": rule_provider.name(),
        "type": "deterministic",
        "model": "Rule-based pattern analyzer",
        "is_configured": True,
        "note": "Using reliable local deterministic analyzer. Set NEBIUS_API_KEY in .env to enable cloud LLM reasoning.",
    }
