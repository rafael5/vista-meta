# ADR-009: Entrypoint chowns bind mounts on start

Date: 2026-04-17
Status: Accepted

## Context
Bind-mounted directories inherit host UID ownership. The in-container `vehu` user runs as UID `${VEHU_UID}` (default 1001). If host user UID differs (e.g., 1000), YDB cannot write to the mounted paths. Two strategies: (A) match build-time UID to host, (B) chown bind mounts at container start.

## Decision
Option B: entrypoint runs `chown -R vehu:vehu` on the four mount points (`dev/r`, `scripts`, `export`, `g`) at every container start. Build uses a fixed UID (1001).

## Consequences
- Positive: Works across different host users (team member with UID 1002, another with 1001 — same image works for both).
- Positive: Survives host migration without image rebuild.
- Positive: Self-healing if someone accidentally chowns a file on the host as root.
- Negative: Tiny startup cost (~seconds even on large export/ trees). Negligible in practice.
- Negative: If host user later adds files with non-vehu UID, they'll be re-owned next container start (expected behavior).

## Alternatives considered
- Option A (build-time UID match): rebuild required if host user UID differs; friction for sharing image.
- `--user $(id -u):$(id -g)` at docker run: breaks YDB install assumptions about `vehu` user account.
- Skip chown, document UID match requirement: fragile; silent failure when mismatched.
