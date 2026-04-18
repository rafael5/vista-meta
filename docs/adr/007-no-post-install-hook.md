# ADR-007: No post-install hook

Date: 2026-04-17
Status: Accepted

## Context
WorldVistA's `-p <script>` flag runs a variant-specific post-install script that creates demo users, configures Panorama, sets up special packages, etc. Examples include `wvDemopi.sh` (adds PROVIDER/PHARMACIST/NURSE demo users), `ov6piko.sh` (Korean ICD-10), `rpmsPostInstall.sh`.

## Decision
Do not use any post-install hook. VEHU-M already includes working demo users and synthetic patient data.

## Consequences
- Positive: Fewer moving parts; fewer places for subtle customization drift.
- Positive: What you see in VEHU is what you get; no "customized by post-install" blind spot when analyzing DD.
- Negative: If a specific demo user pattern is needed later, must add manually or via dev-r/ routines.

## Alternatives considered
- Use `wvDemopi.sh`: redundant with VEHU's users; adds a variable.
- Write a custom hook for vista-meta analysis setup: premature; anything needed can go in dev-r/ on first use.
