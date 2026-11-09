import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import * as vscode from "vscode";

type Status = "ready" | "working" | "waiting" | "input" | "error" | "offline" | "starting";

interface AgentSnapshot {
  pid: number;
  kind: string;
  label: string;
  status: Status;
  attention: boolean;
  activity: string;
}

interface SessionSnapshot {
  id: number;
  key: string;
  name: string;
  short: string;
  status: Status;
  attention: boolean;
  activity: string;
  project: string;
  directory: string;
  pid: number;
  terminal: string;
  terminal_pid: number | null;
  agents: AgentSnapshot[];
}

interface Snapshot {
  schema_version: number;
  diagnostic: string | null;
  active: number;
  counts: Record<Status, number>;
  sessions: SessionSnapshot[];
}

const SYMBOL: Record<Status, string> = {
  ready: "●", working: "◐", waiting: "◇", input: "◆", error: "▲",
  offline: "○", starting: "◌",
};

const LABEL: Record<Status, string> = {
  ready: "READY", working: "WORKING", waiting: "WAITING", input: "INPUT",
  error: "STOP", offline: "OFFLINE", starting: "STARTING",
};

const ICON: Record<Status, {name: string; color: string}> = {
  ready: {name: "pass-filled", color: "testing.iconPassed"},
  working: {name: "sync~spin", color: "charts.yellow"},
  waiting: {name: "clock", color: "charts.yellow"},
  input: {name: "question", color: "charts.yellow"},
  error: {name: "error", color: "testing.iconFailed"},
  offline: {name: "circle-slash", color: "disabledForeground"},
  starting: {name: "loading~spin", color: "charts.blue"},
};

type Node = {kind: "session"; session: SessionSnapshot} | {
  kind: "agent"; session: SessionSnapshot; agent: AgentSnapshot;
};

class SessionsProvider implements vscode.TreeDataProvider<Node>, vscode.Disposable {
  private readonly changed = new vscode.EventEmitter<Node | undefined | void>();
  readonly onDidChangeTreeData = this.changed.event;
  private sessions: SessionSnapshot[] = [];
  private diagnostic: string | null = null;

  update(snapshot: Snapshot): void {
    this.sessions = snapshot.sessions;
    this.diagnostic = snapshot.diagnostic;
    this.changed.fire();
  }

  refresh(): void { this.changed.fire(); }

  getTreeItem(node: Node): vscode.TreeItem {
    const status = node.kind === "session" ? node.session.status : node.agent.status;
    const item = new vscode.TreeItem(
      node.kind === "session" ? (node.session.name || node.session.terminal) : node.agent.label,
      node.kind === "session" && node.session.agents.length
        ? vscode.TreeItemCollapsibleState.Expanded
        : vscode.TreeItemCollapsibleState.None,
    );
    item.id = node.kind === "session" ? `session:${node.session.key}` : `agent:${node.agent.pid}`;
    item.iconPath = new vscode.ThemeIcon(ICON[status].name, new vscode.ThemeColor(ICON[status].color));
    item.description = node.kind === "session"
      ? `${SYMBOL[status]} ${LABEL[status]} · ${node.session.terminal}`
      : `${SYMBOL[status]} ${LABEL[status]} · ${node.agent.activity}`;
    item.tooltip = this.tooltip(node);
    item.contextValue = node.kind;
    item.command = {
      command: "watchai.revealSession",
      title: "Reveal session terminal",
      arguments: [node.session],
    };
    return item;
  }

  getChildren(node?: Node): Node[] {
    if (!node) return this.sessions.map(session => ({kind: "session", session}));
    if (node.kind === "agent") return [];
    return node.session.agents.map(agent => ({kind: "agent", session: node.session, agent}));
  }

  getParent(node: Node): Node | undefined {
    return node.kind === "agent" ? {kind: "session", session: node.session} : undefined;
  }

  emptyMessage(): string {
    if (!this.diagnostic) return "No AI session detected";
    const messages: Record<string, string> = {
      "sem-psutil": "psutil is missing from the WatchAI environment",
      "restrito": "WatchAI cannot read the process table",
      "erro": "The WatchAI process scan failed",
    };
    return messages[this.diagnostic] ?? `WatchAI: ${this.diagnostic}`;
  }

  private tooltip(node: Node): vscode.MarkdownString {
    const session = node.session;
    const status = node.kind === "session" ? session.status : node.agent.status;
    const activity = node.kind === "session" ? session.activity : node.agent.activity;
    const markdown = new vscode.MarkdownString(undefined, true);
    markdown.appendMarkdown(`**${SYMBOL[status]} ${LABEL[status]}**  \n`);
    markdown.appendMarkdown(`${activity || "—"}  \n`);
    markdown.appendMarkdown(`Terminal: \`${session.terminal || "—"}\`  \n`);
    if (session.directory) markdown.appendMarkdown(`Directory: \`${session.directory}\``);
    return markdown;
  }

  dispose(): void { this.changed.dispose(); }
}

class Monitor implements vscode.Disposable {
  private process: ChildProcessWithoutNullStreams | undefined;
  private buffer = "";
  private stopped = false;
  private restartTimer: NodeJS.Timeout | undefined;
  private previous = new Map<string, Status>();

  constructor(
    private readonly onSnapshot: (snapshot: Snapshot) => void,
    private readonly output: vscode.OutputChannel,
  ) {}

  start(): void {
    this.stopProcess();
    this.stopped = false;
    const command = vscode.workspace.getConfiguration("watchai").get<string>("command", "watchai").trim();
    this.output.appendLine(`Starting: ${command} --json`);
    const child = spawn(command, ["--json"], {stdio: ["pipe", "pipe", "pipe"], windowsHide: true});
    child.stdin.end();
    this.process = child;
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", chunk => this.consume(String(chunk)));
    child.stderr.on("data", chunk => this.output.append(String(chunk)));
    child.on("error", error => this.missingCore(error));
    child.on("exit", (code, signal) => {
      if (this.process === child) this.process = undefined;
      this.output.appendLine(`WatchAI core exited (${code ?? signal ?? "unknown"}).`);
      if (!this.stopped) this.restartTimer = setTimeout(() => this.start(), 3000);
    });
  }

  restart(): void { this.start(); }

  private consume(chunk: string): void {
    this.buffer += chunk;
    const lines = this.buffer.split(/\r?\n/);
    this.buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const snapshot = JSON.parse(line) as Snapshot;
        if (snapshot.schema_version !== 1 || !Array.isArray(snapshot.sessions)) {
          throw new Error("unsupported snapshot schema");
        }
        this.notifyTransitions(snapshot);
        this.onSnapshot(snapshot);
      } catch (error) {
        this.output.appendLine(`Invalid WatchAI JSON: ${String(error)}`);
      }
    }
  }

  private notifyTransitions(snapshot: Snapshot): void {
    const enabled = vscode.workspace.getConfiguration("watchai").get<boolean>("notifications", true);
    const next = new Map<string, Status>();
    for (const session of snapshot.sessions) {
      next.set(session.key, session.status);
      const before = this.previous.get(session.key);
      if (!enabled || before === undefined || before === "starting" || before === session.status) continue;
      const message = `${session.name || session.terminal}: ${session.activity}`;
      if (session.status === "error") void vscode.window.showErrorMessage(`WatchAI · STOP · ${message}`);
      else if (session.status === "input") void vscode.window.showWarningMessage(`WatchAI · INPUT · ${message}`);
      else if (session.status === "ready") void vscode.window.showInformationMessage(`WatchAI · READY · ${message}`);
    }
    this.previous = next;
  }

  private missingCore(error: Error): void {
    this.output.appendLine(`Cannot start WatchAI: ${error.message}`);
    void vscode.window.showWarningMessage(
      "WatchAI core was not found. Install it from the public source repository.",
      "Copy install command", "Open repository",
    ).then(choice => {
      if (choice === "Copy install command") void vscode.commands.executeCommand("watchai.copyInstallCommand");
      if (choice === "Open repository") void vscode.env.openExternal(vscode.Uri.parse("https://github.com/LeandroDukievicz/WatchAI#instalação"));
    });
  }

  private stopProcess(): void {
    if (this.restartTimer) clearTimeout(this.restartTimer);
    this.restartTimer = undefined;
    this.buffer = "";
    this.process?.kill();
    this.process = undefined;
  }

  dispose(): void {
    this.stopped = true;
    this.stopProcess();
  }
}

async function revealSession(session: SessionSnapshot): Promise<void> {
  if (session.terminal_pid === null) {
    void vscode.window.showWarningMessage("This session does not expose a terminal process ID.");
    return;
  }
  const terminals = await Promise.all(vscode.window.terminals.map(async terminal => ({
    terminal,
    pid: await terminal.processId,
  })));
  const match = terminals.find(candidate => candidate.pid === session.terminal_pid);
  if (!match) {
    void vscode.window.showWarningMessage(
      `The terminal ${session.terminal} is not an integrated terminal of this VS Code window.`,
    );
    return;
  }
  match.terminal.show(false);
}

function statusText(snapshot: Snapshot): string {
  const order: Status[] = ["error", "input", "ready", "waiting", "working", "starting"];
  const parts = order.filter(status => snapshot.counts[status]).map(
    status => `${SYMBOL[status]}${snapshot.counts[status]}`,
  );
  return parts.length ? `$(pulse) WatchAI ${parts.join(" ")}` : "$(circle-slash) WatchAI";
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel("WatchAI", {log: true});
  const provider = new SessionsProvider();
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 20);
  status.name = "WatchAI sessions";
  status.command = "watchai.sessions.focus";
  status.text = "$(loading~spin) WatchAI";
  status.tooltip = "Open WatchAI sessions";
  status.show();
  const view = vscode.window.createTreeView("watchai.sessions", {treeDataProvider: provider, showCollapseAll: true});
  const monitor = new Monitor(snapshot => {
    provider.update(snapshot);
    status.text = statusText(snapshot);
    status.tooltip = snapshot.sessions.length
      ? `${snapshot.active} active WatchAI session(s)`
      : provider.emptyMessage();
    view.message = snapshot.sessions.length ? undefined : provider.emptyMessage();
  }, output);

  context.subscriptions.push(
    output, provider, status, view, monitor,
    vscode.commands.registerCommand("watchai.refresh", () => monitor.restart()),
    vscode.commands.registerCommand("watchai.revealSession", revealSession),
    vscode.commands.registerCommand("watchai.copyInstallCommand", async () => {
      const command = "pipx install git+https://github.com/LeandroDukievicz/WatchAI.git";
      await vscode.env.clipboard.writeText(command);
      void vscode.window.showInformationMessage("WatchAI installation command copied.");
    }),
    vscode.workspace.onDidChangeConfiguration(event => {
      if (event.affectsConfiguration("watchai.command")) monitor.restart();
    }),
  );
  monitor.start();
}

export function deactivate(): void {}
