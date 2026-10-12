// ============================================================================
// Agent OS — Panneau Graphe (interactive graph, search, node panel)
// ============================================================================

import { store } from "../store";
import type { AgentProfile } from "../types";

interface GraphNode {
  id: string;
  label: string;
  type: "agent" | "skill" | "memory" | "concept";
  x: number;
  y: number;
  vx: number;
  vy: number;
  color: string;
  emoji: string;
  size: number;
  data: Record<string, string>;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  label: string;
  custom?: boolean;
}

interface GraphState {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  searchQuery: string;
  filterType: string;
  animating: boolean;
  connectMode: boolean;
  connectingFrom: string | null;
}

const state: GraphState = {
  nodes: [],
  edges: [],
  selectedNode: null,
  searchQuery: "",
  filterType: "all",
  animating: false,
  connectMode: false,
  connectingFrom: null,
};

export function renderGraph(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-graph" id="aos-graph">
      <div class="aos-graph-header">
        <div class="aos-graph-title">🔗 Graphe des connaissances</div>
        <div class="aos-graph-actions">
          <input type="text" class="aos-input aos-graph-search" id="aos-graph-search" placeholder="Rechercher un nœud...">
          <select class="aos-select" id="aos-graph-filter">
            <option value="all">Tous</option>
            <option value="agent">Agents</option>
            <option value="skill">Skills</option>
            <option value="memory">Mémoire</option>
            <option value="concept">Concepts</option>
          </select>
          <button class="aos-btn aos-btn-sm" id="aos-graph-connect">🔗 Connecter</button>
          <button class="aos-btn aos-btn-sm" id="aos-graph-reset">↺ Réinitialiser</button>
        </div>
      </div>
      <div class="aos-graph-connect-hint" id="aos-graph-connect-hint" style="display:none">
        🔗 Mode connexion actif : cliquez un premier nœud, puis un second pour les relier
      </div>

      <div class="aos-graph-layout">
        <div class="aos-graph-canvas" id="aos-graph-canvas"></div>

        <!-- Side panel -->
        <div class="aos-graph-panel" id="aos-graph-panel" style="display:none">
          <div class="aos-graph-panel-header">
            <span id="aos-gp-title"></span>
            <button class="aos-btn aos-btn-sm" id="aos-gp-close">✕</button>
          </div>
          <div class="aos-graph-panel-body" id="aos-gp-body"></div>
        </div>
      </div>
    </div>
  `;

  buildGraphData().then(() => {
    renderGraphCanvas();
    startForceSimulation();
  });
  bindEvents();
  store.subscribe(onStoreUpdate);
}

async function buildGraphData(): Promise<void> {
  try {
    const r = await fetch("/api/graph");
    const data = await r.json();
    if (data.nodes && data.edges) {
      state.nodes = data.nodes.map((n: any) => ({ ...n, vx: 0, vy: 0 }));
      state.edges = data.edges;
      return;
    }
  } catch (e) {
    console.error("Graph load failed:", e);
  }
  // Fallback: empty
  state.nodes = [];
  state.edges = [];
}

// -- Force simulation -----------------------------------------------------------

function startForceSimulation(): void {
  state.animating = true;
  const canvas = document.getElementById("aos-graph-canvas");
  if (!canvas) return;

  function tick(): void {
    if (!state.animating) return;

    // Repulsion
    for (let i = 0; i < state.nodes.length; i++) {
      for (let j = i + 1; j < state.nodes.length; j++) {
        const a = state.nodes[i], b = state.nodes[j];
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const force = 2000 / (dist * dist);
        const fx = (dx / dist) * force, fy = (dy / dist) * force;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }

    // Attraction (edges)
    state.edges.forEach(e => {
      const a = state.nodes.find(n => n.id === e.source);
      const b = state.nodes.find(n => n.id === e.target);
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
      const force = (dist - 120) * 0.01;
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    });

    // Center gravity
    const cx = 350, cy = 250;
    state.nodes.forEach(n => {
      n.vx += (cx - n.x) * 0.001;
      n.vy += (cy - n.y) * 0.001;
    });

    // Apply velocities
    state.nodes.forEach(n => {
      n.vx *= 0.9; n.vy *= 0.9;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(30, Math.min(670, n.x));
      n.y = Math.max(30, Math.min(470, n.y));
    });

    renderGraphCanvas();
    requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

// -- Canvas rendering -----------------------------------------------------------

function renderGraphCanvas(): void {
  const canvas = document.getElementById("aos-graph-canvas");
  if (!canvas) return;

  const filtered = state.filterType === "all" ? state.nodes : state.nodes.filter(n => n.type === state.filterType);
  const searchMatch = state.searchQuery ? filtered.filter(n => n.label.toLowerCase().includes(state.searchQuery)) : null;

  canvas.innerHTML = `
    <svg width="100%" height="500" class="aos-graph-svg">
      <!-- Edges -->
      ${state.edges.map(e => {
        const src = state.nodes.find(n => n.id === e.source);
        const tgt = state.nodes.find(n => n.id === e.target);
        if (!src || !tgt) return "";
        const isSelected = state.selectedNode?.id === src.id || state.selectedNode?.id === tgt.id;
        const stroke = e.custom ? "#39d2c0" : (isSelected ? "#58a6ff" : "#30363d");
        const dash = e.custom ? 'stroke-dasharray="6,4"' : "";
        const width = e.custom ? 2.5 : (isSelected ? 3 : 1.5);
        return `<line x1="${src.x}" y1="${src.y}" x2="${tgt.x}" y2="${tgt.y}"
          stroke="${stroke}" stroke-width="${width}" ${dash}
          opacity="${searchMatch && !searchMatch.includes(src) && !searchMatch.includes(tgt) ? 0.1 : 0.7}" />`;
      }).join("")}

      <!-- Nodes -->
      ${filtered.map(n => {
        const highlight = searchMatch?.includes(n);
        const selected = state.selectedNode?.id === n.id || state.connectingFrom === n.id;
        const opacity = searchMatch && !highlight ? 0.15 : 1;
        return `<g transform="translate(${n.x},${n.y})" class="aos-graph-node"
          data-node-id="${n.id}" style="cursor:${state.connectMode ? 'crosshair' : 'pointer'};opacity:${opacity}">
          <circle r="${n.size / 2}" fill="${n.color}22" stroke="${selected ? '#58a6ff' : n.color}"
            stroke-width="${selected ? 3 : 2}" />
          <text text-anchor="middle" dy="5" font-size="${n.size / 4}">${n.emoji}</text>
          <text text-anchor="middle" dy="${n.size / 2 + 14}" font-size="10"
            fill="${highlight ? '#58a6ff' : '#8b949e'}" font-weight="${highlight ? '600' : '400'}">${n.label}</text>
        </g>`;
      }).join("")}
    </svg>
  `;

  // Bind node clicks
  canvas.querySelectorAll<SVGElement>(".aos-graph-node").forEach(el => {
    el.addEventListener("click", () => selectNode(el.dataset.nodeId!));
  });
}

// -- Events ---------------------------------------------------------------------

function bindEvents(): void {
  document.getElementById("aos-graph-search")?.addEventListener("input", (e) => {
    state.searchQuery = (e.target as HTMLInputElement).value.toLowerCase();
    renderGraphCanvas();
  });

  document.getElementById("aos-graph-filter")?.addEventListener("change", (e) => {
    state.filterType = (e.target as HTMLSelectElement).value;
    renderGraphCanvas();
  });

  document.getElementById("aos-graph-reset")?.addEventListener("click", () => {
    state.searchQuery = "";
    state.filterType = "all";
    state.selectedNode = null;
    state.connectMode = false;
    state.connectingFrom = null;
    (document.getElementById("aos-graph-search") as HTMLInputElement).value = "";
    (document.getElementById("aos-graph-filter") as HTMLSelectElement).value = "all";
    const panel = document.getElementById("aos-graph-panel");
    if (panel) panel.style.display = "none";
    updateConnectUI();
    renderGraphCanvas();
  });

  document.getElementById("aos-graph-connect")?.addEventListener("click", () => {
    state.connectMode = !state.connectMode;
    state.connectingFrom = null;
    updateConnectUI();
    renderGraphCanvas();
  });

  document.getElementById("aos-gp-close")?.addEventListener("click", () => {
    state.selectedNode = null;
    const panel = document.getElementById("aos-graph-panel");
    if (panel) panel.style.display = "none";
    renderGraphCanvas();
  });
}

function updateConnectUI(): void {
  const btn = document.getElementById("aos-graph-connect");
  const hint = document.getElementById("aos-graph-connect-hint");
  if (btn) {
    btn.classList.toggle("aos-btn-primary", state.connectMode);
    btn.textContent = state.connectMode ? "✕ Annuler connexion" : "🔗 Connecter";
  }
  if (hint) hint.style.display = state.connectMode ? "block" : "none";
}

function selectNode(id: string): void {
  const node = state.nodes.find(n => n.id === id);
  if (!node) return;

  // Mode connexion : premier clic = source, second clic = cible
  if (state.connectMode) {
    if (!state.connectingFrom) {
      state.connectingFrom = id;
      renderGraphCanvas();
      return;
    }
    if (state.connectingFrom === id) {
      state.connectingFrom = null;
      renderGraphCanvas();
      return;
    }
    createConnection(state.connectingFrom, id);
    state.connectingFrom = null;
    return;
  }

  state.selectedNode = node;
  const panel = document.getElementById("aos-graph-panel");
  if (panel) panel.style.display = "block";

  const title = document.getElementById("aos-gp-title");
  if (title) title.textContent = `${node.emoji} ${node.label}`;

  const body = document.getElementById("aos-gp-body");
  if (body) {
    const directEdges = state.edges.filter(e => e.source === id || e.target === id);
    body.innerHTML = `
      <div class="aos-gp-field"><label>Type</label><span>${node.type}</span></div>
      ${Object.entries(node.data).map(([k, v]) => `<div class="aos-gp-field"><label>${k}</label><span>${esc(v)}</span></div>`).join("")}
      <div class="aos-gp-section">
        <label>Connexions directes</label>
        <div class="aos-gp-connections">
          ${directEdges.map(e => {
            const other = e.source === id ? e.target : e.source;
            const otherNode = state.nodes.find(n => n.id === other);
            const delBtn = e.custom ? `<button class="aos-btn aos-btn-sm aos-btn-danger" data-disconnect="${e.source}|${e.target}" title="Supprimer la connexion">✕</button>` : "";
            return `<div class="aos-gp-conn">
              ${e.source === id ? "→" : "←"} ${otherNode?.emoji ?? ""} ${otherNode?.label ?? other}
              <span class="aos-gp-conn-label">${e.label}${e.custom ? " (custom)" : ""}</span>
              ${delBtn}
            </div>`;
          }).join("") || "<span class='aos-empty-state'>Aucune connexion</span>"}
        </div>
      </div>
    `;
    body.querySelectorAll<HTMLButtonElement>("[data-disconnect]").forEach(btn => {
      btn.addEventListener("click", () => {
        const [s, t] = btn.dataset.disconnect!.split("|");
        removeConnection(s, t);
      });
    });
  }

  renderGraphCanvas();
}

// -- Connect / Disconnect ------------------------------------------------------

async function createConnection(source: string, target: string): Promise<void> {
  const r = await fetch("/api/graph/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, target, label: "connecté" }),
  });
  const d = await r.json();
  if (d.success) {
    await buildGraphData();
    renderGraphCanvas();
  } else {
    alert(d.error || "Erreur de connexion");
  }
}

async function removeConnection(source: string, target: string): Promise<void> {
  const r = await fetch("/api/graph/disconnect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, target }),
  });
  const d = await r.json();
  if (d.success) {
    await buildGraphData();
    renderGraphCanvas();
  } else {
    alert(d.error || "Erreur de suppression");
  }
}

async function onStoreUpdate(): Promise<void> {
  if (store.getState().activePanel !== "graph") return;
  await buildGraphData();
  renderGraphCanvas();
}

function esc(s: string): string { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
