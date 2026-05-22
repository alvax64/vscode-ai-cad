type JsonObject = Record<string, unknown>;
type Vec3 = [number, number, number];
type Mat4 = Float32Array;

export { createThreeCadViewerAdapter, ThreeCadViewerAdapter } from "./three-cad-viewer-adapter.js";
export type { ThreeCadViewerAdapterOptions } from "./three-cad-viewer-adapter.js";

export type ForgeCADViewState = {
  camera: JsonObject | null;
  selected_shape_ids: string[];
  visible_node_states: JsonObject;
  clipping: JsonObject;
  active_analysis_tool: string | null;
  viewport_size: { width: number; height: number } | null;
};

export type ForgeCADRendererCapture = {
  dataUrl?: string;
  image_base64?: string;
  mimeType?: string;
  width?: number;
  height?: number;
};

export type ForgeCADRenderRequest = {
  sessionId: string;
  modelId: string;
  revisionId: string;
  tessellatedScene: TessellatedScene;
  config: JsonObject;
};

export type ForgeCADRendererAdapter = {
  renderRevision(request: ForgeCADRenderRequest): Promise<void> | void;
  renderEmpty?(current: ForgeCADCurrentResponse): Promise<void> | void;
  captureView?(config?: JsonObject): Promise<ForgeCADRendererCapture | null | undefined>;
  captureOverview?(
    views?: string[],
    config?: JsonObject
  ): Promise<ForgeCADRendererCapture | null | undefined>;
  setCamera?(camera?: JsonObject): Promise<void> | void;
  setVisibility?(visibleNodeStates?: JsonObject): Promise<void> | void;
  setClipping?(clipping?: JsonObject): Promise<void> | void;
  getViewState?(): Promise<Partial<ForgeCADViewState>> | Partial<ForgeCADViewState>;
  onViewStateChanged?(callback: (viewState: Partial<ForgeCADViewState>) => void): void;
};

export type ForgeCADRendererClientOptions = {
  serviceBaseUrl: string;
  sessionId: string;
  rendererId?: string | null;
  authToken?: string | null;
  adapter?: ForgeCADRendererAdapter;
  mount?: HTMLElement | null;
  fetchImpl?: typeof fetch;
  websocketFactory?: (url: string) => WebSocket;
  logger?: Pick<Console, "error">;
};

export type CreateServiceDrivenRendererOptions = Partial<ForgeCADRendererClientOptions>;

type ForgeCADCurrentResponse = {
  model?: { model_id: string } | null;
  revision?: { revision_id: string } | null;
};

type ForgeCADRendererResponse = {
  renderer: {
    renderer_id: string;
    view_state: Partial<ForgeCADViewState>;
  };
};

type TessellatedScene = {
  instances?: SceneInstance[];
  [key: string]: unknown;
};

type SceneInstance = {
  vertices?: unknown;
  triangles?: unknown;
  normals?: unknown;
  edges?: unknown;
  [key: string]: unknown;
};

type RenderCommand = {
  command_id: string;
  command: string;
  session_id: string;
  renderer_id?: string | null;
  model_id?: string | null;
  revision_id?: string | null;
  payload: {
    tessellated_scene?: TessellatedScene;
    config?: JsonObject;
    views?: string[];
    camera?: JsonObject;
    visible_node_states?: JsonObject;
    clipping?: JsonObject;
  };
};

type ServiceEvent = {
  event_type: string;
  session_id?: string | null;
  model_id?: string | null;
  revision_id?: string | null;
  payload: {
    command?: RenderCommand;
    [key: string]: unknown;
  };
};

const DEFAULT_VIEW_STATE: ForgeCADViewState = {
  camera: null,
  selected_shape_ids: [],
  visible_node_states: {},
  clipping: {},
  active_analysis_tool: null,
  viewport_size: null
};

export class ForgeCADRendererClient {
  readonly serviceBaseUrl: string;
  readonly sessionId: string;
  readonly adapter: ForgeCADRendererAdapter;
  readonly fetchImpl: typeof fetch;
  readonly websocketFactory: (url: string) => WebSocket;
  readonly authToken: string | null;
  readonly logger: Pick<Console, "error">;
  rendererId: string | null;
  currentModelId: string | null = null;
  currentRevisionId: string | null = null;
  viewState: ForgeCADViewState = { ...DEFAULT_VIEW_STATE };
  websocket: WebSocket | null = null;
  emptyPollTimer: number | null = null;
  private eventQueue: Promise<void> = Promise.resolve();

  constructor(options: ForgeCADRendererClientOptions) {
    this.serviceBaseUrl = stripTrailingSlash(options.serviceBaseUrl);
    this.sessionId = options.sessionId;
    this.rendererId = options.rendererId || null;
    this.adapter = options.adapter || new DomStatusRenderer(options.mount);
    this.fetchImpl = options.fetchImpl || window.fetch.bind(window);
    this.websocketFactory = options.websocketFactory || ((url: string) => new WebSocket(url));
    this.authToken = options.authToken || null;
    this.logger = options.logger || console;
  }

  async start(): Promise<this> {
    await this.registerRenderer();
    this.connectEvents();
    this.attachAdapterViewStateListener();
    await this.renderActiveRevision();
    return this;
  }

  async registerRenderer(): Promise<ForgeCADRendererResponse["renderer"]> {
    const result = await this.post<ForgeCADRendererResponse>("/renderers", {
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

  async renderActiveRevision(): Promise<unknown | null> {
    const current = await this.get<ForgeCADCurrentResponse>(
      `/sessions/${encodeURIComponent(this.sessionId)}/current`
    );
    if (!current.model || !current.revision) {
      await this.adapter.renderEmpty?.(current);
      this.startEmptyPolling();
      return null;
    }
    this.stopEmptyPolling();
    return this.renderRevision(current.model.model_id, current.revision.revision_id);
  }

  async renderRevision(
    modelId: string,
    revisionId: string,
    config: JsonObject = {}
  ): Promise<{ tessellated_scene: TessellatedScene }> {
    const path =
      `/models/${encodeURIComponent(modelId)}` +
      `/revisions/${encodeURIComponent(revisionId)}/tessellate`;
    const payload = await this.post<{ tessellated_scene: TessellatedScene }>(path, {});
    this.stopEmptyPolling();
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

  startEmptyPolling(): void {
    if (this.emptyPollTimer !== null) {
      return;
    }
    this.emptyPollTimer = window.setInterval(() => {
      if (this.currentModelId && this.currentRevisionId) {
        this.stopEmptyPolling();
        return;
      }
      this.renderActiveRevision().catch((error: unknown) => {
        this.logger.error("ForgeCAD active-model poll failed", error);
      });
    }, 1000);
  }

  stopEmptyPolling(): void {
    if (this.emptyPollTimer === null) {
      return;
    }
    window.clearInterval(this.emptyPollTimer);
    this.emptyPollTimer = null;
  }

  connectEvents(): void {
    const url = new URL(this.serviceBaseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/events";
    if (this.authToken) {
      url.searchParams.set("token", this.authToken);
    }
    this.websocket = this.websocketFactory(url.toString());
    this.websocket.addEventListener("message", (event: MessageEvent<string>) => {
      const serviceEvent = JSON.parse(event.data) as ServiceEvent;
      this.eventQueue = this.eventQueue
        .then(() => this.handleEvent(serviceEvent))
        .catch((error: unknown) => {
          this.logger.error("ForgeCAD renderer event failed", error);
        });
    });
    this.websocket.addEventListener("close", () => {
      this.websocket = null;
    });
  }

  async handleEvent(event: ServiceEvent): Promise<void> {
    if (event.session_id && event.session_id !== this.sessionId) {
      return;
    }
    if (event.event_type === "revision.created" && event.model_id && event.revision_id) {
      this.stopEmptyPolling();
      await this.renderRevision(event.model_id, event.revision_id);
      return;
    }
    if (event.event_type !== "view.command") {
      return;
    }
    const command = event.payload.command;
    if (!command) {
      return;
    }
    if (command.renderer_id && command.renderer_id !== this.rendererId) {
      return;
    }
    await this.handleCommand(command);
  }

  async handleCommand(command: RenderCommand): Promise<void> {
    if (command.command === "render_revision") {
      const scene = command.payload.tessellated_scene;
      this.currentModelId = command.model_id || null;
      this.currentRevisionId = command.revision_id || null;
      if (scene && command.model_id && command.revision_id) {
        await this.adapter.renderRevision({
          sessionId: command.session_id,
          modelId: command.model_id,
          revisionId: command.revision_id,
          tessellatedScene: scene,
          config: command.payload.config || {}
        });
        await this.reportViewState();
      } else if (command.model_id && command.revision_id) {
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

  async captureView(command: RenderCommand): Promise<void> {
    const capture = await this.adapter.captureView?.(command.payload.config || {});
    if (!capture || !this.rendererId) {
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

  async captureOverview(command: RenderCommand): Promise<void> {
    const capture = await this.adapter.captureOverview?.(
      command.payload.views,
      command.payload.config || {}
    );
    if (!capture || !this.rendererId) {
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

  attachAdapterViewStateListener(): void {
    if (!this.adapter.onViewStateChanged) {
      return;
    }
    this.adapter.onViewStateChanged((viewState) => {
      this.reportViewState(viewState).catch((error: unknown) => {
        this.logger.error("ForgeCAD view-state report failed", error);
      });
    });
  }

  async readViewState(viewState: Partial<ForgeCADViewState> | null = null): Promise<ForgeCADViewState> {
    const adapterState = viewState || (await this.adapter.getViewState?.()) || {};
    this.viewState = normalizeViewState(adapterState);
    return this.viewState;
  }

  async reportViewState(viewState: Partial<ForgeCADViewState> | null = null): Promise<void> {
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

  async get<T>(path: string): Promise<T> {
    const response = await this.fetchImpl(this.serviceBaseUrl + path, {
      headers: this.requestHeaders()
    });
    return readResponse<T>(response);
  }

  async post<T = unknown>(path: string, body: unknown): Promise<T> {
    const response = await this.fetchImpl(this.serviceBaseUrl + path, {
      method: "POST",
      headers: this.requestHeaders({ "content-type": "application/json" }),
      body: JSON.stringify(body)
    });
    return readResponse<T>(response);
  }

  requestHeaders(headers: Record<string, string> = {}): Record<string, string> {
    if (!this.authToken) {
      return headers;
    }
    return {
      ...headers,
      "x-forgecad-token": this.authToken
    };
  }
}

type Bounds = {
  min: Vec3;
  max: Vec3;
  valid: boolean;
};

type MeshBuffer = {
  vertexBuffer: WebGLBuffer;
  normalBuffer: WebGLBuffer;
  indexBuffer: WebGLBuffer;
  indexType: number;
  count: number;
};

type EdgeBuffer = {
  vertexBuffer: WebGLBuffer;
  normalBuffer: WebGLBuffer;
  count: number;
};

type WebGLLocations = {
  position: number;
  normal: number;
  viewProjection: WebGLUniformLocation | null;
  color: WebGLUniformLocation | null;
  lightDirection: WebGLUniformLocation | null;
  useLighting: WebGLUniformLocation | null;
};

export class DomStatusRenderer implements ForgeCADRendererAdapter {
  readonly mount: HTMLElement;
  readonly canvas: HTMLCanvasElement;
  readonly overlay: HTMLDivElement;
  readonly gl: WebGLRenderingContext | null;
  readonly program?: WebGLProgram;
  readonly locations?: WebGLLocations;
  lastRender: ForgeCADRenderRequest | null = null;
  meshes: MeshBuffer[] = [];
  edges: EdgeBuffer[] = [];
  bounds: Bounds | null = null;
  theta = Math.PI / 4;
  phi = Math.PI / 3;
  distance = 1;
  target: Vec3 = [0, 0, 0];
  animationFrame = 0;
  drag: { x: number; y: number } | null = null;
  private onStateChanged?: (viewState: Partial<ForgeCADViewState>) => void;

  constructor(mount?: HTMLElement | null) {
    this.mount = mount || document.body;
    this.canvas = document.createElement("canvas");
    this.overlay = document.createElement("div");
    this.overlay.style.position = "fixed";
    this.overlay.style.left = "16px";
    this.overlay.style.top = "14px";
    this.overlay.style.color = "#c9d1d9";
    this.overlay.style.font = "12px system-ui, sans-serif";
    this.overlay.style.opacity = "0.76";
    this.overlay.style.pointerEvents = "none";
    this.canvas.style.width = "100%";
    this.canvas.style.height = "100%";
    this.canvas.style.display = "block";
    this.canvas.style.cursor = "grab";
    this.mount.replaceChildren(this.canvas, this.overlay);
    this.gl = this.canvas.getContext("webgl", { antialias: true });
    if (this.gl) {
      this.program = createProgram(this.gl, VERTEX_SHADER, FRAGMENT_SHADER);
      this.locations = {
        position: this.gl.getAttribLocation(this.program, "a_position"),
        normal: this.gl.getAttribLocation(this.program, "a_normal"),
        viewProjection: this.gl.getUniformLocation(this.program, "u_viewProjection"),
        color: this.gl.getUniformLocation(this.program, "u_color"),
        lightDirection: this.gl.getUniformLocation(this.program, "u_lightDirection"),
        useLighting: this.gl.getUniformLocation(this.program, "u_useLighting")
      };
    }
    this.installControls();
  }

  async renderRevision(renderRequest: ForgeCADRenderRequest): Promise<void> {
    this.lastRender = renderRequest;
    const scene = renderRequest.tessellatedScene || {};
    this.overlay.textContent = `${renderRequest.modelId} · ${renderRequest.revisionId}`;
    if (!this.gl) {
      this.renderFallback(scene);
      return;
    }
    this.loadScene(scene);
    this.frameScene();
    this.draw();
  }

  async renderEmpty(): Promise<void> {
    this.meshes = [];
    this.edges = [];
    this.overlay.textContent = "No active ForgeCAD model";
    this.clear();
  }

  async captureView(): Promise<ForgeCADRendererCapture> {
    return {
      dataUrl: this.canvas.toDataURL("image/png"),
      mimeType: "image/png",
      width: this.canvas.width,
      height: this.canvas.height
    };
  }

  async captureOverview(): Promise<ForgeCADRendererCapture> {
    return this.captureView();
  }

  async getViewState(): Promise<ForgeCADViewState> {
    return {
      ...DEFAULT_VIEW_STATE,
      camera: {
        target: this.target,
        theta: this.theta,
        phi: this.phi,
        distance: this.distance
      },
      viewport_size: {
        width: this.canvas.clientWidth || this.canvas.width,
        height: this.canvas.clientHeight || this.canvas.height
      }
    };
  }

  async setCamera(camera: JsonObject = {}): Promise<void> {
    if (Array.isArray(camera.target)) {
      this.target = point(camera.target);
    }
    if (Number.isFinite(camera.theta)) {
      this.theta = Number(camera.theta);
    }
    if (Number.isFinite(camera.phi)) {
      this.phi = clamp(Number(camera.phi), 0.08, Math.PI - 0.08);
    }
    if (Number.isFinite(camera.distance)) {
      this.distance = Math.max(Number(camera.distance), 0.001);
    }
    this.draw();
  }

  installControls(): void {
    this.canvas.addEventListener("pointerdown", (event) => {
      this.canvas.setPointerCapture(event.pointerId);
      this.canvas.style.cursor = "grabbing";
      this.drag = { x: event.clientX, y: event.clientY };
    });
    this.canvas.addEventListener("pointermove", (event) => {
      if (!this.drag) {
        return;
      }
      const dx = event.clientX - this.drag.x;
      const dy = event.clientY - this.drag.y;
      this.drag = { x: event.clientX, y: event.clientY };
      this.theta -= dx * 0.01;
      this.phi = clamp(this.phi + dy * 0.01, 0.08, Math.PI - 0.08);
      this.draw();
      this.onStateChanged?.({
        camera: {
          target: this.target,
          theta: this.theta,
          phi: this.phi,
          distance: this.distance
        }
      });
    });
    this.canvas.addEventListener("pointerup", (event) => {
      this.canvas.releasePointerCapture(event.pointerId);
      this.canvas.style.cursor = "grab";
      this.drag = null;
    });
    this.canvas.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        this.distance *= Math.exp(event.deltaY * 0.001);
        this.draw();
      },
      { passive: false }
    );
    window.addEventListener("resize", () => this.draw());
  }

  loadScene(scene: TessellatedScene): void {
    const gl = this.gl;
    if (!gl) {
      return;
    }
    this.meshes.forEach((mesh) => {
      gl.deleteBuffer(mesh.vertexBuffer);
      gl.deleteBuffer(mesh.normalBuffer);
      gl.deleteBuffer(mesh.indexBuffer);
    });
    this.edges.forEach((edge) => {
      gl.deleteBuffer(edge.vertexBuffer);
      gl.deleteBuffer(edge.normalBuffer);
    });
    this.meshes = [];
    this.edges = [];
    const bounds = emptyBounds();
    for (const instance of scene.instances || []) {
      const vertices = numericArray(instance.vertices);
      const triangles = numericArray(instance.triangles);
      if (vertices.length < 9 || triangles.length < 3) {
        continue;
      }
      extendBounds(bounds, vertices);
      const normals = numericArray(instance.normals);
      const maxIndex = maxArray(triangles);
      const normalData =
        normals.length === vertices.length ? normals : Array.from(generatedNormals(vertices, triangles));
      const mesh: MeshBuffer = {
        vertexBuffer: bufferData(gl, gl.ARRAY_BUFFER, new Float32Array(vertices)),
        normalBuffer: bufferData(gl, gl.ARRAY_BUFFER, new Float32Array(normalData)),
        indexBuffer: bufferData(gl, gl.ELEMENT_ARRAY_BUFFER, indexArray(triangles)),
        indexType: maxIndex > 65535 ? gl.UNSIGNED_INT : gl.UNSIGNED_SHORT,
        count: triangles.length
      };
      if (mesh.indexType === gl.UNSIGNED_INT) {
        gl.getExtension("OES_element_index_uint");
      }
      this.meshes.push(mesh);

      const edgeVertices = edgeArray(instance.edges);
      if (edgeVertices.length >= 6) {
        this.edges.push({
          vertexBuffer: bufferData(gl, gl.ARRAY_BUFFER, new Float32Array(edgeVertices)),
          normalBuffer: bufferData(gl, gl.ARRAY_BUFFER, new Float32Array(edgeVertices.length).fill(1)),
          count: edgeVertices.length / 3
        });
      }
    }
    this.bounds = bounds.valid ? bounds : null;
  }

  frameScene(): void {
    if (!this.bounds) {
      this.target = [0, 0, 0];
      this.distance = 100;
      return;
    }
    const min = this.bounds.min;
    const max = this.bounds.max;
    this.target = [
      (min[0] + max[0]) / 2,
      (min[1] + max[1]) / 2,
      (min[2] + max[2]) / 2
    ];
    const radius = Math.max(distance3(min, max) / 2, 1);
    this.distance = radius * 2.8;
  }

  draw(): void {
    if (this.animationFrame) {
      cancelAnimationFrame(this.animationFrame);
    }
    this.animationFrame = requestAnimationFrame(() => {
      this.animationFrame = 0;
      this.drawNow();
    });
  }

  drawNow(): void {
    const gl = this.gl;
    if (!gl || !this.program || !this.locations) {
      return;
    }
    resizeCanvas(this.canvas);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clearColor(0.071, 0.075, 0.086, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.CULL_FACE);
    gl.useProgram(this.program);

    const aspect = this.canvas.width / Math.max(1, this.canvas.height);
    const projection = perspective(Math.PI / 4, aspect, Math.max(0.01, this.distance / 100), this.distance * 100);
    const eye: Vec3 = [
      this.target[0] + this.distance * Math.sin(this.phi) * Math.cos(this.theta),
      this.target[1] + this.distance * Math.sin(this.phi) * Math.sin(this.theta),
      this.target[2] + this.distance * Math.cos(this.phi)
    ];
    const view = lookAt(eye, this.target, [0, 0, 1]);
    const viewProjection = multiply(projection, view);
    gl.uniformMatrix4fv(this.locations.viewProjection, false, viewProjection);
    gl.uniform3f(this.locations.lightDirection, -0.35, -0.55, 0.76);

    for (const mesh of this.meshes) {
      gl.uniform4f(this.locations.color, 0.91, 0.69, 0.14, 1);
      gl.uniform1i(this.locations.useLighting, 1);
      bindAttribute(gl, this.locations.position, mesh.vertexBuffer, 3);
      bindAttribute(gl, this.locations.normal, mesh.normalBuffer, 3);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mesh.indexBuffer);
      gl.drawElements(gl.TRIANGLES, mesh.count, mesh.indexType, 0);
    }

    gl.disable(gl.CULL_FACE);
    gl.depthFunc(gl.LEQUAL);
    for (const edge of this.edges) {
      gl.uniform4f(this.locations.color, 0.04, 0.045, 0.052, 1);
      gl.uniform1i(this.locations.useLighting, 0);
      bindAttribute(gl, this.locations.position, edge.vertexBuffer, 3);
      bindAttribute(gl, this.locations.normal, edge.normalBuffer, 3);
      gl.drawArrays(gl.LINES, 0, edge.count);
    }
    gl.depthFunc(gl.LESS);
  }

  clear(): void {
    if (this.gl) {
      this.draw();
      return;
    }
    const context = this.canvas.getContext("2d");
    if (!context) {
      return;
    }
    context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#121316";
    context.fillRect(0, 0, this.canvas.width, this.canvas.height);
  }

  renderFallback(scene: TessellatedScene): void {
    const context = this.canvas.getContext("2d");
    if (!context) {
      return;
    }
    context.clearRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#121316";
    context.fillRect(0, 0, this.canvas.width, this.canvas.height);
    context.fillStyle = "#f5c542";
    context.font = "24px system-ui, sans-serif";
    context.fillText("ForgeCAD Renderer", 32, 48);
    context.fillStyle = "#f2f2f2";
    context.font = "16px system-ui, sans-serif";
    context.fillText("WebGL is unavailable in this VS Code webview.", 32, 92);
    context.fillText(`instances: ${(scene.instances || []).length}`, 32, 120);
  }

  onViewStateChanged(callback: (viewState: Partial<ForgeCADViewState>) => void): void {
    this.onStateChanged = callback;
  }
}

export function createServiceDrivenRenderer(
  options: CreateServiceDrivenRendererOptions = {}
): ForgeCADRendererClient {
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

async function readResponse<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    const message = payload?.error?.message || response.statusText;
    throw new Error(message);
  }
  return payload as T;
}

function normalizeViewState(viewState: Partial<ForgeCADViewState>): ForgeCADViewState {
  return {
    camera: viewState.camera || null,
    selected_shape_ids: Array.from(viewState.selected_shape_ids || []),
    visible_node_states: { ...(viewState.visible_node_states || {}) },
    clipping: { ...(viewState.clipping || {}) },
    active_analysis_tool: viewState.active_analysis_tool || null,
    viewport_size: viewState.viewport_size || null
  };
}

function stripTrailingSlash(value: string): string {
  return value.replace(/\/$/, "");
}

function stripDataUrlPrefix(value: unknown): string {
  return String(value || "").replace(/^data:[^,]+,/, "");
}

const VERTEX_SHADER = `
attribute vec3 a_position;
attribute vec3 a_normal;
uniform mat4 u_viewProjection;
varying vec3 v_normal;
void main() {
  gl_Position = u_viewProjection * vec4(a_position, 1.0);
  v_normal = a_normal;
}
`;

const FRAGMENT_SHADER = `
precision mediump float;
uniform vec4 u_color;
uniform vec3 u_lightDirection;
uniform bool u_useLighting;
varying vec3 v_normal;
void main() {
  float light = u_useLighting ? max(dot(normalize(v_normal), normalize(u_lightDirection)), 0.0) : 1.0;
  float shade = u_useLighting ? 0.38 + light * 0.62 : 1.0;
  gl_FragColor = vec4(u_color.rgb * shade, u_color.a);
}
`;

function createProgram(gl: WebGLRenderingContext, vertexSource: string, fragmentSource: string): WebGLProgram {
  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  const program = gl.createProgram();
  if (!program) {
    throw new Error("Failed to create WebGL program");
  }
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program) || "Failed to link WebGL program");
  }
  return program;
}

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) {
    throw new Error("Failed to create WebGL shader");
  }
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader) || "Failed to compile WebGL shader");
  }
  return shader;
}

function bufferData(
  gl: WebGLRenderingContext,
  target: number,
  data: Float32Array | Uint16Array | Uint32Array
): WebGLBuffer {
  const buffer = gl.createBuffer();
  if (!buffer) {
    throw new Error("Failed to create WebGL buffer");
  }
  gl.bindBuffer(target, buffer);
  gl.bufferData(target, data as unknown as BufferSource, gl.STATIC_DRAW);
  return buffer;
}

function bindAttribute(
  gl: WebGLRenderingContext,
  location: number,
  buffer: WebGLBuffer,
  size: number
): void {
  if (location < 0) {
    return;
  }
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.enableVertexAttribArray(location);
  gl.vertexAttribPointer(location, size, gl.FLOAT, false, 0, 0);
}

function numericArray(value: unknown): number[] {
  return Array.isArray(value) ? value.map(Number).filter(Number.isFinite) : [];
}

function edgeArray(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  if (typeof value[0] === "number") {
    return numericArray(value);
  }
  return value.flatMap((point) => numericArray(point).slice(0, 3));
}

function indexArray(values: number[]): Uint32Array | Uint16Array {
  const max = maxArray(values);
  return max > 65535 ? new Uint32Array(values) : new Uint16Array(values);
}

function maxArray(values: number[]): number {
  let max = 0;
  for (const value of values) {
    if (value > max) {
      max = value;
    }
  }
  return max;
}

function generatedNormals(vertices: number[], indices: number[]): Float32Array {
  const normals = new Float32Array(vertices.length);
  for (let index = 0; index + 2 < indices.length; index += 3) {
    const ia = indices[index] * 3;
    const ib = indices[index + 1] * 3;
    const ic = indices[index + 2] * 3;
    const a: Vec3 = [vertices[ia], vertices[ia + 1], vertices[ia + 2]];
    const b: Vec3 = [vertices[ib], vertices[ib + 1], vertices[ib + 2]];
    const c: Vec3 = [vertices[ic], vertices[ic + 1], vertices[ic + 2]];
    const normal = normalize(cross(subtract(b, a), subtract(c, a)));
    for (const offset of [ia, ib, ic]) {
      normals[offset] += normal[0];
      normals[offset + 1] += normal[1];
      normals[offset + 2] += normal[2];
    }
  }
  for (let index = 0; index + 2 < normals.length; index += 3) {
    const normal = normalize([normals[index], normals[index + 1], normals[index + 2]]);
    normals[index] = normal[0];
    normals[index + 1] = normal[1];
    normals[index + 2] = normal[2];
  }
  return normals;
}

function emptyBounds(): Bounds {
  return {
    min: [Infinity, Infinity, Infinity],
    max: [-Infinity, -Infinity, -Infinity],
    valid: false
  };
}

function extendBounds(bounds: Bounds, vertices: number[]): void {
  for (let index = 0; index + 2 < vertices.length; index += 3) {
    bounds.valid = true;
    for (let axis = 0; axis < 3; axis += 1) {
      bounds.min[axis] = Math.min(bounds.min[axis], vertices[index + axis]);
      bounds.max[axis] = Math.max(bounds.max[axis], vertices[index + axis]);
    }
  }
}

function resizeCanvas(canvas: HTMLCanvasElement): void {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.floor(canvas.clientWidth * ratio));
  const height = Math.max(1, Math.floor(canvas.clientHeight * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function perspective(fovy: number, aspect: number, near: number, far: number): Mat4 {
  const f = 1 / Math.tan(fovy / 2);
  const nf = 1 / (near - far);
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) * nf, -1,
    0, 0, 2 * far * near * nf, 0
  ]);
}

function lookAt(eye: Vec3, center: Vec3, up: Vec3): Mat4 {
  const z = normalize(subtract(eye, center));
  const x = normalize(cross(up, z));
  const y = cross(z, x);
  return new Float32Array([
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -dot(x, eye), -dot(y, eye), -dot(z, eye), 1
  ]);
}

function multiply(a: Mat4, b: Mat4): Mat4 {
  const out = new Float32Array(16);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      out[column * 4 + row] =
        a[0 * 4 + row] * b[column * 4 + 0] +
        a[1 * 4 + row] * b[column * 4 + 1] +
        a[2 * 4 + row] * b[column * 4 + 2] +
        a[3 * 4 + row] * b[column * 4 + 3];
    }
  }
  return out;
}

function point(value: unknown[]): Vec3 {
  return [
    Number(value[0] ?? 0),
    Number(value[1] ?? 0),
    Number(value[2] ?? 0)
  ];
}

function subtract(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0]
  ];
}

function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function normalize(value: Vec3): Vec3 {
  const length = Math.hypot(value[0], value[1], value[2]);
  if (!length) {
    return [0, 0, 1];
  }
  return [value[0] / length, value[1] / length, value[2] / length];
}

function distance3(a: Vec3, b: Vec3): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
