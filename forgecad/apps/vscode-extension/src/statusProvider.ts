import * as vscode from "vscode";
import { ForgeCADServiceManager } from "./serviceManager";

type StatusState = "info" | "pass" | "warning";

export class ForgeCADStatusProvider
  implements vscode.TreeDataProvider<vscode.TreeItem>, vscode.Disposable
{
  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly serviceManager: ForgeCADServiceManager) {}

  refresh(): void {
    this.emitter.fire(undefined);
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(): Promise<vscode.TreeItem[]> {
    const status = await this.serviceManager.getStatus();
    const current = status.current || null;
    const model = current?.model || null;
    const revision = current?.revision || null;
    const items = [
      item(`Mode: ${status.mode}`, "service", status.mode === "stopped" ? "warning" : "pass"),
      item(
        `Trusted: ${status.trusted ? "yes" : "no"}`,
        "trust",
        status.trusted ? "pass" : "warning"
      ),
      item(`Endpoint: ${status.baseUrl || "<none>"}`, "endpoint", "info"),
      item(`Session: ${status.sessionId || "<none>"}`, "session", "info"),
      item(`Model: ${model?.model_id || "<none>"}`, "model", model ? "info" : "warning"),
      item(
        `Revision: ${revision?.revision_id || "<none>"}`,
        "revision",
        revision ? "info" : "warning"
      )
    ];
    if (status.health?.dependencies) {
      const deps = Object.entries(status.health.dependencies)
        .map(([name, ok]) => `${name}:${ok ? "ok" : "missing"}`)
        .join(" ");
      items.push(item(`CAD deps: ${deps}`, "dependencies", "info"));
    }
    return items;
  }

  dispose(): void {
    this.emitter.dispose();
  }
}

function item(label: string, id: string, state: StatusState): vscode.TreeItem {
  const treeItem = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  treeItem.id = id;
  treeItem.contextValue = id;
  treeItem.iconPath = new vscode.ThemeIcon(iconForState(state));
  return treeItem;
}

function iconForState(state: StatusState): string {
  if (state === "pass") {
    return "pass";
  }
  if (state === "warning") {
    return "warning";
  }
  return "circle-outline";
}
