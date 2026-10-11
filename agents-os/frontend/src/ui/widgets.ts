// ============================================================================
// Agent OS — UI: Widget grid system (draggable, resizable)
// ============================================================================

import { store } from "../store";
import type { DashboardWidget, ActivityEvent, MetricsSnapshot } from "../types";

const COL_W = 320;
const ROW_H = 220;
const GAP = 16;
const COLS = 3;

// -- Widget renderer -----------------------------------------------------------

export function renderWidgetGrid(container: HTMLElement): void {
  const state = store.getState();
  const widgets = state.widgets;

  container.innerHTML = `<div class="aos-widget-grid" id="aos-widget-grid"></div>`;
  const grid = document.getElementById("aos-widget-grid");
  if (!grid) return;

  grid.style.cssText = `
    display: grid;
    grid-template-columns: repeat(${COLS}, 1fr);
    gap: ${GAP}px;
    padding: 0;
  `;

  widgets.forEach(w => {
    const card = document.createElement("div");
    card.className = "aos-widget-card";
    card.id = `widget-${w.id}`;
    card.draggable = true;
    card.dataset.widgetId = w.id;
    card.style.cssText = `grid-column: span ${w.w};`;
    card.innerHTML = `
      <div class="aos-widget-header">
        <span class="aos-widget-title">${w.title}</span>
        <div class="aos-widget-actions">
          <button class="aos-widget-btn" data-action="minimize" title="Réduire">${w.minimized ? "□" : "−"}</button>
        </div>
      </div>
      <div class="aos-widget-body${w.minimized ? " aos-hidden" : ""}" id="widget-body-${w.id}"></div>
    `;
    card.addEventListener("click", (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "minimize") {
        store.updateWidget(w.id, { minimized: !w.minimized });
      }
    });
    card.addEventListener("dragstart", (e) => handleDragStart(e, w.id));
    card.addEventListener("dragover", (e) => e.preventDefault());
    card.addEventListener("drop", (e) => handleDrop(e, w.id));
    grid.appendChild(card);
  });

  // Populate widget bodies
  widgets.forEach(w => {
    const body = document.getElementById(`widget-body-${w.id}`);
    if (!body || w.minimized) return;
    renderWidgetContent(body, w);
  });
}

function renderWidgetContent(body: HTMLElement, widget: DashboardWidget): void {
  const state = store.getState();
  const s = state.status;
  switch (widget.type) {
    case "metric":
      renderMetricWidget(body, widget);
      break;
    case "chart":
      renderChartWidget(body, widget, state);
      break;
    case "feed":
      renderFeedWidget(body, state.activityFeed);
      break;
    case "actions":
      renderActionsWidget(body);
      break;
  }
}

// -- Metric widget --------------------------------------------------------------

function renderMetricWidget(body: HTMLElement, widget: DashboardWidget): void {
  const s = store.getState().status;
  if (!s) {
    body.innerHTML = `<div class="aos-metric-loading">Chargement...</div>`;
    return;
  }
  let value = "";
  let subtitle = "";
  switch (widget.id) {
    case "metrics-calls":
      value = `${s.total_calls}`;
      subtitle = "appels API totaux";
      break;
    case "metrics-errors":
      const rate = s.total_calls > 0 ? ((s.errors / s.total_calls) * 100).toFixed(1) : "0.0";
      value = `${rate}%`;
      subtitle = `${s.errors} erreurs`;
      break;
    case "metrics-uptime":
      const h = Math.floor(s.uptime_seconds / 3600);
      const m = Math.floor((s.uptime_seconds % 3600) / 60);
      value = `${h}h ${m}m`;
      subtitle = "uptime";
      break;
  }
  body.innerHTML = `
    <div class="aos-metric-value">${value}</div>
    <div class="aos-metric-sub">${subtitle}</div>
  `;
}

// -- Chart widget ---------------------------------------------------------------

function renderChartWidget(body: HTMLElement, widget: DashboardWidget, state: ReturnType<typeof store.getState>): void {
  const metrics = state.metrics;
  if (metrics.length < 2) {
    body.innerHTML = `<div class="aos-chart-placeholder">Collecte des métriques...</div>`;
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.id = `chart-${widget.id}`;
  canvas.style.width = "100%";
  canvas.style.height = "160px";
  body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  drawMiniChart(ctx, canvas, metrics, widget.id);
}

function drawMiniChart(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement, metrics: MetricsSnapshot[], widgetId: string): void {
  const W = canvas.width = canvas.clientWidth * 2;
  const H = canvas.height = 160 * 2;
  ctx.scale(1, 1);

  ctx.fillStyle = "var(--aos-surface)";
  ctx.fillRect(0, 0, W, H);

  const points = metrics.map((m, i) => {
    let val: number;
    if (widgetId === "chart-latency") val = m.latency_ms;
    else val = m.total_calls;
    return { x: (i / (metrics.length - 1)) * (W - 40) + 20, y: H - 20 - (val / Math.max(...metrics.map(m2 => widgetId === "chart-latency" ? m2.latency_ms : m2.total_calls), 1)) * (H - 40) };
  });

  ctx.beginPath();
  ctx.strokeStyle = "#58a6ff";
  ctx.lineWidth = 3;
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.stroke();

  // Fill below line
  ctx.lineTo(points[points.length - 1].x, H - 20);
  ctx.lineTo(points[0].x, H - 20);
  ctx.closePath();
  ctx.fillStyle = "rgba(88,166,255,0.1)";
  ctx.fill();
}

// -- Feed widget ----------------------------------------------------------------

function renderFeedWidget(body: HTMLElement, feed: ActivityEvent[]): void {
  if (feed.length === 0) {
    body.innerHTML = `<div class="aos-feed-empty">Aucune activité récente</div>`;
    return;
  }
  const iconMap: Record<string, string> = {
    info: "ℹ️", success: "✅", error: "❌", tool_call: "🔧", agent_action: "🤖",
  };
  body.innerHTML = `
    <div class="aos-feed-list">
      ${feed.slice(0, 20).map(e => `
        <div class="aos-feed-item aos-feed-${e.type}">
          <span class="aos-feed-icon">${iconMap[e.type] ?? "•"}</span>
          <span class="aos-feed-msg">${escHtml(e.message)}</span>
          <span class="aos-feed-time">${formatTime(e.timestamp)}</span>
        </div>
      `).join("")}
    </div>
  `;
}

// -- Actions widget -------------------------------------------------------------

function renderActionsWidget(body: HTMLElement): void {
  body.innerHTML = `
    <div class="aos-actions-list">
      <button class="aos-action-btn" data-global-action="refresh">🔄 Rafraîchir les données</button>
      <button class="aos-action-btn" data-global-action="reset-widgets">📐 Réinitialiser la grille</button>
      <button class="aos-action-btn" data-global-action="export-state">💾 Exporter l'état</button>
    </div>
  `;
  body.querySelectorAll<HTMLButtonElement>(".aos-action-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.globalAction;
      if (action === "refresh") {
        store.startPolling(3000);
        store.fetchProfiles().catch(() => {});
      }
      if (action === "reset-widgets") {
        // Reset widget positions
        store.getState().widgets.forEach(w => store.updateWidget(w.id, { x: 0, y: 0 }));
      }
      if (action === "export-state") {
        const data = JSON.stringify(store.getState(), null, 2);
        const blob = new Blob([data], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "agent-os-state.json"; a.click();
        URL.revokeObjectURL(url);
      }
    });
  });
}

// -- Drag & Drop ----------------------------------------------------------------

let dragWidgetId: string | null = null;

function handleDragStart(e: DragEvent, widgetId: string): void {
  dragWidgetId = widgetId;
  e.dataTransfer!.effectAllowed = "move";
  e.dataTransfer!.setData("text/plain", widgetId);
}

function handleDrop(e: DragEvent, targetId: string): void {
  e.preventDefault();
  if (!dragWidgetId || dragWidgetId === targetId) return;
  // Simple swap - exchange positions
  const state = store.getState();
  const src = state.widgets.find(w => w.id === dragWidgetId);
  const tgt = state.widgets.find(w => w.id === targetId);
  if (src && tgt) {
    store.moveWidget(src.id, tgt.x, tgt.y);
    store.moveWidget(tgt.id, src.x, src.y);
  }
  dragWidgetId = null;
}

// -- Helpers --------------------------------------------------------------------

function escHtml(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("fr", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
