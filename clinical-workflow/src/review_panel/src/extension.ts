import * as fs from "fs/promises";
import * as path from "path";
import * as vscode from "vscode";
import {
  DecisionReceipt,
  ReviewPacket,
  validateDecisionReceiptForPacket,
  validateReviewPacket,
} from "./schema";
import { renderReviewPanelHtml, renderStatusHtml } from "./webview";

interface LoadedPacket {
  packet: ReviewPacket;
  filePath: string;
}

export function activate(context: vscode.ExtensionContext): void {
  const provider = new ReviewQueueProvider();
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(ReviewQueueProvider.viewType, provider),
    vscode.commands.registerCommand("clinicalReviewPanel.open", async () => {
      await vscode.commands.executeCommand("workbench.view.extension.clinicalReviewPanel");
    }),
  );
}

export function deactivate(): void {
  // No resources require explicit disposal.
}

class ReviewQueueProvider implements vscode.WebviewViewProvider {
  static readonly viewType = "clinicalReviewPanel.reviewQueue";

  private view?: vscode.WebviewView;
  private current?: LoadedPacket;

  async resolveWebviewView(webviewView: vscode.WebviewView): Promise<void> {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
    };

    webviewView.webview.onDidReceiveMessage(async (message: { type?: string; receipt?: DecisionReceipt }) => {
      if (message.type === "refresh") {
        await this.refresh();
      }
      if (message.type === "submitDecision" && message.receipt) {
        await this.submitDecision(message.receipt);
      }
    });

    await this.refresh();
  }

  private async refresh(): Promise<void> {
    if (!this.view) {
      return;
    }

    const nonce = getNonce();
    try {
      const workspaceRoot = getWorkspaceRoot();
      if (!workspaceRoot) {
        this.current = undefined;
        this.view.webview.html = renderStatusHtml(
          "No workspace folder",
          "Open the clinical workflow repository before using the review queue.",
          nonce,
        );
        return;
      }

      const queueDir = path.join(workspaceRoot, ".review_queue");
      const loaded = await loadNextPendingPacket(queueDir);
      this.current = loaded;
      if (!loaded) {
        this.view.webview.html = renderStatusHtml(
          "No pending review packets",
          "The .review_queue folder has no packet waiting for a decision receipt.",
          nonce,
        );
        return;
      }

      this.view.webview.html = renderReviewPanelHtml(loaded.packet, nonce);
    } catch (error) {
      this.current = undefined;
      this.view.webview.html = renderStatusHtml("Cannot load review queue", getErrorMessage(error), nonce);
    }
  }

  private async submitDecision(receipt: DecisionReceipt): Promise<void> {
    if (!this.current || !this.view) {
      vscode.window.showErrorMessage("No active review packet is loaded.");
      return;
    }

    const errors = validateDecisionReceiptForPacket(this.current.packet, receipt);
    if (errors.length) {
      await this.view.webview.postMessage({ type: "validationErrors", errors });
      return;
    }

    const decisionPath = path.join(
      path.dirname(this.current.filePath),
      `${this.current.packet.review_id}_decision.json`,
    );
    await fs.writeFile(decisionPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
    vscode.window.showInformationMessage(`Decision receipt written: ${path.basename(decisionPath)}`);
    await this.refresh();
  }
}

async function loadNextPendingPacket(queueDir: string): Promise<LoadedPacket | undefined> {
  let entries: string[];
  try {
    entries = await fs.readdir(queueDir);
  } catch (error) {
    if (isNodeError(error) && error.code === "ENOENT") {
      return undefined;
    }
    throw error;
  }

  const entrySet = new Set(entries);
  const candidates = entries
    .filter((entry) => entry.endsWith(".json"))
    .filter((entry) => !isReceiptFile(entry))
    .sort((left, right) => left.localeCompare(right));

  for (const candidate of candidates) {
    const filePath = path.join(queueDir, candidate);
    const raw = await fs.readFile(filePath, "utf8");
    const parsed = JSON.parse(raw) as ReviewPacket;
    const errors = validateReviewPacket(parsed);
    if (errors.length) {
      throw new Error(`${candidate} is not a valid ReviewPacket: ${errors.join("; ")}`);
    }
    if (entrySet.has(`${parsed.review_id}_decision.json`)) {
      continue;
    }
    return { packet: parsed, filePath };
  }

  return undefined;
}

function isReceiptFile(fileName: string): boolean {
  return (
    fileName === ".queue_scope.json" ||
    fileName.endsWith("_decision.json") ||
    fileName.includes("_decision_") ||
    fileName.endsWith("_clarification.json") ||
    fileName.endsWith("_confirmation.json") ||
    fileName.endsWith("_rework.json") ||
    fileName.endsWith("_conflict.json") ||
    fileName.endsWith("_corrupt.json")
  );
}

function getWorkspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let nonce = "";
  for (let index = 0; index < 32; index += 1) {
    nonce += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return nonce;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return typeof error === "object" && error !== null && "code" in error;
}
