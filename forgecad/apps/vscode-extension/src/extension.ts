import * as path from "path";
import * as vscode from "vscode";
import { createOutput } from "./output";
import { ForgeCADServiceManager } from "./serviceManager";
import { ForgeCADStatusProvider } from "./statusProvider";
import { ForgeCADViewerPanel } from "./viewerPanel";
import type { ForgeCADRevision, Output } from "./types";

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const output = createOutput();
  const serviceManager = new ForgeCADServiceManager(context, output);
  const statusProvider = new ForgeCADStatusProvider(serviceManager);
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 50);

  statusBar.command = "forgecad.showStatus";
  statusBar.tooltip = "ForgeCAD service status";
  statusBar.show();

  async function refreshStatusBar(): Promise<void> {
    const status = await serviceManager.getStatus();
    statusBar.text =
      status.mode === "stopped"
        ? "$(debug-disconnect) ForgeCAD"
        : `$(server-process) ForgeCAD ${status.sessionId || ""}`;
    statusBar.tooltip = status.baseUrl
      ? `ForgeCAD ${status.mode}: ${status.baseUrl}`
      : "ForgeCAD service is stopped";
    statusProvider.refresh();
  }

  const statusSubscription = serviceManager.onDidChangeStatus(() => {
    refreshStatusBar().catch((error: unknown) => output.warn(errorMessage(error)));
  });
  const trustSubscription = vscode.workspace.onDidGrantWorkspaceTrust(() => {
    refreshStatusBar().catch((error: unknown) => output.warn(errorMessage(error)));
  });

  context.subscriptions.push(
    output.channel,
    statusBar,
    statusProvider,
    statusSubscription,
    trustSubscription,
    { dispose: () => void serviceManager.dispose() },
    vscode.window.registerTreeDataProvider("forgecadStatus", statusProvider),
    vscode.commands.registerCommand("forgecad.startService", () =>
      run(output, async () => {
        await serviceManager.startOrConnect();
        await refreshStatusBar();
        vscode.window.showInformationMessage("ForgeCAD service is ready.");
      })
    ),
    vscode.commands.registerCommand("forgecad.stopService", () =>
      run(output, async () => {
        await serviceManager.stop();
        await refreshStatusBar();
        vscode.window.showInformationMessage("ForgeCAD service stopped.");
      })
    ),
    vscode.commands.registerCommand("forgecad.openViewer", () =>
      run(output, async () => {
        await ForgeCADViewerPanel.open(context, serviceManager);
        await refreshStatusBar();
      })
    ),
    vscode.commands.registerCommand("forgecad.resetSession", () =>
      run(output, async () => {
        const session = await serviceManager.resetSession();
        await refreshStatusBar();
        vscode.window.showInformationMessage(`ForgeCAD session reset: ${session.session_id}`);
      })
    ),
    vscode.commands.registerCommand("forgecad.exportStl", () =>
      run(output, async () => {
        if (!vscode.workspace.isTrusted) {
          throw new Error("STL export requires a trusted workspace.");
        }
        await serviceManager.startOrConnect();
        const target = await vscode.window.showSaveDialog({
          title: "Export active ForgeCAD model as STL",
          filters: { STL: ["stl"] },
          defaultUri: defaultExportUri()
        });
        if (!target) {
          return;
        }
        const result = await serviceManager.exportCurrentStl(target.fsPath);
        await refreshStatusBar();
        vscode.window.showInformationMessage(`Exported STL: ${result.export.output_path}`);
      })
    ),
    vscode.commands.registerCommand("forgecad.showStatus", () =>
      run(output, async () => {
        const status = await serviceManager.getStatus();
        output.info(JSON.stringify(status, null, 2));
        output.show();
        await refreshStatusBar();
      })
    ),
    vscode.commands.registerCommand("forgecad.copyMcpServiceEndpoint", () =>
      run(output, async () => {
        const status = await serviceManager.startOrConnect();
        const payload = {
          service: status.baseUrl,
          session_id: status.sessionId,
          token: status.authToken
        };
        await vscode.env.clipboard.writeText(JSON.stringify(payload));
        vscode.window.showInformationMessage("ForgeCAD service endpoint copied.");
      })
    ),
    vscode.commands.registerCommand("forgecad.openActiveModelSource", () =>
      run(output, async () => {
        const current = await serviceManager.current();
        const sourcePath = sourcePathFromRevision(current.revision, serviceManager.workspaceRoot());
        if (!sourcePath) {
          vscode.window.showInformationMessage("The active ForgeCAD revision has no file source.");
          return;
        }
        const document = await vscode.workspace.openTextDocument(vscode.Uri.file(sourcePath));
        await vscode.window.showTextDocument(document);
      })
    ),
    vscode.commands.registerCommand("forgecad.refreshStatus", () =>
      run(output, async () => {
        await refreshStatusBar();
      })
    )
  );

  await refreshStatusBar();
  if (vscode.workspace.getConfiguration("forgecad").get<boolean>("service.autostart", false)) {
    void run(output, async () => {
      await serviceManager.startOrConnect();
      await refreshStatusBar();
      if (vscode.workspace.getConfiguration("forgecad").get<boolean>("viewer.openOnStart", false)) {
        await ForgeCADViewerPanel.open(context, serviceManager);
      }
    });
  }
}

async function run(output: Output, task: () => Promise<void>): Promise<void> {
  try {
    await task();
  } catch (error) {
    output.error(error instanceof Error && error.stack ? error.stack : errorMessage(error));
    vscode.window.showErrorMessage(`ForgeCAD: ${errorMessage(error)}`);
  }
}

function defaultExportUri(): vscode.Uri | undefined {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri;
  if (!root) {
    return undefined;
  }
  return vscode.Uri.joinPath(root, "forgecad-export.stl");
}

function sourcePathFromRevision(
  revision: ForgeCADRevision | null,
  workspaceRoot: string | null
): string | null {
  const sourceRef = revision?.source_ref || {};
  const candidate = stringField(sourceRef, "path") || stringField(sourceRef, "file") || stringField(sourceRef, "filename");
  if (!candidate) {
    return null;
  }
  if (path.isAbsolute(candidate)) {
    return candidate;
  }
  return workspaceRoot ? path.join(workspaceRoot, candidate) : path.resolve(candidate);
}

function stringField(sourceRef: Record<string, unknown>, key: string): string | null {
  const value = sourceRef[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function deactivate(): void {}
