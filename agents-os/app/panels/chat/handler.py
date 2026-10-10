# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Chat (Agents conversationnels)
Interface de chat avec les agents Hermes via API OpenAI-compatible.
"""
import time
from hermes_client import call_hermes_api, stats, stats_lock


def handle_chat_completions(handler, body):
    """POST /v1/chat/completions — API OpenAI-compatible."""
    model = body.get("model", "hermes-agent")
    messages = body.get("messages", [])
    profile = model.replace("hermes-", "", 1) if model.startswith("hermes-") else "devops"
    with stats_lock:
        stats["total_calls"] += 1
        stats["calls_per_agent"][profile] = stats["calls_per_agent"].get(profile, 0) + 1
    result = call_hermes_api(profile, messages)
    is_err = result.startswith("[Erreur]")
    if is_err:
        with stats_lock:
            stats["errors"] += 1
    handler._send_json({
        "id": f"chatcmpl-{int(time.time())}", "object": "chat.completion",
        "created": int(time.time()), "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": result},
                      "finish_reason": "error" if is_err else "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


def handle_chat(handler, body):
    """POST /api/chat — Chat simplifie (profile + message)."""
    profile = body.get("profile", "devops")
    message = body.get("message", "")
    result = call_hermes_api(profile, [{"role": "user", "content": message}])
    handler._send_json({"response": result})
