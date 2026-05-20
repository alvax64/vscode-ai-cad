export type ForgeCADViewState = {
  camera: Record<string, unknown> | null;
  selected_shape_ids: string[];
  visible_node_states: Record<string, unknown>;
  clipping: Record<string, unknown>;
  active_analysis_tool: string | null;
  viewport_size: { width: number; height: number } | null;
};

export type ForgeCADRenderCommand = {
  command_id: string;
  command: string;
  session_id: string;
  renderer_id?: string | null;
  model_id?: string | null;
  revision_id?: string | null;
  payload: Record<string, unknown>;
  status: string;
};

export type ForgeCADServiceClientOptions = {
  baseUrl: string;
  authToken?: string;
  fetchImpl?: typeof fetch;
};

export class ForgeCADServiceClient {
  readonly baseUrl: string;
  private readonly authToken: string | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ForgeCADServiceClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  health() {
    return this.get("/health");
  }

  current(sessionId: string) {
    return this.get(`/sessions/${encodeURIComponent(sessionId)}/current`);
  }

  tessellate(modelId: string, revisionId: string) {
    return this.post(
      `/models/${encodeURIComponent(modelId)}/revisions/${encodeURIComponent(revisionId)}/tessellate`,
      {},
    );
  }

  registerRenderer(input: {
    session_id: string;
    renderer_id?: string;
    capabilities?: Record<string, unknown>;
    view_state?: Partial<ForgeCADViewState>;
  }) {
    return this.post("/renderers", input);
  }

  updateViewState(
    rendererId: string,
    input: {
      view_state: Partial<ForgeCADViewState>;
      model_id?: string | null;
      revision_id?: string | null;
    },
  ) {
    return this.post(`/renderers/${encodeURIComponent(rendererId)}/view-state`, input);
  }

  recordCapture(
    rendererId: string,
    input: {
      command_id?: string | null;
      image_base64: string;
      mime_type?: string;
      width?: number;
      height?: number;
      model_id?: string | null;
      revision_id?: string | null;
      view_state?: Partial<ForgeCADViewState>;
    },
  ) {
    return this.post(`/renderers/${encodeURIComponent(rendererId)}/captures`, input);
  }

  renderActiveRevision(sessionId: string, rendererId?: string) {
    return this.post("/render/render_revision", {
      session_id: sessionId,
      renderer_id: rendererId,
    });
  }

  eventsWebSocketUrl() {
    const url = new URL(this.baseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/events";
    if (this.authToken) {
      url.searchParams.set("token", this.authToken);
    }
    return url.toString();
  }

  private async get(path: string) {
    const response = await this.fetchImpl(this.baseUrl + path, {
      headers: this.requestHeaders(),
    });
    return this.readResponse(response);
  }

  private async post(path: string, body: unknown) {
    const response = await this.fetchImpl(this.baseUrl + path, {
      method: "POST",
      headers: this.requestHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(body),
    });
    return this.readResponse(response);
  }

  private requestHeaders(headers: Record<string, string> = {}) {
    if (!this.authToken) {
      return headers;
    }
    return {
      ...headers,
      "x-forgecad-token": this.authToken,
    };
  }

  private async readResponse(response: Response) {
    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error?.message ?? response.statusText;
      throw new Error(message);
    }
    return payload;
  }
}
