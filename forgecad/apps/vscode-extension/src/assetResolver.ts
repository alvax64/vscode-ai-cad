import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

export type ForgeCADAssetRoots = {
  forgecadRoot: string;
  corePath: string;
  servicePath: string;
  rendererPath: string;
  source: "vendor" | "monorepo";
};

export function resolveAssetRoots(context: vscode.ExtensionContext): ForgeCADAssetRoots {
  const vendorRoot = path.join(context.extensionPath, "vendor");
  const vendor = rootsFromBase(vendorRoot, "vendor");
  if (rootsExist(vendor)) {
    return vendor;
  }

  const monorepoRoot = path.resolve(context.extensionPath, "..", "..");
  const monorepo = {
    forgecadRoot: monorepoRoot,
    corePath: path.join(monorepoRoot, "python", "forgecad_core"),
    servicePath: path.join(monorepoRoot, "python", "forgecad_service"),
    rendererPath: path.join(monorepoRoot, "packages", "webview-renderer"),
    source: "monorepo" as const
  };
  if (rootsExist(monorepo)) {
    return monorepo;
  }

  throw new Error(
    "ForgeCAD extension assets are missing. Run `npm run package-assets` in " +
      "forgecad/apps/vscode-extension or install an extension build that includes vendor assets."
  );
}

function rootsFromBase(base: string, source: "vendor"): ForgeCADAssetRoots {
  return {
    forgecadRoot: base,
    corePath: path.join(base, "python", "forgecad_core"),
    servicePath: path.join(base, "python", "forgecad_service"),
    rendererPath: path.join(base, "webview-renderer"),
    source
  };
}

function rootsExist(roots: ForgeCADAssetRoots): boolean {
  return (
    fs.existsSync(path.join(roots.corePath, "forgecad_core")) &&
    fs.existsSync(path.join(roots.servicePath, "forgecad_service")) &&
    fs.existsSync(path.join(roots.rendererPath, "dist", "forgecad-renderer-client.js"))
  );
}
