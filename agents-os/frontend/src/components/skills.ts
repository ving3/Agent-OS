// ============================================================================
// Agent OS — Panneau Skills (catalogue, config, logs)
// ============================================================================

import { store } from "../store";
import type { SkillInfo } from "../types";

interface SkillsState {
  skills: SkillInfo[];
  selectedSkill: SkillInfo | null;
  searchQuery: string;
}

const state: SkillsState = { skills: [], selectedSkill: null, searchQuery: "" };

export function renderSkills(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-skills" id="aos-skills">
      <div class="aos-skills-header">
        <div class="aos-skills-title">🧩 Catalogue de compétences</div>
        <div class="aos-skills-actions">
          <input type="text" class="aos-input aos-skills-search" id="aos-skills-search" placeholder="Rechercher...">
          <span class="aos-skills-count" id="aos-skills-count">0 compétences</span>
        </div>
      </div>

      <!-- Detail panel -->
      <div class="aos-skills-detail" id="aos-skills-detail" style="display:none">
        <div class="aos-skills-detail-header">
          <span class="aos-skills-detail-name" id="aos-sd-name"></span>
          <button class="aos-btn aos-btn-sm" id="aos-sd-close">✕ Fermer</button>
        </div>
        <div class="aos-skills-detail-body">
          <div class="aos-skills-detail-section">
            <label>Chemin</label>
            <code id="aos-sd-path"></code>
          </div>
          <div class="aos-skills-detail-section">
            <label>Description</label>
            <p id="aos-sd-desc"></p>
          </div>
          <div class="aos-skills-detail-section">
            <label>Configuration</label>
            <div class="aos-skills-config" id="aos-sd-config">
              <div class="aos-empty-state">Aucune configuration requise</div>
            </div>
          </div>
          <div class="aos-skills-detail-section">
            <label>Derniers logs d'exécution</label>
            <div class="aos-skills-logs" id="aos-sd-logs">
              <div class="aos-empty-state">Aucun log récent</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Grid -->
      <div class="aos-skills-grid" id="aos-skills-grid"></div>
    </div>
  `;

  bindEvents();
  store.subscribe(onStoreUpdate);
  loadSkills();
}

function bindEvents(): void {
  document.getElementById("aos-skills-search")?.addEventListener("input", (e) => {
    state.searchQuery = (e.target as HTMLInputElement).value.toLowerCase();
    renderGrid();
  });
  document.getElementById("aos-sd-close")?.addEventListener("click", () => {
    state.selectedSkill = null;
    const detail = document.getElementById("aos-skills-detail");
    if (detail) detail.style.display = "none";
  });
}

async function loadSkills(): Promise<void> {
  try {
    const r = await fetch("/api/skills");
    const data = await r.json();
    state.skills = data.skills || [];
    renderGrid();
    updateCount();
  } catch (e) {
    console.error("Skills load failed:", e);
  }
}

function renderGrid(): void {
  const grid = document.getElementById("aos-skills-grid");
  if (!grid) return;

  const filtered = state.searchQuery
    ? state.skills.filter(s =>
        s.name.toLowerCase().includes(state.searchQuery) ||
        s.description.toLowerCase().includes(state.searchQuery) ||
        s.path.toLowerCase().includes(state.searchQuery))
    : state.skills;

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="aos-empty-state">${state.searchQuery ? "Aucune compétence trouvée" : "Aucune compétence chargée"}</div>`;
    return;
  }

  grid.innerHTML = filtered.map(s => `
    <div class="aos-skill-card" data-skill="${s.name}">
      <div class="aos-skill-card-header">
        <span class="aos-skill-card-icon">🧩</span>
        <div>
          <div class="aos-skill-card-name">${esc(s.name)}</div>
          <div class="aos-skill-card-path">${esc(s.path)}</div>
        </div>
        <span class="aos-skill-card-status aos-status-active">Actif</span>
      </div>
      <div class="aos-skill-card-body">
        <p class="aos-skill-card-desc">${esc(s.description || "Aucune description")}</p>
      </div>
    </div>
  `).join("");

  grid.querySelectorAll<HTMLElement>(".aos-skill-card").forEach(card => {
    card.addEventListener("click", () => {
      const name = card.dataset.skill!;
      state.selectedSkill = state.skills.find(s => s.name === name) ?? null;
      showDetail();
    });
  });
}

function showDetail(): void {
  const s = state.selectedSkill;
  if (!s) return;

  const detail = document.getElementById("aos-skills-detail");
  if (detail) detail.style.display = "block";

  const nameEl = document.getElementById("aos-sd-name");
  if (nameEl) nameEl.textContent = `🧩 ${s.name}`;

  const pathEl = document.getElementById("aos-sd-path");
  if (pathEl) pathEl.textContent = s.path;

  const descEl = document.getElementById("aos-sd-desc");
  if (descEl) descEl.textContent = s.description || "Aucune description";

  // Scroll to detail
  detail?.scrollIntoView({ behavior: "smooth" });
}

function updateCount(): void {
  const el = document.getElementById("aos-skills-count");
  if (el) el.textContent = `${state.skills.length} compétences`;
}

function onStoreUpdate(): void {
  if (store.getState().activePanel !== "skills") return;
  const storeSkills = store.getState().skills;
  if (storeSkills.length !== state.skills.length) {
    state.skills = storeSkills;
    renderGrid();
    updateCount();
  }
}

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
