import * as crypto from "crypto";
import * as path from "path";
import { spawn, type ChildProcessByStdio } from "child_process";
import { Readable } from "stream";
import * as vscode from "vscode";
import { resolveAssetRoots, type ForgeCADAssetRoots } from "./assetResolver";
import { ForgeCADServiceClient } from "./serviceClient";
import type {
  ForgeCADCurrent,
  ForgeCADHealth,
  ForgeCADMode,
  ForgeCADSession,
  ForgeCADStatus,
  Output
} from "./types";

export class ForgeCADServiceManager {
  private process: ChildProcessByStdio<null, Readable, Readable> | null = null;
  private baseUrl: string | null = null;
  private sessionId: string | null = null;
  private authToken: string | null = null;
  private client: ForgeCADServiceClient | null = null;
  private mode: ForgeCADMode = "stopped";
  private lastHealth: ForgeCADHealth | null = null;
  private lastCurrent: ForgeCADCurrent | null = null;
  private readonly statusEmitter = new vscode.EventEmitter<void>();
  readonly onDidChangeStatus = this.statusEmitter.event;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly output: Output
  ) {}

  async startOrConnect(): Promise<ForgeCADStatus> {
    if (this.client && this.baseUrl && this.sessionId) {
      return this.getStatus();
    }

    const externalUrl = this.config().get<string>("service.url", "").trim();
    if (externalUrl) {
      await this.connect(externalUrl);
    } else {
      await this.startLocal();
    }
    await this.ensureSession();
    this.statusEmitter.fire();
    return this.getStatus();
  }

  async connect(baseUrl: string): Promise<void> {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.authToken = this.config().get<string>("service.token", "").trim() || null;
    this.client = new ForgeCADServiceClient(this.baseUrl, this.authToken);
    this.lastHealth = await this.client.health();
    this.mode = "external";
    this.output.info(`Connected to ForgeCAD service at ${this.baseUrl}`);
  }

  async startLocal(): Promise<void> {
    if (!vscode.workspace.isTrusted) {
      throw new Error("ForgeCAD local service startup requires a trusted workspace.");
    }

    const assets = resolveAssetRoots(this.context);
    const pythonPath = this.pythonPath();
    const host = this.config().get<string>("service.host", "127.0.0.1");
    const port = Number(this.config().get<number>("service.port", 0));
    this.authToken = crypto.randomBytes(32).toString("base64url");
    const args = [
      "-m",
      "forgecad_service",
      "--host",
      host,
      "--port",
      String(port),
      "--quiet",
      "--auth-token",
      this.authToken
    ];
    const env = {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      FORGECAD_SERVICE_TOKEN: this.authToken,
      PYTHONPATH: [assets.corePath, assets.servicePath, process.env.PYTHONPATH]
        .filter(Boolean)
        .join(path.delimiter),
      FORGECAD_WORKSPACE_TRUSTED: String(vscode.workspace.isTrusted),
      FORGECAD_WORKSPACE_ROOT: this.workspaceRoot() || ""
    };

    this.output.info(
      `Starting ForgeCAD service from ${assets.source} assets with ${pythonPath} ${args
        .slice(0, -1)
        .join(" ")} <token>`
    );
    const childProcess = spawn(pythonPath, args, {
      cwd: assets.forgecadRoot,
      env,
      stdio: ["ignore", "pipe", "pipe"]
    });
    this.process = childProcess;

    childProcess.stderr.on("data", (data: Buffer) => {
      this.output.warn(data.toString("utf8").trimEnd());
    });
    childProcess.on("exit", (code, signal) => {
      this.output.info(`ForgeCAD service exited code=${code} signal=${signal}`);
      this.process = null;
      if (this.mode === "local") {
        this.mode = "stopped";
        this.baseUrl = null;
        this.client = null;
        this.sessionId = null;
        this.authToken = null;
        this.statusEmitter.fire();
      }
    });

    this.baseUrl = await this.waitForServiceUrl(childProcess);
    this.client = new ForgeCADServiceClient(this.baseUrl, this.authToken);
    this.lastHealth = await this.client.health();
    this.mode = "local";
    this.output.info(`ForgeCAD service listening at ${this.baseUrl}`);
  }

  waitForServiceUrl(childProcess: ChildProcessByStdio<null, Readable, Readable>): Promise<string> {
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
      childProcess.stdout.on("data", (data: Buffer) => {
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

  async ensureSession(): Promise<string> {
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

  async resetSession(): Promise<ForgeCADSession> {
    if (!this.client) {
      await this.startOrConnect();
    }
    if (!this.client) {
      throw new Error("ForgeCAD service is not connected.");
    }
    const session = await this.client.createSession(this.workspaceRoot());
    this.sessionId = session.session_id;
    this.lastCurrent = await this.client.current(this.sessionId);
    this.statusEmitter.fire();
    return session;
  }

  async current(): Promise<ForgeCADCurrent> {
    if (!this.client || !this.sessionId) {
      await this.startOrConnect();
    }
    if (!this.client || !this.sessionId) {
      throw new Error("ForgeCAD service is not connected.");
    }
    this.lastCurrent = await this.client.current(this.sessionId);
    this.statusEmitter.fire();
    return this.lastCurrent;
  }

  async evaluateScript(
    script: string,
    options: {
      name: string;
      sourceRef?: Record<string, unknown>;
    }
  ): Promise<Record<string, unknown>> {
    if (!this.client || !this.sessionId) {
      await this.startOrConnect();
    }
    if (!this.client || !this.sessionId) {
      throw new Error("ForgeCAD service is not connected.");
    }
    const result = await this.client.evaluateScript(
      this.sessionId,
      script,
      options.name,
      options.sourceRef
    );
    this.lastCurrent = await this.client.current(this.sessionId);
    this.statusEmitter.fire();
    return result;
  }

  async exportCurrentStl(outputPath: string) {
    if (!this.client) {
      await this.startOrConnect();
    }
    if (!this.client) {
      throw new Error("ForgeCAD service is not connected.");
    }
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

  async stop(): Promise<void> {
    if (this.mode === "external") {
      this.mode = "stopped";
      this.baseUrl = null;
      this.client = null;
      this.sessionId = null;
      this.authToken = null;
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
    this.authToken = null;
    this.lastHealth = null;
    this.lastCurrent = null;
    this.statusEmitter.fire();
  }

  async getStatus(): Promise<ForgeCADStatus> {
    if (this.client) {
      try {
        this.lastHealth = await this.client.health();
        if (this.sessionId) {
          this.lastCurrent = await this.client.current(this.sessionId);
        }
      } catch (error) {
        this.output.warn(`ForgeCAD service status check failed: ${errorMessage(error)}`);
      }
    }
    return {
      mode: this.mode,
      baseUrl: this.baseUrl,
      sessionId: this.sessionId,
      authToken: this.authToken,
      health: this.lastHealth,
      current: this.lastCurrent,
      trusted: vscode.workspace.isTrusted
    };
  }

  assetRoots(): ForgeCADAssetRoots {
    return resolveAssetRoots(this.context);
  }

  config(): vscode.WorkspaceConfiguration {
    return vscode.workspace.getConfiguration("forgecad");
  }

  pythonPath(): string {
    const configured = this.config().get<string>("python.path", "").trim();
    if (configured) {
      return configured;
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  workspaceRoot(): string | null {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || null;
  }

  dispose(): Promise<void> {
    const stopped = this.stop();
    this.statusEmitter.dispose();
    return stopped;
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
