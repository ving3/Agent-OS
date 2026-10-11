// ============================================================================
// Agent OS — Panneau Chat (streaming, thought chains, tool calls)
// ============================================================================

import { store } from "../store";
import type { AgentProfile, ChatMessage } from "../types";

// -- Types ----------------------------------------------------------------------

interface ToolCall {
  id: string;
  name: string;
  args: string;
  output: string;
  status: "running" | "done" | "error";
}

interface ChatState {
  selectedAgent: string | null;
  messages: Record<string, ChatMessage[]>;
  streaming: boolean;
  abortController: AbortController | null;
  systemPrompt: string;
}

const state: ChatState = {
  selectedAgent: null,
  messages: {},
  streaming: false,
  abortController: null,
  systemPrompt: "",
};

// -- Renderer -------------------------------------------------------------------

export function renderChat(container: HTMLElement): void {
  const profiles = store.getState().profiles;

  container.innerHTML = `
    <div class="aos-chat" id="aos-chat">
      <!-- Agent tabs -->
      <div class="aos-chat-tabs" id="aos-chat-tabs"></div>

      <!-- Chat area -->
      <div class="aos-chat-main">
        <div class="aos-chat-messages" id="aos-chat-messages">
          <div class="aos-chat-empty">Sélectionne un agent pour commencer</div>
        </div>

        <!-- System prompt editor -->
        <div class="aos-chat-system" id="aos-chat-system" style="display:none">
          <div class="aos-chat-system-header" id="aos-chat-system-toggle">
            ⚙️ System Prompt <span class="aos-chat-system-arrow">▸</span>
          </div>
          <textarea class="aos-chat-system-input" id="aos-chat-system-input"
            placeholder="Instructions système personnalisées..."></textarea>
        </div>

        <!-- Input -->
        <div class="aos-chat-input-row">
          <textarea class="aos-chat-textarea" id="aos-chat-input"
            placeholder="Écris ton message... (Shift+Enter = nouvelle ligne)"
            rows="2"></textarea>
          <div class="aos-chat-input-actions">
            <button class="aos-btn aos-btn-primary" id="aos-chat-send" disabled>
              <span id="aos-chat-send-icon">▶</span> Envoyer
            </button>
            <button class="aos-btn aos-btn-danger" id="aos-chat-stop" style="display:none">
              ■ Stop
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  renderTabs(profiles);
  bindEvents();

  if (profiles.length > 0 && !state.selectedAgent) {
    selectAgent(profiles[0].name);
  }

  store.subscribe(onStoreUpdate);
}

// -- Tabs -----------------------------------------------------------------------

function renderTabs(profiles: AgentProfile[]): void {
  const tabs = document.getElementById("aos-chat-tabs");
  if (!tabs) return;

  tabs.innerHTML = profiles.map(p => {
    const active = state.selectedAgent === p.name ? " active" : "";
    return `<button class="aos-chat-tab${active}" data-agent="${p.name}">
      <span class="aos-chat-tab-emoji">${p.emoji}</span>
      <span>${esc(p.name)}</span>
    </button>`;
  }).join("");
}

function selectAgent(name: string): void {
  state.selectedAgent = name;
  if (!state.messages[name]) state.messages[name] = [];
  renderTabs(store.getState().profiles);
  renderMessages();
  updateSendButton();
}

// -- Messages -------------------------------------------------------------------

function renderMessages(): void {
  const container = document.getElementById("aos-chat-messages");
  if (!container || !state.selectedAgent) return;

  const msgs = state.messages[state.selectedAgent] || [];
  if (msgs.length === 0) {
    container.innerHTML = `<div class="aos-chat-empty">Démarre une conversation avec ${state.selectedAgent}</div>`;
    return;
  }

  container.innerHTML = msgs.map((m, i) => {
    switch (m.role) {
      case "user":
        return `<div class="aos-chat-msg aos-chat-msg-user">
          <div class="aos-chat-msg-content">${esc(m.content)}</div>
          <div class="aos-chat-msg-time">${fmtTime(m.timestamp)}</div>
        </div>`;
      case "agent":
        return `<div class="aos-chat-msg aos-chat-msg-agent">
          <div class="aos-chat-msg-content">${formatContent(m.content)}</div>
          <div class="aos-chat-msg-time">${fmtTime(m.timestamp)}</div>
        </div>`;
      case "tool":
        return `<div class="aos-chat-msg aos-chat-msg-tool">
          <div class="aos-chat-tool-header" data-tool-id="${i}">
            🔧 ${m.toolCall?.name ?? "Tool"} <span class="aos-chat-tool-status">${m.toolCall?.output ? "✓" : "..."}</span>
          </div>
          <div class="aos-chat-tool-body" id="tool-body-${i}" style="display:none">
            <div class="aos-chat-tool-section">
              <div class="aos-chat-tool-label">Arguments</div>
              <pre class="aos-chat-tool-pre">${esc(m.toolCall?.args ?? "")}</pre>
            </div>
            ${m.toolCall?.output ? `
            <div class="aos-chat-tool-section">
              <div class="aos-chat-tool-label">Résultat</div>
              <pre class="aos-chat-tool-pre">${esc(m.toolCall.output)}</pre>
            </div>` : ""}
          </div>
        </div>`;
      case "system":
        return `<div class="aos-chat-msg aos-chat-msg-system">
          <div class="aos-chat-msg-content">${esc(m.content)}</div>
        </div>`;
      default:
        return "";
    }
  }).join("");

  // Bind tool toggles
  container.querySelectorAll<HTMLElement>(".aos-chat-tool-header").forEach(h => {
    h.addEventListener("click", () => {
      const id = h.dataset.toolId!;
      const body = document.getElementById(`tool-body-${id}`);
      if (body) body.style.display = body.style.display === "none" ? "block" : "none";
    });
  });

  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

// -- Events ---------------------------------------------------------------------

function bindEvents(): void {
  // Tab clicks
  document.getElementById("aos-chat-tabs")?.addEventListener("click", (e) => {
    const tab = (e.target as HTMLElement).closest<HTMLElement>(".aos-chat-tab");
    if (!tab) return;
    selectAgent(tab.dataset.agent!);
  });

  // Send button
  document.getElementById("aos-chat-send")?.addEventListener("click", sendMessage);

  // Stop button
  document.getElementById("aos-chat-stop")?.addEventListener("click", stopStreaming);

  // Input keyboard
  const input = document.getElementById("aos-chat-input") as HTMLTextAreaElement;
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  input?.addEventListener("input", updateSendButton);

  // System prompt toggle
  document.getElementById("aos-chat-system-toggle")?.addEventListener("click", () => {
    const body = document.getElementById("aos-chat-system-input");
    const arrow = document.querySelector(".aos-chat-system-arrow") as HTMLElement;
    if (body) {
      const shown = body.style.display !== "none";
      body.style.display = shown ? "none" : "block";
      if (arrow) arrow.textContent = shown ? "▸" : "▾";
    }
  });
  document.getElementById("aos-chat-system-input")?.addEventListener("input", (e) => {
    state.systemPrompt = (e.target as HTMLTextAreaElement).value;
  });
}

function updateSendButton(): void {
  const input = document.getElementById("aos-chat-input") as HTMLTextAreaElement;
  const btn = document.getElementById("aos-chat-send") as HTMLButtonElement;
  if (btn) btn.disabled = !input?.value.trim() || !state.selectedAgent || state.streaming;
}

// -- Send / Stream --------------------------------------------------------------

async function sendMessage(): Promise<void> {
  const input = document.getElementById("aos-chat-input") as HTMLTextAreaElement;
  const content = input?.value.trim();
  if (!content || !state.selectedAgent || state.streaming) return;

  input.value = "";
  updateSendButton();

  // Add user message
  const userMsg: ChatMessage = {
    id: crypto.randomUUID(),
    role: "user",
    content,
    timestamp: Date.now(),
    agent: state.selectedAgent,
  };
  state.messages[state.selectedAgent].push(userMsg);
  renderMessages();

  // Start streaming
  state.streaming = true;
  state.abortController = new AbortController();

  const sendBtn = document.getElementById("aos-chat-send");
  const stopBtn = document.getElementById("aos-chat-stop");
  if (sendBtn) sendBtn.style.display = "none";
  if (stopBtn) stopBtn.style.display = "inline-block";

  // Add loading placeholder
  const loadingId = crypto.randomUUID();
  const loadingMsg: ChatMessage = {
    id: loadingId,
    role: "agent",
    content: "⏳ ...",
    timestamp: Date.now(),
    agent: state.selectedAgent,
  };
  state.messages[state.selectedAgent].push(loadingMsg);
  renderMessages();

  // Build messages array
  const apiMessages: { role: string; content: string }[] = [];
  if (state.systemPrompt) {
    apiMessages.push({ role: "system", content: state.systemPrompt });
  }
  for (const m of state.messages[state.selectedAgent]) {
    if (m.role === "user") apiMessages.push({ role: "user", content: m.content });
    if (m.role === "agent" && m.id !== loadingId) apiMessages.push({ role: "assistant", content: m.content });
  }

  try {
    const r = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: `hermes-${state.selectedAgent}`, messages: apiMessages }),
      signal: state.abortController.signal,
    });

    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const responseText = data.choices?.[0]?.message?.content ?? "[Erreur] Réponse vide";

    // Replace loading with actual response
    const msgs = state.messages[state.selectedAgent];
    const idx = msgs.findIndex(m => m.id === loadingId);
    if (idx >= 0) {
      msgs[idx] = {
        id: crypto.randomUUID(),
        role: "agent",
        content: responseText,
        timestamp: Date.now(),
        agent: state.selectedAgent,
      };
    }

    // Parse potential tool calls in response
    const toolCallMatch = responseText.match(/\[TOOL_CALL\]\s*(\w+)\s*\n(.*?)\n\[TOOL_OUTPUT\]\s*\n([\s\S]*?)(?=\[TOOL_CALL\]|$)/);
    if (toolCallMatch) {
      msgs.push({
        id: crypto.randomUUID(),
        role: "tool",
        content: "",
        timestamp: Date.now(),
        agent: state.selectedAgent,
        toolCall: {
          name: toolCallMatch[1],
          args: toolCallMatch[2].trim(),
          output: toolCallMatch[3].trim(),
        },
      });
    }

    store.addActivity({
      id: crypto.randomUUID(),
      timestamp: Date.now(),
      type: "success",
      agent: state.selectedAgent,
      message: `Réponse de ${state.selectedAgent}`,
      details: responseText.slice(0, 200),
    });
  } catch (e: unknown) {
    if ((e as Error).name === "AbortError") {
      const msgs = state.messages[state.selectedAgent];
      const idx = msgs.findIndex(m => m.id === loadingId);
      if (idx >= 0) msgs.splice(idx, 1);
    } else {
      const msgs = state.messages[state.selectedAgent];
      const idx = msgs.findIndex(m => m.id === loadingId);
      if (idx >= 0) {
        msgs[idx] = {
          id: crypto.randomUUID(),
          role: "agent",
          content: `[Erreur] ${(e as Error).message}`,
          timestamp: Date.now(),
          agent: state.selectedAgent,
        };
      }
    }
  }

  state.streaming = false;
  state.abortController = null;
  if (sendBtn) sendBtn.style.display = "inline-block";
  if (stopBtn) stopBtn.style.display = "none";
  renderMessages();
  updateSendButton();
}

function stopStreaming(): void {
  if (state.abortController) {
    state.abortController.abort();
  }
}

// -- Store sync -----------------------------------------------------------------

function onStoreUpdate(): void {
  if (store.getState().activePanel !== "chat") return;
  const profiles = store.getState().profiles;
  renderTabs(profiles);

  // Keep selected agent if still exists
  if (state.selectedAgent && !profiles.find(p => p.name === state.selectedAgent)) {
    state.selectedAgent = profiles.length > 0 ? profiles[0].name : null;
  }
}

// -- Helpers --------------------------------------------------------------------

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit" });
}

function formatContent(text: string): string {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code class=\"aos-inline-code\">$1</code>")
    .replace(/\n/g, "<br>");
}
