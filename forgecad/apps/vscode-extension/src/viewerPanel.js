"use strict";

const path = require("path");
const vscode = require("vscode");

class ForgeCADViewerPanel {
  static currentPanel = null;

  static async open(context, serviceManager) {
    const status = await serviceManager.startOrConnect();
    if (!status.baseUrl || !status.sessionId) {
      throw new Error("ForgeCAD service did not provide an endpoint and session.");
    }

    if (ForgeCADViewerPanel.currentPanel) {
      ForgeCADViewerPanel.currentPanel.panel.reveal(vscode.ViewColumn.Beside);
      await ForgeCADViewerPanel.currentPanel.update(status);
      return ForgeCADViewerPanel.currentPanel;
    }

    const rendererRoot = vscode.Uri.file(
      path.resolve(context.extensionPath, "..", "..", "packages", "webview-renderer")
    );
    const panel = vscode.window.createWebviewPanel(
      "forgecadViewer",
      "ForgeCAD Viewer",
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [rendererRoot]
      }
    );

    const instance = new ForgeCADViewerPanel(context, panel, rendererRoot);
    ForgeCADViewerPanel.currentPanel = instance;
    panel.onDidDispose(() => {
      if (ForgeCADViewerPanel.currentPanel === instance) {
        ForgeCADViewerPanel.currentPanel = null;
      }
    });
    await instance.update(status);
    return instance;
  }

  constructor(context, panel, rendererRoot) {
    this.context = context;
    this.panel = panel;
    this.rendererRoot = rendererRoot;
  }

  async update(status) {
    this.panel.webview.html = this.html(status);
  }

  html(status) {
    const nonce = randomNonce();
    const webview = this.panel.webview;
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.rendererRoot, "src", "forgecad-renderer-client.js")
    );
    const serviceBaseUrl = JSON.stringify(status.baseUrl);
    const sessionId = JSON.stringify(status.sessionId);
    const connectSrc = connectSources(status.baseUrl).join(" ");
    const csp = [
      "default-src 'none'",
      `img-src ${webview.cspSource} data:`,
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `script-src ${webview.cspSource} 'nonce-${nonce}'`,
      `connect-src ${connectSrc}`
    ].join("; ");

    return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta
      http-equiv="Content-Security-Policy"
      content="${escapeHtml(csp)}"
    />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ForgeCAD Viewer</title>
    <style>
      html, body, #cad_viewer {
        width: 100%;
        height: 100%;
        margin: 0;
        padding: 0;
        overflow: hidden;
        background: #121316;
      }
      .status {
        position: fixed;
        left: 12px;
        bottom: 10px;
        color: #c9d1d9;
        font: 12px system-ui, sans-serif;
        opacity: 0.72;
        pointer-events: none;
      }
    </style>
  </head>
  <body>
    <div id="cad_viewer"></div>
    <div class="status">service ${escapeHtml(status.baseUrl)} · ${escapeHtml(status.sessionId)}</div>
    <script nonce="${nonce}" type="module">
      import { createServiceDrivenRenderer } from "${scriptUri}";

      const renderer = createServiceDrivenRenderer({
        serviceBaseUrl: ${serviceBaseUrl},
        sessionId: ${sessionId},
        mount: document.getElementById("cad_viewer")
      });
      renderer.start().catch((error) => {
        document.body.textContent = error.message;
      });
    </script>
  </body>
</html>`;
  }
}

function randomNonce() {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let value = "";
  for (let index = 0; index < 32; index += 1) {
    value += alphabet[Math.floor(Math.random() * alphabet.length)];
  }
  return value;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function connectSources(baseUrl) {
  const sources = [
    "http://127.0.0.1:*",
    "ws://127.0.0.1:*",
    "http://localhost:*",
    "ws://localhost:*"
  ];
  try {
    const url = new URL(baseUrl);
    sources.push(url.origin);
    if (url.protocol === "https:") {
      sources.push(`wss://${url.host}`);
    } else if (url.protocol === "http:") {
      sources.push(`ws://${url.host}`);
    }
  } catch {
    /* Ignore invalid URL; service calls will report the real error. */
  }
  return Array.from(new Set(sources));
}

module.exports = {
  ForgeCADViewerPanel
};
