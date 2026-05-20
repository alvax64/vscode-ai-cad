"use strict";

const vscode = require("vscode");

function createOutput() {
  const channel = vscode.window.createOutputChannel("ForgeCAD");
  return {
    channel,
    info(message) {
      channel.appendLine(`[info] ${message}`);
    },
    warn(message) {
      channel.appendLine(`[warn] ${message}`);
    },
    error(message) {
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

module.exports = {
  createOutput
};
