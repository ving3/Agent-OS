# -*- coding: utf-8 -*-
"""
Agent OS — Schemas Pydantic (contrat API entre backend et frontend)
Ces schemas sont la source de verite — le frontend TypeScript les reflete dans types.ts
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Auth ───────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)

class SignupRequest(BaseModel):
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)

class TokenResponse(BaseModel):
    token: str
    user: UserInfo


# ── Utilisateurs ───────────────────────────────────────────────────────────────

class UserPermissions(BaseModel):
    panels: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)

class UserInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str  # "admin" | "user"
    permissions: UserPermissions = Field(default_factory=UserPermissions)

class UserRecord(UserInfo):
    disabled: bool = False
    created_at: str = ""

class CreateUserRequest(BaseModel):
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    role: str = Field(default="user", pattern="^(admin|user)$")
    permissions: UserPermissions = Field(default_factory=UserPermissions)

class UpdateUserRequest(BaseModel):
    id: int
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    disabled: Optional[bool] = None

class UpdatePermissionsRequest(BaseModel):
    id: int
    permissions: UserPermissions

class DeleteUserRequest(BaseModel):
    id: int


# ── Agents ─────────────────────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    emoji: str = "🤖"
    color: str = "#58a6ff"
    desc: str = ""

class AgentProfile(BaseModel):
    name: str
    emoji: str = "🤖"
    color: str = "#58a6ff"
    description: str = ""
    memory: str = ""
    has_memory: bool = False

class CreateAgentRequest(BaseModel):
    name: str = Field(..., max_length=64)
    emoji: str = "🤖"
    color: str = "#58a6ff"
    description: str = ""
    provider: str = Field(default="deepseek", max_length=32)
    model: str = Field(default="deepseek-v4-pro", max_length=128)
    base_url: str = Field(default="", max_length=255)  # requis pour provider=custom

class DeleteAgentRequest(BaseModel):
    name: str


# ── Fournisseurs LLM ───────────────────────────────────────────────────────────

class ProviderInfo(BaseModel):
    id: str
    label: str
    models: list[str]
    base_url: str = ""
    key_configured: bool = False

class ProviderListResponse(BaseModel):
    providers: list[ProviderInfo]


# ── Système ────────────────────────────────────────────────────────────────────

class SystemStatus(BaseModel):
    status: str  # "online" | "offline"
    uptime_seconds: int
    total_calls: int
    calls_per_agent: dict[str, int]
    errors: int
    profiles: list[str]
    agents: dict[str, AgentConfig]
    panels: list[str]
    user: UserInfo


# ── Skills ─────────────────────────────────────────────────────────────────────

class SkillInfo(BaseModel):
    name: str
    path: str
    description: str = ""


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    profile: str = "devops"
    message: str

class ChatResponse(BaseModel):
    response: str

class ChatCompletionMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "hermes-agent"
    messages: list[ChatCompletionMessage]

class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionMessage
    finish_reason: str = "stop"

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


# ── Modèles (OpenAI-compatible) ────────────────────────────────────────────────

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "hermes"

class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


# ── Réponses génériques ────────────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    success: bool = True

class ErrorResponse(BaseModel):
    error: str

class ProfileResponse(BaseModel):
    name: str
    emoji: str = "🤖"
    description: str = ""
    memory: str = ""

class ProfileListResponse(BaseModel):
    profiles: list[AgentProfile]

class SkillListResponse(BaseModel):
    skills: list[SkillInfo]

class UserListResponse(BaseModel):
    users: list[UserRecord]
    panels: list[str]
    agents: list[str]
