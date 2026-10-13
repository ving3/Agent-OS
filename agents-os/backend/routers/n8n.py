# -*- coding: utf-8 -*-
"""Agent OS — Router n8n : orchestration des agents via workflows"""
import httpx
from fastapi import APIRouter, Request
from database import get_user_from_token
from services.hermes_client import call_hermes_api
from config import N8N_URL
from schemas import (
    N8nWorkflowListResponse, N8nWorkflow,
    N8nExecutionListResponse, N8nExecution,
    N8nTriggerRequest, N8nOrchestrateRequest, N8nOrchestrateResponse,
)

router = APIRouter(prefix="/api/n8n", tags=["n8n"])


def _require_auth(request: Request) -> bool:
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    return get_user_from_token(token) is not None


def _n8n_client() -> httpx.Client:
    return httpx.Client(base_url=N8N_URL, timeout=15.0)


@router.get("/status")
def n8n_status(request: Request):
    """Etat de l'instance n8n."""
    if not _require_auth(request):
        return {"online": False, "error": "Non autorise"}
    try:
        with _n8n_client() as c:
            r = c.get("/healthz")
        return {"online": r.status_code == 200}
    except Exception as e:
        return {"online": False, "error": str(e)}


@router.get("/workflows", response_model=N8nWorkflowListResponse)
def list_workflows(request: Request):
    """Liste les workflows n8n."""
    if not _require_auth(request):
        return {"workflows": [], "online": False}
    try:
        with _n8n_client() as c:
            r = c.get("/api/v1/workflows")
            r.raise_for_status()
            data = r.json().get("data", [])
        workflows = [N8nWorkflow(
            id=str(w.get("id", "")),
            name=w.get("name", "Sans nom"),
            active=bool(w.get("active", False)),
            created_at=str(w.get("createdAt", "")),
            updated_at=str(w.get("updatedAt", "")),
        ) for w in data]
        return {"workflows": workflows, "online": True}
    except Exception:
        return {"workflows": [], "online": False}


@router.get("/workflows/{workflow_id}/executions", response_model=N8nExecutionListResponse)
def list_executions(workflow_id: str, request: Request):
    """Executions recentes d'un workflow n8n."""
    if not _require_auth(request):
        return {"executions": []}
    try:
        with _n8n_client() as c:
            r = c.get("/api/v1/executions", params={"limit": 20, "workflowId": workflow_id})
            r.raise_for_status()
            data = r.json().get("data", [])
        executions = [N8nExecution(
            id=e.get("id", 0),
            workflow_id=str(e.get("workflowId", "")),
            status=str(e.get("status", "unknown")),
            started_at=str(e.get("startedAt", "")),
            stopped_at=str(e.get("stoppedAt", "")),
        ) for e in data]
        return {"executions": executions}
    except Exception:
        return {"executions": []}


@router.post("/trigger")
def trigger_workflow(body: N8nTriggerRequest, request: Request):
    """Execute un workflow n8n (via l'API REST)."""
    if not _require_auth(request):
        return {"success": False, "error": "Non autorise"}
    wf_id = body.workflow_id
    if not wf_id:
        return {"success": False, "error": "workflow_id requis"}
    try:
        with _n8n_client() as c:
            r = c.post(f"/api/v1/workflows/{wf_id}/run", json=body.payload)
            if r.status_code in (404, 405):
                # Fallback : endpoint d'execution directe (anciennes versions)
                r2 = c.post(f"/api/v1/executions/{wf_id}")
                r = r2
            if r.status_code >= 400:
                return {"success": False, "error": f"n8n HTTP {r.status_code}"}
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/orchestrate", response_model=N8nOrchestrateResponse)
def orchestrate(body: N8nOrchestrateRequest, request: Request):
    """Orchestre une chaine d'agents.

    Deux modes :
      - workflow_id fourni : declenche le workflow n8n correspondant
      - sinon : orchestration sequentielle locale (chaque agent recoit le
        message et le contexte des reponses precedentes)
    """
    if not _require_auth(request):
        return {"success": False, "error": "Non autorise"}

    # Mode workflow n8n
    if body.workflow_id:
        try:
            with _n8n_client() as c:
                r = c.post(f"/api/v1/workflows/{body.workflow_id}/run",
                           json={"agents": body.agents, "message": body.message})
                if r.status_code >= 400:
                    return {"success": False, "error": f"n8n HTTP {r.status_code}"}
            return {"success": True, "results": []}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Mode sequentiel local
    if not body.agents:
        return {"success": False, "error": "Aucun agent specifie"}
    results = []
    context = body.message
    for agent in body.agents:
        reply = call_hermes_api(agent, [{"role": "user", "content": context}])
        results.append({"agent": agent, "response": reply})
        if reply.startswith("[Erreur]"):
            break
        # Le contexte s'enrichit de la reponse pour l'agent suivant
        context = f"{context}\n\n[Reponse de {agent}]\n{reply[:2000]}"
    return {"success": True, "results": results}
