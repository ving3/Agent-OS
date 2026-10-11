// ============================================================================
// Agent OS — Panneau Canvas (multi-block editor, undo/redo, export)
// ============================================================================

import { store } from "../store";

// -- Types ----------------------------------------------------------------------

interface CanvasBlock {
  id: string;
  type: "markdown" | "code" | "image" | "card";
  content: string;
  language?: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

interface CanvasState {
  blocks: CanvasBlock[];
  undoStack: CanvasBlock[][];
  redoStack: CanvasBlock[][];
  selectedBlock: string | null;
  editingBlock: string | null;
  scale: number;
  offsetX: number;
  offsetY: number;
  connecting: string | null;
  connections: { from: string; to: string }[];
}

const state: CanvasState = {
  blocks: loadCanvas(),
  undoStack: [],
  redoStack: [],
  selectedBlock: null,
  editingBlock: null,
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  connecting: null,
  connections: [],
};

// -- Persistence ----------------------------------------------------------------

function loadCanvas(): CanvasBlock[] {
  try { const d = localStorage.getItem("aos_canvas"); if (d) return JSON.parse(d); } catch {}
  return [
    { id: crypto.randomUUID(), type: "markdown", content: "# Nouveau Canvas\n\nCliquez pour éditer.", x: 40, y: 40, w: 320, h: 180 },
  ];
}

function saveCanvas(): void { try { localStorage.setItem("aos_canvas", JSON.stringify(state.blocks)); } catch {} }

function pushUndo(): void {
  state.undoStack.push(JSON.parse(JSON.stringify(state.blocks)));
  if (state.undoStack.length > 50) state.undoStack.shift();
  state.redoStack = [];
}

// -- Renderer -------------------------------------------------------------------

export function renderCanvas(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-canvas" id="aos-canvas">
      <div class="aos-canvas-toolbar">
        <div class="aos-canvas-tools">
          <button class="aos-btn aos-btn-sm" data-canvas-action="add-md">📝 +Texte</button>
          <button class="aos-btn aos-btn-sm" data-canvas-action="add-code">💻 +Code</button>
          <button class="aos-btn aos-btn-sm" data-canvas-action="add-card">🃏 +Carte</button>
          <span class="aos-canvas-sep">|</span>
          <button class="aos-btn aos-btn-sm" data-canvas-action="undo" id="aos-cv-undo" disabled>↩ Undo</button>
          <button class="aos-btn aos-btn-sm" data-canvas-action="redo" id="aos-cv-redo" disabled>↪ Redo</button>
          <span class="aos-canvas-sep">|</span>
          <button class="aos-btn aos-btn-sm" data-canvas-action="export-json">💾 JSON</button>
          <button class="aos-btn aos-btn-sm" data-canvas-action="export-md">📄 Markdown</button>
          <button class="aos-btn aos-btn-sm" data-canvas-action="clear">🗑️ Clear</button>
        </div>
        <div class="aos-canvas-zoom">
          <button class="aos-btn aos-btn-sm" data-canvas-action="zoom-out">−</button>
          <span id="aos-cv-zoom">100%</span>
          <button class="aos-btn aos-btn-sm" data-canvas-action="zoom-in">+</button>
          <button class="aos-btn aos-btn-sm" data-canvas-action="zoom-reset">↺</button>
        </div>
      </div>
      <div class="aos-canvas-area" id="aos-canvas-area">
        <div class="aos-canvas-inner" id="aos-canvas-inner"></div>
        <svg class="aos-canvas-svg" id="aos-canvas-svg"></svg>
      </div>
    </div>
  `;

  renderBlocks();
  renderConnections();
  bindEvents();
  updateUndoButtons();
}

// -- Blocks ---------------------------------------------------------------------

function renderBlocks(): void {
  const inner = document.getElementById("aos-canvas-inner");
  if (!inner) return;

  inner.style.transform = `translate(${state.offsetX}px,${state.offsetY}px) scale(${state.scale})`;
  inner.style.transformOrigin = "0 0";

  inner.innerHTML = state.blocks.map(b => `
    <div class="aos-canvas-block ${state.selectedBlock === b.id ? "aos-canvas-block-selected" : ""}"
         data-block-id="${b.id}"
         style="left:${b.x}px;top:${b.y}px;width:${b.w}px;min-height:${b.h}px">
      <div class="aos-canvas-block-header">
        <span class="aos-canvas-block-type">${typeIcon(b.type)} ${b.type}</span>
        <div class="aos-canvas-block-actions">
          <button class="aos-btn aos-btn-sm" data-block-action="link" data-block-id="${b.id}" title="Connecter">🔗</button>
          <button class="aos-btn aos-btn-sm" data-block-action="delete" data-block-id="${b.id}">✕</button>
        </div>
      </div>
      <div class="aos-canvas-block-body" data-block-edit="${b.id}">
        ${state.editingBlock === b.id ? renderBlockEditor(b) : renderBlockContent(b)}
      </div>
    </div>
  `).join("");

  // Bind block selection
  inner.querySelectorAll<HTMLElement>(".aos-canvas-block").forEach(el => {
    el.addEventListener("click", (e) => {
      if ((e.target as HTMLElement).closest("button")) return;
      selectBlock(el.dataset.blockId!);
    });
    el.addEventListener("dblclick", (e) => {
      if ((e.target as HTMLElement).closest("button")) return;
      startEdit(el.dataset.blockId!);
    });
  });

  // Bind block actions
  inner.querySelectorAll<HTMLButtonElement>("[data-block-action]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const action = btn.dataset.blockAction!;
      const id = btn.dataset.blockId!;
      if (action === "delete") deleteBlock(id);
      if (action === "link") toggleConnect(id);
    });
  });
}

function renderBlockContent(b: CanvasBlock): string {
  switch (b.type) {
    case "markdown": return `<div class="aos-cv-md">${renderMd(b.content)}</div>`;
    case "code": return `<pre class="aos-cv-code"><code>${esc(b.content)}</code></pre>`;
    case "card": return `<div class="aos-cv-card"><strong>${esc(b.content.split("\n")[0] || "")}</strong><p>${esc(b.content.split("\n").slice(1).join("\n"))}</p></div>`;
    case "image": return `<div class="aos-cv-img">${b.content ? `<img src="${esc(b.content)}" alt="image" onerror="this.style.display='none'">` : "Pas d'image"}</div>`;
  }
}

function renderBlockEditor(b: CanvasBlock): string {
  return `<textarea class="aos-cv-editor" data-edit-id="${b.id}"
    rows="${Math.max(4, b.content.split("\n").length)}">${esc(b.content)}</textarea>
    <div class="aos-cv-editor-bar">
      <button class="aos-btn aos-btn-sm aos-btn-primary" data-edit-save="${b.id}">✓</button>
      <button class="aos-btn aos-btn-sm" data-edit-cancel="${b.id}">✕</button>
    </div>`;
}

// -- Connections ----------------------------------------------------------------

function renderConnections(): void {
  const svg = document.getElementById("aos-canvas-svg");
  if (!svg) return;

  svg.innerHTML = state.connections.map(c => {
    const from = state.blocks.find(b => b.id === c.from);
    const to = state.blocks.find(b => b.id === c.to);
    if (!from || !to) return "";
    const x1 = from.x + from.w / 2, y1 = from.y + from.h;
    const x2 = to.x + to.w / 2, y2 = to.y;
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#58a6ff" stroke-width="2" marker-end="url(#arrow)"/>`;
  }).join("") + `<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#58a6ff"/></marker></defs>`;
}

// -- Events ---------------------------------------------------------------------

function bindEvents(): void {
  // Toolbar
  document.querySelectorAll<HTMLButtonElement>("[data-canvas-action]").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.canvasAction!;
      switch (action) {
        case "add-md": addBlock("markdown"); break;
        case "add-code": addBlock("code"); break;
        case "add-card": addBlock("card"); break;
        case "undo": undo(); break;
        case "redo": redo(); break;
        case "export-json": exportCanvas("json"); break;
        case "export-md": exportCanvas("md"); break;
        case "clear": clearCanvas(); break;
        case "zoom-in": zoom(0.1); break;
        case "zoom-out": zoom(-0.1); break;
        case "zoom-reset": zoom(1 - state.scale); break;
      }
    });
  });

  // Edit save/cancel
  document.getElementById("aos-canvas-inner")?.addEventListener("click", (e) => {
    const btn = (e.target as HTMLElement).closest<HTMLButtonElement>("[data-edit-save], [data-edit-cancel]");
    if (!btn) return;
    const id = btn.dataset.editSave || btn.dataset.editCancel!;
    if (btn.dataset.editSave) saveEdit(id);
    else cancelEdit();
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if (store.getState().activePanel !== "canvas") return;
    if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); undo(); }
    if ((e.ctrlKey || e.metaKey) && e.key === "y") { e.preventDefault(); redo(); }
    if (e.key === "Escape") { state.selectedBlock = null; state.editingBlock = null; state.connecting = null; renderBlocks(); }
  });
}

// -- Block operations -----------------------------------------------------------

function addBlock(type: CanvasBlock["type"]): void {
  pushUndo();
  state.blocks.push({
    id: crypto.randomUUID(),
    type,
    content: type === "code" ? "// code" : type === "card" ? "Titre\nDescription" : "## Nouveau bloc",
    x: 60 + state.blocks.length * 30,
    y: 60 + state.blocks.length * 30,
    w: 320,
    h: type === "code" ? 160 : 140,
    language: type === "code" ? "javascript" : undefined,
  });
  saveCanvas();
  renderBlocks();
}

function selectBlock(id: string): void {
  state.selectedBlock = id;
  state.editingBlock = null;
  renderBlocks();
}

function startEdit(id: string): void {
  state.editingBlock = id;
  renderBlocks();
  setTimeout(() => {
    const ta = document.querySelector<HTMLTextAreaElement>(`[data-edit-id="${id}"]`);
    if (ta) { ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); }
  }, 50);
}

function saveEdit(id: string): void {
  pushUndo();
  const ta = document.querySelector<HTMLTextAreaElement>(`[data-edit-id="${id}"]`);
  if (ta) {
    const block = state.blocks.find(b => b.id === id);
    if (block) block.content = ta.value;
  }
  state.editingBlock = null;
  saveCanvas();
  renderBlocks();
}

function cancelEdit(): void {
  state.editingBlock = null;
  renderBlocks();
}

function deleteBlock(id: string): void {
  pushUndo();
  state.blocks = state.blocks.filter(b => b.id !== id);
  state.connections = state.connections.filter(c => c.from !== id && c.to !== id);
  if (state.selectedBlock === id) state.selectedBlock = null;
  saveCanvas();
  renderBlocks();
  renderConnections();
}

function toggleConnect(id: string): void {
  if (state.connecting === null) {
    state.connecting = id;
  } else if (state.connecting !== id) {
    state.connections.push({ from: state.connecting, to: id });
    state.connecting = null;
    renderConnections();
  } else {
    state.connecting = null;
  }
}

// -- Undo/Redo ------------------------------------------------------------------

function undo(): void {
  if (state.undoStack.length === 0) return;
  state.redoStack.push(JSON.parse(JSON.stringify(state.blocks)));
  state.blocks = state.undoStack.pop()!;
  saveCanvas();
  renderBlocks();
  renderConnections();
  updateUndoButtons();
}

function redo(): void {
  if (state.redoStack.length === 0) return;
  state.undoStack.push(JSON.parse(JSON.stringify(state.blocks)));
  state.blocks = state.redoStack.pop()!;
  saveCanvas();
  renderBlocks();
  renderConnections();
  updateUndoButtons();
}

function updateUndoButtons(): void {
  const undo = document.getElementById("aos-cv-undo") as HTMLButtonElement;
  const redo = document.getElementById("aos-cv-redo") as HTMLButtonElement;
  if (undo) undo.disabled = state.undoStack.length === 0;
  if (redo) redo.disabled = state.redoStack.length === 0;
}

// -- Zoom -----------------------------------------------------------------------

function zoom(delta: number): void {
  state.scale = Math.max(0.2, Math.min(3, state.scale + delta));
  const el = document.getElementById("aos-cv-zoom");
  if (el) el.textContent = Math.round(state.scale * 100) + "%";
  renderBlocks();
}

// -- Export ---------------------------------------------------------------------

function exportCanvas(format: "json" | "md"): void {
  let content: string;
  let filename: string;
  let mime: string;

  if (format === "json") {
    content = JSON.stringify({ blocks: state.blocks, connections: state.connections }, null, 2);
    filename = "canvas-export.json";
    mime = "application/json";
  } else {
    content = state.blocks.map(b => {
      if (b.type === "code") return "```" + (b.language || "") + "\n" + b.content + "\n```";
      return b.content;
    }).join("\n\n---\n\n");
    filename = "canvas-export.md";
    mime = "text/markdown";
  }

  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function clearCanvas(): void {
  if (!confirm("Effacer tout le canvas ?")) return;
  pushUndo();
  state.blocks = [];
  state.connections = [];
  saveCanvas();
  renderBlocks();
  renderConnections();
}

// -- Helpers --------------------------------------------------------------------

function typeIcon(t: string): string { return ({ markdown: "📝", code: "💻", image: "🖼️", card: "🃏" })[t] || "📄"; }
function esc(s: string): string { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

function renderMd(text: string): string {
  return esc(text)
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^# (.+)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}
