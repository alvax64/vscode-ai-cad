import * as http from "http";
import * as https from "https";
import type {
  ForgeCADCurrent,
  ForgeCADExportResult,
  ForgeCADHealth,
  ForgeCADSession
} from "./types";

export class ForgeCADServiceClient {
  readonly baseUrl: string;
  readonly authToken: string | null;

  constructor(baseUrl: string, authToken: string | null = null) {
    this.baseUrl = String(baseUrl || "").replace(/\/$/, "");
    this.authToken = authToken;
  }

  health(): Promise<ForgeCADHealth> {
    return this.get("/health");
  }

  createSession(rootPath: string | null): Promise<ForgeCADSession> {
    return this.post("/sessions", { root_path: rootPath });
  }

  current(sessionId: string): Promise<ForgeCADCurrent> {
    return this.get(`/sessions/${encodeURIComponent(sessionId)}/current`);
  }

  renderRevision(sessionId: string, rendererId?: string): Promise<Record<string, unknown>> {
    return this.post("/render/render_revision", {
      session_id: sessionId,
      renderer_id: rendererId
    });
  }

  exportStl(
    modelId: string,
    revisionId: string,
    outputPath: string
  ): Promise<ForgeCADExportResult> {
    return this.post(
      `/models/${encodeURIComponent(modelId)}/revisions/${encodeURIComponent(revisionId)}/export/stl`,
      { output_path: outputPath }
    );
  }

  get<T>(path: string): Promise<T> {
    return requestJson<T>("GET", this.baseUrl + path, undefined, this.authToken);
  }

  post<T>(path: string, body: unknown): Promise<T> {
    return requestJson<T>("POST", this.baseUrl + path, body, this.authToken);
  }
}

function requestJson<T>(
  method: string,
  targetUrl: string,
  body?: unknown,
  authToken?: string | null
): Promise<T> {
  return new Promise((resolve, reject) => {
    const url = new URL(targetUrl);
    const payload = body === undefined ? undefined : Buffer.from(JSON.stringify(body));
    const transport = url.protocol === "https:" ? https : http;
    const headers: Record<string, string> = {
      accept: "application/json"
    };
    if (payload) {
      headers["content-type"] = "application/json";
      headers["content-length"] = String(payload.length);
    }
    if (authToken) {
      headers["x-forgecad-token"] = authToken;
    }

    const request = transport.request(
      {
        method,
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers
      },
      (response) => {
        const chunks: Buffer[] = [];
        response.on("data", (chunk: Buffer) => chunks.push(chunk));
        response.on("end", () => {
          const raw = Buffer.concat(chunks).toString("utf8");
          let parsed: unknown = {};
          if (raw.length > 0) {
            try {
              parsed = JSON.parse(raw);
            } catch {
              reject(new Error(`Invalid JSON from ForgeCAD service: ${raw}`));
              return;
            }
          }
          if ((response.statusCode || 500) >= 400) {
            const message =
              serviceErrorMessage(parsed) || response.statusMessage || "Service error";
            const err = new Error(message) as Error & { response?: unknown };
            err.response = parsed;
            reject(err);
            return;
          }
          resolve(parsed as T);
        });
      }
    );
    request.on("error", reject);
    request.setTimeout(10000, () => {
      request.destroy(new Error(`Timed out calling ForgeCAD service ${method} ${targetUrl}`));
    });
    if (payload) {
      request.write(payload);
    }
    request.end();
  });
}

function serviceErrorMessage(value: unknown): string | null {
  if (
    value &&
    typeof value === "object" &&
    "error" in value &&
    value.error &&
    typeof value.error === "object" &&
    "message" in value.error &&
    typeof value.error.message === "string"
  ) {
    return value.error.message;
  }
  return null;
}
