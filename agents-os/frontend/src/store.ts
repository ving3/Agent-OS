// ============================================================================
// Agent OS — Store d'état global (pattern Observable)
// ============================================================================

import type {
  AppState, PanelName, SystemStatus, AgentProfile, SkillInfo,
  ActivityEvent, DashboardWidget, MetricsSnapshot, UserInfo,
} from "./types";

type Listener = (state: AppState) => void;

const defaultWidgets: DashboardWidget[] = [
  { id: "metrics-calls", title: "Requêtes totales", type: "metric", x: 0, y: 0, w: 1, h: 1, minimized: false },
  { id: "metrics-errors", title: "Taux d'erreur", type: "metric", x: 1, y: 0, w: 1, h: 1, minimized: false },
  { id: "metrics-uptime", title: "Uptime", type: "metric", x: 2, y: 0, w: 1, h: 1, minimized: false },
  { id: "chart-latency", title: "Latence LLM (ms)", type: "chart", x: 0, y: 1, w: 2, h: 1, minimized: false },
  { id: "chart-calls", title: "Appels par agent", type: "chart", x: 2, y: 1, w: 1, h: 1, minimized: false },
  { id: "feed-activity", title: "Flux d'activité", type: "feed", x: 0, y: 2, w: 2, h: 1, minimized: false },
  { id: "actions-quick", title: "Actions rapides", type: "actions", x: 2, y: 2, w: 1, h: 1, minimized: false },
];

const initialState: AppState = {
  activePanel: "overview",
  status: null,
  profiles: [],
  skills: [],
  activityFeed: [],
  widgets: loadWidgetLayout(),
  metrics: [],
  loading: true,
  error: null,
};

// -- Layout persistence -------------------------------------------------------

function loadWidgetLayout(): DashboardWidget[] {
  try {
    const saved = localStorage.getItem("aos_widgets");
    if (saved) {
      const parsed = JSON.parse(saved) as DashboardWidget[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch { /* ignore */ }
  return defaultWidgets;
}

function saveWidgetLayout(widgets: DashboardWidget[]): void {
  try { localStorage.setItem("aos_widgets", JSON.stringify(widgets)); } catch { /* ignore */ }
}

// -- Store --------------------------------------------------------------------

class Store {
  private state: AppState = { ...initialState };
  private listeners = new Set<Listener>();
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  getState(): Readonly<AppState> {
    return this.state;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => void this.listeners.delete(listener);
  }

  private notify(): void {
    const snapshot = this.snapshot();
    this.listeners.forEach(fn => fn(snapshot));
  }

  private snapshot(): AppState {
    return {
      ...this.state,
      profiles: [...this.state.profiles],
      skills: [...this.state.skills],
      activityFeed: [...this.state.activityFeed],
      widgets: [...this.state.widgets],
      metrics: [...this.state.metrics],
    };
  }

  // -- Mutations ----------------------------------------------------------------

  setPanel(panel: PanelName): void {
    this.state = { ...this.state, activePanel: panel, error: null };
    this.notify();
    this.fetchPanelData(panel);
  }

  setStatus(status: SystemStatus): void {
    this.state = { ...this.state, status, loading: false };
    this.notify();
  }

  setProfiles(profiles: AgentProfile[]): void {
    this.state = { ...this.state, profiles };
    this.notify();
  }

  setSkills(skills: SkillInfo[]): void {
    this.state = { ...this.state, skills };
    this.notify();
  }

  setError(err: string): void {
    this.state = { ...this.state, error: err, loading: false };
    this.notify();
  }

  addActivity(event: ActivityEvent): void {
    const feed = [event, ...this.state.activityFeed].slice(0, 500);
    this.state = { ...this.state, activityFeed: feed };
    this.notify();
  }

  addMetric(snapshot: MetricsSnapshot): void {
    const metrics = [...this.state.metrics, snapshot].slice(-120); // keep last 2 min
    this.state = { ...this.state, metrics };
    this.notify();
  }

  updateWidget(id: string, patch: Partial<DashboardWidget>): void {
    const widgets = this.state.widgets.map(w => w.id === id ? { ...w, ...patch } : w);
    this.state = { ...this.state, widgets };
    saveWidgetLayout(widgets);
    this.notify();
  }

  moveWidget(id: string, x: number, y: number): void {
    const widgets = this.state.widgets.map(w => w.id === id ? { ...w, x, y } : w);
    this.state = { ...this.state, widgets };
    saveWidgetLayout(widgets);
    this.notify();
  }

  setLoading(loading: boolean): void {
    this.state = { ...this.state, loading };
    this.notify();
  }

  // -- Data fetching -----------------------------------------------------------

  async fetchPanelData(panel: PanelName): Promise<void> {
    this.setLoading(true);
    try {
      switch (panel) {
        case "overview":
          await Promise.all([this.fetchStatus(), this.fetchProfiles(), this.fetchSkills()]);
          break;
        case "skills":
          await this.fetchSkills();
          break;
        case "admin":
          break;
        default:
          break;
      }
    } catch (e) {
      this.setError(e instanceof Error ? e.message : "Erreur inconnue");
    }
  }

  async fetchStatus(): Promise<void> {
    const r = await fetch("/api/status");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const status = await r.json() as SystemStatus & { error?: string };
    // L'API retourne 200 + {error} si le token est invalide — ne pas l'accepter
    if (status.error) throw new Error(status.error);
    this.setStatus(status);
    const metric: MetricsSnapshot = {
      timestamp: Date.now(),
      total_calls: status.total_calls,
      errors: status.errors,
      calls_per_agent: status.calls_per_agent,
      uptime_seconds: status.uptime_seconds,
      latency_ms: 0,
    };
    this.addMetric(metric);
  }

  async fetchProfiles(): Promise<void> {
    const r = await fetch("/api/profiles");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { profiles: AgentProfile[] };
    this.setProfiles(data.profiles);
  }

  async fetchSkills(): Promise<void> {
    const r = await fetch("/api/skills");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { skills: SkillInfo[] };
    this.setSkills(data.skills);
  }

  async fetchUsers(): Promise<UserInfo[] | null> {
    if (this.state.status?.user.role !== "admin") return null;
    const r = await fetch("/api/users");
    if (!r.ok) return null;
    const data = await r.json() as { users: UserInfo[] };
    return data.users;
  }

  // -- Polling -----------------------------------------------------------------

  startPolling(intervalMs = 5000): void {
    this.stopPolling();
    this.fetchStatus().catch(() => { /* ignore */ });
    this.fetchProfiles().catch(() => { /* ignore */ });
    this.pollTimer = setInterval(() => {
      this.fetchStatus().catch(() => { /* ignore */ });
    }, intervalMs);
  }

  stopPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }
}

export const store = new Store();
