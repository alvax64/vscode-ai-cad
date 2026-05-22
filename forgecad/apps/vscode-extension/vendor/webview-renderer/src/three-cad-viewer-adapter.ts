import type {
  ForgeCADRendererAdapter,
  ForgeCADRendererCapture,
  ForgeCADRenderRequest,
  ForgeCADViewState
} from "./forgecad-renderer-client";

type JsonObject = Record<string, unknown>;
type Vec3 = [number, number, number];
type Quat = [number, number, number, number];
type VisibilityState = [number, number];

type ThreeCadViewerModule = {
  Display: new (container: HTMLElement, options: JsonObject) => ThreeCadDisplay;
  Viewer: new (
    display: ThreeCadDisplay,
    options: JsonObject,
    notifyCallback: (change: JsonObject) => void,
    pinAsPngCallback?: unknown
  ) => ThreeCadViewer;
  Timer?: new (name: string, timeit?: boolean | number) => {
    split(name: string): void;
    stop(): void;
  };
};

type ThreeCadDisplay = {
  viewer?: ThreeCadViewer;
  setTool?(name: string, flag: boolean): void;
  dispose?(): void;
};

type ThreeCadViewer = {
  camera?: { camera_distance?: number; up?: string; updateProjectionMatrix?(): void };
  controls?: { getTarget(): { toArray(): Vec3 } };
  display: ThreeCadDisplay;
  treeview?: { getStates(): Record<string, VisibilityState>; handleStateChange?: (...args: unknown[]) => void } | null;
  state?: { get(key: string): unknown };
  clear(): void;
  render(meshData: JsonObject, renderOptions: JsonObject, viewerOptions: JsonObject): void;
  update(updateMarker?: boolean, notify?: boolean): void;
  resize?(): void;
  resizeCadView?(cadWidth: number, treeWidth: number, height: number, glass: boolean): void;
  glassMode?(flag: boolean): void;
  showTools?(flag: boolean): void;
  setAxes?(flag: boolean): void;
  setAxes0?(flag: boolean): void;
  setGrids?(grids: [boolean, boolean, boolean]): void;
  setGridCenter?(flag: boolean): void;
  setOrtho?(flag: boolean): void;
  setTransparent?(flag: boolean): void;
  setBlackEdges?(flag: boolean): void;
  setCameraZoom?(zoom: number): void;
  setCameraPosition?(position: Vec3): void;
  setCameraQuaternion?(quaternion: Quat): void;
  setCameraTarget?(target: Vec3): void;
  setEdgeColor?(color: unknown): void;
  setOpacity?(opacity: number): void;
  setAmbientLight?(value: number): void;
  setDirectLight?(value: number): void;
  setMetalness?(value: number): void;
  setRoughness?(value: number): void;
  setZoomSpeed?(value: number): void;
  setPanSpeed?(value: number): void;
  setRotateSpeed?(value: number): void;
  collapseNodes?(value: unknown): void;
  setView?(view: string): void;
  presetCamera?(view: string, zoom?: number | null): void;
  setExplode?(flag: boolean): void;
  setState?(id: string, state: VisibilityState): void;
  setStates?(states: Record<string, VisibilityState>): void;
  setActiveTab?(tab: string): void;
  setClipIntersection?(flag: boolean): void;
  setClipSlider?(index: number, value: number): void;
  getClipSlider?(index: number): number;
  setClipNormal?(index: number, normal: Vec3, slider?: number): void;
  setClipPlaneHelpers?(flag: boolean): void;
  setClipObjectColorCaps?(flag: boolean): void;
  getClipPlaneHelpers?(): boolean;
  getObjectColorCaps?(): boolean;
  getClipIntersection?(): boolean;
  setZebraCount?(value: number): void;
  setZebraOpacity?(value: number): void;
  setZebraDirection?(value: number): void;
  setZebraColorScheme?(value: string): void;
  setZebraMappingMode?(value: string): void;
  getZebraCount?(): number;
  getZebraOpacity?(): number;
  getZebraDirection?(): number;
  getZebraColorScheme?(): string;
  getZebraMappingMode?(): string;
  setStudioEnvironment?(value: string): void;
  setStudioEnvIntensity?(value: number): void;
  setStudioEnvRotation?(value: number): void;
  setStudioBackground?(value: string): void;
  setStudioToneMapping?(value: string): void;
  setStudioExposure?(value: number): void;
  setStudioShadowIntensity?(value: number): void;
  setStudioShadowSoftness?(value: number): void;
  setStudioAOIntensity?(value: number): void;
  setStudioTextureMapping?(value: string): void;
  setStudio4kEnvMaps?(value: boolean): void;
  getCameraPosition?(): Vec3;
  getCameraQuaternion?(): Quat;
  getCameraZoom?(): number;
  getCameraTarget?(): Vec3;
  getStates?(): Record<string, VisibilityState>;
  getImage?(filename: string): Promise<{ task: string; dataUrl: string | ArrayBuffer | null }>;
  handleBackendResponse?(data: JsonObject): void;
  setRelativeTime?(value: number): void;
  getRelativeTime?(): number;
  addPositionTrack?(selector: string, times: number[], values: number[][]): void;
  addTranslationTrack?(selector: string, axis: string, times: number[], values: number[]): void;
  addQuaternionTrack?(selector: string, times: number[], values: number[][]): void;
  addRotationTrack?(selector: string, axis: string, times: number[], values: number[]): void;
  initAnimation?(duration: number, speed: number): void;
  gridHelper?: { clearCache?(): void; update?(zoom: number, notify?: boolean): void };
};

export type ThreeCadViewerAdapterOptions = {
  mount?: HTMLElement | null;
  moduleUrl: string;
  logger?: Pick<Console, "error" | "log">;
};

const MIN_WIDTH = 450;
const VIEWER_WIDTH_CHROME = 2;
const TREE_WIDTH_CHROME = 4;
const VIEWER_BODY_HEIGHT_CHROME = 4;
const TOOLBAR_FALLBACK_HEIGHT = 30;

const DISPLAY_DEFAULTS = {
  cadWidth: 730,
  height: 525,
  treeWidth: 240,
  glass: true,
  theme: "browser",
  tools: true,
  pinning: false,
  keymap: {
    shift: "shiftKey",
    ctrl: "ctrlKey",
    meta: "metaKey",
    alt: "altKey"
  },
  newTreeBehavior: true,
  measurementDebug: false,
  measureTools: true,
  selectTool: true,
  explodeTool: true,
  zscaleTool: false,
  zebraTool: true,
  studioTool: true
};

const VIEWER_DEFAULTS = {
  timeit: false,
  tools: true,
  glass: true,
  up: "Z",
  zoom: 1.0,
  position: null,
  quaternion: null,
  target: null,
  control: "trackball",
  centerGrid: false,
  gridFontSize: 12,
  newTreeBehavior: true,
  studioEnvironment: "studio",
  studioEnvIntensity: 1.0,
  studioEnvRotation: 0,
  studioBackground: "environment",
  studioToneMapping: "neutral",
  studioExposure: 1.0,
  studioShadowIntensity: 0.5,
  studioShadowSoftness: 0.2,
  studioAOIntensity: 0.5,
  studioTextureMapping: "parametric",
  studio4kEnvMaps: false
};

const RENDER_DEFAULTS = {
  ambientIntensity: 1.0,
  directIntensity: 1.1,
  metalness: 0.3,
  roughness: 0.65,
  edgeColor: 0x707070,
  defaultOpacity: 0.5,
  normalLen: 0,
  angularTolerance: 0.2,
  deviation: 0.1,
  defaultColor: "#e8b024"
};

const VIEW_NAMES = new Set(["iso", "left", "right", "top", "bottom", "rear", "front"]);

export class ThreeCadViewerAdapter implements ForgeCADRendererAdapter {
  readonly mount: HTMLElement;
  readonly moduleUrl: string;
  readonly logger: Pick<Console, "error" | "log">;
  private readonly resizeObserver?: ResizeObserver;
  private modulePromise: Promise<ThreeCadViewerModule> | null = null;
  private display: ThreeCadDisplay | null = null;
  private viewer: ThreeCadViewer | null = null;
  private hasRenderedRevision = false;
  private meshData: JsonObject | null = null;
  private shapes: JsonObject | null = null;
  private config: JsonObject = {};
  private oldStates: Record<string, VisibilityState> | null = null;
  private message: JsonObject = {};
  private lastBbRadius: number | null = null;
  private zoom: number | null = null;
  private position: Vec3 | null = null;
  private quaternion: Quat | null = null;
  private target: Vec3 | null = null;
  private cameraDistance: number | null = null;
  private clipping = {
    planeHelpers: null as boolean | null,
    objectColors: null as boolean | null,
    intersection: null as boolean | null
  };
  private zebra = {
    count: null as number | null,
    opacity: null as number | null,
    direction: null as number | null,
    colorScheme: null as string | null,
    mappingMode: null as string | null
  };
  private relativeTime: number | null = null;
  private onStateChanged?: (viewState: Partial<ForgeCADViewState>) => void;

  constructor(options: ThreeCadViewerAdapterOptions) {
    if (!options.moduleUrl) {
      throw new Error("ThreeCadViewerAdapter requires moduleUrl");
    }
    this.mount = options.mount || document.body;
    this.moduleUrl = options.moduleUrl;
    this.logger = options.logger || console;
    window.addEventListener("resize", () => this.resize());
    if (typeof ResizeObserver !== "undefined") {
      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.mount);
    }
    this.installThemeObserver();
  }

  async renderRevision(renderRequest: ForgeCADRenderRequest): Promise<void> {
    const config = { ...(renderRequest.tessellatedScene.config as JsonObject | undefined), ...renderRequest.config };
    await this.showViewer(renderRequest.tessellatedScene as JsonObject, config);
  }

  async renderEmpty(): Promise<void> {
    this.mount.replaceChildren(emptyState("No active ForgeCAD model"));
    this.display = null;
    this.viewer = null;
    this.hasRenderedRevision = false;
    this.meshData = null;
    this.shapes = null;
  }

  async captureView(config: JsonObject = {}): Promise<ForgeCADRendererCapture> {
    const viewer = this.requireRenderedViewer();
    const filename = typeof config.filename === "string" ? config.filename : `forgecad-capture-${Date.now()}.png`;
    const result = await viewer.getImage?.(filename);
    if (result?.dataUrl) {
      return {
        dataUrl: typeof result.dataUrl === "string" ? result.dataUrl : "",
        mimeType: "image/png"
      };
    }
    const canvas = this.mount.querySelector("canvas");
    return {
      dataUrl: canvas instanceof HTMLCanvasElement ? canvas.toDataURL("image/png") : "",
      mimeType: "image/png",
      width: canvas instanceof HTMLCanvasElement ? canvas.width : undefined,
      height: canvas instanceof HTMLCanvasElement ? canvas.height : undefined
    };
  }

  async captureOverview(): Promise<ForgeCADRendererCapture> {
    return this.captureView();
  }

  async setCamera(camera: JsonObject = {}): Promise<void> {
    const config: JsonObject = {};
    if (isVec3(camera.position)) {
      config.position = camera.position;
    }
    if (isQuat(camera.quaternion)) {
      config.quaternion = camera.quaternion;
    }
    if (isVec3(camera.target)) {
      config.target = camera.target;
    }
    if (typeof camera.zoom === "number") {
      config.zoom = camera.zoom;
    }
    if (typeof camera.view === "string") {
      config.reset_camera = camera.view;
    }
    this.applyUiConfig(config);
  }

  async setVisibility(visibleNodeStates: JsonObject = {}): Promise<void> {
    this.applyUiConfig({ states: visibleNodeStates });
  }

  async setClipping(clipping: JsonObject = {}): Promise<void> {
    this.applyUiConfig(clipping);
  }

  async getViewState(): Promise<Partial<ForgeCADViewState>> {
    return this.readViewState();
  }

  onViewStateChanged(callback: (viewState: Partial<ForgeCADViewState>) => void): void {
    this.onStateChanged = callback;
  }

  async showViewer(meshData: JsonObject, config: JsonObject = {}): Promise<void> {
    const { Display, Viewer } = await this.loadModule();
    this.meshData = viewerMeshData(meshData);
    this.shapes = asJsonObject(this.meshData.shapes) || this.meshData;
    this.config = normalizeConfig(config);
    const displayOptions = this.getDisplayOptions(this.config.theme as string | undefined);

    if (!this.display) {
      this.mount.replaceChildren();
      this.display = new Display(this.mount, displayOptions);
    }
    const previousStates = this.readTreeStates();
    if (this.viewer) {
      this.viewer.clear();
      this.hasRenderedRevision = false;
    } else {
      this.viewer = new Viewer(this.display, displayOptions, (change) => this.notifyChange(change), null);
    }
    this.render(previousStates);
    this.viewer.glassMode?.(Boolean(displayOptions.glass));
    this.viewer.showTools?.(Boolean(displayOptions.tools));
  }

  private render(previousStates: Record<string, VisibilityState> = {}): void {
    const viewer = this.requireViewer();
    const meshData = this.meshData || {};
    const shapes = this.shapes || {};
    const config = this.config || {};
    const renderOptions = this.renderOptions(config);
    const viewerOptions = this.viewerOptions(config);
    const resetCamera = String(preset(config, "reset_camera", "keep")).toLowerCase();
    const bb = asJsonObject(shapes.bb);
    const center = bboxCenter(bb);
    const bbRadius = bboxRadius(bb, center);
    const useStoredState = resetCamera === "keep" || resetCamera === "center";
    const newZoom = config.zoom !== undefined;

    if (!useStoredState) {
      viewerOptions.zoom = typeof config.zoom === "number" ? config.zoom : 1.0;
      copyIfDefined(viewerOptions, config, "position");
      copyIfDefined(viewerOptions, config, "quaternion");
      copyIfDefined(viewerOptions, config, "target");
      this.cameraDistance = null;
    } else {
      this.applyStoredCamera(viewerOptions, config, resetCamera, center, bbRadius);
    }

    this.applyPersistentClipAndZebra(viewerOptions, config);
    if (typeof config.tab === "string") {
      viewerOptions.tab = config.tab;
    }

    viewer.render(meshData, renderOptions, viewerOptions);
    this.hasRenderedRevision = true;
    this.restoreTreeStates(previousStates, meshData, config);
    this.resizeIfNeeded(config);
    this.applyPostRenderCamera(resetCamera, newZoom);
    this.captureViewerState();

    if (config.explode === true) {
      viewer.setExplode?.(true);
    }
    if (typeof config.analysis_tool === "string") {
      this.activateAnalysisTool(config.analysis_tool);
    }
    this.lastBbRadius = bbRadius;
  }

  private renderOptions(config: JsonObject): JsonObject {
    return {
      ambientIntensity: preset(config, "ambient_intensity", RENDER_DEFAULTS.ambientIntensity),
      directIntensity: preset(config, "direct_intensity", RENDER_DEFAULTS.directIntensity),
      metalness: preset(config, "metalness", RENDER_DEFAULTS.metalness),
      roughness: preset(config, "roughness", RENDER_DEFAULTS.roughness),
      edgeColor: preset(config, "default_edgecolor", RENDER_DEFAULTS.edgeColor),
      defaultOpacity: preset(config, "default_opacity", RENDER_DEFAULTS.defaultOpacity),
      normalLen: preset(config, "normal_len", RENDER_DEFAULTS.normalLen),
      angularTolerance: preset(config, "angular_tolerance", RENDER_DEFAULTS.angularTolerance),
      deviation: preset(config, "deviation", RENDER_DEFAULTS.deviation),
      defaultColor: preset(config, "default_color", RENDER_DEFAULTS.defaultColor)
    };
  }

  private viewerOptions(config: JsonObject): JsonObject {
    return {
      axes: preset(config, "axes", false),
      axes0: preset(config, "axes0", true),
      blackEdges: preset(config, "black_edges", false),
      grid: normalizeGrid(preset(config, "grid", [false, false, false])),
      collapse: preset(config, "collapse", 1),
      ortho: preset(config, "ortho", true),
      ticks: preset(config, "ticks", 5),
      centerGrid: preset(config, "center_grid", VIEWER_DEFAULTS.centerGrid),
      gridFontSize: preset(config, "grid_font_size", VIEWER_DEFAULTS.gridFontSize),
      timeit: preset(config, "timeit", VIEWER_DEFAULTS.timeit),
      tools: preset(config, "tools", VIEWER_DEFAULTS.tools),
      glass: preset(config, "glass", VIEWER_DEFAULTS.glass),
      up: preset(config, "up", VIEWER_DEFAULTS.up),
      transparent: preset(config, "transparent", false),
      control: preset(config, "control", VIEWER_DEFAULTS.control),
      panSpeed: preset(config, "pan_speed", 1),
      zoomSpeed: preset(config, "zoom_speed", 1),
      rotateSpeed: preset(config, "rotate_speed", 1),
      clipSlider0: config.clip_slider_0,
      clipSlider1: config.clip_slider_1,
      clipSlider2: config.clip_slider_2,
      clipNormal0: config.clip_normal_0,
      clipNormal1: config.clip_normal_1,
      clipNormal2: config.clip_normal_2,
      studioEnvironment: preset(config, "studio_environment", VIEWER_DEFAULTS.studioEnvironment),
      studioEnvIntensity: preset(config, "studio_env_intensity", VIEWER_DEFAULTS.studioEnvIntensity),
      studioEnvRotation: preset(config, "studio_env_rotation", VIEWER_DEFAULTS.studioEnvRotation),
      studioBackground: preset(config, "studio_background", VIEWER_DEFAULTS.studioBackground),
      studioToneMapping: preset(config, "studio_tone_mapping", VIEWER_DEFAULTS.studioToneMapping),
      studioExposure: preset(config, "studio_exposure", VIEWER_DEFAULTS.studioExposure),
      studioShadowIntensity: preset(config, "studio_shadow_intensity", VIEWER_DEFAULTS.studioShadowIntensity),
      studioShadowSoftness: preset(config, "studio_shadow_softness", VIEWER_DEFAULTS.studioShadowSoftness),
      studioAOIntensity: preset(config, "studio_ao_intensity", VIEWER_DEFAULTS.studioAOIntensity),
      studioTextureMapping: preset(config, "studio_texture_mapping", VIEWER_DEFAULTS.studioTextureMapping),
      studio4kEnvMaps: preset(config, "studio_4k_env_maps", VIEWER_DEFAULTS.studio4kEnvMaps)
    };
  }

  private getDisplayOptions(theme?: string): JsonObject {
    const glass = Boolean(preset(this.config, "glass", DISPLAY_DEFAULTS.glass));
    const tools = Boolean(preset(this.config, "tools", DISPLAY_DEFAULTS.tools));
    const treeWidth = Number(preset(this.config, "tree_width", DISPLAY_DEFAULTS.treeWidth));
    const { width, height } = this.measureAvailableSize();
    const widthChrome = tools && !glass ? treeWidth + TREE_WIDTH_CHROME : VIEWER_WIDTH_CHROME;
    const heightChrome = this.measureToolbarHeight(tools) + VIEWER_BODY_HEIGHT_CHROME;
    return {
      glass,
      treeWidth,
      cadWidth: Math.max(MIN_WIDTH - (glass || !tools ? 0 : treeWidth), width - widthChrome),
      height: Math.max(120, height - heightChrome),
      theme: theme || DISPLAY_DEFAULTS.theme,
      tools,
      keymap: preset(this.config, "modifier_keys", DISPLAY_DEFAULTS.keymap),
      newTreeBehavior: preset(this.config, "new_tree_behavior", DISPLAY_DEFAULTS.newTreeBehavior),
      measureTools: DISPLAY_DEFAULTS.measureTools,
      measurementDebug: DISPLAY_DEFAULTS.measurementDebug,
      selectTool: DISPLAY_DEFAULTS.selectTool,
      explodeTool: DISPLAY_DEFAULTS.explodeTool,
      zscaleTool: DISPLAY_DEFAULTS.zscaleTool,
      zebraTool: DISPLAY_DEFAULTS.zebraTool,
      studioTool: DISPLAY_DEFAULTS.studioTool,
      pinning: DISPLAY_DEFAULTS.pinning
    };
  }

  private measureAvailableSize(): { width: number; height: number } {
    const rect = this.mount.getBoundingClientRect();
    return {
      width: Math.max(1, Math.floor(rect.width || this.mount.clientWidth || window.innerWidth || DISPLAY_DEFAULTS.cadWidth)),
      height: Math.max(1, Math.floor(rect.height || this.mount.clientHeight || window.innerHeight || DISPLAY_DEFAULTS.height))
    };
  }

  private measureToolbarHeight(tools: boolean): number {
    if (!tools) {
      return 0;
    }
    const toolbar = this.mount.querySelector(".tcv_cad_toolbar");
    if (toolbar instanceof HTMLElement) {
      return Math.ceil(toolbar.getBoundingClientRect().height || toolbar.offsetHeight || TOOLBAR_FALLBACK_HEIGHT);
    }
    return TOOLBAR_FALLBACK_HEIGHT;
  }

  private applyStoredCamera(
    viewerOptions: JsonObject,
    config: JsonObject,
    resetCamera: string,
    center: Vec3,
    bbRadius: number
  ): void {
    if (isVec3(config.position)) {
      viewerOptions.position = config.position;
    } else if (this.position && this.target) {
      if (resetCamera === "keep") {
        const cameraDistance = 2.5 * bbRadius;
        const direction = normalize([
          this.position[0] - this.target[0],
          this.position[1] - this.target[1],
          this.position[2] - this.target[2]
        ]);
        viewerOptions.position = [
          direction[0] * cameraDistance + this.target[0],
          direction[1] * cameraDistance + this.target[1],
          direction[2] * cameraDistance + this.target[2]
        ];
      } else if (resetCamera === "center") {
        viewerOptions.position = [
          this.position[0] - this.target[0] + center[0],
          this.position[1] - this.target[1] + center[1],
          this.position[2] - this.target[2] + center[2]
        ];
        this.target = center;
      }
    }
    this.position = asVec3(viewerOptions.position) || this.position;

    viewerOptions.quaternion = asQuat(config.quaternion) || this.quaternion || undefined;
    this.quaternion = asQuat(viewerOptions.quaternion) || this.quaternion;
    viewerOptions.target = asVec3(config.target) || this.target || undefined;
    this.target = asVec3(viewerOptions.target) || this.target;
    viewerOptions.zoom = typeof config.zoom === "number" ? config.zoom : this.zoom || undefined;
    this.zoom = typeof viewerOptions.zoom === "number" ? viewerOptions.zoom : this.zoom;
  }

  private applyPersistentClipAndZebra(viewerOptions: JsonObject, config: JsonObject): void {
    setPersistent(viewerOptions, config, "clip_intersection", "clipIntersection", this.clipping.intersection);
    setPersistent(viewerOptions, config, "clip_planes", "clipPlaneHelpers", this.clipping.planeHelpers);
    setPersistent(viewerOptions, config, "clip_object_colors", "clipObjectColors", this.clipping.objectColors);
    setPersistent(viewerOptions, config, "zebra_count", "zebraCount", this.zebra.count);
    setPersistent(viewerOptions, config, "zebra_opacity", "zebraOpacity", this.zebra.opacity);
    setPersistent(viewerOptions, config, "zebra_direction", "zebraDirection", this.zebra.direction);
    setPersistent(viewerOptions, config, "zebra_color_scheme", "zebraColorScheme", this.zebra.colorScheme);
    setPersistent(viewerOptions, config, "zebra_mapping_mode", "zebraMappingMode", this.zebra.mappingMode);
  }

  private restoreTreeStates(
    previousStates: Record<string, VisibilityState>,
    meshData: JsonObject,
    config: JsonObject
  ): void {
    const viewer = this.requireViewer();
    const newStates = treeStatesFromMeshData(meshData);
    if (asJsonObject(config.states)) {
      this.applyStates(config.states as Record<string, VisibilityState>);
      return;
    }
    for (const [key, state] of Object.entries(previousStates)) {
      if (key in newStates && (state[0] !== newStates[key][0] || state[1] !== newStates[key][1])) {
        viewer.setState?.(key, state);
      }
    }
  }

  private applyPostRenderCamera(resetCamera: string, newZoom: boolean): void {
    const viewer = this.requireViewer();
    if (!newZoom && resetCamera === "keep" && this.cameraDistance != null) {
      const currentDistance = viewer.camera?.camera_distance;
      if (typeof currentDistance === "number" && typeof this.zoom === "number") {
        viewer.setCameraZoom?.((this.zoom * currentDistance) / this.cameraDistance);
      }
    }
    if (VIEW_NAMES.has(resetCamera)) {
      viewer.setView?.(resetCamera);
      viewer.presetCamera?.(resetCamera);
    }
  }

  private captureViewerState(): void {
    const viewer = this.requireViewer();
    this.position = viewer.getCameraPosition?.() || this.position;
    this.quaternion = viewer.getCameraQuaternion?.() || this.quaternion;
    this.target = viewer.getCameraTarget?.() || viewer.controls?.getTarget().toArray() || this.target;
    this.zoom = viewer.getCameraZoom?.() ?? this.zoom;
    this.cameraDistance = viewer.camera?.camera_distance ?? this.cameraDistance;
    this.clipping = {
      planeHelpers: viewer.getClipPlaneHelpers?.() ?? this.clipping.planeHelpers,
      objectColors: viewer.getObjectColorCaps?.() ?? this.clipping.objectColors,
      intersection: viewer.getClipIntersection?.() ?? this.clipping.intersection
    };
    this.zebra = {
      count: viewer.getZebraCount?.() ?? this.zebra.count,
      opacity: viewer.getZebraOpacity?.() ?? this.zebra.opacity,
      direction: viewer.getZebraDirection?.() ?? this.zebra.direction,
      colorScheme: viewer.getZebraColorScheme?.() ?? this.zebra.colorScheme,
      mappingMode: viewer.getZebraMappingMode?.() ?? this.zebra.mappingMode
    };
    this.relativeTime = viewer.getRelativeTime?.() ?? this.relativeTime;
    this.message = {
      ...this.message,
      position: this.position,
      quaternion: this.quaternion,
      target: this.target,
      zoom: this.zoom,
      states: this.readTreeStates(),
      clip_intersection: this.clipping.intersection,
      clip_planes: this.clipping.planeHelpers,
      clip_object_colors: this.clipping.objectColors,
      zebra_count: this.zebra.count,
      zebra_opacity: this.zebra.opacity,
      zebra_direction: this.zebra.direction,
      zebra_color_scheme: this.zebra.colorScheme,
      zebra_mapping_mode: this.zebra.mappingMode,
      relative_time: this.relativeTime
    };
    this.onStateChanged?.(this.readViewState());
  }

  private notifyChange(change: JsonObject): void {
    let changed = false;
    for (const [key, entry] of Object.entries(change)) {
      const next = asJsonObject(entry)?.new;
      if (next !== undefined) {
        this.message[key] = next;
        changed = true;
      }
    }
    const states = this.readTreeStates();
    const statesJson = JSON.stringify(states);
    if (!this.oldStates || JSON.stringify(this.oldStates) !== statesJson) {
      this.message.states = states;
      this.oldStates = JSON.parse(statesJson) as Record<string, VisibilityState>;
      changed = true;
    }
    if (changed) {
      this.captureChangeCache(change);
      this.onStateChanged?.(this.readViewState());
    }
  }

  private captureChangeCache(change: JsonObject): void {
    this.zoom = changedNumber(change, "zoom", this.zoom);
    this.position = changedVec3(change, "position", this.position);
    this.quaternion = changedQuat(change, "quaternion", this.quaternion);
    this.target = changedVec3(change, "target", this.target);
    this.clipping.intersection = changedBoolean(change, "clip_intersection", this.clipping.intersection);
    this.clipping.planeHelpers = changedBoolean(change, "clip_planes", this.clipping.planeHelpers);
    this.clipping.objectColors = changedBoolean(change, "clip_object_colors", this.clipping.objectColors);
    this.zebra.count = changedNumber(change, "zebra_count", this.zebra.count);
    this.zebra.opacity = changedNumber(change, "zebra_opacity", this.zebra.opacity);
    this.zebra.direction = changedNumber(change, "zebra_direction", this.zebra.direction);
    this.zebra.colorScheme = changedString(change, "zebra_color_scheme", this.zebra.colorScheme);
    this.zebra.mappingMode = changedString(change, "zebra_mapping_mode", this.zebra.mappingMode);
    this.relativeTime = changedNumber(change, "relative_time", this.relativeTime);
  }

  private applyUiConfig(config: JsonObject): void {
    const viewer = this.viewer;
    if (!viewer) {
      return;
    }
    const normalized = normalizeConfig(config);
    for (const [key, value] of Object.entries(normalized)) {
      if (value === undefined) {
        continue;
      }
      if (key === "axes" && typeof value === "boolean") viewer.setAxes?.(value);
      else if (key === "axes0" && typeof value === "boolean") viewer.setAxes0?.(value);
      else if (key === "grid") viewer.setGrids?.(normalizeGrid(value));
      else if (key === "center_grid" && typeof value === "boolean") viewer.setGridCenter?.(value);
      else if (key === "ortho" && typeof value === "boolean") viewer.setOrtho?.(value);
      else if (key === "transparent" && typeof value === "boolean") viewer.setTransparent?.(value);
      else if (key === "black_edges" && typeof value === "boolean") viewer.setBlackEdges?.(value);
      else if (key === "zoom" && typeof value === "number") viewer.setCameraZoom?.(value);
      else if (key === "position" && isVec3(value)) viewer.setCameraPosition?.(value);
      else if (key === "quaternion" && isQuat(value)) viewer.setCameraQuaternion?.(value);
      else if (key === "target" && isVec3(value)) viewer.setCameraTarget?.(value);
      else if (key === "up" && typeof value === "string" && viewer.camera) {
        viewer.camera.up = value;
        viewer.camera.updateProjectionMatrix?.();
      } else if (key === "default_edgecolor") viewer.setEdgeColor?.(value);
      else if (key === "default_opacity" && typeof value === "number") viewer.setOpacity?.(value);
      else if (key === "ambient_intensity" && typeof value === "number") viewer.setAmbientLight?.(value);
      else if (key === "direct_intensity" && typeof value === "number") viewer.setDirectLight?.(value);
      else if (key === "metalness" && typeof value === "number") viewer.setMetalness?.(value);
      else if (key === "roughness" && typeof value === "number") viewer.setRoughness?.(value);
      else if (key === "zoom_speed" && typeof value === "number") viewer.setZoomSpeed?.(value);
      else if (key === "pan_speed" && typeof value === "number") viewer.setPanSpeed?.(value);
      else if (key === "rotate_speed" && typeof value === "number") viewer.setRotateSpeed?.(value);
      else if (key === "glass" && typeof value === "boolean") viewer.glassMode?.(value);
      else if (key === "tools" && typeof value === "boolean") viewer.showTools?.(value);
      else if (key === "collapse") viewer.collapseNodes?.(value);
      else if (key === "tree_width" && typeof value === "number") this.resize(Number(value));
      else if (key === "reset_camera" && typeof value === "string") this.applyResetCamera(value);
      else if (key === "explode" && typeof value === "boolean") viewer.setExplode?.(value);
      else if (key === "analysis_tool" && typeof value === "string") this.activateAnalysisTool(value);
      else if (key === "states" && asJsonObject(value)) this.applyStates(value as Record<string, VisibilityState>);
      else if (key === "tab" && typeof value === "string") viewer.setActiveTab?.(value);
      else if (key === "clip_intersection" && typeof value === "boolean") viewer.setClipIntersection?.(value);
      else if (key.startsWith("clip_slider") && typeof value === "number") viewer.setClipSlider?.(Number(key.slice(-1)), value);
      else if (key.startsWith("clip_normal") && isVec3(value)) {
        const index = Number(key.slice(-1));
        viewer.setClipNormal?.(index, value, viewer.getClipSlider?.(index));
      } else if (key === "clip_planes" && typeof value === "boolean") viewer.setClipPlaneHelpers?.(value);
      else if (key === "clip_object_colors" && typeof value === "boolean") viewer.setClipObjectColorCaps?.(value);
      else if (key === "zebra_count" && typeof value === "number") viewer.setZebraCount?.(value);
      else if (key === "zebra_opacity" && typeof value === "number") viewer.setZebraOpacity?.(value);
      else if (key === "zebra_direction" && typeof value === "number") viewer.setZebraDirection?.(value);
      else if (key === "zebra_color_scheme" && typeof value === "string") viewer.setZebraColorScheme?.(value);
      else if (key === "zebra_mapping_mode" && typeof value === "string") viewer.setZebraMappingMode?.(value);
      else if (key === "studio_environment" && typeof value === "string") viewer.setStudioEnvironment?.(value);
      else if (key === "studio_env_intensity" && typeof value === "number") viewer.setStudioEnvIntensity?.(value);
      else if (key === "studio_env_rotation" && typeof value === "number") viewer.setStudioEnvRotation?.(value);
      else if (key === "studio_background" && typeof value === "string") viewer.setStudioBackground?.(value);
      else if (key === "studio_tone_mapping" && typeof value === "string") viewer.setStudioToneMapping?.(value);
      else if (key === "studio_exposure" && typeof value === "number") viewer.setStudioExposure?.(value);
      else if (key === "studio_shadow_intensity" && typeof value === "number") viewer.setStudioShadowIntensity?.(value);
      else if (key === "studio_shadow_softness" && typeof value === "number") viewer.setStudioShadowSoftness?.(value);
      else if (key === "studio_ao_intensity" && typeof value === "number") viewer.setStudioAOIntensity?.(value);
      else if (key === "studio_texture_mapping" && typeof value === "string") viewer.setStudioTextureMapping?.(value);
      else if (key === "studio_4k_env_maps" && typeof value === "boolean") viewer.setStudio4kEnvMaps?.(value);
      else if (key === "relative_time" && typeof value === "number") viewer.setRelativeTime?.(value);
    }
    this.captureViewerState();
  }

  private applyResetCamera(value: string): void {
    const viewer = this.requireRenderedViewer();
    const reset = value.toLowerCase();
    if (reset === "reset") {
      viewer.setView?.("iso");
      viewer.resize?.();
    } else if (VIEW_NAMES.has(reset)) {
      viewer.setView?.(reset);
      viewer.presetCamera?.(reset);
    } else if (reset === "center") {
      viewer.resize?.();
    }
  }

  private activateAnalysisTool(tool: string): void {
    const active = this.viewer?.state?.get("activeTool");
    if (typeof active === "string" && ["distance", "properties", "select"].includes(active)) {
      this.display?.setTool?.(active, false);
    }
    if (["distance", "properties", "select"].includes(tool)) {
      this.display?.setTool?.(tool, true);
    }
  }

  private applyStates(states: Record<string, VisibilityState>): void {
    const viewer = this.requireRenderedViewer();
    if (viewer.setStates) {
      viewer.setStates(states);
      return;
    }
    for (const [key, value] of Object.entries(states)) {
      if (isVisibilityState(value)) {
        viewer.setState?.(key, value);
      }
    }
  }

  private resize(treeWidth?: number): void {
    const viewer = this.viewer;
    if (!viewer || !this.hasRenderedRevision) {
      return;
    }
    const displayOptions = this.getDisplayOptions(this.config.theme as string | undefined);
    viewer.resizeCadView?.(
      Number(displayOptions.cadWidth),
      treeWidth ?? Number(displayOptions.treeWidth),
      Number(displayOptions.height),
      Boolean(displayOptions.glass)
    );
    viewer.gridHelper?.clearCache?.();
    viewer.gridHelper?.update?.(viewer.getCameraZoom?.() ?? 1, true);
    viewer.update?.(true, true);
  }

  private resizeIfNeeded(config: JsonObject): void {
    if (typeof config.tree_width === "number") {
      this.resize(config.tree_width);
    }
  }

  private readTreeStates(): Record<string, VisibilityState> {
    if (!this.viewer || !this.hasRenderedRevision) {
      return {};
    }
    return this.viewer?.getStates?.() || this.viewer?.treeview?.getStates() || {};
  }

  private readViewState(): Partial<ForgeCADViewState> {
    const states = this.readTreeStates();
    const renderedViewer = this.hasRenderedRevision ? this.viewer : null;
    return {
      camera: {
        position: this.position || renderedViewer?.getCameraPosition?.() || null,
        quaternion: this.quaternion || renderedViewer?.getCameraQuaternion?.() || null,
        target: this.target || renderedViewer?.getCameraTarget?.() || null,
        zoom: this.zoom ?? renderedViewer?.getCameraZoom?.() ?? null
      },
      selected_shape_ids: selectedShapeIds(this.message),
      visible_node_states: states,
      clipping: {
        clip_intersection: this.clipping.intersection,
        clip_planes: this.clipping.planeHelpers,
        clip_object_colors: this.clipping.objectColors
      },
      active_analysis_tool: typeof this.message.activeTool === "string" ? this.message.activeTool : null,
      viewport_size: {
        width: window.innerWidth,
        height: window.innerHeight
      }
    };
  }

  private async loadModule(): Promise<ThreeCadViewerModule> {
    if (!this.modulePromise) {
      this.modulePromise = import(this.moduleUrl) as Promise<ThreeCadViewerModule>;
    }
    return this.modulePromise;
  }

  private requireViewer(): ThreeCadViewer {
    if (!this.viewer) {
      throw new Error("ForgeCAD viewer has not rendered a revision yet.");
    }
    return this.viewer;
  }

  private requireRenderedViewer(): ThreeCadViewer {
    const viewer = this.requireViewer();
    if (!this.hasRenderedRevision) {
      throw new Error("ForgeCAD viewer has not rendered a revision yet.");
    }
    return viewer;
  }

  private installThemeObserver(): void {
    const observer = new MutationObserver(() => {
      const viewer = this.viewer;
      if (!viewer || this.config.theme !== "browser") {
        return;
      }
      const theme = document.body.className === "vscode-light" ? "light" : "dark";
      (viewer as ThreeCadViewer & { setTheme?: (theme: string) => void }).setTheme?.(theme);
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
  }
}

export function createThreeCadViewerAdapter(options: ThreeCadViewerAdapterOptions): ThreeCadViewerAdapter {
  return new ThreeCadViewerAdapter(options);
}

function preset(config: JsonObject, key: string, defaultValue: unknown): unknown {
  return config[key] == null ? defaultValue : config[key];
}

function normalizeConfig(config: JsonObject): JsonObject {
  const result: JsonObject = {};
  for (const [key, value] of Object.entries(config || {})) {
    if (value == null) {
      continue;
    }
    if (key === "reset_camera" && typeof value === "string") {
      result[key] = value.toLowerCase();
    } else if (key === "collapse") {
      result[key] = collapseValue(value);
    } else {
      result[key] = value;
    }
  }
  return result;
}

function collapseValue(value: unknown): unknown {
  if (value === "none" || value === "E") return 2;
  if (value === "leaves" || value === "1") return -1;
  if (value === "all" || value === "C") return 0;
  if (value === "root" || value === "R") return 1;
  return value;
}

function asJsonObject(value: unknown): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : null;
}

function copyIfDefined(target: JsonObject, source: JsonObject, key: string): void {
  if (source[key] !== undefined) {
    target[key] = source[key];
  }
}

function setPersistent(
  target: JsonObject,
  source: JsonObject,
  sourceKey: string,
  targetKey: string,
  lastValue: unknown
): void {
  target[targetKey] = source[sourceKey] !== undefined ? source[sourceKey] : lastValue;
}

function normalizeGrid(value: unknown): [boolean, boolean, boolean] {
  if (Array.isArray(value)) {
    return [Boolean(value[0]), Boolean(value[1]), Boolean(value[2])];
  }
  return [Boolean(value), Boolean(value), Boolean(value)];
}

function bboxCenter(bb: JsonObject | null): Vec3 {
  if (!bb) {
    return [0, 0, 0];
  }
  return [
    (num(bb.xmax) + num(bb.xmin)) / 2,
    (num(bb.ymax) + num(bb.ymin)) / 2,
    (num(bb.zmax) + num(bb.zmin)) / 2
  ];
}

function bboxRadius(bb: JsonObject | null, center: Vec3): number {
  if (!bb) {
    return 1;
  }
  return Math.max(
    Math.sqrt(
      Math.pow(num(bb.xmax) - num(bb.xmin), 2) +
        Math.pow(num(bb.ymax) - num(bb.ymin), 2) +
        Math.pow(num(bb.zmax) - num(bb.zmin), 2)
    ),
    length(center),
    1
  );
}

function num(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function length(v: Vec3): number {
  return Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
}

function normalize(v: Vec3): Vec3 {
  const n = length(v) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}

function treeStatesFromMeshData(meshData: JsonObject): Record<string, VisibilityState> {
  const root = asJsonObject(asJsonObject(meshData.shapes)?.parts ? meshData.shapes : meshData);
  const states: Record<string, VisibilityState> = {};
  walkShapeTree(root, states);
  return states;
}

function viewerMeshData(meshData: JsonObject): JsonObject {
  const instances = Array.isArray(meshData.instances) ? meshData.instances : null;
  const shapes = asJsonObject(meshData.shapes);
  if (!instances || !shapes || instances.every(isEncodedInstance)) {
    return normalizeViewerMeshData(meshData);
  }
  const clonedShapes = cloneJson(shapes);
  resolveRawShapeRefs(clonedShapes, instances);
  return normalizeViewerShapes(clonedShapes);
}

function normalizeViewerMeshData(meshData: JsonObject): JsonObject {
  const cloned = cloneJson(meshData);
  const shapes = asJsonObject(cloned.shapes);
  if (shapes) {
    normalizeViewerShapes(shapes);
  }
  return cloned;
}

function normalizeViewerShapes(shapes: JsonObject): JsonObject {
  if (typeof shapes.id !== "string") {
    shapes.id = "/result";
  }
  if (typeof shapes.name !== "string") {
    shapes.name = "result";
  }
  if (!Array.isArray(shapes.parts)) {
    shapes.parts = [];
  }
  return shapes;
}

function isEncodedInstance(value: unknown): boolean {
  const instance = asJsonObject(value);
  return Boolean(instance && isEncodedBuffer(instance.vertices));
}

function isEncodedBuffer(value: unknown): boolean {
  const buffer = asJsonObject(value);
  return Boolean(buffer && typeof buffer.buffer === "string" && buffer.codec === "b64");
}

function resolveRawShapeRefs(node: JsonObject, instances: unknown[]): void {
  const parts = Array.isArray(node.parts) ? node.parts : [];
  for (const part of parts) {
    const child = asJsonObject(part);
    if (!child) {
      continue;
    }
    const shape = asJsonObject(child.shape);
    const ref = shape && typeof shape.ref === "number" ? shape.ref : null;
    if (ref !== null && ref >= 0 && ref < instances.length) {
      child.shape = cloneJson(instances[ref]);
    }
    resolveRawShapeRefs(child, instances);
  }
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function walkShapeTree(node: JsonObject | null, states: Record<string, VisibilityState>): void {
  if (!node) {
    return;
  }
  const parts = Array.isArray(node.parts) ? node.parts : null;
  if (parts) {
    for (const part of parts) {
      walkShapeTree(asJsonObject(part), states);
    }
    return;
  }
  if (typeof node.id === "string" && isVisibilityState(node.state)) {
    states[node.id] = node.state;
  }
}

function isVisibilityState(value: unknown): value is VisibilityState {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  );
}

function selectedShapeIds(message: JsonObject): string[] {
  const selected = message.selected || message.selectedShapeIDs || message.selected_shape_ids;
  return Array.isArray(selected) ? selected.map(String) : [];
}

function changedNumber(change: JsonObject, key: string, fallback: number | null): number | null {
  const value = asJsonObject(change[key])?.new;
  return typeof value === "number" ? value : fallback;
}

function changedString(change: JsonObject, key: string, fallback: string | null): string | null {
  const value = asJsonObject(change[key])?.new;
  return typeof value === "string" ? value : fallback;
}

function changedBoolean(change: JsonObject, key: string, fallback: boolean | null): boolean | null {
  const value = asJsonObject(change[key])?.new;
  return typeof value === "boolean" ? value : fallback;
}

function changedVec3(change: JsonObject, key: string, fallback: Vec3 | null): Vec3 | null {
  const value = asJsonObject(change[key])?.new;
  return asVec3(value) || fallback;
}

function changedQuat(change: JsonObject, key: string, fallback: Quat | null): Quat | null {
  const value = asJsonObject(change[key])?.new;
  return asQuat(value) || fallback;
}

function asVec3(value: unknown): Vec3 | null {
  return isVec3(value) ? value : null;
}

function isVec3(value: unknown): value is Vec3 {
  return Array.isArray(value) && value.length >= 3 && value.slice(0, 3).every((item) => typeof item === "number");
}

function asQuat(value: unknown): Quat | null {
  return isQuat(value) ? value : null;
}

function isQuat(value: unknown): value is Quat {
  return Array.isArray(value) && value.length >= 4 && value.slice(0, 4).every((item) => typeof item === "number");
}

function emptyState(text: string): HTMLElement {
  const element = document.createElement("div");
  element.textContent = text;
  element.style.height = "100%";
  element.style.display = "grid";
  element.style.placeItems = "center";
  element.style.color = "#c9d1d9";
  element.style.font = "13px system-ui, sans-serif";
  element.style.background = "#121316";
  return element;
}
