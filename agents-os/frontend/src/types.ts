// ============================================================================
// Agent OS — Types TypeScript (miroir des schemas Pydantic backend/schemas.py)
// ============================================================================

export interface UserPermissions {
  panels: string[];
  agents: string[];
}

export interface UserInfo {
  id: number;
  name: string;
  email: string;
  role: "admin" | "user";
  permissions: UserPermissions;
}

export interface UserRecord extends UserInfo {
  disabled: boolean;
  created_at: string;
}

export interface AgentConfig {
  emoji: string;
  color: string;
  desc: string;
}

export interface AgentProfile {
  name: string;
  emoji: string;
  color: string;
  description: string;
  memory: string;
  has_memory: boolean;
}

export interface SystemStatus {
  status: "online" | "offline";
  uptime_seconds: number;
  total_calls: number;
  calls_per_agent: Record<string, number>;
  errors: number;
  profiles: string[];
  agents: Record<string, AgentConfig>;
  panels: PanelName[];
  user: UserInfo;
}

export interface SkillInfo {
  name: string;
  path: string;
  description: string;
}

export interface ModelInfo {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

// -- Chat --------------------------------------------------------------------

export interface ChatRequest {
  profile: string;
  message: string;
}

export interface ChatResponse {
  response: string;
}

export interface ChatCompletionMessage {
  role: string;
  content: string;
}

export interface ChatCompletionChoice {
  index: number;
  message: ChatCompletionMessage;
  finish_reason: string;
}

export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

// -- Admin -------------------------------------------------------------------

export interface CreateUserRequest {
  name: string;
  email: string;
  password: string;
  role: "admin" | "user";
  permissions: UserPermissions;
}

export interface UpdateUserRequest {
  id: number;
  role?: "admin" | "user";
  disabled?: boolean;
}

export interface CreateAgentRequest {
  name: string;
  emoji: string;
  color: string;
  description: string;
}

// -- n8n ---------------------------------------------------------------------

export interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface N8nExecution {
  id: number;
  workflow_id: string;
  status: string;
  started_at: string;
  stopped_at: string;
}

export interface N8nOrchestrateResult {
  agent: string;
  response: string;
}

// -- UI types ----------------------------------------------------------------

export type PanelName = "overview" | "canvas" | "graph" | "chat" | "memory" | "skills" | "kanban" | "admin" | "n8n";

export interface ActivityEvent {
  id: string;
  timestamp: number;
  type: "info" | "success" | "error" | "tool_call" | "agent_action";
  agent?: string;
  message: string;
  details?: string;
}

export interface DashboardWidget {
  id: string;
  title: string;
  type: "metric" | "chart" | "feed" | "actions";
  x: number;
  y: number;
  w: number;
  h: number;
  minimized: boolean;
}

export interface MetricsSnapshot {
  timestamp: number;
  total_calls: number;
  errors: number;
  calls_per_agent: Record<string, number>;
  uptime_seconds: number;
  latency_ms: number;
}

export interface AppState {
  activePanel: PanelName;
  status: SystemStatus | null;
  profiles: AgentProfile[];
  skills: SkillInfo[];
  activityFeed: ActivityEvent[];
  widgets: DashboardWidget[];
  metrics: MetricsSnapshot[];
  loading: boolean;
  error: string | null;
}
