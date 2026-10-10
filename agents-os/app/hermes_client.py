# -*- coding: utf-8 -*-
"""
Agentic OS — Client API Hermes (OpenAI-compatible)
"""
import httpx
import threading
import time
from pathlib import Path
from config import HERMES_API_URL, HERMES_API_KEY, PROFILES_DIR, SKILLS_DIR


stats = {"start_time": time.time(), "total_calls": 0, "calls_per_agent": {}, "errors": 0}
stats_lock = threading.Lock()
http_client = httpx.Client(timeout=120.0)


def call_hermes_api(profile: str, messages: list) -> str:
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"
    system_prompt = ""
    user_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_prompt = content
        elif role == "user":
            user_msgs.append(content)
    api_msgs = []
    if system_prompt:
        api_msgs.append({"role": "system", "content": f"Tu es l'agent {profile}. {system_prompt}"})
    else:
        api_msgs.append({"role": "system", "content": f"Tu es l'agent {profile}. Reponds en francais."})
    for c in user_msgs:
        api_msgs.append({"role": "user", "content": c})
    try:
        resp = http_client.post(
            f"{HERMES_API_URL}/v1/chat/completions",
            headers=headers,
            json={"model": "hermes-agent", "messages": api_msgs},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "[Erreur] Reponse vide")
    except httpx.HTTPStatusError as e:
        return f"[Erreur] API Hermes: HTTP {e.response.status_code}"
    except Exception as e:
        return f"[Erreur] {e}"


def get_agent_memory(profile_name: str) -> str:
    mem_file = Path(PROFILES_DIR) / profile_name / "memories" / "memory.md"
    if mem_file.exists():
        return mem_file.read_text()
    return ""


def list_skills() -> list[dict]:
    skills = []
    sp = Path(SKILLS_DIR)
    if sp.is_dir():
        for sf in sp.rglob("SKILL.md"):
            rel = sf.parent.relative_to(sp)
            content = sf.read_text()
            name, desc = "", ""
            in_front = False
            for line in content.split("\n"):
                if line.strip() == "---":
                    in_front = not in_front
                    continue
                if in_front:
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"')
            skills.append({"name": name or sf.parent.name, "path": str(rel), "description": desc})
    return skills


def list_profiles() -> list[str]:
    pp = Path(PROFILES_DIR)
    if pp.is_dir():
        return sorted(p.name for p in pp.iterdir() if p.is_dir())
    return []
