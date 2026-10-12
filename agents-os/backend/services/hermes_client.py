# -*- coding: utf-8 -*-
"""Agent OS — Services: client Hermes, gestion des profils/skills"""
import httpx, threading, time, subprocess
from pathlib import Path
from config import HERMES_API_URL, HERMES_API_KEY, PROFILES_DIR, SKILLS_DIR, AGENTS, HERMES_UID, HERMES_GID

stats = {"start_time": time.time(), "total_calls": 0, "calls_per_agent": {}, "errors": 0}
stats_lock = threading.Lock()
http_client = httpx.Client(timeout=120.0)


def call_hermes_api(profile: str, messages: list[dict]) -> str:
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"
    system_prompt = ""
    user_msgs = []
    for msg in messages:
        if msg.get("role") == "system":
            system_prompt = msg["content"]
        elif msg.get("role") == "user":
            user_msgs.append(msg["content"])
    api_msgs = []
    if system_prompt:
        api_msgs.append({"role": "system", "content": f"Tu es l'agent {profile}. {system_prompt}"})
    else:
        api_msgs.append({"role": "system", "content": f"Tu es l'agent {profile}. Réponds en français."})
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
        return data.get("choices", [{}])[0].get("message", {}).get("content", "[Erreur] Réponse vide")
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


def create_agent_profile(name: str, description: str, model: str, base_url: str, api_key: str = "") -> bool:
    """Cree un profil agent directement sur le PVC Hermes (monte rw).

    Plus robuste que kubectl exec : ecriture directe des fichiers
    avec ownership hermes (uid/gid 10000) pour que l'agent puisse
    ecrire dans son profil (memoires, sessions).
    """
    import os as _os

    profile_dir = Path(PROFILES_DIR) / name
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)

        soul = (
            f"# Agent {name}\n\n{description}\n\n"
            f"## Role\n\nAgent cree depuis Agentic OS Dashboard.\n"
        )
        config = f"model:\n  provider: openai\n  default: {model}\n  base_url: {base_url}\n"
        if api_key:
            config += f"  api_key: {api_key}\n"

        (profile_dir / "SOUL.md").write_text(soul)
        (profile_dir / "config.yaml").write_text(config)

        # Ownership hermes (uid/gid 10000) pour permettre les ecritures runtime
        try:
            _os.chown(profile_dir, HERMES_UID, HERMES_GID)
            for f in profile_dir.iterdir():
                _os.chown(f, HERMES_UID, HERMES_GID)
        except (PermissionError, OSError):
            pass  # pas root : les permissions par defaut suffisent en lecture

        return True
    except Exception:
        return False


def delete_agent_profile(name: str) -> bool:
    """Supprime un profil agent directement sur le PVC Hermes."""
    import shutil

    profile_dir = Path(PROFILES_DIR) / name
    try:
        if profile_dir.is_dir():
            shutil.rmtree(profile_dir)
        return True
    except Exception:
        return False
