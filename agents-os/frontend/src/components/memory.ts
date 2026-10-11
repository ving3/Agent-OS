// ============================================================================
// Agent OS — Panneau Mémoire (explorer, semantic search, CRUD)
// ============================================================================

import { store } from "../store";
import type { AgentProfile } from "../types";

interface MemoryState {
  profiles: AgentProfile[];
  selectedProfile: string | null;
  searchQuery: string;
  editMode: boolean;
  editContent: string;
}

const state: MemoryState = { profiles: [], selectedProfile: null, searchQuery: "", editMode: false, editContent: "" };

export function renderMemory(container: HTMLElement): void {
  const profiles = store.getState().profiles;

  container.innerHTML = `
    <div class="aos-memory" id="aos-memory">
      <div class="aos-memory-header">
        <div class="aos-memory-title">🧠 Mémoire des agents</div>
        <div class="aos-memory-actions">
          <input type="text" class="aos-input aos-memory-search" id="aos-memory-search" placeholder="Recherche sémantique...">
          <span class="aos-memory-count" id="aos-memory-count">${profiles.length} agents</span>
        </div>
      </div>

      <!-- Memory editor -->
      <div class="aos-memory-editor" id="aos-memory-editor" style="display:none">
        <div class="aos-memory-editor-header">
          <span id="aos-me-name"></span>
          <div>
            <button class="aos-btn aos-btn-sm" id="aos-me-edit">✏️ Éditer</button>
            <button class="aos-btn aos-btn-sm" id="aos-me-close">✕ Fermer</button>
          </div>
        </div>
        <div class="aos-memory-editor-body">
          <div id="aos-me-view" class="aos-memory-content"></div>
          <textarea id="aos-me-textarea" class="aos-input aos-memory-textarea" style="display:none"></textarea>
          <div class="aos-memory-editor-actions" id="aos-me-actions" style="display:none">
            <button class="aos-btn aos-btn-primary" id="aos-me-save">💾 Sauvegarder</button>
            <button class="aos-btn" id="aos-me-cancel">Annuler</button>
          </div>
        </div>
      </div>

      <!-- Search results -->
      <div class="aos-memory-results" id="aos-memory-results" style="display:none">
        <div class="aos-memory-results-header">Résultats de recherche</div>
        <div id="aos-memory-results-list"></div>
      </div>

      <!-- Profiles list -->
      <div class="aos-memory-list" id="aos-memory-list"></div>
    </div>
  `;

  state.profiles = profiles;
  renderProfileList();
  bindEvents();
  store.subscribe(onStoreUpdate);
}

function renderProfileList(): void {
  const list = document.getElementById("aos-memory-list");
  if (!list) return;

  const profiles = state.profiles;
  if (profiles.length === 0) {
    list.innerHTML = `<div class="aos-empty-state">Aucun agent avec mémoire</div>`;
    return;
  }

  list.innerHTML = profiles.map(p => `
    <div class="aos-memory-card" data-agent="${p.name}">
      <div class="aos-memory-card-header">
        <span class="aos-memory-card-emoji">${p.emoji}</span>
        <div>
          <div class="aos-memory-card-name">${esc(p.name)}</div>
          <div class="aos-memory-card-meta">
            ${p.has_memory ? "🧠 Mémoire active" : "📭 Vide"}
            ${p.memory ? ` · ${p.memory.length} caractères` : ""}
          </div>
        </div>
        <button class="aos-btn aos-btn-sm" data-action="view" data-agent="${p.name}">📖 Voir</button>
      </div>
      ${p.memory ? `
      <div class="aos-memory-card-preview">${esc(p.memory.slice(0, 200))}${p.memory.length > 200 ? "..." : ""}</div>
      ` : ""}
    </div>
  `).join("");

  // Bind view buttons
  list.querySelectorAll<HTMLButtonElement>("[data-action='view']").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditor(btn.dataset.agent!);
    });
  });
}

function openEditor(agentName: string): void {
  const profile = state.profiles.find(p => p.name === agentName);
  if (!profile) return;

  state.selectedProfile = agentName;
  state.editMode = false;
  state.editContent = profile.memory || "";

  const editor = document.getElementById("aos-memory-editor");
  if (editor) editor.style.display = "block";

  const nameEl = document.getElementById("aos-me-name");
  if (nameEl) nameEl.textContent = `${profile.emoji} ${profile.name}`;

  const view = document.getElementById("aos-me-view");
  if (view) {
    view.innerHTML = profile.memory
      ? `<div class="aos-memory-md">${formatMarkdown(profile.memory)}</div>`
      : `<div class="aos-empty-state">Aucune mémoire pour ${profile.name}</div>`;
  }

  const textarea = document.getElementById("aos-me-textarea") as HTMLTextAreaElement;
  const actions = document.getElementById("aos-me-actions");
  if (textarea) { textarea.value = state.editContent; textarea.style.display = "none"; }
  if (actions) actions.style.display = "none";
  if (view) view.style.display = "block";

  editor.scrollIntoView({ behavior: "smooth" });
}

function bindEvents(): void {
  document.getElementById("aos-memory-search")?.addEventListener("input", (e) => {
    state.searchQuery = (e.target as HTMLInputElement).value.toLowerCase();
    if (state.searchQuery.length >= 2) performSearch();
    else hideSearchResults();
  });

  document.getElementById("aos-me-edit")?.addEventListener("click", () => {
    state.editMode = true;
    const view = document.getElementById("aos-me-view");
    const textarea = document.getElementById("aos-me-textarea") as HTMLTextAreaElement;
    const actions = document.getElementById("aos-me-actions");
    if (view) view.style.display = "none";
    if (textarea) { textarea.style.display = "block"; textarea.focus(); }
    if (actions) actions.style.display = "flex";
  });

  document.getElementById("aos-me-save")?.addEventListener("click", saveMemory);
  document.getElementById("aos-me-cancel")?.addEventListener("click", cancelEdit);
  document.getElementById("aos-me-close")?.addEventListener("click", closeEditor);
}

function performSearch(): void {
  const results = document.getElementById("aos-memory-results");
  const list = document.getElementById("aos-memory-results-list");
  if (!results || !list) return;

  results.style.display = "block";
  const hits: { agent: string; snippet: string; score: number }[] = [];

  state.profiles.forEach(p => {
    if (!p.memory) return;
    const idx = p.memory.toLowerCase().indexOf(state.searchQuery);
    if (idx >= 0) {
      const start = Math.max(0, idx - 40);
      const end = Math.min(p.memory.length, idx + state.searchQuery.length + 40);
      const snippet = (start > 0 ? "..." : "") + p.memory.slice(start, end) + (end < p.memory.length ? "..." : "");
      hits.push({ agent: p.name, snippet, score: 1.0 - idx / p.memory.length });
    }
  });

  if (hits.length === 0) {
    list.innerHTML = `<div class="aos-empty-state">Aucun résultat pour "${state.searchQuery}"</div>`;
  } else {
    list.innerHTML = hits.map(h => `
      <div class="aos-memory-hit" data-agent="${h.agent}">
        <div class="aos-memory-hit-header">
          <span class="aos-memory-hit-agent">${h.agent}</span>
          <span class="aos-memory-hit-score">Score: ${(h.score * 100).toFixed(0)}%</span>
        </div>
        <div class="aos-memory-hit-snippet">${esc(h.snippet).replace(new RegExp(state.searchQuery, 'gi'), m => `<mark>${m}</mark>`)}</div>
      </div>
    `).join("");
  }

  list.querySelectorAll<HTMLElement>(".aos-memory-hit").forEach(hit => {
    hit.addEventListener("click", () => openEditor(hit.dataset.agent!));
  });
}

function hideSearchResults(): void {
  const results = document.getElementById("aos-memory-results");
  if (results) results.style.display = "none";
}

function saveMemory(): void {
  // Memory is read-only from profiles directory
  // In a full implementation, this would POST to /api/memory/update
  const textarea = document.getElementById("aos-me-textarea") as HTMLTextAreaElement;
  if (textarea) state.editContent = textarea.value;
  state.editMode = false;
  openEditor(state.selectedProfile!);
}

function cancelEdit(): void {
  state.editMode = false;
  const textarea = document.getElementById("aos-me-textarea") as HTMLTextAreaElement;
  if (textarea) { textarea.value = state.editContent; textarea.style.display = "none"; }
  const actions = document.getElementById("aos-me-actions");
  if (actions) actions.style.display = "none";
  const view = document.getElementById("aos-me-view");
  if (view) view.style.display = "block";
}

function closeEditor(): void {
  state.selectedProfile = null;
  const editor = document.getElementById("aos-memory-editor");
  if (editor) editor.style.display = "none";
}

function onStoreUpdate(): void {
  if (store.getState().activePanel !== "memory") return;
  const profiles = store.getState().profiles;
  if (JSON.stringify(profiles.map(p => p.name)) !== JSON.stringify(state.profiles.map(p => p.name))) {
    state.profiles = profiles;
    renderProfileList();
  }
}

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatMarkdown(text: string): string {
  return esc(text)
    .replace(/^# (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h4>$1</h4>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}
