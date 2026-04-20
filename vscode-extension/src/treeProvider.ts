import * as path from 'path';
import * as vscode from 'vscode';
import { analyze, RoutineInfo, routineNameFromPath } from './routine';
import { byColumn, topN, vistaMHostDir } from './tsv';

/**
 * Sidebar TreeDataProvider. Hierarchy:
 *
 *   Routine <NAME>            — package, lines, in/out-degree
 *     ├─ Tags (N)             — each clickable, reveals line
 *     ├─ Callers (N)          — each clickable, opens the caller routine
 *     ├─ Callees (N)          — each clickable, opens the callee routine
 *     ├─ Globals (N)
 *     └─ XINDEX (N)           — each clickable, reveals line
 */
export class RoutineTreeProvider implements vscode.TreeDataProvider<Node> {
  private _onDidChange = new vscode.EventEmitter<Node | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  private info: RoutineInfo | null = null;
  private activeFile: string | null = null;

  setActiveFile(filePath: string | null): void {
    if (filePath === this.activeFile) return;
    this.activeFile = filePath;
    this.recomputeInfo();
    this._onDidChange.fire();
  }

  refresh(): void {
    this.recomputeInfo();
    this._onDidChange.fire();
  }

  private recomputeInfo(): void {
    if (!this.activeFile) {
      this.info = null;
      return;
    }
    const name = routineNameFromPath(this.activeFile);
    this.info = name ? analyze(name) : null;
  }

  getTreeItem(el: Node): vscode.TreeItem {
    return el.toTreeItem();
  }

  getChildren(el?: Node): Node[] {
    if (!this.info) {
      if (!this.activeFile) {
        return [new MessageNode('Open a VistA .m file to see its context.')];
      }
      return [new MessageNode(
        `Routine not found in code-model TSVs. ` +
        `Path: ${path.basename(this.activeFile)}. ` +
        `Run \`make sync-routines && make routines-comprehensive\`.`,
      )];
    }
    if (!el) {
      return this.rootNodes();
    }
    return el.children();
  }

  private rootNodes(): Node[] {
    const info = this.info!;
    const n = topN();
    const nodes: Node[] = [];

    nodes.push(new HeaderNode(info));

    if (info.tags.length > 0) {
      nodes.push(new SectionNode(
        `Tags (${info.tags.length})`,
        info.tags.slice(0, n).map(t => new TagNode(info, t)),
      ));
    }

    if (info.callers.length > 0) {
      nodes.push(new SectionNode(
        `Callers (${info.callers.length})`,
        info.callers.slice(0, n).map(c => new CallerNode(c)),
      ));
    }

    if (info.callees.length > 0) {
      nodes.push(new SectionNode(
        `Callees (${info.callees.length})`,
        info.callees.slice(0, n).map(c => new CalleeNode(c)),
      ));
    }

    if (info.globals.length > 0) {
      nodes.push(new SectionNode(
        `Globals (${info.globals.length})`,
        info.globals.slice(0, n).map(g => new GlobalNode(g)),
      ));
    }

    if (info.xindexErrors.length > 0) {
      nodes.push(new SectionNode(
        `XINDEX (${info.xindexErrors.length})`,
        info.xindexErrors.slice(0, n).map(e => new XindexNode(info, e)),
        true,
      ));
    }

    return nodes;
  }
}

// ── Node types ───────────────────────────────────────────────────────

abstract class Node {
  abstract toTreeItem(): vscode.TreeItem;
  children(): Node[] { return []; }
}

class HeaderNode extends Node {
  constructor(private readonly info: RoutineInfo) { super(); }

  toTreeItem(): vscode.TreeItem {
    const i = this.info;
    const label = `${i.routineName}  [${i.package}]`;
    const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
    const bits: string[] = [];
    bits.push(`${i.lineCount} lines`);
    bits.push(`in=${i.inDegree}`);
    bits.push(`out=${i.outDegree}`);
    if (i.rpcCount) bits.push(`RPC×${i.rpcCount}`);
    if (i.optionCount) bits.push(`OPT×${i.optionCount}`);
    item.description = bits.join(' · ');
    item.iconPath = new vscode.ThemeIcon('symbol-module');
    item.tooltip = `source: ${i.sourcePath ?? '(not synced)'}`;
    return item;
  }
}

class SectionNode extends Node {
  constructor(
    private readonly title: string,
    private readonly kids: Node[],
    private readonly expanded: boolean = false,
  ) { super(); }

  toTreeItem(): vscode.TreeItem {
    const state = this.expanded
      ? vscode.TreeItemCollapsibleState.Expanded
      : vscode.TreeItemCollapsibleState.Collapsed;
    const item = new vscode.TreeItem(this.title, state);
    item.iconPath = new vscode.ThemeIcon('list-tree');
    return item;
  }

  children(): Node[] { return this.kids; }
}

class MessageNode extends Node {
  constructor(private readonly msg: string) { super(); }
  toTreeItem(): vscode.TreeItem {
    const it = new vscode.TreeItem(this.msg);
    it.iconPath = new vscode.ThemeIcon('info');
    return it;
  }
}

class TagNode extends Node {
  constructor(
    private readonly info: RoutineInfo,
    private readonly tag: { name: string; line: number },
  ) { super(); }

  toTreeItem(): vscode.TreeItem {
    const it = new vscode.TreeItem(this.tag.name);
    it.description = `line ${this.tag.line}`;
    it.iconPath = new vscode.ThemeIcon('symbol-method');
    if (this.info.sourcePath) {
      it.command = {
        command: 'vscode.open',
        title: 'Open',
        arguments: [
          vscode.Uri.file(this.info.sourcePath),
          { selection: new vscode.Range(
              this.tag.line - 1, 0, this.tag.line - 1, 0,
          ) },
        ],
      };
    }
    return it;
  }
}

class CallerNode extends Node {
  constructor(private readonly c: {
    callerRoutine: string;
    callerPackage: string;
    refCount: number;
  }) { super(); }

  toTreeItem(): vscode.TreeItem {
    const it = new vscode.TreeItem(this.c.callerRoutine);
    it.description = `${this.c.callerPackage}  ×${this.c.refCount}`;
    it.iconPath = new vscode.ThemeIcon('arrow-small-right');
    const srcPath = resolveRoutinePath(this.c.callerRoutine);
    if (srcPath) {
      it.command = {
        command: 'vscode.open',
        title: 'Open caller',
        arguments: [vscode.Uri.file(srcPath)],
      };
    }
    return it;
  }
}

class CalleeNode extends Node {
  constructor(private readonly c: {
    tag: string;
    routine: string;
    kind: string;
    refCount: number;
  }) { super(); }

  toTreeItem(): vscode.TreeItem {
    const label = this.c.tag
      ? `${this.c.tag}^${this.c.routine}`
      : `^${this.c.routine}`;
    const it = new vscode.TreeItem(label);
    it.description = `${this.c.kind}  ×${this.c.refCount}`;
    it.iconPath = new vscode.ThemeIcon('arrow-small-left');
    const srcPath = resolveRoutinePath(this.c.routine);
    if (srcPath) {
      it.command = {
        command: 'vscode.open',
        title: 'Open callee',
        arguments: [vscode.Uri.file(srcPath)],
      };
    }
    return it;
  }
}

class GlobalNode extends Node {
  constructor(private readonly g: {
    globalName: string;
    refCount: number;
  }) { super(); }

  toTreeItem(): vscode.TreeItem {
    const it = new vscode.TreeItem(`^${this.g.globalName}`);
    it.description = `×${this.g.refCount}`;
    it.iconPath = new vscode.ThemeIcon('database');
    return it;
  }
}

class XindexNode extends Node {
  constructor(
    private readonly info: RoutineInfo,
    private readonly err: {
      line: string;
      tagOffset: string;
      errorText: string;
      severity: string;
    },
  ) { super(); }

  toTreeItem(): vscode.TreeItem {
    const it = new vscode.TreeItem(
      `[${this.err.severity}] ${this.err.errorText}`,
    );
    it.description = `${this.err.tagOffset}  line ${this.err.line}`;
    it.iconPath = new vscode.ThemeIcon(
      this.err.severity === 'F' ? 'error'
        : this.err.severity === 'W' ? 'warning'
          : 'info',
    );
    if (this.info.sourcePath && /^\d+$/.test(this.err.line)) {
      const l = parseInt(this.err.line, 10);
      it.command = {
        command: 'vscode.open',
        title: 'Reveal',
        arguments: [
          vscode.Uri.file(this.info.sourcePath),
          { selection: new vscode.Range(l - 1, 0, l - 1, 0) },
        ],
      };
    }
    return it;
  }
}

// ── helpers ──────────────────────────────────────────────────────────

function resolveRoutinePath(routineName: string): string | null {
  const byName = byColumn('routines-comprehensive.tsv', 'routine_name');
  const rows = byName.get(routineName);
  if (!rows || rows.length === 0) return null;
  const container = rows[0]['source_path'] || '';
  if (!container) return null;
  const host = container.replace(/^\/opt\/VistA-M\//, '');
  const p = path.join(vistaMHostDir(), host);
  return p;
}
