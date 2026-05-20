"use strict";

const http = require("http");
const https = require("https");

class ForgeCADServiceClient {
  constructor(baseUrl) {
    this.baseUrl = String(baseUrl || "").replace(/\/$/, "");
  }

  health() {
    return this.get("/health");
  }

  createSession(rootPath) {
    return this.post("/sessions", { root_path: rootPath });
  }

  current(sessionId) {
    return this.get(`/sessions/${encodeURIComponent(sessionId)}/current`);
  }

  renderRevision(sessionId, rendererId) {
    return this.post("/render/render_revision", {
      session_id: sessionId,
      renderer_id: rendererId
    });
  }

  exportStl(modelId, revisionId, outputPath) {
    return this.post(
      `/models/${encodeURIComponent(modelId)}/revisions/${encodeURIComponent(revisionId)}/export/stl`,
      { output_path: outputPath }
    );
  }

  get(path) {
    return requestJson("GET", this.baseUrl + path);
  }

  post(path, body) {
    return requestJson("POST", this.baseUrl + path, body);
  }
}

function requestJson(method, targetUrl, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(targetUrl);
    const payload = body === undefined ? undefined : Buffer.from(JSON.stringify(body));
    const transport = url.protocol === "https:" ? https : http;
    const request = transport.request(
      {
        method,
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers: {
          accept: "application/json",
          ...(payload
            ? {
                "content-type": "application/json",
                "content-length": String(payload.length)
              }
            : {})
        }
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const raw = Buffer.concat(chunks).toString("utf8");
          let parsed = {};
          if (raw.length > 0) {
            try {
              parsed = JSON.parse(raw);
            } catch (error) {
              reject(new Error(`Invalid JSON from ForgeCAD service: ${raw}`));
              return;
            }
          }
          if ((response.statusCode || 500) >= 400) {
            const message = parsed?.error?.message || response.statusMessage || "Service error";
            const err = new Error(message);
            err.response = parsed;
            reject(err);
            return;
          }
          resolve(parsed);
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

module.exports = {
  ForgeCADServiceClient
};
