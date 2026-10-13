// ============================================================================
// Agent OS — Panneau Administration (RBAC, users, system config)
// ============================================================================

import { store } from "../store";
import type { UserRecord, PanelName, AgentProfile, UserPermissions } from "../types";

// -- State ----------------------------------------------------------------------

interface AdminState {
  users: UserRecord[];
  panels: PanelName[];
  agents: string[];
  selectedUserId: number | null;
  editingPerms: UserPermissions | null;
  deletingAgentName: string | null;
}

let state: AdminState = { users: [], panels: [], agents: [], selectedUserId: null, editingPerms: null, deletingAgentName: null };

// -- Renderer -------------------------------------------------------------------

export function renderAdmin(container: HTMLElement): void {
  container.innerHTML = `
    <div class="aos-admin" id="aos-admin">
      <!-- Stats bar -->
      <div class="aos-admin-stats" id="aos-admin-stats"></div>

      <!-- Create user -->
      <div class="aos-card aos-mb">
        <div class="aos-card-header">
          <span class="aos-card-title">➕ Créer un utilisateur</span>
        </div>
        <div class="aos-card-body">
          <div class="aos-form-grid">
            <div class="aos-form-group">
              <label>Nom</label>
              <input type="text" id="au-name" class="aos-input" placeholder="Nom complet">
            </div>
            <div class="aos-form-group">
              <label>Email</label>
              <input type="email" id="au-email" class="aos-input" placeholder="email@local.home">
            </div>
            <div class="aos-form-group">
              <label>Mot de passe</label>
              <input type="password" id="au-pass" class="aos-input" placeholder="Min 6 caractères">
            </div>
            <div class="aos-form-group">
              <label>Rôle</label>
              <select id="au-role" class="aos-select">
                <option value="user">Utilisateur</option>
                <option value="admin">Administrateur</option>
              </select>
            </div>
          </div>
          <div class="aos-form-actions">
            <button class="aos-btn aos-btn-primary" id="au-create">Créer</button>
            <span class="aos-msg" id="au-msg"></span>
          </div>
        </div>
      </div>

      <!-- Permissions modal -->
      <div class="aos-modal" id="perms-modal" style="display:none">
        <div class="aos-modal-card">
          <div class="aos-modal-header">
            <span class="aos-modal-title">🔑 Permissions</span>
            <span id="perms-user-name" class="aos-modal-subtitle"></span>
            <button class="aos-modal-close" data-close="perms-modal">✕</button>
          </div>
          <div class="aos-modal-body">
            <div class="aos-perms-section">
              <h4>Panneaux autorisés</h4>
              <div id="perms-panels" class="aos-perms-grid"></div>
            </div>
            <div class="aos-perms-section">
              <h4>Agents autorisés</h4>
              <div id="perms-agents" class="aos-perms-grid"></div>
            </div>
          </div>
          <div class="aos-modal-footer">
            <button class="aos-btn aos-btn-primary" id="perms-save">Enregistrer</button>
            <button class="aos-btn" data-close="perms-modal">Annuler</button>
          </div>
        </div>
      </div>

      <!-- Delete agent modal -->
      <div class="aos-modal" id="delete-agent-modal" style="display:none">
        <div class="aos-modal-card">
          <div class="aos-modal-header">
            <span class="aos-modal-title">⚠️ Supprimer l'agent</span>
            <button class="aos-modal-close" data-close="delete-agent-modal">✕</button>
          </div>
          <div class="aos-modal-body">
            <p>Tapez <strong id="da-name-confirm" class="aos-text-red"></strong> pour confirmer.</p>
            <input type="text" id="da-confirm-input" class="aos-input aos-mt" placeholder="Nom de l'agent">
          </div>
          <div class="aos-modal-footer">
            <button class="aos-btn aos-btn-danger" id="da-confirm-btn" disabled>Confirmer</button>
            <button class="aos-btn" data-close="delete-agent-modal">Annuler</button>
          </div>
        </div>
      </div>

      <!-- Create agent modal -->
      <div class="aos-modal" id="create-agent-modal" style="display:none">
        <div class="aos-modal-card">
          <div class="aos-modal-header">
            <span class="aos-modal-title">🤖 Créer un agent IA</span>
            <button class="aos-modal-close" data-close="create-agent-modal">✕</button>
          </div>
          <div class="aos-modal-body">
            <div class="aos-form-grid aos-form-grid-2col">
              <div class="aos-form-group">
                <label>Nom unique</label>
                <input type="text" id="aa-name" class="aos-input" placeholder="mon-agent">
              </div>
              <div class="aos-form-group">
                <label>Emoji</label>
                <input type="text" id="aa-emoji" class="aos-input" value="🤖">
              </div>
              <div class="aos-form-group">
                <label>Couleur</label>
                <input type="color" id="aa-color" class="aos-input" value="#58a6ff" style="height:40px;padding:4px">
              </div>
              <div class="aos-form-group" style="grid-column:1/-1">
                <label>Description</label>
                <input type="text" id="aa-desc" class="aos-input" placeholder="Description du rôle de l'agent">
              </div>
              <div class="aos-form-group" style="grid-column:1/-1">
                <label>Persona (SOUL.md)</label>
                <textarea id="aa-persona" class="aos-input" rows="9" style="resize:vertical;font-family:inherit;line-height:1.5"># Persona

Tu es un agent IA spécialisé.

## Rôle

Décris ici la mission de l'agent.

## Style de réponse

- Réponds en français
- Sois précis et technique
</textarea>
              </div>
              <div class="aos-form-group">
                <label>Fournisseur LLM</label>
                <select id="aa-provider" class="aos-select">
                  <option value="">Chargement...</option>
                </select>
              </div>
              <div class="aos-form-group">
                <label>Modèle</label>
                <select id="aa-model" class="aos-select">
                  <option value="">Choisir un fournisseur</option>
                </select>
              </div>
              <div class="aos-form-group" id="aa-baseurl-group" style="grid-column:1/-1;display:none">
                <label>Base URL (fournisseur custom)</label>
                <input type="text" id="aa-baseurl" class="aos-input" placeholder="https://mon-endpoint/v1">
              </div>
            </div>
          </div>
          <div class="aos-modal-footer">
            <button class="aos-btn aos-btn-primary" id="aa-create">Créer l'agent</button>
            <button class="aos-btn" data-close="create-agent-modal">Annuler</button>
            <span class="aos-msg" id="aa-msg"></span>
          </div>
        </div>
      </div>

      <!-- Users table + agents section -->
      <div class="aos-card aos-mb">
        <div class="aos-card-header">
          <span class="aos-card-title">👥 Utilisateurs</span>
          <button class="aos-btn aos-btn-sm" id="au-refresh">🔄 Rafraîchir</button>
        </div>
        <div class="aos-table-wrap">
          <table class="aos-table">
            <thead>
              <tr><th>ID</th><th>Nom</th><th>Email</th><th>Rôle</th><th>Permissions</th><th>Statut</th><th>Actions</th></tr>
            </thead>
            <tbody id="admin-users-tbody"></tbody>
          </table>
        </div>
      </div>

      <!-- Agents section -->
      <div class="aos-card">
        <div class="aos-card-header">
          <span class="aos-card-title">🤖 Agents IA</span>
          <button class="aos-btn aos-btn-sm aos-btn-green" id="aa-open-create">+ Créer un agent</button>
        </div>
        <div class="aos-card-body">
          <div class="aos-agent-admin-grid" id="aos-agent-admin-grid"></div>
        </div>
      </div>
    </div>
  `;

  bindEvents();
  store.subscribe(onStoreUpdate);
  loadData();
}

// -- Events ---------------------------------------------------------------------

function bindEvents(): void {
  // Create user
  document.getElementById("au-create")?.addEventListener("click", handleCreateUser);
  // Refresh
  document.getElementById("au-refresh")?.addEventListener("click", loadData);
  // Permissions save
  document.getElementById("perms-save")?.addEventListener("click", handleSavePerms);
  // Create agent
  document.getElementById("aa-create")?.addEventListener("click", handleCreateAgent);
  document.getElementById("aa-open-create")?.addEventListener("click", () => {
    const modal = document.getElementById("create-agent-modal");
    if (modal) modal.style.display = "flex";
    loadProviders();
  });
  // Provider -> model cascade
  document.getElementById("aa-provider")?.addEventListener("change", (e) => {
    updateModelOptions((e.target as HTMLSelectElement).value);
  });
  // Delete agent confirm
  document.getElementById("da-confirm-btn")?.addEventListener("click", handleDeleteAgent);
  document.getElementById("da-confirm-input")?.addEventListener("input", (e) => {
    const btn = document.getElementById("da-confirm-btn") as HTMLButtonElement;
    const match = (e.target as HTMLInputElement).value.trim() === state.deletingAgentName;
    if (btn) { btn.disabled = !match; btn.style.opacity = match ? "1" : "0.5"; }
  });
  // Modal close
  document.querySelectorAll("[data-close]").forEach(el => {
    el.addEventListener("click", () => {
      const modalId = (el as HTMLElement).dataset.close;
      const modal = document.getElementById(modalId!);
      if (modal) modal.style.display = "none";
    });
  });
}

// -- Data loading ---------------------------------------------------------------

async function loadData(): Promise<void> {
  try {
    const r = await fetch("/api/users");
    if (!r.ok) return;
    const data = await r.json();
    state.users = data.users;
    state.panels = data.panels;
    state.agents = data.agents;
    renderUsers();
    renderStats();
    renderAgentCards();
  } catch (e) {
    console.error("Admin load failed:", e);
  }
}

// -- Stats ----------------------------------------------------------------------

function renderStats(): void {
  const el = document.getElementById("aos-admin-stats");
  if (!el) return;
  const total = state.users.length;
  const admins = state.users.filter(u => u.role === "admin").length;
  const users = total - admins;
  el.innerHTML = `
    <div class="aos-stat-card"><div class="aos-stat-val">${total}</div><div class="aos-stat-lbl">Total</div></div>
    <div class="aos-stat-card"><div class="aos-stat-val">${admins}</div><div class="aos-stat-lbl">Administrateurs</div></div>
    <div class="aos-stat-card"><div class="aos-stat-val">${users}</div><div class="aos-stat-lbl">Utilisateurs</div></div>
    <div class="aos-stat-card"><div class="aos-stat-val">${state.agents.length}</div><div class="aos-stat-lbl">Agents</div></div>
  `;
}

// -- Users table ----------------------------------------------------------------

function renderUsers(): void {
  const tbody = document.getElementById("admin-users-tbody");
  if (!tbody) return;
  if (state.users.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="aos-empty-cell">Aucun utilisateur</td></tr>`;
    return;
  }
  tbody.innerHTML = state.users.map(u => {
    const roleBadge = `<span class="aos-badge aos-badge-${u.role}">${u.role}</span>`;
    const statusBadge = u.disabled
      ? `<span class="aos-badge aos-badge-danger">désactivé</span>`
      : `<span class="aos-badge aos-badge-success">actif</span>`;
    const perms = u.permissions || { panels: [], agents: [] };
    const permSummary = u.role === "admin"
      ? `<span class="aos-perm-summary">Tout</span>`
      : `<span class="aos-perm-link" data-uid="${u.id}">${perms.panels?.length ?? 0} panneaux, ${perms.agents?.length ?? 0} agents ✏️</span>`;
    return `<tr>
      <td>${u.id}</td>
      <td>${esc(u.name)}</td>
      <td>${esc(u.email)}</td>
      <td>${roleBadge}</td>
      <td>${permSummary}</td>
      <td>${statusBadge}</td>
      <td>
        <select class="aos-select aos-select-sm" data-uid="${u.id}" data-action="user-action">
          <option value="">Action...</option>
          <option value="admin">Promouvoir admin</option>
          <option value="user">Rétrograder user</option>
          <option value="${u.disabled ? "enable" : "disable"}">${u.disabled ? "Activer" : "Désactiver"}</option>
          <option value="delete">Supprimer</option>
        </select>
      </td>
    </tr>`;
  });

  // Bind perm links
  tbody.querySelectorAll<HTMLElement>(".aos-perm-link").forEach(el => {
    el.addEventListener("click", () => openPerms(Number(el.dataset.uid!)));
  });

  // Bind action selects
  tbody.querySelectorAll<HTMLSelectElement>("[data-action='user-action']").forEach(sel => {
    sel.addEventListener("change", () => {
      const uid = Number(sel.dataset.uid);
      const action = sel.value;
      sel.value = "";
      if (action) handleUserAction(uid, action);
    });
  });
}

// -- Permissions modal -----------------------------------------------------------

function openPerms(uid: number): void {
  const user = state.users.find(u => u.id === uid);
  if (!user) return;
  state.selectedUserId = uid;
  state.editingPerms = JSON.parse(JSON.stringify(user.permissions || { panels: [], agents: [] }));

  const nameEl = document.getElementById("perms-user-name");
  if (nameEl) nameEl.textContent = user.name;

  const panelsEl = document.getElementById("perms-panels");
  if (panelsEl) {
    panelsEl.innerHTML = state.panels.map(p => {
      const checked = state.editingPerms?.panels?.includes(p) ?? false;
      return `<label class="aos-perm-chip ${checked ? "aos-perm-chip-active" : ""}">
        <input type="checkbox" ${checked ? "checked" : ""} value="${p}" class="aos-perm-cb" data-perm-type="panel">
        ${p}
      </label>`;
    }).join("");
  }

  const agentsEl = document.getElementById("perms-agents");
  if (agentsEl) {
    agentsEl.innerHTML = state.agents.map(a => {
      const checked = state.editingPerms?.agents?.includes(a) ?? false;
      return `<label class="aos-perm-chip ${checked ? "aos-perm-chip-active" : ""}">
        <input type="checkbox" ${checked ? "checked" : ""} value="${a}" class="aos-perm-cb" data-perm-type="agent">
        ${a}
      </label>`;
    }).join("");
  }

  // Bind checkbox changes
  document.querySelectorAll<HTMLInputElement>(".aos-perm-cb").forEach(cb => {
    cb.addEventListener("change", () => {
      const type = cb.dataset.permType as "panel" | "agent";
      const value = cb.value;
      if (!state.editingPerms) state.editingPerms = { panels: [], agents: [] };
      if (type === "panel") {
        if (cb.checked) state.editingPerms.panels = [...(state.editingPerms.panels || []), value];
        else state.editingPerms.panels = (state.editingPerms.panels || []).filter(p => p !== value);
      } else {
        if (cb.checked) state.editingPerms.agents = [...(state.editingPerms.agents || []), value];
        else state.editingPerms.agents = (state.editingPerms.agents || []).filter(a => a !== value);
      }
      // Update chip style
      const chip = cb.closest(".aos-perm-chip");
      if (chip) chip.classList.toggle("aos-perm-chip-active", cb.checked);
    });
  });

  document.getElementById("perms-modal")!.style.display = "flex";
}

// -- Agent cards ----------------------------------------------------------------

function renderAgentCards(): void {
  const el = document.getElementById("aos-agent-admin-grid");
  if (!el) return;
  if (state.agents.length === 0) {
    el.innerHTML = `<div class="aos-empty-state">Aucun agent</div>`;
    return;
  }
  const profiles = store.getState().profiles;
  el.innerHTML = state.agents.map(name => {
    const profile = profiles.find(p => p.name === name);
    const emoji = profile?.emoji ?? "🤖";
    const color = profile?.color ?? "#58a6ff";
    const desc = profile?.description ?? "";
    const builtin = ["architect", "senior-dev", "code-reviewer", "qa-engineer", "devops"];
    return `<div class="aos-agent-admin-card">
      <div class="aos-agent-admin-avatar" style="background:${color}22;color:${color}">${emoji}</div>
      <div class="aos-agent-admin-info">
        <div class="aos-agent-admin-name">${esc(name)}</div>
        <div class="aos-agent-admin-desc">${esc(desc)}</div>
      </div>
      ${builtin.includes(name) ? `<span class="aos-badge">intégré</span>` : `<button class="aos-btn aos-btn-sm aos-btn-danger" data-delete-agent="${name}">✕ Supprimer</button>`}
    </div>`;
  }).join("");

  el.querySelectorAll<HTMLButtonElement>("[data-delete-agent]").forEach(btn => {
    btn.addEventListener("click", () => openDeleteAgent(btn.dataset.deleteAgent!));
  });
}

function openDeleteAgent(name: string): void {
  state.deletingAgentName = name;
  const nameEl = document.getElementById("da-name-confirm");
  if (nameEl) nameEl.textContent = name;
  const input = document.getElementById("da-confirm-input") as HTMLInputElement;
  if (input) input.value = "";
  const btn = document.getElementById("da-confirm-btn") as HTMLButtonElement;
  if (btn) { btn.disabled = true; btn.style.opacity = "0.5"; }
  document.getElementById("delete-agent-modal")!.style.display = "flex";
}

// -- Handlers -------------------------------------------------------------------

async function handleCreateUser(): Promise<void> {
  const name = (document.getElementById("au-name") as HTMLInputElement)?.value.trim();
  const email = (document.getElementById("au-email") as HTMLInputElement)?.value.trim();
  const password = (document.getElementById("au-pass") as HTMLInputElement)?.value;
  const role = (document.getElementById("au-role") as HTMLSelectElement)?.value;
  const msgEl = document.getElementById("au-msg");

  if (!name || !email || !password) {
    if (msgEl) { msgEl.textContent = "Tous les champs sont obligatoires"; msgEl.className = "aos-msg aos-msg-error"; }
    return;
  }
  try {
    const r = await fetch("/api/admin/user/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password, role, permissions: { panels: [], agents: [] } }),
    });
    const d = await r.json();
    if (d.error) {
      if (msgEl) { msgEl.textContent = d.error; msgEl.className = "aos-msg aos-msg-error"; }
    } else {
      if (msgEl) { msgEl.textContent = "Utilisateur créé !"; msgEl.className = "aos-msg aos-msg-success"; }
      ["au-name", "au-email", "au-pass"].forEach(id => {
        const el = document.getElementById(id) as HTMLInputElement;
        if (el) el.value = "";
      });
      loadData();
    }
  } catch (e) {
    if (msgEl) { msgEl.textContent = "Erreur réseau"; msgEl.className = "aos-msg aos-msg-error"; }
  }
}

async function handleUserAction(uid: number, action: string): Promise<void> {
  if (action === "delete") {
    if (!confirm("Supprimer définitivement cet utilisateur ?")) return;
    await fetch("/api/admin/user/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: uid }),
    });
  } else if (action === "enable" || action === "disable") {
    await fetch("/api/admin/user/update", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: uid, disabled: action === "disable" }),
    });
  } else {
    await fetch("/api/admin/user/update", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: uid, role: action }),
    });
  }
  loadData();
}

async function handleSavePerms(): Promise<void> {
  if (!state.selectedUserId || !state.editingPerms) return;
  await fetch("/api/admin/user/permissions", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: state.selectedUserId, permissions: state.editingPerms }),
  });
  document.getElementById("perms-modal")!.style.display = "none";
  loadData();
}

// -- Fournisseurs LLM ------------------------------------------------------------

let providersCache: { id: string; label: string; models: string[]; base_url: string; key_configured: boolean }[] = [];

async function loadProviders(): Promise<void> {
  if (providersCache.length > 0) { renderProviderOptions(); return; }
  try {
    const r = await fetch("/api/providers");
    const d = await r.json();
    providersCache = d.providers || [];
    renderProviderOptions();
  } catch {
    /* ignore */
  }
}

function renderProviderOptions(): void {
  const sel = document.getElementById("aa-provider") as HTMLSelectElement;
  if (!sel) return;
  sel.innerHTML = providersCache.map(p =>
    `<option value="${p.id}">${p.label}${p.key_configured ? " ✓" : ""}</option>`
  ).join("");
  if (providersCache.length > 0) updateModelOptions(providersCache[0].id);
}

function updateModelOptions(providerId: string): void {
  const modelSel = document.getElementById("aa-model") as HTMLSelectElement;
  const urlGroup = document.getElementById("aa-baseurl-group");
  if (!modelSel) return;
  const p = providersCache.find(x => x.id === providerId);
  if (!p) { modelSel.innerHTML = ""; return; }

  // Fournisseur custom : saisie libre + base_url requis
  if (p.id === "custom") {
    if (urlGroup) urlGroup.style.display = "block";
    modelSel.outerHTML = `<input type="text" id="aa-model" class="aos-input" placeholder="nom-du-modele">`;
  } else {
    if (urlGroup) urlGroup.style.display = "none";
    const input = document.getElementById("aa-model");
    if (input && input.tagName === "INPUT") {
      input.outerHTML = `<select id="aa-model" class="aos-select"></select>`;
    }
    const sel = document.getElementById("aa-model") as HTMLSelectElement;
    sel.innerHTML = p.models.map(m => `<option value="${m}">${m}</option>`).join("");
  }
}

async function handleCreateAgent(): Promise<void> {
  const name = (document.getElementById("aa-name") as HTMLInputElement)?.value.trim();
  const emoji = (document.getElementById("aa-emoji") as HTMLInputElement)?.value || "🤖";
  const color = (document.getElementById("aa-color") as HTMLInputElement)?.value || "#58a6ff";
  const desc = (document.getElementById("aa-desc") as HTMLInputElement)?.value.trim();
  const persona = (document.getElementById("aa-persona") as HTMLTextAreaElement)?.value.trim() || "";
  const provider = (document.getElementById("aa-provider") as HTMLSelectElement)?.value || "deepseek";
  const modelEl = document.getElementById("aa-model") as HTMLInputElement | HTMLSelectElement;
  const model = modelEl?.value.trim() || "";
  const baseUrl = (document.getElementById("aa-baseurl") as HTMLInputElement)?.value.trim() || "";
  const msgEl = document.getElementById("aa-msg");

  if (!name) {
    if (msgEl) { msgEl.textContent = "Le nom est obligatoire"; msgEl.className = "aos-msg aos-msg-error"; }
    return;
  }
  if (!model) {
    if (msgEl) { msgEl.textContent = "Le modèle est obligatoire"; msgEl.className = "aos-msg aos-msg-error"; }
    return;
  }
  try {
    const r = await fetch("/api/admin/agent/create", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, emoji, color, description: desc, persona, provider, model, base_url: baseUrl }),
    });
    const d = await r.json();
    if (d.error) {
      if (msgEl) { msgEl.textContent = d.error; msgEl.className = "aos-msg aos-msg-error"; }
    } else {
      document.getElementById("create-agent-modal")!.style.display = "none";
      store.fetchProfiles();
      loadData();
    }
  } catch (e) {
    if (msgEl) { msgEl.textContent = "Erreur réseau"; msgEl.className = "aos-msg aos-msg-error"; }
  }
}

async function handleDeleteAgent(): Promise<void> {
  if (!state.deletingAgentName) return;
  const r = await fetch("/api/admin/agent/delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: state.deletingAgentName }),
  });
  const d = await r.json();
  if (!d.error) {
    document.getElementById("delete-agent-modal")!.style.display = "none";
    store.fetchProfiles();
    loadData();
  }
}

// -- Store sync -----------------------------------------------------------------

function onStoreUpdate(): void {
  if (store.getState().activePanel !== "admin") return;
  const profiles = store.getState().profiles;
  const newAgents = profiles.map(p => p.name);
  if (JSON.stringify(newAgents) !== JSON.stringify(state.agents)) {
    state.agents = newAgents;
    renderAgentCards();
  }
}

// -- Helpers --------------------------------------------------------------------

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
