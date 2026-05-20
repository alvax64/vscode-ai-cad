export class LegacyViewerAdapter {
  constructor(options = {}) {
    this.window = options.window || window;
    this.vscode = options.vscode || this.window.acquireVsCodeApi?.();
    this.pendingCaptures = new Map();
    this.viewState = {};
    this.window.addEventListener("message", (event) => {
      const data = event.data;
      if (data?.command === "screenshot") {
        const pending = this.pendingCaptures.get(data.text.filename);
        if (pending) {
          this.pendingCaptures.delete(data.text.filename);
          pending({
            dataUrl: data.text.data,
            mimeType: "image/png"
          });
        }
      } else if (data?.command === "status") {
        this.viewState = fromLegacyStatus(data.text || {});
        this.onStateChanged?.(this.viewState);
      }
    });
  }

  async renderRevision({ tessellatedScene, config }) {
    this.window.postMessage(
      {
        type: "data",
        data: tessellatedScene,
        config: config || {}
      },
      "*"
    );
  }

  async captureView(config = {}) {
    const filename = config.filename || `forgecad-capture-${Date.now()}.png`;
    const capture = new Promise((resolve) => {
      this.pendingCaptures.set(filename, resolve);
    });
    this.window.postMessage({ type: "screenshot", filename }, "*");
    return capture;
  }

  async setCamera(camera) {
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

  async setVisibility(visibleNodeStates) {
    this.window.postMessage(
      {
        type: "ui",
        config: { states: visibleNodeStates }
      },
      "*"
    );
  }

  async setClipping(clipping) {
    this.window.postMessage(
      {
        type: "ui",
        config: clipping
      },
      "*"
    );
  }

  async getViewState() {
    return this.viewState;
  }

  onViewStateChanged(callback) {
    this.onStateChanged = callback;
  }
}

function fromLegacyStatus(status) {
  return {
    camera: {
      position: status.position || null,
      quaternion: status.quaternion || null,
      target: status.target || null,
      zoom: status.zoom || null
    },
    selected_shape_ids: status.selected || [],
    visible_node_states: status.states || {},
    clipping: {
      clip_intersection: status.clip_intersection,
      clip_planes: status.clip_planes,
      clip_object_colors: status.clip_object_colors
    },
    active_analysis_tool: status.active_analysis_tool || null,
    viewport_size: status.viewport_size || null
  };
}
