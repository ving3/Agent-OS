# -*- coding: utf-8 -*-
"""Agent OS — Router Chat (API OpenAI-compatible)"""
import time
from fastapi import APIRouter, Request
from database import get_user_from_token
from services.hermes_client import call_hermes_api, stats, stats_lock
from schemas import ChatRequest, ChatResponse, ChatCompletionRequest, ChatCompletionResponse, ChatCompletionChoice, ChatCompletionMessage, ChatCompletionUsage

router = APIRouter(tags=["chat"])


def _get_token(request: Request) -> str | None:
    return request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")


@router.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    _get_token(request)  # require auth
    result = call_hermes_api(body.profile, [{"role": "user", "content": body.message}])
    return {"response": result}


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(body: ChatCompletionRequest, request: Request):
    _get_token(request)
    model = body.model
    profile = model.replace("hermes-", "", 1) if model.startswith("hermes-") else "devops"
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    with stats_lock:
        stats["total_calls"] += 1
        stats["calls_per_agent"][profile] = stats["calls_per_agent"].get(profile, 0) + 1

    result = call_hermes_api(profile, messages)
    is_err = result.startswith("[Erreur]")
    if is_err:
        with stats_lock:
            stats["errors"] += 1

    now = int(time.time())
    return {
        "id": f"chatcmpl-{now}",
        "object": "chat.completion",
        "created": now,
        "model": model,
        "choices": [ChatCompletionChoice(
            message=ChatCompletionMessage(role="assistant", content=result),
            finish_reason="error" if is_err else "stop",
        )],
        "usage": ChatCompletionUsage(),
    }
