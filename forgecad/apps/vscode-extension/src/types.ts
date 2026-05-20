export type ForgeCADMode = "stopped" | "external" | "local";

export type ForgeCADHealth = {
  ok: boolean;
  service: string;
  phase: number;
  dependencies?: Record<string, boolean>;
};

export type ForgeCADSession = {
  session_id: string;
  root_path: string | null;
  active_model_id: string | null;
  active_revision_id: string | null;
};

export type ForgeCADModel = {
  model_id: string;
  session_id: string;
  name: string;
  source_kind: string;
  active_revision_id: string;
  revision_ids: string[];
};

export type ForgeCADRevision = {
  revision_id: string;
  model_id: string;
  session_id: string;
  source_ref: Record<string, unknown>;
  metadata: Record<string, unknown>;
  scene_tree: Record<string, unknown>;
};

export type ForgeCADCurrent = {
  session: ForgeCADSession;
  model: ForgeCADModel | null;
  revision: ForgeCADRevision | null;
};

export type ForgeCADExportResult = {
  session_id: string;
  model_id: string;
  revision_id: string;
  export: {
    output_path: string;
    format: string;
    size_bytes: number;
  };
};

export type ForgeCADStatus = {
  mode: ForgeCADMode;
  baseUrl: string | null;
  sessionId: string | null;
  authToken: string | null;
  health: ForgeCADHealth | null;
  current: ForgeCADCurrent | null;
  trusted: boolean;
};

export type Output = {
  channel: import("vscode").OutputChannel;
  info(message: string): void;
  warn(message: string): void;
  error(message: string): void;
  show(): void;
  dispose(): void;
};
