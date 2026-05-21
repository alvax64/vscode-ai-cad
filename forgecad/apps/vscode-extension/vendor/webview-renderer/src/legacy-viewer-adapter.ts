import type {
  ForgeCADRendererAdapter,
  ForgeCADRendererCapture,
  ForgeCADRenderRequest,
  ForgeCADViewState
} from "./forgecad-renderer-client";

type JsonObject = Record<string, unknown>;

type LegacyWindow = Window & {
  acquireVsCodeApi?: () => unknown;
};

type LegacyViewerAdapterOptions = {
  window?: LegacyWindow;
  vscode?: unknown;
};

type LegacyMessage = {
  command?: string;
  text?: JsonObject;
};

type PendingCapture = (capture: ForgeCADRendererCapture) => void;

export class LegacyViewerAdapter implements ForgeCADRendererAdapter {
  readonly window: LegacyWindow;
  readonly vscode?: unknown;
  private readonly pendingCaptures = new Map<string, PendingCapture>();
  private viewState: Partial<ForgeCADViewState> = {};
  private onStateChanged?: (viewState: Partial<ForgeCADViewState>) => void;

  constructor(options: LegacyViewerAdapterOptions = {}) {
    this.window = options.window || window;
    this.vscode = options.vscode || this.window.acquireVsCodeApi?.();
    this.window.addEventListener("message", (event: MessageEvent) => {
      this.handleMessage(toLegacyMessage(event.data));
    });
  }

  async renderRevision({ tessellatedScene, config }: ForgeCADRenderRequest): Promise<void> {
    this.window.postMessage(
      {
        type: "data",
        data: tessellatedScene,
        config: config || {}
      },
      "*"
    );
  }

  async captureView(config: JsonObject = {}): Promise<ForgeCADRendererCapture> {
    const filename =
      typeof config.filename === "string" ? config.filename : `forgecad-capture-${Date.now()}.png`;
    const capture = new Promise<ForgeCADRendererCapture>((resolve) => {
      this.pendingCaptures.set(filename, resolve);
    });
    this.window.postMessage({ type: "screenshot", filename }, "*");
    return capture;
  }

  async setCamera(camera: JsonObject = {}): Promise<void> {
    this.window.postMessage(
      {
        type: "ui",
        config: {
          position: camera.position,
          quaternion: camera.quaternion,
          target: camera.target,
          zoom: camera.zoom
        }
      },
      "*"
    );
  }

  async setVisibility(visibleNodeStates: JsonObject = {}): Promise<void> {
    this.window.postMessage(
      {
        type: "ui",
        config: { states: visibleNodeStates }
      },
      "*"
    );
  }

  async setClipping(clipping: JsonObject = {}): Promise<void> {
    this.window.postMessage(
      {
        type: "ui",
        config: clipping
      },
      "*"
    );
  }

  async getViewState(): Promise<Partial<ForgeCADViewState>> {
    return this.viewState;
  }

  onViewStateChanged(callback: (viewState: Partial<ForgeCADViewState>) => void): void {
    this.onStateChanged = callback;
  }

  private handleMessage(data: LegacyMessage): void {
    if (data.command === "screenshot") {
      const text = data.text || {};
      const filename = typeof text.filename === "string" ? text.filename : "";
      const pending = this.pendingCaptures.get(filename);
      if (!pending) {
        return;
      }
      this.pendingCaptures.delete(filename);
      pending({
        dataUrl: typeof text.data === "string" ? text.data : "",
        mimeType: "image/png"
      });
      return;
    }
    if (data.command === "status") {
      this.viewState = fromLegacyStatus(data.text || {});
      this.onStateChanged?.(this.viewState);
    }
  }
}

function toLegacyMessage(value: unknown): LegacyMessage {
  if (!value || typeof value !== "object") {
    return {};
  }
  return value as LegacyMessage;
}

function fromLegacyStatus(status: JsonObject): Partial<ForgeCADViewState> {
  return {
    camera: {
      position: status.position || null,
      quaternion: status.quaternion || null,
      target: status.target || null,
      zoom: status.zoom || null
    },
    selected_shape_ids: Array.isArray(status.selected) ? status.selected.map(String) : [],
    visible_node_states: isJsonObject(status.states) ? status.states : {},
    clipping: {
      clip_intersection: status.clip_intersection,
      clip_planes: status.clip_planes,
      clip_object_colors: status.clip_object_colors
    },
    active_analysis_tool:
      typeof status.active_analysis_tool === "string" ? status.active_analysis_tool : null,
    viewport_size: isViewportSize(status.viewport_size) ? status.viewport_size : null
  };
}

function isJsonObject(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isViewportSize(value: unknown): value is { width: number; height: number } {
  return (
    isJsonObject(value) &&
    typeof value.width === "number" &&
    typeof value.height === "number"
  );
}
