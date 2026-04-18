# ADR-006: Skip VistA bootstrap

Date: 2026-04-17
Status: Accepted

## Context
VistA has a historic "bootstrap" process (`ZTMGRSET`, `^XUP`) that establishes Kernel security, primary namespaces, and system-wide parameters on a freshly-installed M system. WorldVistA's `-b` flag skips this — Docker-hosted VistA never goes through a clean bootstrap because the globals arrive pre-populated.

## Decision
Skip bootstrap. Equivalent to WorldVistA's `-b` flag. VEHU-M globals are imported pre-bootstrapped; the image inherits that state.

## Consequences
- Positive: Build time drops (bootstrap takes minutes and is interactive).
- Positive: Reproducible — no random UCI assignments, no Kernel site-specific state.
- Negative: Cannot test bootstrap flows (Kernel Install, XU*8.0*n patches that touch bootstrap logic) in this image. Out of scope anyway.

## Alternatives considered
- Bootstrap on first run in entrypoint: complex, slow, and produces nondeterministic state.
- Interactive bootstrap one-time: breaks the "rebuild and go" promise.
