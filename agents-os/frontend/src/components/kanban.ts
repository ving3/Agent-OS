// ============================================================================
// Agent OS — Panneau Kanban (drag-drop, tasks, link to chat/canvas)
// ============================================================================

import { store } from "../store";
import type { KanbanTask } from "../types";

interface KanbanState {
  tasks: KanbanTask[];
  columns: { id: string; title: string; emoji: string }[];
  editingTask: number | null;
  draggingTask: number | null;
  dragOverCol: string | null;
}

const COLUMNS = [
  { id: "todo", title: "À faire", emoji: "📋" },
  { id: "progress", title: "En cours", emoji: "🔄" },
  { id: "review", title: "Review", emoji: "👁️" },
  { id: "done", title: "Terminé", emoji: "✅" },
];

const state: KanbanState = {
  tasks: loadTasks(),
  columns: COLUMNS,
  editingTask: null,
  draggingTask: null,
  dragOverCol: null,
};

function loadTasks(): KanbanTask[] {
  try {
    const d = localStorage.getItem("aos_tasks_v3");
    if (d) return JSON.parse(d);
  } catch {}
  return [
    { id: 1, title: "Configurer l'authentification SSO", agent: "architect", status: "todo", created: new Date().toISOString() },
    { id: 2, title: "Implémenter le streaming SSE du chat", agent: "senior-dev", status: "progress", created: new Date().toISOString() },
    { id: 3, title: "Auditer les permissions RBAC", agent: "code-reviewer", status: "done", created: new Date().toISOString() },
  ];
}

function saveTasks(): void {
  try { localStorage.setItem("aos_tasks_v3", JSON.stringify(state.tasks)); } catch {}
}

// -- Renderer -------------------------------------------------------------------

export function renderKanban(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-kanban" id="aos-kanban">
      <div class="aos-kanban-header">
        <div class="aos-kanban-title">📋 Tableau Kanban</div>
        <div class="aos-kanban-actions">
          <button class="aos-btn aos-btn-primary" id="aos-kb-add">+ Ajouter une mission</button>
          <button class="aos-btn" id="aos-kb-export">📄 Exporter</button>
        </div>
      </div>

      <!-- Add task modal -->
      <div class="aos-modal" id="kb-add-modal" style="display:none">
        <div class="aos-modal-card">
          <div class="aos-modal-header">
            <span class="aos-modal-title">➕ Nouvelle mission</span>
            <button class="aos-modal-close" data-close="kb-add-modal">✕</button>
          </div>
          <div class="aos-modal-body">
            <div class="aos-form-grid">
              <div class="aos-form-group" style="grid-column:1/-1">
                <label>Titre</label>
                <input type="text" id="kb-task-title" class="aos-input" placeholder="Titre de la mission">
              </div>
              <div class="aos-form-group">
                <label>Agent assigné</label>
                <select id="kb-task-agent" class="aos-select">
                  ${store.getState().profiles.map(p => `<option value="${p.name}">${p.emoji} ${p.name}</option>`).join("")}
                  <option value="devops">⚙️ devops</option>
                </select>
              </div>
              <div class="aos-form-group">
                <label>Priorité</label>
                <select id="kb-task-priority" class="aos-select">
                  <option value="low">Basse</option>
                  <option value="medium" selected>Moyenne</option>
                  <option value="high">Haute</option>
                  <option value="critical">Critique</option>
                </select>
              </div>
            </div>
          </div>
          <div class="aos-modal-footer">
            <button class="aos-btn aos-btn-primary" id="kb-add-confirm">Créer</button>
            <button class="aos-btn" data-close="kb-add-modal">Annuler</button>
          </div>
        </div>
      </div>

      <!-- Edit task modal -->
      <div class="aos-modal" id="kb-edit-modal" style="display:none">
        <div class="aos-modal-card">
          <div class="aos-modal-header">
            <span class="aos-modal-title">✏️ Éditer la mission</span>
            <button class="aos-modal-close" data-close="kb-edit-modal">✕</button>
          </div>
          <div class="aos-modal-body">
            <div class="aos-form-grid">
              <div class="aos-form-group" style="grid-column:1/-1">
                <label>Titre</label>
                <input type="text" id="kb-edit-title" class="aos-input">
              </div>
              <div class="aos-form-group">
                <label>Agent</label>
                <select id="kb-edit-agent" class="aos-select">
                  ${store.getState().profiles.map(p => `<option value="${p.name}">${p.emoji} ${p.name}</option>`).join("")}
                </select>
              </div>
              <div class="aos-form-group">
                <label>Statut</label>
                <select id="kb-edit-status" class="aos-select">
                  ${COLUMNS.map(c => `<option value="${c.id}">${c.emoji} ${c.title}</option>`).join("")}
                </select>
              </div>
              <div class="aos-form-group" style="grid-column:1/-1">
                <label>Description (Markdown)</label>
                <textarea id="kb-edit-desc" class="aos-input" rows="4" style="resize:vertical"></textarea>
              </div>
            </div>
          </div>
          <div class="aos-modal-footer">
            <button class="aos-btn aos-btn-primary" id="kb-edit-save">💾 Sauvegarder</button>
            <button class="aos-btn aos-btn-danger" id="kb-edit-delete">🗑️ Supprimer</button>
            <button class="aos-btn" data-close="kb-edit-modal">Annuler</button>
          </div>
        </div>
      </div>

      <!-- Board -->
      <div class="aos-kanban-board" id="aos-kanban-board">
        ${state.columns.map(c => `
          <div class="aos-kanban-col" data-col="${c.id}">
            <div class="aos-kanban-col-header">
              <span>${c.emoji} ${c.title}</span>
              <span class="aos-kanban-col-count">${state.tasks.filter(t => t.status === c.id).length}</span>
            </div>
            <div class="aos-kanban-col-body" data-col-body="${c.id}"></div>
          </div>
        `).join("")}
      </div>
    </div>
  `;

  renderAllColumns();
  bindEvents();
  store.subscribe(onStoreUpdate);
}

// -- Column rendering -----------------------------------------------------------

function renderAllColumns(): void {
  state.columns.forEach(c => renderColumn(c.id));
}

function renderColumn(colId: string): void {
  const body = document.querySelector(`[data-col-body="${colId}"]`);
  if (!body) return;

  const tasks = state.tasks.filter(t => t.status === colId);

  if (tasks.length === 0) {
    body.innerHTML = `<div class="aos-kanban-empty">Glissez une carte ici</div>`;
  } else {
    body.innerHTML = tasks.map(t => {
      const agent = store.getState().profiles.find(p => p.name === t.agent);
      const emoji = agent?.emoji ?? "🤖";
      const color = agent?.color ?? "#58a6ff";
      return `<div class="aos-kanban-card" draggable="true" data-task-id="${t.id}"
        style="border-left: 3px solid ${color}">
        <div class="aos-kanban-card-header">
          <span class="aos-kanban-card-agent">${emoji} ${esc(t.agent)}</span>
          <div class="aos-kanban-card-actions">
            <button class="aos-btn aos-btn-sm" data-kb-edit="${t.id}">✏️</button>
          </div>
        </div>
        <div class="aos-kanban-card-title">${esc(t.title)}</div>
        <div class="aos-kanban-card-meta">${new Date(t.created).toLocaleDateString("fr")}</div>
      </div>`;
    }).join("");
  }

  // Update counts
  state.columns.forEach(c => {
    const count = document.querySelector(`[data-col="${c.id}"] .aos-kanban-col-count`);
    if (count) count.textContent = String(state.tasks.filter(t => t.status === c.id).length);
  });

  // Bind drag
  body.querySelectorAll<HTMLElement>(".aos-kanban-card").forEach(card => {
    card.addEventListener("dragstart", (e) => {
      state.draggingTask = Number(card.dataset.taskId);
      card.classList.add("aos-kanban-card-dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("aos-kanban-card-dragging");
      state.draggingTask = null;
      state.dragOverCol = null;
      document.querySelectorAll(".aos-kanban-col").forEach(c => c.classList.remove("aos-kanban-col-over"));
    });
  });

  // Bind edit
  body.querySelectorAll<HTMLButtonElement>("[data-kb-edit]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openEditTask(Number(btn.dataset.kbEdit));
    });
  });
}

// -- Events ---------------------------------------------------------------------

function bindEvents(): void {
  // Add task
  document.getElementById("aos-kb-add")?.addEventListener("click", () => {
    const modal = document.getElementById("kb-add-modal");
    if (modal) modal.style.display = "flex";
  });
  document.getElementById("kb-add-confirm")?.addEventListener("click", addTask);
  document.getElementById("kb-edit-save")?.addEventListener("click", saveEditTask);
  document.getElementById("kb-edit-delete")?.addEventListener("click", deleteEditTask);
  document.getElementById("aos-kb-export")?.addEventListener("click", exportKanban);

  // Modal close
  document.querySelectorAll("[data-close]").forEach(el => {
    el.addEventListener("click", () => {
      const modal = document.getElementById(el.getAttribute("data-close")!);
      if (modal) modal.style.display = "none";
    });
  });

  // Drop zones
  document.querySelectorAll<HTMLElement>("[data-col-body]").forEach(body => {
    body.addEventListener("dragover", (e) => {
      e.preventDefault();
      const col = (body.closest("[data-col]") as HTMLElement)?.dataset.col!;
      state.dragOverCol = col;
      document.querySelectorAll(".aos-kanban-col").forEach(c => c.classList.remove("aos-kanban-col-over"));
      body.closest(".aos-kanban-col")?.classList.add("aos-kanban-col-over");
    });
    body.addEventListener("drop", (e) => {
      e.preventDefault();
      const col = (body.closest("[data-col]") as HTMLElement)?.dataset.col!;
      if (state.draggingTask !== null) {
        moveTask(state.draggingTask, col);
      }
      document.querySelectorAll(".aos-kanban-col").forEach(c => c.classList.remove("aos-kanban-col-over"));
    });
  });
}

// -- Task operations ------------------------------------------------------------

function addTask(): void {
  const title = (document.getElementById("kb-task-title") as HTMLInputElement)?.value.trim();
  const agent = (document.getElementById("kb-task-agent") as HTMLSelectElement)?.value;
  if (!title) return;

  state.tasks.push({
    id: Date.now(),
    title,
    agent,
    status: "todo",
    created: new Date().toISOString(),
  });

  saveTasks();
  renderAllColumns();
  document.getElementById("kb-add-modal")!.style.display = "none";
  (document.getElementById("kb-task-title") as HTMLInputElement).value = "";
}

function moveTask(taskId: number, newStatus: string): void {
  const task = state.tasks.find(t => t.id === taskId);
  if (task) {
    task.status = newStatus;
    saveTasks();
    renderAllColumns();
  }
}

function openEditTask(taskId: number): void {
  const task = state.tasks.find(t => t.id === taskId);
  if (!task) return;

  state.editingTask = taskId;
  const modal = document.getElementById("kb-edit-modal");
  if (modal) modal.style.display = "flex";

  (document.getElementById("kb-edit-title") as HTMLInputElement).value = task.title;
  (document.getElementById("kb-edit-agent") as HTMLSelectElement).value = task.agent;
  (document.getElementById("kb-edit-status") as HTMLSelectElement).value = task.status;
}

function saveEditTask(): void {
  if (state.editingTask === null) return;
  const task = state.tasks.find(t => t.id === state.editingTask);
  if (!task) return;

  task.title = (document.getElementById("kb-edit-title") as HTMLInputElement).value.trim();
  task.agent = (document.getElementById("kb-edit-agent") as HTMLSelectElement).value;
  task.status = (document.getElementById("kb-edit-status") as HTMLSelectElement).value;

  saveTasks();
  renderAllColumns();
  document.getElementById("kb-edit-modal")!.style.display = "none";
  state.editingTask = null;
}

function deleteEditTask(): void {
  if (state.editingTask === null) return;
  state.tasks = state.tasks.filter(t => t.id !== state.editingTask);
  saveTasks();
  renderAllColumns();
  document.getElementById("kb-edit-modal")!.style.display = "none";
  state.editingTask = null;
}

function exportKanban(): void {
  const markdown = state.columns.map(c => {
    const tasks = state.tasks.filter(t => t.status === c.id);
    return `## ${c.emoji} ${c.title}\n\n${tasks.map(t => `- [ ] **${t.title}** (${t.agent})`).join("\n")}`;
  }).join("\n\n");

  const blob = new Blob([markdown], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "kanban-export.md"; a.click();
  URL.revokeObjectURL(url);
}

function onStoreUpdate(): void {
  if (store.getState().activePanel !== "kanban") return;
  // Refresh agent options
}

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
