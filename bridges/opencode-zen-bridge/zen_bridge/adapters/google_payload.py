"""Формирование payload для прямого Google API и структур OpenAI usage."""

from __future__ import annotations

from typing import Any

GOOGLE_STOP_SEQUENCES = (
    "<|im_end|>",
    "<|endoftext|>",
    "[/INST]",
    "</s>",
    "\n\nHuman:",
    "\n\nUser:",
)
GOOGLE_CONTINUE_TEXT = "Continue immediately."


def _build_google_payload(
    prompt: str,
    effort: str,
    max_output: int,
    contents: list[dict[str, Any]] | None = None,
    system_instruction: str = "",
    emulate_tools: bool = False,
) -> dict[str, Any]:
    """Тело generateContent: systemInstruction + чередующиеся user/model contents."""
    payload: dict[str, Any] = {}
    if system_instruction.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    if contents is None:
        payload["contents"] = [{"role": "user", "parts": [{"text": prompt}]}]
    else:
        payload["contents"] = list(contents)
        if payload["contents"] and payload["contents"][-1]["role"] == "model":
            payload["contents"].append(
                {"role": "user", "parts": [{"text": GOOGLE_CONTINUE_TEXT}]}
            )
    gen_cfg: dict[str, Any] = {
        "maxOutputTokens": max_output,
        "stopSequences": list(GOOGLE_STOP_SEQUENCES),
    }
    if effort:
        level = "HIGH" if effort in ("high", "xhigh") else effort.upper()
        gen_cfg["thinkingConfig"] = {"includeThoughts": True, "thinkingLevel": level}
    payload["generationConfig"] = gen_cfg
    return payload


def _build_openai_usage(
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    reasoning_tokens: int = 0,
) -> dict[str, Any]:
    """OpenAI usage объект."""
    usage_obj: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    if cached_tokens > 0:
        usage_obj["cached_tokens"] = cached_tokens
        usage_obj["prompt_tokens_details"] = {"cached_tokens": cached_tokens}
    if reasoning_tokens > 0:
        usage_obj["completion_tokens_details"] = {"reasoning_tokens": reasoning_tokens}
    return usage_obj
