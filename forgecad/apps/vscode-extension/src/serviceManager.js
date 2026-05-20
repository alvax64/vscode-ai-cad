"use strict";

const path = require("path");
const { spawn } = require("child_process");
const vscode = require("vscode");
const { ForgeCADServiceClient } = require("./serviceClient");

class ForgeCADServiceManager {
  constructor(context, output) {
    this.context = context;
    this.output = output;
    this.process = null;
    this.baseUrl = null;
    this.sessionId = null;
    this.client = null;
    this.mode = "stopped";
    this.lastHealth = null;
    this.lastCurrent = null;
    this.statusEmitter = new vscode.EventEmitter();
    this.onDidChangeStatus = this.statusEmitter.event;
  }

  async startOrConnect() {
    if (this.client && this.baseUrl && this.sessionId) {
      return this.getStatus();
    }

    const externalUrl = this.config().get("service.url", "").trim();
    if (externalUrl) {
      await this.connect(externalUrl);
    } else {
      await this.startLocal();
    }
    await this.ensureSession();
    this.statusEmitter.fire();
    return this.getStatus();
  }

  async connect(baseUrl) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.client = new ForgeCADServiceClient(this.baseUrl);
    this.lastHealth = await this.client.health();
    this.mode = "external";
    this.output.info(`Connected to ForgeCAD service at ${this.baseUrl}`);
  }

  async startLocal() {
    if (!vscode.workspace.isTrusted) {
      throw new Error("ForgeCAD local service startup requires a trusted workspace.");
    }

    const forgecadRoot = path.resolve(this.context.extensionPath, "..", "..");
    const corePath = path.join(forgecadRoot, "python", "forgecad_core");
    const servicePath = path.join(forgecadRoot, "python", "forgecad_service");
    const pythonPath = this.pythonPath();
    const host = this.config().get("service.host", "127.0.0.1");
    const port = Number(this.config().get("service.port", 0));
    const args = [
      "-m",
      "forgecad_service",
      "--host",
      host,
      "--port",
      String(port),
      "--quiet"
    ];
    const env = {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      PYTHONPATH: [corePath, servicePath, process.env.PYTHONPATH]
        .filter(Boolean)
        .join(path.delimiter),
      FORGECAD_WORKSPACE_TRUSTED: String(vscode.workspace.isTrusted),
      FORGECAD_WORKSPACE_ROOT: this.workspaceRoot() || ""
    };

    this.output.info(`Starting ForgeCAD service with ${pythonPath} ${args.join(" ")}`);
    this.process = spawn(pythonPath, args, {
      cwd: forgecadRoot,
      env,
      stdio: ["ignore", "pipe", "pipe"]
    });

    this.process.stderr.on("data", (data) => {
      this.output.warn(data.toString("utf8").trimEnd());
    });
    this.process.on("exit", (code, signal) => {
      this.output.info(`ForgeCAD service exited code=${code} signal=${signal}`);
      this.process = null;
      if (this.mode === "local") {
        this.mode = "stopped";
        this.baseUrl = null;
        this.client = null;
        this.sessionId = null;
        this.statusEmitter.fire();
      }
    });

    this.baseUrl = await this.waitForServiceUrl(this.process);
    this.client = new ForgeCADServiceClient(this.baseUrl);
    this.lastHealth = await this.client.health();
    this.mode = "local";
    this.output.info(`ForgeCAD service listening at ${this.baseUrl}`);
  }

  waitForServiceUrl(childProcess) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const timeout = setTimeout(() => {
        settled = true;
        reject(new Error("Timed out waiting for ForgeCAD service to report its URL."));
      }, 15000);
      childProcess.once("error", (error) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timeout);
        reject(error);
      });
      childProcess.once("exit", (code, signal) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeout(timeout);
        reject(new Error(`ForgeCAD service exited before startup code=${code} signal=${signal}`));
      });
      childProcess.stdout.on("data", (data) => {
        if (settled) {
          return;
        }
        const text = data.toString("utf8");
        this.output.info(text.trimEnd());
        const match = text.match(/http:\/\/[^\s]+/);
        if (match) {
          settled = true;
          clearTimeout(timeout);
          resolve(match[0].replace(/\/$/, ""));
        }
      });
    });
  }

  async ensureSession() {
    if (!this.client) {
      throw new Error("ForgeCAD service is not connected.");
    }
    if (this.sessionId) {
      return this.sessionId;
    }
    const session = await this.client.createSession(this.workspaceRoot());
    this.sessionId = session.session_id;
    this.lastCurrent = await this.client.current(this.sessionId);
    this.output.info(`ForgeCAD workspace session ${this.sessionId}`);
    return this.sessionId;
  }

  async resetSession() {
    if (!this.client) {
      await this.startOrConnect();
    }
    const session = await this.client.createSession(this.workspaceRoot());
    this.sessionId = session.session_id;
    this.lastCurrent = await this.client.current(this.sessionId);
    this.statusEmitter.fire();
    return session;
  }

  async current() {
    if (!this.client || !this.sessionId) {
      await this.startOrConnect();
    }
    this.lastCurrent = await this.client.current(this.sessionId);
    this.statusEmitter.fire();
    return this.lastCurrent;
  }

  async exportCurrentStl(outputPath) {
    const current = await this.current();
    if (!current.model || !current.revision) {
      throw new Error("No active ForgeCAD model is available to export.");
    }
    const result = await this.client.exportStl(
      current.model.model_id,
      current.revision.revision_id,
      outputPath
    );
    this.statusEmitter.fire();
    return result;
  }

  async stop() {
    if (this.mode === "external") {
      this.mode = "stopped";
      this.baseUrl = null;
      this.client = null;
      this.sessionId = null;
      this.statusEmitter.fire();
      return;
    }
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this.mode = "stopped";
    this.baseUrl = null;
    this.client = null;
    this.sessionId = null;
    this.lastHealth = null;
    this.lastCurrent = null;
    this.statusEmitter.fire();
  }

  async getStatus() {
    if (this.client) {
      try {
        this.lastHealth = await this.client.health();
        if (this.sessionId) {
          this.lastCurrent = await this.client.current(this.sessionId);
        }
      } catch (error) {
        this.output.warn(`ForgeCAD service status check failed: ${error.message}`);
      }
    }
    return {
      mode: this.mode,
      baseUrl: this.baseUrl,
      sessionId: this.sessionId,
      health: this.lastHealth,
      current: this.lastCurrent,
      trusted: vscode.workspace.isTrusted
    };
  }

  config() {
    return vscode.workspace.getConfiguration("forgecad");
  }

  pythonPath() {
    const configured = this.config().get("python.path", "").trim();
    if (configured) {
      return configured;
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  workspaceRoot() {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || null;
  }

  dispose() {
    const stopped = this.stop();
    this.statusEmitter.dispose();
    return stopped;
  }
}

module.exports = {
  ForgeCADServiceManager
};
