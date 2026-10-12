# -*- coding: utf-8 -*-
"""Agent OS — Router Graph : relations entre agents et skills"""
from collections import Counter
from pathlib import Path
from fastapi import APIRouter, Request
from pydantic import BaseModel
from database import get_user_from_token
from services.hermes_client import list_profiles, list_skills
from config import AGENTS, PROFILES_DIR, SKILLS_DIR, DATA_DIR, PANELS

router = APIRouter(prefix="/api", tags=["graph"])

CONNECTIONS_FILE = Path(DATA_DIR) / "graph-connections.json"


class ConnectRequest(BaseModel):
    source: str
    target: str
    label: str = ""


def _load_connections() -> list[dict]:
    """Charge les connexions personnalisees depuis le fichier JSON."""
    import json
    if CONNECTIONS_FILE.exists():
        try:
            return json.loads(CONNECTIONS_FILE.read_text())
        except Exception:
            pass
    return []


def _save_connections(connections: list[dict]) -> None:
    """Sauvegarde les connexions personnalisees."""
    import json
    CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONNECTIONS_FILE.write_text(json.dumps(connections, indent=2))


def _read_profile_soul(name: str) -> str:
    """Lit le SOUL.md d'un profil agent."""
    soul_path = Path(PROFILES_DIR) / name / "SOUL.md"
    if soul_path.exists():
        return soul_path.read_text().lower()
    return ""


def _extract_keywords(text: str) -> set[str]:
    """Extrait les mots-clés significatifs d'un texte."""
    stopwords = {
        "le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "en", "au",
        "aux", "pour", "par", "sur", "dans", "avec", "sans", "que", "qui", "pas",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "under", "again",
        "further", "then", "once", "here", "there", "when", "where", "why",
        "how", "all", "both", "each", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "just", "now", "also", "agent", "agents",
    }
    words = set()
    for word in text.replace("\n", " ").replace(",", " ").replace(".", " ").split():
        w = word.strip("()[]{}\"'").lower()
        if len(w) > 2 and w not in stopwords:
            words.add(w)
    return words


def _cosine_similarity(a: set[str], b: set[str]) -> float:
    """Calcule la similarité cosinus entre deux ensembles de mots."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    return intersection / ((len(a) ** 0.5) * (len(b) ** 0.5))


@router.get("/graph")
def get_graph(request: Request):
    """Retourne les nœuds (agents + skills) et les arêtes (relations)."""
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not get_user_from_token(token):
        return {"nodes": [], "edges": []}

    nodes = []
    edges = []

    # 1. Nœuds agents
    profiles = list_profiles()
    agent_keywords: dict[str, set[str]] = {}
    for name in profiles:
        ai = AGENTS.get(name, {})
        soul = _read_profile_soul(name)
        keywords = _extract_keywords(soul) | _extract_keywords(ai.get("desc", ""))
        agent_keywords[name] = keywords

        nodes.append({
            "id": f"agent-{name}",
            "label": name,
            "type": "agent",
            "color": ai.get("color", "#58a6ff"),
            "emoji": ai.get("emoji", "🤖"),
            "size": 50,
            "data": {
                "description": ai.get("desc", ""),
                "keywords": ", ".join(sorted(keywords)[:8]),
                "memory": "Active" if _read_profile_soul(name) else "Vide",
            },
        })

    # 2. Nœuds skills
    skills = list_skills()
    skill_nodes: list[str] = []
    for s in skills:
        sid = f"skill-{s['name']}"
        skill_nodes.append(sid)
        nodes.append({
            "id": sid,
            "label": s["name"],
            "type": "skill",
            "color": "#d29922",
            "emoji": "🧩",
            "size": 35,
            "data": {
                "path": s["path"],
                "description": s.get("description", ""),
            },
        })

    # 3. Arêtes agent ↔ agent (similarité des SOUL.md)
    agent_names = list(agent_keywords.keys())
    for i in range(len(agent_names)):
        for j in range(i + 1, len(agent_names)):
            a, b = agent_names[i], agent_names[j]
            sim = _cosine_similarity(agent_keywords[a], agent_keywords[b])
            if sim > 0.05:  # seuil minimal
                edges.append({
                    "source": f"agent-{a}",
                    "target": f"agent-{b}",
                    "weight": round(sim, 3),
                    "label": f"similarité {round(sim * 100)}%",
                })

    # 4. Arêtes agent ↔ skill (les skills sont globales — chaque agent peut les utiliser)
    for name in agent_names:
        keywords = agent_keywords[name]
        for skill_node in skill_nodes:
            skill_name = skill_node.replace("skill-", "")
            skill_keywords = _extract_keywords(skill_name.replace("-", " "))
            sim = _cosine_similarity(keywords, skill_keywords)
            if sim > 0.03:
                edges.append({
                    "source": f"agent-{name}",
                    "target": skill_node,
                    "weight": round(sim, 3),
                    "label": f"compatibilité {round(sim * 100)}%",
                })

    # 5. Nœuds concepts (extraits des descriptions)
    all_keywords = Counter()
    for kw_set in agent_keywords.values():
        all_keywords.update(kw_set)
    top_concepts = [w for w, c in all_keywords.most_common(8) if c >= 2]

    for concept in top_concepts:
        cid = f"concept-{concept}"
        nodes.append({
            "id": cid,
            "label": concept,
            "type": "concept",
            "color": "#bc8cff",
            "emoji": "💡",
            "size": 30,
            "data": {"count": str(all_keywords[concept])},
        })
        # Connecter les concepts aux agents qui les mentionnent
        for name in agent_names:
            if concept in agent_keywords[name]:
                edges.append({
                    "source": f"agent-{name}",
                    "target": cid,
                    "weight": 0.5,
                    "label": concept,
                })

    # 6. Connexions personnalisees (remplacent les auto si doublon)
    custom_edges = _load_connections()
    if custom_edges:
        # Supprimer les aretes auto qui ont un doublon custom
        custom_pairs = {(c["source"], c["target"]) for c in custom_edges} | \
                       {(c["target"], c["source"]) for c in custom_edges}
        edges = [e for e in edges if (e["source"], e["target"]) not in custom_pairs]
        # Ajouter les aretes custom
        edges.extend(custom_edges)

    return {"nodes": nodes, "edges": edges}


# ── Connexions personnalisees ──────────────────────────────────────────────────

@router.post("/graph/connect")
def connect_nodes(body: ConnectRequest, request: Request):
    """Cree une connexion personnalisee entre deux nœuds."""
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not get_user_from_token(token):
        return {"success": False, "error": "Non autorise"}

    connections = _load_connections()
    # Eviter les doublons
    existing = any(
        (c["source"] == body.source and c["target"] == body.target) or
        (c["source"] == body.target and c["target"] == body.source)
        for c in connections
    )
    if existing:
        return {"success": False, "error": "Connexion deja existante"}

    connections.append({
        "source": body.source,
        "target": body.target,
        "label": body.label or "connecté",
        "weight": 0.8,
        "custom": True,
    })
    _save_connections(connections)
    return {"success": True, "connection": connections[-1]}


@router.post("/graph/disconnect")
def disconnect_nodes(body: ConnectRequest, request: Request):
    """Supprime une connexion personnalisee entre deux nœuds."""
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not get_user_from_token(token):
        return {"success": False, "error": "Non autorise"}

    connections = _load_connections()
    before = len(connections)
    connections = [
        c for c in connections
        if not (
            (c["source"] == body.source and c["target"] == body.target) or
            (c["source"] == body.target and c["target"] == body.source)
        )
    ]
    if len(connections) == before:
        return {"success": False, "error": "Connexion non trouvee"}
    _save_connections(connections)
    return {"success": True}
