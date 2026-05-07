// Hover provider for MUMPS files. All facts come from the same
// code-model TSVs the sidebar uses — no parsing, no container.
//
// What we hover:
//   - Routine name           (RTN, ^RTN)            -> routine card
//   - Tag^Routine            (TAG^RTN, $$TAG^RTN)   -> routine card + tag badge
//   - Tag in current routine (bare TAG at column 0) -> tag location + xindex hits
//   - Global reference       (^GLOBAL[(...)])       -> who-references summary
//
// Disambiguation rule: a token that exists in routines-comprehensive.tsv
// is a routine; otherwise an `^X` form is a global. Routines and FileMan
// globals do not collide in practice (e.g. ^DPT is a global; ^DGRP is a
// routine), so this is reliable.

import * as path from 'path';
import * as vscode from 'vscode';
import { byColumn, topN } from './tsv';

const TOKEN_RE =
  /\$?\$?[A-Za-z%][A-Za-z0-9]*(?:\^[A-Za-z%][A-Za-z0-9]*)?|\^[A-Za-z%][A-Za-z0-9]*/;

interface ParsedToken {
  raw: string;
  hasDollarDollar: boolean;
  tag: string | null;     // left side of ^, or bare ident if no ^
  routine: string | null; // right side of ^, or bare ident if it resolves
  isCaretGlobalForm: boolean; // started with ^ and no tag
}

function parseToken(raw: string): ParsedToken {
  let s = raw;
  let hasDollarDollar = false;
  if (s.startsWith('$$')) {
    hasDollarDollar = true;
    s = s.slice(2);
  }
  if (s.startsWith('^')) {
    return {
      raw,
      hasDollarDollar,
      tag: null,
      routine: s.slice(1),
      isCaretGlobalForm: true,
    };
  }
  const idx = s.indexOf('^');
  if (idx >= 0) {
    return {
      raw,
      hasDollarDollar,
      tag: s.slice(0, idx),
      routine: s.slice(idx + 1),
      isCaretGlobalForm: false,
    };
  }
  // Bare identifier — could be a routine name or a tag in the current
  // routine. Caller decides.
  return {
    raw,
    hasDollarDollar,
    tag: s,
    routine: s,
    isCaretGlobalForm: false,
  };
}

function followsRoutineCallVerb(line: string, col: number): boolean {
  // Looks back from the token position; if the previous non-space is
  // D, G, J, DO, GOTO, JOB (case-insensitive), this is a routine call.
  const prefix = line.slice(0, col).trimEnd();
  return /(?:^|\s|:)(?:D|DO|G|GOTO|J|JOB)$/i.test(prefix);
}

function buildRoutineHover(routineName: string, tagHint: string | null): vscode.MarkdownString | null {
  const byName = byColumn('routines-comprehensive.tsv', 'routine_name');
  const rows = byName.get(routineName);
  if (!rows || rows.length === 0) return null;
  const r = rows[0];

  const md = new vscode.MarkdownString();
  md.isTrusted = true;
  md.supportHtml = false;

  md.appendMarkdown(`**Routine \`${routineName}\`** — ${r['package'] || '(no package)'}\n\n`);

  const facts: string[] = [];
  const lc = r['line_count']; if (lc) facts.push(`${lc} lines`);
  const tc = r['tag_count']; if (tc) facts.push(`${tc} tags`);
  const inDeg = r['in_degree']; if (inDeg) facts.push(`in-degree ${inDeg}`);
  const outDeg = r['out_degree']; if (outDeg) facts.push(`out-degree ${outDeg}`);
  const rpc = r['rpc_count']; if (rpc && rpc !== '0') facts.push(`${rpc} RPC${rpc === '1' ? '' : 's'}`);
  const opt = r['option_count']; if (opt && opt !== '0') facts.push(`${opt} option${opt === '1' ? '' : 's'}`);
  const dg = r['distinct_globals_touched']; if (dg && dg !== '0') facts.push(`${dg} globals`);
  if (facts.length) md.appendMarkdown(facts.join(' · ') + '\n\n');

  if (tagHint) {
    const tagsByRoutine = byColumn('xindex-tags.tsv', 'routine');
    const tagRows = tagsByRoutine.get(routineName) ?? [];
    const has = tagRows.some(t => t['tag'] === tagHint);
    md.appendMarkdown(
      has
        ? `**Tag** \`${tagHint}\` — found in routine\n\n`
        : `**Tag** \`${tagHint}\` — *not found in xindex-tags.tsv* (could be a label in a comment or a missing extract)\n\n`,
    );
  }

  const limit = Math.max(3, Math.min(topN(), 8));

  // Top callers
  const callsByCallee = byColumn('routine-calls.tsv', 'callee_routine');
  const callerRows = callsByCallee.get(routineName) ?? [];
  if (callerRows.length) {
    const agg = new Map<string, number>();
    for (const cr of callerRows) {
      const k = cr['caller_name'] || '';
      const n = parseInt(cr['ref_count'] || '0', 10);
      agg.set(k, (agg.get(k) || 0) + n);
    }
    const top = [...agg.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit);
    md.appendMarkdown(`**Top callers** (${callerRows.length} total)\n\n`);
    for (const [name, n] of top) md.appendMarkdown(`- \`${name}\` × ${n}\n`);
    md.appendMarkdown('\n');
  }

  // Top callees
  const callsByCaller = byColumn('routine-calls.tsv', 'caller_name');
  const calleeRows = callsByCaller.get(routineName) ?? [];
  if (calleeRows.length) {
    const top = [...calleeRows]
      .sort((a, b) => parseInt(b['ref_count'] || '0', 10) - parseInt(a['ref_count'] || '0', 10))
      .slice(0, limit);
    md.appendMarkdown(`**Top callees** (${calleeRows.length} total)\n\n`);
    for (const cr of top) {
      const tag = cr['callee_tag'] || '';
      const rt = cr['callee_routine'] || '';
      const ref = cr['ref_count'] || '0';
      md.appendMarkdown(`- \`${tag ? tag + '^' : '^'}${rt}\` × ${ref}\n`);
    }
    md.appendMarkdown('\n');
  }

  // Top globals touched
  const globalsByRoutine = byColumn('routine-globals.tsv', 'routine_name');
  const globalRows = globalsByRoutine.get(routineName) ?? [];
  if (globalRows.length) {
    const top = [...globalRows]
      .sort((a, b) => parseInt(b['ref_count'] || '0', 10) - parseInt(a['ref_count'] || '0', 10))
      .slice(0, Math.min(5, limit));
    md.appendMarkdown(`**Top globals**\n\n`);
    for (const gr of top) {
      md.appendMarkdown(`- \`${gr['global_name']}\` × ${gr['ref_count']}\n`);
    }
    md.appendMarkdown('\n');
  }

  // Source path footer
  const src = r['source_path'];
  if (src) md.appendMarkdown(`*${path.basename(src)}*\n`);

  return md;
}

function buildGlobalHover(globalName: string): vscode.MarkdownString | null {
  // routine-globals.tsv stores globals as e.g. "^DPT" — match exactly.
  const key = globalName.startsWith('^') ? globalName : '^' + globalName;
  const byGlobal = byColumn('routine-globals.tsv', 'global_name');
  const rows = byGlobal.get(key);
  if (!rows || rows.length === 0) return null;

  const md = new vscode.MarkdownString();
  md.isTrusted = true;

  let totalRefs = 0;
  for (const r of rows) totalRefs += parseInt(r['ref_count'] || '0', 10);

  md.appendMarkdown(`**Global \`${key}\`**\n\n`);
  md.appendMarkdown(
    `Referenced by **${rows.length}** routines · **${totalRefs}** total refs\n\n`,
  );

  const top = [...rows]
    .sort((a, b) => parseInt(b['ref_count'] || '0', 10) - parseInt(a['ref_count'] || '0', 10))
    .slice(0, Math.max(5, Math.min(topN(), 10)));
  md.appendMarkdown(`**Top consumers**\n\n`);
  for (const r of top) {
    md.appendMarkdown(`- \`${r['routine_name']}\` (${r['package'] || '?'}) × ${r['ref_count']}\n`);
  }

  return md;
}

function buildTagInRoutineHover(routineName: string, tag: string): vscode.MarkdownString | null {
  const tagsByRoutine = byColumn('xindex-tags.tsv', 'routine');
  const tagRows = tagsByRoutine.get(routineName) ?? [];
  const exact = tagRows.find(t => t['tag'] === tag);
  if (!exact) return null;

  const md = new vscode.MarkdownString();
  md.isTrusted = true;
  md.appendMarkdown(`**Tag \`${tag}\`** in routine \`${routineName}\`\n\n`);

  // Cross-routine callers of this entry point
  const callsByCallee = byColumn('routine-calls.tsv', 'callee_routine');
  const callerRows = (callsByCallee.get(routineName) ?? []).filter(
    r => r['callee_tag'] === tag,
  );
  if (callerRows.length) {
    md.appendMarkdown(
      `Called as \`${tag}^${routineName}\` by **${callerRows.length}** caller${callerRows.length === 1 ? '' : 's'}:\n\n`,
    );
    const agg = new Map<string, number>();
    for (const cr of callerRows) {
      const k = cr['caller_name'] || '';
      const n = parseInt(cr['ref_count'] || '0', 10);
      agg.set(k, (agg.get(k) || 0) + n);
    }
    const top = [...agg.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
    for (const [name, n] of top) md.appendMarkdown(`- \`${name}\` × ${n}\n`);
  } else {
    md.appendMarkdown(`*No external callers found in routine-calls.tsv* — likely a private/internal label.\n`);
  }

  return md;
}

export class VistaMetaHoverProvider implements vscode.HoverProvider {
  provideHover(
    doc: vscode.TextDocument,
    pos: vscode.Position,
  ): vscode.ProviderResult<vscode.Hover> {
    const range = doc.getWordRangeAtPosition(pos, TOKEN_RE);
    if (!range) return null;
    const raw = doc.getText(range);
    const parsed = parseToken(raw);
    const line = doc.lineAt(pos.line).text;

    // Case 1: TAG^ROUTINE or $$TAG^ROUTINE — always a routine call
    if (parsed.tag && parsed.routine && parsed.raw.includes('^') && !parsed.isCaretGlobalForm) {
      const md = buildRoutineHover(parsed.routine, parsed.tag);
      return md ? new vscode.Hover(md, range) : null;
    }

    // Case 2: ^X — could be a routine call or a global
    if (parsed.isCaretGlobalForm && parsed.routine) {
      const byName = byColumn('routines-comprehensive.tsv', 'routine_name');
      const isRoutine = byName.has(parsed.routine);
      // If a `(` follows immediately, it's a global, even if a routine
      // by the same name exists (rare but possible).
      const after = line[range.end.character] || '';
      if (isRoutine && after !== '(') {
        const md = buildRoutineHover(parsed.routine, null);
        return md ? new vscode.Hover(md, range) : null;
      }
      const md = buildGlobalHover(parsed.routine);
      return md ? new vscode.Hover(md, range) : null;
    }

    // Case 3: bare identifier — routine name elsewhere, or tag here
    if (parsed.routine && !parsed.raw.includes('^')) {
      // Bare identifier at column 0 is a tag of the current routine
      const atLineStart = range.start.character === 0;
      if (atLineStart) {
        const thisRoutine = path.basename(doc.fileName, '.m');
        const md = buildTagInRoutineHover(thisRoutine, parsed.routine);
        if (md) return new vscode.Hover(md, range);
      }
      // After a D/DO/G/GOTO/J/JOB verb, treat as routine call shorthand
      if (followsRoutineCallVerb(line, range.start.character)) {
        const md = buildRoutineHover(parsed.routine, null);
        return md ? new vscode.Hover(md, range) : null;
      }
      // Otherwise, only resolve to a routine if a routine of that exact
      // name actually exists (avoid noisy hovers on local variables).
      const byName = byColumn('routines-comprehensive.tsv', 'routine_name');
      if (byName.has(parsed.routine)) {
        const md = buildRoutineHover(parsed.routine, null);
        return md ? new vscode.Hover(md, range) : null;
      }
    }

    return null;
  }
}
