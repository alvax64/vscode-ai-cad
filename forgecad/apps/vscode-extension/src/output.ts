import * as vscode from "vscode";
import type { Output } from "./types";

export function createOutput(): Output {
  const channel = vscode.window.createOutputChannel("ForgeCAD");
  return {
    channel,
    info(message: string) {
      channel.appendLine(`[info] ${message}`);
    },
    warn(message: string) {
      channel.appendLine(`[warn] ${message}`);
    },
    error(message: string) {
      channel.appendLine(`[error] ${message}`);
    },
    show() {
      channel.show(true);
    },
    dispose() {
      channel.dispose();
    }
  };
}
