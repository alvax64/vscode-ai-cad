"use strict";

const vscode = require("vscode");

class ForgeCADStatusProvider {
  constructor(serviceManager) {
    this.serviceManager = serviceManager;
    this.emitter = new vscode.EventEmitter();
    this.onDidChangeTreeData = this.emitter.event;
  }

  refresh() {
    this.emitter.fire();
  }

  getTreeItem(element) {
    return element;
  }

  async getChildren() {
    const status = await this.serviceManager.getStatus();
    const current = status.current || {};
    const model = current.model || null;
    const revision = current.revision || null;
    const items = [
      item(`Mode: ${status.mode}`, "service", status.mode === "stopped" ? "warning" : "pass"),
      item(`Trusted: ${status.trusted ? "yes" : "no"}`, "trust", status.trusted ? "pass" : "warning"),
      item(`Endpoint: ${status.baseUrl || "<none>"}`, "endpoint", "info"),
      item(`Session: ${status.sessionId || "<none>"}`, "session", "info"),
      item(`Model: ${model?.model_id || "<none>"}`, "model", model ? "info" : "warning"),
      item(`Revision: ${revision?.revision_id || "<none>"}`, "revision", revision ? "info" : "warning")
    ];
    if (status.health?.dependencies) {
      const deps = Object.entries(status.health.dependencies)
        .map(([name, ok]) => `${name}:${ok ? "ok" : "missing"}`)
        .join(" ");
      items.push(item(`CAD deps: ${deps}`, "dependencies", "info"));
    }
    return items;
  }

  dispose() {
    this.emitter.dispose();
  }
}

function item(label, id, state) {
  const treeItem = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  treeItem.id = id;
  treeItem.contextValue = id;
  treeItem.iconPath = new vscode.ThemeIcon(iconForState(state));
  return treeItem;
}

function iconForState(state) {
  if (state === "pass") {
    return "pass";
  }
  if (state === "warning") {
    return "warning";
  }
  return "circle-outline";
}

module.exports = {
  ForgeCADStatusProvider
};
