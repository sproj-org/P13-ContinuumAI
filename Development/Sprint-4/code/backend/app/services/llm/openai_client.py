"""OpenAI client wrapper for JSON-only responses."""

from __future__ import annotations

import json
from typing import Any


class OpenAIJSONError(RuntimeError):
    """Raised when model output cannot be parsed as JSON."""


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.2) -> None:
<<<<<<< HEAD
=======
        if not api_key or not api_key.strip():
            raise OpenAIJSONError("OPENAI_API_KEY is missing. Set it in backend/.env or your shell environment.")
>>>>>>> 7599888825e1aa7a1658e7d3beb0d95f793251d2
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIJSONError("openai package is not installed. Install backend requirements first.") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        corrective_prompt: str | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if corrective_prompt:
            messages.append({"role": "user", "content": corrective_prompt})

        completion = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            response_format={"type": "json_object"},
            messages=messages,
        )
        raw_text = completion.choices[0].message.content or ""
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise OpenAIJSONError(f"Model output is not valid JSON: {raw_text[:200]}") from exc
        if not isinstance(payload, dict):
            raise OpenAIJSONError("Model output must be a JSON object.")
        return payload
