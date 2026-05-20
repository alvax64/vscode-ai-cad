const DEFAULT_VIEW_STATE = {
  camera: null,
  selected_shape_ids: [],
  visible_node_states: {},
  clipping: {},
  active_analysis_tool: null,
  viewport_size: null
};

export class ForgeCADRendererClient {
  constructor(options) {
    this.serviceBaseUrl = stripTrailingSlash(options.serviceBaseUrl);
    this.sessionId = options.sessionId;
    this.rendererId = options.rendererId || null;
    this.adapter = options.adapter || new DomStatusRenderer(options.mount);
    this.fetchImpl = options.fetchImpl || window.fetch.bind(window);
    this.websocketFactory = options.websocketFactory || ((url) => new WebSocket(url));
    this.authToken = options.authToken || null;
    this.logger = options.logger || console;
    this.currentModelId = null;
    this.currentRevisionId = null;
    this.viewState = { ...DEFAULT_VIEW_STATE };
    this.websocket = null;
  }

  async start() {
    await this.registerRenderer();
    await this.renderActiveRevision();
    this.connectEvents();
    this.attachAdapterViewStateListener();
    return this;
  }

  async registerRenderer() {
    const result = await this.post("/renderers", {
      session_id: this.sessionId,
      renderer_id: this.rendererId,
      capabilities: {
        commands: [
          "render_revision",
          "capture_view",
          "capture_overview",
          "set_camera",
          "set_visibility",
          "set_clipping",
          "get_view_state"
        ],
        capture: Boolean(this.adapter.captureView),
        overview_capture: Boolean(this.adapter.captureOverview)
      },
      view_state: this.viewState
    });
    this.rendererId = result.renderer.renderer_id;
    this.viewState = normalizeViewState(result.renderer.view_state);
    return result.renderer;
  }

  async renderActiveRevision() {
    const current = await this.get(`/sessions/${encodeURIComponent(this.sessionId)}/current`);
    if (!current.model || !current.revision) {
      await this.adapter.renderEmpty?.(current);
      return null;
    }
    return this.renderRevision(current.model.model_id, current.revision.revision_id);
  }

  async renderRevision(modelId, revisionId, config = {}) {
    const path =
      `/models/${encodeURIComponent(modelId)}` +
      `/revisions/${encodeURIComponent(revisionId)}/tessellate`;
    const payload = await this.post(path, {});
    this.currentModelId = modelId;
    this.currentRevisionId = revisionId;
    await this.adapter.renderRevision({
      sessionId: this.sessionId,
      modelId,
      revisionId,
      tessellatedScene: payload.tessellated_scene,
      config
    });
    await this.reportViewState();
    return payload;
  }

  connectEvents() {
    const url = new URL(this.serviceBaseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/events";
    if (this.authToken) {
      url.searchParams.set("token", this.authToken);
    }
    this.websocket = this.websocketFactory(url.toString());
    this.websocket.addEventListener("message", (event) => {
      this.handleEvent(JSON.parse(event.data)).catch((error) => {
        this.logger.error("ForgeCAD renderer event failed", error);
      });
    });
    this.websocket.addEventListener("close", () => {
      this.websocket = null;
    });
  }

  async handleEvent(event) {
    if (event.session_id && event.session_id !== this.sessionId) {
      return;
    }
    if (event.event_type === "revision.created") {
      await this.renderRevision(event.model_id, event.revision_id);
      return;
    }
    if (event.event_type !== "view.command") {
      return;
    }
    const command = event.payload.command;
    if (command.renderer_id && command.renderer_id !== this.rendererId) {
      return;
    }
    await this.handleCommand(command);
  }

  async handleCommand(command) {
    if (command.command === "render_revision") {
      const scene = command.payload.tessellated_scene;
      this.currentModelId = command.model_id;
      this.currentRevisionId = command.revision_id;
      if (scene) {
        await this.adapter.renderRevision({
          sessionId: command.session_id,
          modelId: command.model_id,
          revisionId: command.revision_id,
          tessellatedScene: scene,
          config: command.payload.config || {}
        });
        await this.reportViewState();
      } else {
        await this.renderRevision(command.model_id, command.revision_id);
      }
      return;
    }
    if (command.command === "capture_view") {
      await this.captureView(command);
      return;
    }
    if (command.command === "capture_overview") {
      await this.captureOverview(command);
      return;
    }
    if (command.command === "set_camera") {
      await this.adapter.setCamera?.(command.payload.camera);
      await this.reportViewState();
      return;
    }
    if (command.command === "set_visibility") {
      await this.adapter.setVisibility?.(command.payload.visible_node_states);
      await this.reportViewState();
      return;
    }
    if (command.command === "set_clipping") {
      await this.adapter.setClipping?.(command.payload.clipping);
      await this.reportViewState();
      return;
    }
    if (command.command === "get_view_state") {
      await this.reportViewState();
    }
  }

  async captureView(command) {
    const capture = await this.adapter.captureView?.(command.payload.config || {});
    if (!capture) {
      return;
    }
    await this.post(`/renderers/${encodeURIComponent(this.rendererId)}/captures`, {
      command_id: command.command_id,
      image_base64: stripDataUrlPrefix(capture.dataUrl || capture.image_base64),
      mime_type: capture.mimeType || "image/png",
      width: capture.width,
      height: capture.height,
      model_id: command.model_id || this.currentModelId,
      revision_id: command.revision_id || this.currentRevisionId,
      view_state: await this.readViewState()
    });
  }

  async captureOverview(command) {
    const capture = await this.adapter.captureOverview?.(
      command.payload.views,
      command.payload.config || {}
    );
    if (!capture) {
      return;
    }
    await this.post(`/renderers/${encodeURIComponent(this.rendererId)}/captures`, {
      command_id: command.command_id,
      image_base64: stripDataUrlPrefix(capture.dataUrl || capture.image_base64),
      mime_type: capture.mimeType || "image/png",
      width: capture.width,
      height: capture.height,
      model_id: command.model_id || this.currentModelId,
      revision_id: command.revision_id || this.currentRevisionId,
      view_state: await this.readViewState()
    });
  }

  attachAdapterViewStateListener() {
    if (!this.adapter.onViewStateChanged) {
      return;
    }
    this.adapter.onViewStateChanged((viewState) => {
      this.reportViewState(viewState).catch((error) => {
        this.logger.error("ForgeCAD view-state report failed", error);
      });
    });
  }

  async readViewState(viewState = null) {
    const adapterState = viewState || (await this.adapter.getViewState?.()) || {};
    this.viewState = normalizeViewState(adapterState);
    return this.viewState;
  }

  async reportViewState(viewState = null) {
    await this.readViewState(viewState);
    if (!this.rendererId) {
      return;
    }
    await this.post(`/renderers/${encodeURIComponent(this.rendererId)}/view-state`, {
      model_id: this.currentModelId,
      revision_id: this.currentRevisionId,
      view_state: this.viewState
    });
  }

  async get(path) {
    const response = await this.fetchImpl(this.serviceBaseUrl + path, {
      headers: this.requestHeaders()
    });
    return readResponse(response);
  }

  async post(path, body) {
    const response = await this.fetchImpl(this.serviceBaseUrl + path, {
      method: "POST",
      headers: this.requestHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(body)
    });
    return readResponse(response);
  }

  requestHeaders(headers = {}) {
    if (!this.authToken) {
      return headers;
    }
    return {
      ...headers,
      "x-forgecad-token": this.authToken
    };
  }
}

export class DomStatusRenderer {
  constructor(mount) {
    this.mount = mount || document.body;
    this.canvas = document.createElement("canvas");
    this.canvas.width = 960;
    this.canvas.height = 540;
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.display = "block";
    this.mount.replaceChildren(this.canvas);
    this.lastRender = null;
  }

  async renderRevision(renderRequest) {
    this.lastRender = renderRequest;
    const context = this.canvas.getContext("2d");
    context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#121316";
    context.fillRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#f5c542";
    context.font = "24px system-ui, sans-serif";
    context.fillText("ForgeCAD Renderer", 32, 48);
    context.fillStyle = "#f2f2f2";
    context.font = "16px system-ui, sans-serif";
    context.fillText(`model: ${renderRequest.modelId}`, 32, 92);
    context.fillText(`revision: ${renderRequest.revisionId}`, 32, 120);
    const scene = renderRequest.tessellatedScene || {};
    const shapeCount = Object.keys(scene.shapes || {}).length;
    const instanceCount = Array.isArray(scene.instances) ? scene.instances.length : 0;
    context.fillText(`shapes: ${shapeCount}`, 32, 158);
    context.fillText(`instances: ${instanceCount}`, 32, 186);
  }

  async renderEmpty() {
    const context = this.canvas.getContext("2d");
    context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#121316";
    context.fillRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#f2f2f2";
    context.font = "18px system-ui, sans-serif";
    context.fillText("No active ForgeCAD model", 32, 48);
  }

  async captureView() {
    return {
      dataUrl: this.canvas.toDataURL("image/png"),
      mimeType: "image/png",
      width: this.canvas.width,
      height: this.canvas.height
    };
  }

  async captureOverview() {
    return this.captureView();
  }

  async getViewState() {
    return {
      ...DEFAULT_VIEW_STATE,
      viewport_size: {
        width: this.canvas.clientWidth || this.canvas.width,
        height: this.canvas.clientHeight || this.canvas.height
      }
    };
  }
}

export function createServiceDrivenRenderer(options = {}) {
  const params = new URLSearchParams(window.location.search);
  const serviceBaseUrl = options.serviceBaseUrl || params.get("service");
  const sessionId = options.sessionId || params.get("session");
  if (!serviceBaseUrl || !sessionId) {
    throw new Error("ForgeCAD renderer requires service and session parameters");
  }
  const mount = options.mount || document.getElementById("cad_viewer") || document.body;
  return new ForgeCADRendererClient({
    serviceBaseUrl,
    sessionId,
    authToken: options.authToken || params.get("token"),
    rendererId: options.rendererId || params.get("renderer"),
    adapter: options.adapter,
    mount,
    logger: options.logger
  });
}

async function readResponse(response) {
  const payload = await response.json();
  if (!response.ok) {
    const message = payload?.error?.message || response.statusText;
    throw new Error(message);
  }
  return payload;
}

function normalizeViewState(viewState) {
  return {
    camera: viewState.camera || null,
    selected_shape_ids: Array.from(viewState.selected_shape_ids || []),
    visible_node_states: { ...(viewState.visible_node_states || {}) },
    clipping: { ...(viewState.clipping || {}) },
    active_analysis_tool: viewState.active_analysis_tool || null,
    viewport_size: viewState.viewport_size || null
  };
}

function stripTrailingSlash(value) {
  return value.replace(/\/$/, "");
}

function stripDataUrlPrefix(value) {
  return String(value || "").replace(/^data:[^,]+,/, "");
}
