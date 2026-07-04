// Pure helpers over the schema_version 1 data contract — no vscode
// imports, so these are node-testable against the real artifacts.
//
// The extension consumes a *data root*: a directory holding
// code-model/ + data-model/ (+ meta/, and — in an unpacked
// vista-meta-data-v1 release bundle — manifest.json). Both the dev
// tree (vista/export) and the published bundle satisfy it.

export interface DataVintage {
  label: string; // short UI label, e.g. "data-v1 · 23d037f1" or "dev tree · schema v1"
  schemaVersion: number | null;
  contentHash: string | null;
  detail: string; // tooltip-sized provenance line
}

// manifest.json (the in-bundle release manifest, V7) — authoritative
// when present: it pins schema_version, content_hash and the R3
// engine identity of the data being read.
export function vintageFromManifest(doc: {
  tag?: string;
  schema_version?: number;
  content_hash?: string;
  engine?: string;
  engine_image?: string;
  extraction_timestamp?: string;
}): DataVintage {
  const hash = doc.content_hash ?? null;
  return {
    label: `${doc.tag ?? 'release'} · ${hash ? hash.slice(0, 8) : '?'}`,
    schemaVersion: doc.schema_version ?? null,
    contentHash: hash,
    detail:
      `vista-meta ${doc.tag ?? 'release'} — schema_version ${doc.schema_version ?? '?'}, ` +
      `content_hash ${hash ?? '?'}, engine ${doc.engine ?? '?'} ` +
      `(${doc.engine_image ?? '?'}), extracted ${doc.extraction_timestamp ?? '?'}`,
  };
}

// meta/column-manifest.json (V3) — what a dev tree carries; no data
// identity, but it still pins the schema version.
export function vintageFromColumnManifest(doc: { schema_version?: number }): DataVintage {
  return {
    label: `dev tree · schema v${doc.schema_version ?? '?'}`,
    schemaVersion: doc.schema_version ?? null,
    contentHash: null,
    detail:
      `vista-meta dev tree — schema_version ${doc.schema_version ?? '?'} ` +
      `(no manifest.json; data identity unpinned)`,
  };
}

// files.tsv global_root is a storage root like `^DPT(` or `^DD("IX",`;
// routine-globals.tsv global_name is the bare name (`DPT`). The join
// key between them is the root's base name.
export function globalBase(globalRoot: string): string {
  const noCaret = globalRoot.startsWith('^') ? globalRoot.slice(1) : globalRoot;
  const paren = noCaret.indexOf('(');
  return paren === -1 ? noCaret : noCaret.slice(0, paren);
}
