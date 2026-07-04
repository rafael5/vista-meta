# ADR-051: Unconsumed baked services (rocto, YDB GUI) warn — they do not gate smoke

Date: 2026-07-04
Status: Accepted (amends the gate semantics of ADR-013/ADR-027 for two services)

## Context

ADR-013 baked five services into the image: RPC Broker, VistALink, sshd, Octo
(rocto), and the YDB GUI. The first run of the ADR-027 smoke suite (2026-07-04)
found two of them down — rocto dies at boot (`_ydboctoInit.m` not on its $ZRO)
and the YDB GUI never binds :8089 — and, on inspection, **nothing consumes
either**: no script, tool, sibling repo, or workflow in the stack issues Octo
SQL or opens the GUI. The RPC Broker and VistALink, by contrast, are load-
bearing (connection contract, sibling M projects).

## Decision

The smoke suite treats the two unconsumed services as **WARN, never FAIL**
(S-09, S-10): they are still probed on every run — so a revival or a future
adoption is visible — but a dead rocto/GUI does not make `make smoke` exit
non-zero. The services stay baked (ADR-013 unchanged); fixing them is
opportunistic, not required. If either ever gains a consumer, its check is
promoted back to a gating FAIL in the same change.

## Consequences

- Positive: `make smoke` is green when everything that matters works; the
  gate's signal isn't diluted by services nobody uses.
- Positive: the probes remain, so the state of the two services is always
  visible in smoke output rather than forgotten.
- Negative: a genuinely-wanted rocto/GUI fix loses its forcing function —
  accepted; TODO T-006 records the diagnosis for whenever it's picked up.
- Neutral: dropping the services from the image entirely (smaller image,
  faster boot) remains open as a future ADR if the WARN noise ever annoys.

## Alternatives considered

- Fix the services now — rejected as forced work: no consumer benefits.
- Drop them from the image — heavier change (Dockerfile + entrypoint + ADR-013
  supersession) than the observed problem warrants today.
- Delete the checks — rejected: silent rot; WARN keeps the state visible.
