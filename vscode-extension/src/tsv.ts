// Lazy TSV reader. One file, read once, cached until reloadAll().
//
// The code-model directory is large (~1M rows across all files); we
// never need all of them at once, and loading is cheap enough that
// we don't bother with streaming. Worst case: routine-calls.tsv at
// ~20MB reads in ~200ms on the first access and stays warm.

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';
import {
  DataVintage,
  vintageFromColumnManifest,
  vintageFromManifest,
} from './model';

export type Row = Record<string, string>;

const cache: Map<string, Row[]> = new Map();

// Resolve a vista-meta data dir. Tries, in order:
//   1. An absolute / tilde-prefixed config value (used as-is)
//   2. Walking up from the active file until ``<dir>/<rel>`` exists —
//      this is what makes the sidebar work when you've drilled into a
//      VistA file inside vista-meta from a parent workspace like
//      ``~/projects``
//   3. Walking up from each workspaceFolder (covers folder roots that
//      aren't the active file's project)
//   4. Falling back to ``workspaceFolders[0] / rel`` so the previous
//      behavior still applies when the file isn't open yet
function findUpward(start: string, rel: string): string | null {
  let dir = fs.statSync(start, { throwIfNoEntry: false })?.isDirectory()
    ? start
    : path.dirname(start);
  for (let depth = 0; depth < 64; depth++) {
    const cand = path.join(dir, rel);
    if (fs.existsSync(cand)) return cand;
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
  return null;
}

function resolveDataDir(configKey: string, defaultRel: string): string {
  const cfg = vscode.workspace.getConfiguration('vistaCompass');
  const rel = cfg.get<string>(configKey, defaultRel);

  // (1) absolute / tilde-prefixed — use directly.
  if (rel.startsWith('/') || rel.startsWith('~')) {
    return rel.replace(/^~/, process.env.HOME ?? '~');
  }

  // (2) walk up from the active editor's file.
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    const found = findUpward(editor.document.uri.fsPath, rel);
    if (found) return found;
  }

  // (3) walk up from each workspace folder.
  for (const wf of vscode.workspace.workspaceFolders ?? []) {
    const found = findUpward(wf.uri.fsPath, rel);
    if (found) return found;
  }

  // (4) legacy fallback.
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? '.';
  return path.join(root, rel);
}

export type Model = 'code-model' | 'data-model';

// The data ROOT: a directory holding code-model/ + data-model/ — the
// dev tree (vista/export) or an unpacked vista-meta-data-v1 release
// bundle. Resolution order:
//   1. vistaCompass.dataPath (absolute/tilde or workspace-relative,
//      same walk-up rules as the legacy key)
//   2. auto-discovery of `vista/export`, then `vista-meta-data-v1`
//   3. the legacy codeModelPath's parent (back-compat)
// Validity = <root>/code-model/routines.tsv exists.
function isDataRoot(dir: string): boolean {
  return fs.existsSync(path.join(dir, 'code-model', 'routines.tsv'));
}

function dataRoot(): string {
  const cfg = vscode.workspace.getConfiguration('vistaCompass');
  const configured = cfg.get<string>('dataPath', '');
  const candidates = configured
    ? [configured]
    : ['vista/export', 'vista-meta-data-v1'];
  for (const rel of candidates) {
    const dir = resolveDataDir('dataPath', rel);
    if (isDataRoot(dir)) return dir;
  }
  // legacy fallback: the old code-model key names the child directly
  return path.dirname(resolveDataDir('codeModelPath', 'vista/export/code-model'));
}

export function modelDir(model: Model): string {
  return path.join(dataRoot(), model);
}

function codeModelDir(): string {
  return modelDir('code-model');
}

// The vintage of the data being read (V7 manifest.json in a bundle,
// V3 meta/column-manifest.json in the dev tree). Cached with the TSVs.
let vintageCache: DataVintage | null | undefined;

export function dataVintage(): DataVintage | null {
  if (vintageCache !== undefined) return vintageCache;
  const root = dataRoot();
  try {
    const manifest = path.join(root, 'manifest.json');
    if (fs.existsSync(manifest)) {
      vintageCache = vintageFromManifest(JSON.parse(fs.readFileSync(manifest, 'utf-8')));
      return vintageCache;
    }
    const colManifest = path.join(root, 'meta', 'column-manifest.json');
    if (fs.existsSync(colManifest)) {
      vintageCache = vintageFromColumnManifest(
        JSON.parse(fs.readFileSync(colManifest, 'utf-8')),
      );
      return vintageCache;
    }
  } catch {
    // fall through — a broken manifest reads as "unknown", not a crash
  }
  vintageCache = null;
  return vintageCache;
}

export function vistaMHostDir(): string {
  return resolveDataDir('vistaMHostPath', 'vista/vista-m-host');
}

export function topN(): number {
  const cfg = vscode.workspace.getConfiguration('vistaCompass');
  return cfg.get<number>('topN', 15);
}

export function reloadAll(): void {
  cache.clear();
  vintageCache = undefined;
}

export function load(name: string): Row[] {
  return loadModel('code-model', name);
}

export function loadModel(model: Model, name: string): Row[] {
  // Cache keyed by absolute path: the data root can change as the
  // active file moves across projects, so name alone isn't enough.
  const file = path.join(modelDir(model), name);
  const cached = cache.get(file);
  if (cached) return cached;

  let rows: Row[] = [];
  try {
    const text = fs.readFileSync(file, 'utf-8');
    const lines = text.split('\n');
    if (lines.length < 2) {
      cache.set(file, rows);
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
  cache.set(file, rows);
  return rows;
}

// Index helpers — O(n) scan is fine at this scale, but memoize the
// indexes we end up querying many times.
const indexCache: Map<string, Map<string, Row[]>> = new Map();

export function byColumn(name: string, col: string): Map<string, Row[]> {
  return byColumnIn('code-model', name, col);
}

export function byColumnIn(model: Model, name: string, col: string): Map<string, Row[]> {
  // Key by absolute path so a data-root change invalidates indexes.
  const file = path.join(modelDir(model), name);
  const key = `${file}::${col}`;
  const cached = indexCache.get(key);
  if (cached) return cached;
  const idx: Map<string, Row[]> = new Map();
  for (const row of loadModel(model, name)) {
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
