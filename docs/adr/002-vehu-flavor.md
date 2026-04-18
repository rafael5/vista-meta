# ADR-002: VEHU as VistA flavor

Date: 2026-04-17
Status: Accepted

## Context
Multiple VistA distributions exist: FOIA VistA (clean, no patient data), OSEHRA VistA (FOIA minus VA redactions), VEHU (FOIA + synthetic patient data, maintained by Sam Habiel), WorldVistA EHR 3.0, RPMS, vxVistA. Need one to standardize on.

## Decision
Target VEHU. Source: `github.com/WorldVistA/VistA-VEHU-M/archive/master.zip`.

## Consequences
- Positive: Synthetic patient data enables realistic DD/global analytics without privacy concerns.
- Positive: Most actively maintained open-source VistA image (monthly updates historically).
- Positive: OSEHRA-inherited enhancements (Enhanced XINDEX, Log4M, non-Kernel routine fixes) already baked in.
- Negative: Slightly larger than FOIA due to patient data; irrelevant for our use case.
- Neutral: Ties us to VEHU-M update cadence; pinnable via image date tag.

## Alternatives considered
- FOIA VistA: too clean; lab/pharmacy globals need realistic data to study.
- WorldVistA EHR 3.0: smaller user base, less active; demo-user quirks.
- RPMS: different namespace concerns (IHS-specific); not our target domain.
