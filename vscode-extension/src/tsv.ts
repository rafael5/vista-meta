// Lazy TSV reader. One file, read once, cached until reloadAll().
//
// The code-model directory is large (~1M rows across all files); we
// never need all of them at once, and loading is cheap enough that
// we don't bother with streaming. Worst case: routine-calls.tsv at
// ~20MB reads in ~200ms on the first access and stays warm.

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

export type Row = Record<string, string>;

const cache: Map<string, Row[]> = new Map();

function codeModelDir(): string {
  const cfg = vscode.workspace.getConfiguration('vistaMeta');
  const rel = cfg.get<string>('codeModelPath', 'vista/export/code-model');
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '.';
  return path.join(root, rel);
}

export function vistaMHostDir(): string {
  const cfg = vscode.workspace.getConfiguration('vistaMeta');
  const rel = cfg.get<string>('vistaMHostPath', 'vista/vista-m-host');
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '.';
  return path.join(root, rel);
}

export function topN(): number {
  const cfg = vscode.workspace.getConfiguration('vistaMeta');
  return cfg.get<number>('topN', 15);
}

export function reloadAll(): void {
  cache.clear();
}

export function load(name: string): Row[] {
  const cached = cache.get(name);
  if (cached) return cached;

  const file = path.join(codeModelDir(), name);
  let rows: Row[] = [];
  try {
    const text = fs.readFileSync(file, 'utf-8');
    const lines = text.split('\n');
    if (lines.length < 2) {
      cache.set(name, rows);
      return rows;
    }
    const header = lines[0].split('\t');
    for (let i = 1; i < lines.length; i++) {
      const ln = lines[i];
      if (!ln) continue;
      const parts = ln.split('\t');
      const row: Row = {};
      for (let j = 0; j < header.length; j++) {
        row[header[j]] = parts[j] ?? '';
      }
      rows.push(row);
    }
  } catch (err) {
    // File missing is not fatal — sidebar will show what it can
    rows = [];
  }
  cache.set(name, rows);
  return rows;
}

// Index helpers — O(n) scan is fine at this scale, but memoize the
// indexes we end up querying many times.
const indexCache: Map<string, Map<string, Row[]>> = new Map();

export function byColumn(name: string, col: string): Map<string, Row[]> {
  const key = `${name}::${col}`;
  const cached = indexCache.get(key);
  if (cached) return cached;
  const idx: Map<string, Row[]> = new Map();
  for (const row of load(name)) {
    const k = row[col];
    if (!k) continue;
    let arr = idx.get(k);
    if (!arr) {
      arr = [];
      idx.set(k, arr);
    }
    arr.push(row);
  }
  indexCache.set(key, idx);
  return idx;
}

export function clearIndexes(): void {
  indexCache.clear();
}
