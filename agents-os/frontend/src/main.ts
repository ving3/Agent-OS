// ============================================================================
// Agent OS — Point d'entrée du frontend
// ============================================================================

import { store } from "./store";
import { renderShell } from "./ui/shell";
import { renderDashboard } from "./components/dashboard";
import { renderAdmin } from "./components/admin";
import { renderChat } from "./components/chat";
import { renderSkills } from "./components/skills";
import { renderMemory } from "./components/memory";
import type { PanelName } from "./types";

// -- Bootstrap ------------------------------------------------------------------

function init(): void {
  renderShell();

  // Start polling for system status
  store.startPolling(5000);

  // Subscribe to panel changes
  store.subscribe(state => {
    const content = document.getElementById("aos-content");
    if (!content) return;

    switch (state.activePanel) {
      case "overview":
        renderDashboard(content);
        break;
      case "canvas":
        content.innerHTML = renderPlaceholder("Canvas", "🖥️ Terminaux des agents — À implémenter");
        break;
      case "graph":
        content.innerHTML = renderPlaceholder("Graphe", "🔗 Visualisation des dépendances — À implémenter");
        break;
      case "chat":
        renderChat(content);
        break;
      case "memory":
        renderMemory(content);
        break;
      case "skills":
        renderSkills(content);
        break;
      case "kanban":
        content.innerHTML = renderPlaceholder("Kanban", "📋 Tableau de tâches — À implémenter");
        break;
      case "admin":
        renderAdmin(content);
        break;
    }
  });

  // Initial render
  store.setPanel("overview");
}

function renderPlaceholder(title: string, desc: string): string {
  return `
    <div class="aos-placeholder">
      <div class="aos-placeholder-icon">${desc.charAt(0)}</div>
      <h2>${title}</h2>
      <p>${desc}</p>
      <div class="aos-placeholder-bar"></div>
    </div>
  `;
}

// -- Start ----------------------------------------------------------------------

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
