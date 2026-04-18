# ADR-001: Project identity and analytics scope

Date: 2026-04-17
Status: Accepted

## Context
Project originally framed as "vista-grpc" — a gRPC wrapper over FileMan's RPC Broker API. As the conversation progressed, the actual goal became clear: extract and normalize VistA metadata (FileMan DD, routine cross-refs, global structures including those bypassing FileMan). This is analytics work, not API wrapping.

## Decision
Rename project to `vista-meta`. Drop all gRPC references from spec. Scope is VistA metadata analytics: schema extraction, XINDEX analysis, global-structure archaeology, and building a normalized conceptual layer above raw FileMan.

## Consequences
- Positive: Name matches actual purpose; downstream tooling decisions flow naturally from analytics scope (DuckDB-friendly TSV outputs, baked DD exporters, M-Unit for test authoring).
- Positive: Scope discipline — gRPC can be a v2 concern if ever needed; not a foundation assumption.
- Negative: Some early conversation artifacts reference `vista-grpc`; superseded by this ADR.

## Alternatives considered
- Keep `vista-grpc` name and expand scope — rejected, name would mislead future readers.
- Keep both projects separate — rejected, premature; the gRPC layer was never started.
