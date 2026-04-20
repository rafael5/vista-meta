// Derive everything the sidebar needs about a given routine from the
// code-model TSVs.

import * as fs from 'fs';
import * as path from 'path';
import { byColumn, load, Row, vistaMHostDir } from './tsv';

export interface Tag {
  name: string;
  line: number;
}

export interface CalleeSummary {
  tag: string;
  routine: string;
  kind: string;
  refCount: number;
}

export interface CallerSummary {
  callerRoutine: string;
  callerPackage: string;
  tag: string;       // which tag in THIS routine they call
  refCount: number;
}

export interface GlobalUsage {
  globalName: string;
  refCount: number;
}

export interface XindexError {
  line: string;       // XINDEX uses "line" as a text field
  tagOffset: string;
  errorText: string;
  severity: string;   // F | W | I | S | ?
}

export interface RoutineInfo {
  routineName: string;
  package: string;
  sourcePath: string | null;   // host-absolute path under vista-m-host
  lineCount: number;
  inDegree: number;
  outDegree: number;
  rpcCount: number;
  optionCount: number;
  tags: Tag[];                 // parsed from the open file (not TSV)
  callees: CalleeSummary[];    // sorted desc by refCount
  callers: CallerSummary[];    // sorted desc by refCount
  globals: GlobalUsage[];      // sorted desc by refCount
  xindexErrors: XindexError[]; // from xindex-errors.tsv if present
}

function resolveSourcePath(row: Row): string | null {
  const containerPath = row['source_path'] || '';
  if (!containerPath) return null;
  // Map /opt/VistA-M/... -> vista/vista-m-host/...
  const host = containerPath.replace(
    /^\/opt\/VistA-M\//,
    '',
  );
  const p = path.join(vistaMHostDir(), host);
  return fs.existsSync(p) ? p : null;
}

function parseTags(filePath: string): Tag[] {
  try {
    const text = fs.readFileSync(filePath, 'utf-8');
    const lines = text.split('\n');
    const tags: Tag[] = [];
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i];
      if (i === 0) continue; // line 1 = routine header
      if (!ln) continue;
      const first = ln[0];
      if (first === ' ' || first === '\t' || first === ';') continue;
      const m = ln.match(/^([A-Za-z%][A-Za-z0-9]*|[0-9]+)/);
      if (m) {
        tags.push({ name: m[1], line: i + 1 });
      }
    }
    return tags;
  } catch {
    return [];
  }
}

function sevOf(errorText: string): string {
  const first = errorText.trim().charAt(0);
  return 'FWISE'.includes(first) ? first : '?';
}

export function analyze(routineName: string): RoutineInfo | null {
  // 1. Find the routine
  const byName = byColumn('routines-comprehensive.tsv', 'routine_name');
  const rows = byName.get(routineName);
  if (!rows || rows.length === 0) {
    return null;
  }
  const row = rows[0];
  const sourcePath = resolveSourcePath(row);

  // 2. Tags — parse from on-disk source if available
  const tags = sourcePath ? parseTags(sourcePath) : [];

  // 3. Callees — this routine calls out
  const callsByCaller = byColumn('routine-calls.tsv', 'caller_name');
  const calleeRows = callsByCaller.get(routineName) ?? [];
  const callees: CalleeSummary[] = calleeRows.map(r => ({
    tag: r['callee_tag'] || '',
    routine: r['callee_routine'] || '',
    kind: r['kind'] || '',
    refCount: parseInt(r['ref_count'] || '0', 10),
  }));
  callees.sort((a, b) => b.refCount - a.refCount);

  // 4. Callers — this routine is called by
  const callsByCallee = byColumn('routine-calls.tsv', 'callee_routine');
  const callerRows = callsByCallee.get(routineName) ?? [];
  const callerAgg: Map<string, CallerSummary> = new Map();
  for (const r of callerRows) {
    const key = r['caller_name'] || '';
    const existing = callerAgg.get(key);
    if (existing) {
      existing.refCount += parseInt(r['ref_count'] || '0', 10);
    } else {
      callerAgg.set(key, {
        callerRoutine: key,
        callerPackage: r['caller_package'] || '',
        tag: r['callee_tag'] || '',
        refCount: parseInt(r['ref_count'] || '0', 10),
      });
    }
  }
  const callers = Array.from(callerAgg.values());
  callers.sort((a, b) => b.refCount - a.refCount);

  // 5. Globals
  const globalsByRoutine = byColumn('routine-globals.tsv', 'routine_name');
  const globalRows = globalsByRoutine.get(routineName) ?? [];
  const globals: GlobalUsage[] = globalRows.map(r => ({
    globalName: r['global_name'] || '',
    refCount: parseInt(r['ref_count'] || '0', 10),
  }));
  globals.sort((a, b) => b.refCount - a.refCount);

  // 6. XINDEX errors (if TSV present)
  const errByRoutine = byColumn('xindex-errors.tsv', 'routine');
  const errRows = errByRoutine.get(routineName) ?? [];
  const xindexErrors: XindexError[] = errRows.map(r => ({
    line: r['line_text'] || '',
    tagOffset: r['tag_offset'] || '',
    errorText: r['error_text'] || '',
    severity: sevOf(r['error_text'] || ''),
  }));

  return {
    routineName,
    package: row['package'] || '',
    sourcePath,
    lineCount: parseInt(row['line_count'] || '0', 10),
    inDegree: parseInt(row['in_degree'] || '0', 10),
    outDegree: parseInt(row['out_degree'] || '0', 10),
    rpcCount: parseInt(row['rpc_count'] || '0', 10),
    optionCount: parseInt(row['option_count'] || '0', 10),
    tags,
    callees,
    callers,
    globals,
    xindexErrors,
  };
}

// Best-effort: extract routine name from the currently-open file's
// path + first line. Returns null if neither source works.
export function routineNameFromPath(filePath: string): string | null {
  const base = path.basename(filePath, '.m');
  if (base && /^[A-Za-z%][A-Za-z0-9]{0,7}$/.test(base)) {
    return base;
  }
  try {
    const first = fs.readFileSync(filePath, 'utf-8').split('\n')[0];
    const m = first.match(/^([A-Za-z%][A-Za-z0-9]*)/);
    return m ? m[1] : null;
  } catch {
    return null;
  }
}
