// ============================================================================
// Agent OS — Point d'entrée du frontend (SPA avec login)
// ============================================================================

import { store } from "./store";
import { renderShell } from "./ui/shell";
import { renderDashboard } from "./components/dashboard";
import { renderAdmin } from "./components/admin";
import { renderChat } from "./components/chat";
import { renderSkills } from "./components/skills";
import { renderMemory } from "./components/memory";
import { renderCanvas } from "./components/canvas";
import { renderGraph } from "./components/graph";
import { renderKanban } from "./components/kanban";
import { renderN8n } from "./components/n8n";

// -- Bootstrap ------------------------------------------------------------------

function init(): void {
  const token = getCookie("token");
  if (!token) {
    renderLoginPage();
    return;
  }

  fetch("/api/status", { headers: { "Authorization": `Bearer ${token}` } })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || data.error) { renderLoginPage(); return; }
      renderShell();
      store.startPolling(5000);
      // Ne re-rendre le panel QUE lors d'un changement de panel.
      // (sinon, chaque notification du polling (5s) detruisait le DOM :
      //  modales fermees, saisies effacees, selections perdues)
      let currentPanel: string | null = null;
      store.subscribe(state => {
        if (state.activePanel === currentPanel) return;
        currentPanel = state.activePanel;
        const content = document.getElementById("aos-content");
        if (!content) return;
        switch (state.activePanel) {
          case "overview": renderDashboard(content); break;
          case "admin": renderAdmin(content); break;
          case "chat": renderChat(content); break;
          case "skills": renderSkills(content); break;
          case "memory": renderMemory(content); break;
          case "canvas": renderCanvas(content); break;
          case "graph": renderGraph(content); break;
          case "kanban": renderKanban(content); break;
          case "n8n": renderN8n(content); break;
        }
      });
      store.setPanel("overview");
    })
    .catch(() => renderLoginPage());
}

// -- Login page ----------------------------------------------------------------

function renderLoginPage(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <div class="aos-auth-container">
      <div class="aos-auth-card">
        <div class="aos-auth-logo">⚡ Agentic OS</div>
        <div class="aos-auth-sub">Connectez-vous pour accéder au dashboard</div>
        <div class="aos-auth-error" id="auth-error" style="display:none"></div>
        <form onsubmit="return false">
          <div class="aos-form-group">
            <label>Email</label>
            <input type="email" id="auth-email" class="aos-input" placeholder="admin@local.home" autofocus>
          </div>
          <div class="aos-form-group">
            <label>Mot de passe</label>
            <input type="password" id="auth-password" class="aos-input" placeholder="Mot de passe">
          </div>
          <button type="submit" class="aos-btn aos-btn-primary aos-btn-full" id="auth-submit">Se connecter</button>
        </form>
        <div class="aos-auth-footer">
          Pas encore de compte ? <a href="#" id="auth-show-signup">Créer un compte</a>
        </div>
      </div>
    </div>
  `;

  document.getElementById("auth-submit")?.addEventListener("click", doLogin);
  document.getElementById("auth-password")?.addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
  document.getElementById("auth-show-signup")?.addEventListener("click", e => { e.preventDefault(); renderSignupPage(); });
}

function renderSignupPage(): void {
  const app = document.getElementById("app");
  if (!app) return;

  app.innerHTML = `
    <div class="aos-auth-container">
      <div class="aos-auth-card">
        <div class="aos-auth-logo">⚡ Agentic OS</div>
        <div class="aos-auth-sub">Créez votre compte</div>
        <div class="aos-auth-info" id="signup-info">Premier compte = administrateur</div>
        <div class="aos-auth-error" id="auth-error" style="display:none"></div>
        <form onsubmit="return false">
          <div class="aos-form-group">
            <label>Nom</label>
            <input type="text" id="auth-name" class="aos-input" placeholder="Votre nom" autofocus>
          </div>
          <div class="aos-form-group">
            <label>Email</label>
            <input type="email" id="auth-email" class="aos-input" placeholder="email@local.home">
          </div>
          <div class="aos-form-group">
            <label>Mot de passe</label>
            <input type="password" id="auth-password" class="aos-input" placeholder="6+ caractères">
          </div>
          <button type="submit" class="aos-btn aos-btn-primary aos-btn-full" id="auth-submit">Créer mon compte</button>
        </form>
        <div class="aos-auth-footer">
          Déjà un compte ? <a href="#" id="auth-show-login">Se connecter</a>
        </div>
      </div>
    </div>
  `;

  document.getElementById("auth-submit")?.addEventListener("click", doSignup);
  document.getElementById("auth-password")?.addEventListener("keydown", e => { if (e.key === "Enter") doSignup(); });
  document.getElementById("auth-show-login")?.addEventListener("click", e => { e.preventDefault(); renderLoginPage(); });
}

async function doLogin(): Promise<void> {
  const email = (document.getElementById("auth-email") as HTMLInputElement)?.value.trim();
  const password = (document.getElementById("auth-password") as HTMLInputElement)?.value;
  const err = document.getElementById("auth-error");
  const btn = document.getElementById("auth-submit") as HTMLButtonElement;
  if (!email || !password) { showAuthErr(err, "Tous les champs sont obligatoires"); return; }
  btn.disabled = true; btn.textContent = "Connexion...";
  try {
    const r = await fetch("/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
    const d = await r.json();
    if (d.error) { showAuthErr(err, d.error); btn.disabled = false; btn.textContent = "Se connecter"; return; }
    document.cookie = `token=${d.token}; Path=/; SameSite=Lax`;
    init();
  } catch { showAuthErr(err, "Erreur réseau"); btn.disabled = false; btn.textContent = "Se connecter"; }
}

async function doSignup(): Promise<void> {
  const name = (document.getElementById("auth-name") as HTMLInputElement)?.value.trim();
  const email = (document.getElementById("auth-email") as HTMLInputElement)?.value.trim();
  const password = (document.getElementById("auth-password") as HTMLInputElement)?.value;
  const err = document.getElementById("auth-error");
  const btn = document.getElementById("auth-submit") as HTMLButtonElement;
  if (!name || !email || !password) { showAuthErr(err, "Tous les champs sont obligatoires"); return; }
  if (password.length < 6) { showAuthErr(err, "Mot de passe : 6 caractères minimum"); return; }
  btn.disabled = true; btn.textContent = "Création...";
  try {
    const r = await fetch("/api/signup", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, email, password }) });
    const d = await r.json();
    if (d.error) { showAuthErr(err, d.error); btn.disabled = false; btn.textContent = "Créer mon compte"; return; }
    document.cookie = `token=${d.token}; Path=/; SameSite=Lax`;
    init();
  } catch { showAuthErr(err, "Erreur réseau"); btn.disabled = false; btn.textContent = "Créer mon compte"; }
}

function showAuthErr(el: HTMLElement | null, msg: string): void {
  if (el) { el.style.display = "block"; el.textContent = msg; }
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

// -- Start ----------------------------------------------------------------------

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
