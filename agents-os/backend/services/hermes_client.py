# -*- coding: utf-8 -*-
"""Agent OS — Services: client Hermes, gestion des profils/skills"""
import httpx, threading, time, subprocess
from pathlib import Path
from config import HERMES_API_URL, HERMES_API_KEY, PROFILES_DIR, SKILLS_DIR, AGENTS

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


def _k8s_exec(command: str) -> bool:
    """Execute une commande dans le pod Hermes via l'API Kubernetes."""
    import urllib.request
    import ssl
    import json as _json
    import base64

    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ca_path = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    namespace = "ai"
    pod_name = None

    # Trouver le nom du pod Hermes
    try:
        token = open(token_path).read().strip()
        ctx = ssl.create_default_context(cafile=ca_path)
        req = urllib.request.Request(
            f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/pods?labelSelector=app.kubernetes.io/name=hermes",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = urllib.request.urlopen(req, context=ctx, timeout=10)
        data = _json.loads(resp.read())
        items = data.get("items", [])
        if items:
            pod_name = items[0]["metadata"]["name"]
    except Exception:
        pass

    if not pod_name:
        return False

    # Exec via subprocess avec timeout court
    try:
        b64cmd = base64.b64encode(command.encode()).decode()
        result = subprocess.run(
            ["kubectl",
             "--server", "https://kubernetes.default.svc",
             "--token", open(token_path).read().strip(),
             "--certificate-authority", ca_path,
             "--request-timeout", "15s",
             "--insecure-skip-tls-verify", "true",
             "exec", "-n", namespace, pod_name, "--",
             "sh", "-c", command],
            capture_output=True, text=True, timeout=20,
        )
        return result.returncode == 0
    except Exception:
        return False


def create_agent_profile(name: str, description: str, model: str, base_url: str, api_key: str = "") -> bool:
    """Cree un profil agent avec le modele et le fournisseur choisis.

    Le config.yaml du profil definit le modele par defaut et l'endpoint.
    La cle API est incluse si fournie (sinon la cle globale est utilisee).
    """
    key_line = f"  api_key: {api_key}\n" if api_key else ""
    cmd = (
        f"mkdir -p /opt/data/profiles/{name} && "
        f"cat > /opt/data/profiles/{name}/SOUL.md << 'SOUL'\n"
        f"# Agent {name}\n\n{description}\n\n"
        f"## Role\n\nAgent cree depuis Agentic OS Dashboard.\n"
        f"SOUL\n"
        f"cat > /opt/data/profiles/{name}/config.yaml << 'CFG'\n"
        f"model:\n  provider: openai\n  default: {model}\n"
        f"  base_url: {base_url}\n"
        f"{key_line}"
        f"CFG"
    )
    return _k8s_exec(cmd)


def delete_agent_profile(name: str) -> bool:
    return _k8s_exec(f"rm -rf /opt/data/profiles/{name}")
