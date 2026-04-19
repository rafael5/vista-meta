# PIKS Analysis Guide

Classification results and analytical findings from the vista-meta
PIKS classification of VEHU's FileMan data structures.

Date: 2026-04-19
Spec: docs/vista-meta-spec-v0.4.md § 11

---

## 1. What is PIKS?

Every FileMan file and global is classified into exactly one of four
categories based on its primary audience and purpose:

| Category | What it holds | Who uses it | Count | % |
|---|---|---|---|---|
| **P** (Patient) | Clinical care data — demographics, encounters, diagnoses, medications, labs, vitals, notes, orders, billing | Clinicians, patients, care coordinators | 3,073 | 37.2% |
| **I** (Institution) | Facility/org structure — locations, divisions, **providers/staff**, teams, scheduling, procurement, engineering | Administrators, planners, VISN leadership | 2,880 | 34.9% |
| **K** (Knowledge) | Terminologies, code tables, templates, formulary, reminders, order dialogs, clinical rules | Clinical informaticists, coding specialists | 1,106 | 13.4% |
| **S** (System) | Config, operations, VistA internals — Kernel, FileMan meta, protocols, HL7, security, TaskMan, devices | IT staff, VistA developers | 845 | 10.2% |

Coverage: 7,904 of 8,261 files auto-classified (95.7%) + 217 triage.
File 200 (NEW PERSON) reclassified from S to I per RF-008.

---

## 2. How files were classified

### 2.1 Automated heuristics (95.7% of classifications)

The `VMPIKS` routine applies deterministic rules in tier order:

| Tier | Heuristics | Confidence | Files classified | What it checks |
|---|---|---|---|---|
| 1 | H-01 to H-04 | Certain | 130 | Structural identity: File 2=P, File 4=I, ^DD=S |
| 2 | H-06 to H-09 | High | 1,427 | Pointer to anchor file: ptr→File 2=P, →File 4=I, →File 200=S |
| 3 | H-10 to H-13 | High | 651 | Known global root patterns |
| 4 | H-14 to H-17 | Moderate | 964 | Package namespace prefix |
| 5 | H-18 | Moderate | 10 | Pointer topology: high in / low out = K (reference table) |
| 6 | H-20 to H-23 | Low | 175 | File name patterns: "TYPE"→K, "PARAMETER"→S |
| — | H-05 | Certain | 4,424 | Subfile inheritance from classified parent |
| 9 | H-36,H-38-H-40 | Moderate | 125 | Graph propagation using neighbor labels |

### 2.2 Manual triage (4.6% of classifications)

217 top-level files classified in three batches:

| Triage category | Count | Method |
|---|---|---|
| B (package batch) | 174 | Global prefix → known package → PIKS |
| C (individual) | 42 | Domain knowledge, file name, pointer analysis |
| A (vestigial) | 1 | Empty file, no pointers, no data → S |

### 2.3 Traceability

Every classification has two fields:
- `piks_method`: which heuristic fired (H-01 through H-40) or `manual`/`manual-package`
- `piks_evidence`: the specific data that triggered it

Example: File 52 (PRESCRIPTION) → `piks=P, method=H-06, evidence=field=.02 PATIENT points to file 2`

---

## 3. Key structural findings

### 3.1 VistA's most-referenced files

These are the structural hubs — the files everything else points to:

| Rank | File | Name | Inbound pointers | PIKS |
|---|---|---|---|---|
| 1 | 200 | NEW PERSON | 1,244 | S |
| 2 | 2 | PATIENT | 379 | P |
| 3 | 4 | INSTITUTION | 321 | I |
| 4 | 44 | HOSPITAL LOCATION | 248 | I |
| 5 | 5 | STATE | 124 | K |
| 6 | 80 | ICD DIAGNOSIS | 117 | K |
| 7 | 40.8 | MEDICAL CENTER DIVISION | 85 | I |
| 8 | 50 | DRUG | 83 | K |
| 9 | 60 | LABORATORY TEST | 81 | K |
| 10 | 3.5 | DEVICE | 73 | S |

File 200 (NEW PERSON) is VistA's structural center — 3.3x more
referenced than PATIENT. It's the user/provider identity hub that
connects System, Institution, and Patient domains.

### 3.2 Scale and hierarchy

| Metric | Value |
|---|---|
| Total FileMan files | 8,261 |
| Top-level files | 2,954 |
| Subfiles (multiples) | 5,307 |
| Top:sub ratio | 1:1.8 |
| Total fields | 69,809 |
| Widest file | Generic Code Sheet (2,603 fields) |
| Largest table | ICD DRG PDX (1M records), Lexicon (905K) |
| Average fields/file | ~8.5 |

### 3.3 Cross-PIKS pointer matrix

3,868 pointer fields cross PIKS boundaries. This is VistA's semantic
wiring — how the four data categories interconnect:

```
              Target PIKS
              P       I       K       S
Source  P     —      1,477    433     308
PIKS    I     560     —       524     231
        K     23      129     —        70
        S     36       58      19      —
```

(Updated 2026-04-19 after File 200 reclassification from S to I — see RF-008, RF-009)

Key patterns:

| Pattern | Count | Meaning |
|---|---|---|
| **P→I** | 1,477 | Patient records reference providers/staff and facilities — the dominant cross-PIKS pattern. Every encounter, order, and note links to who did it and where. |
| **I→P** | 560 | Institution/staff files reference patient data — provider workload, team assignments, scheduling |
| **I→K** | 524 | Facility setup uses knowledge tables — clinic types, service categories, coding configurations |
| **P→K** | 433 | Clinical data coded with terminologies — the FHIR terminology binding points (ICD, CPT, drug codes) |
| **P→S** | 308 | Patient data references system entities — order protocols, notification options |
| **I→S** | 231 | Institution config references system infrastructure |
| **K→I** | 129 | Knowledge tables reference institution data — formulary by facility, location-specific rules |
| **K→S** | 70 | Knowledge references system infrastructure |
| **S→I** | 58 | System config references facility data |
| **S→P** | 36 | System files reference patient data — small and warrants individual security review |
| **K→P** | 23 | Knowledge pointing to patient data — rare, investigate individually |
| **S→K** | 19 | System references knowledge tables |

**Key insight from RF-008**: The original S→P count (461) was inflated by
File 200's misclassification. True System→Patient is only 36 fields —
much smaller security review scope.

### 3.4 FileMan coverage

| Category | Count | % |
|---|---|---|
| Total globals in database | 486 | 100% |
| FileMan-described | 418 | 86.0% |
| Non-FileMan | 67 | 13.8% |
| Scratch/temp | 1 | 0.2% |

The non-FileMan globals are mostly small utility/reference data.
Pharmacy and Lab globals in VEHU ARE FileMan-described — the
non-FM concern from the spec may be production-specific.

---

## 4. PIKS distribution details

### 4.1 Patient (P) — 2,815 files (34.1%)

Clinical care data: the longitudinal patient record.

Top subdomains (by file count):
- Registration/ADT (DG*): demographics, admissions, eligibility
- Pharmacy (PS*): prescriptions, dispensing, IV, unit dose
- Lab (LR*): orders, results, accessions
- Radiology (RA*): exams, reports, procedures
- Surgery (SR*): cases, procedures, operative reports
- TIU (TIU*): clinical notes, documents
- Orders (OR*): CPRS order entry, order actions
- Vitals (GMR*): vital measurements, templates
- Mental Health (YS*, YTT*): assessments, instruments
- Integrated Billing (IB*): claims, insurance, billing events

Characteristics:
- Sensitivity: `protected` (contains PHI)
- Volatility: `dynamic` (changes with every clinical encounter)
- Portability: `site-specific` (records belong to this facility)
- Volume: `high-volume` (largest tables have millions of records)

### 4.2 Institution (I) — 1,539 files (18.6%)

Facility and organizational structure.

Top subdomains:
- Facilities (File 4, 40.8): institution, division, station
- Locations (File 44, 42): clinic, ward, bed
- Scheduling (SD*): appointments, availability
- Procurement (PRC*): purchase orders, contracts
- Engineering (EN*): work orders, equipment
- Personnel (PRS*): payroll, time & attendance
- PCMM teams (SCT*): team assignments

Characteristics:
- Sensitivity: `operational` (some provider PII)
- Volatility: `slow` (changes on administrative cycles)
- Portability: `site-specific`
- Volume: `moderate`

### 4.3 Knowledge (K) — 1,096 files (13.3%)

Terminologies, templates, workflows, clinical rules.

Top subdomains:
- ICD/CPT coding (ICD*, ICPT*): diagnosis and procedure codes
- Lexicon (LEX*): clinical terms, concept maps
- Drug knowledge (PSD*, PSN*): drug classes, ingredients, formulary
- RxNorm (ETSRXN*): medication concept names
- Lab definitions (LAM*, LAB*): test definitions, instruments
- Order dialogs (ORD*): order entry templates
- Reminders (PXR*): clinical reminder rules
- Health factors (AUTTHF*): PCE health factors

Characteristics:
- Sensitivity: `public` (generally not PHI; some licensed content)
- Volatility: `static` to `slow`
- Portability: `universal` to `national`
- Volume: `reference` to `high-volume` (Lexicon/RxNorm are large)

### 4.4 System (S) — 2,671 files (32.3%)

Configuration, operations, VistA infrastructure.

Top subdomains:
- FileMan meta (DD, DI*, 0.x, 1.x): data dictionary, file definitions
- Kernel (XU*, XT*): parameters, options, security keys
- MailMan (XM*): messages, baskets
- HL7 (HL*): link configurations, message protocols
- Protocols (ORD 101): event-driven actions
- VistALink (XOB*): J2SE connections
- Web services (XWB*): RPC broker
- Package management (XPD*, 9.4): patches, builds
- Local/test (ZZ*): site-specific artifacts

Characteristics:
- Sensitivity: `operational` (may contain credentials)
- Volatility: `slow` to `ephemeral`
- Portability: `site-specific`
- Volume: `reference` to `moderate`

---

## 5. Data files

All data is in `vista/export/normalized/`:

| File | Rows | Description |
|---|---|---|
| `files.tsv` | 8,261 | File inventory: number, name, global root, field count, pointer counts, record count |
| `piks.tsv` | 7,904 | Automated PIKS classifications with method + evidence |
| `piks-triage.tsv` | 217 | Manual triage classifications |
| `field-piks.tsv` | 69,809 | Field-level PIKS: file_piks, ref_piks, cross_piks, sensitivity_flag |
| `RESEARCH.md` | — | Research log with RF-001 through RF-007 |

---

## 6. How to use this data

### Explore the cross-PIKS matrix
```bash
# All Patient→Knowledge pointer fields (FHIR terminology bindings)
grep "P.*K.*Y" vista/export/normalized/field-piks.tsv

# System files referencing patient data (security review)
grep "S.*P.*Y" vista/export/normalized/field-piks.tsv

# Knowledge files pointing to patient data (should be rare)
grep "K.*P.*Y" vista/export/normalized/field-piks.tsv
```

### Find files by PIKS category
```bash
# All Patient files sorted by record count
grep "	P	" vista/export/normalized/piks.tsv | cut -f1 | while read f; do
  grep "^$f	" vista/export/normalized/files.tsv
done | sort -t$'\t' -k8 -rn | head -20

# All unclassified files
comm -23 <(tail -n +2 vista/export/normalized/files.tsv | cut -f1 | sort) \
         <(tail -n +2 vista/export/normalized/piks.tsv | cut -f1 | sort)
```

### Run the classifier on a fresh system
```bash
# Inside the container:
D RUN^VMFILES         # extract file inventory
D RUN^VMPIKS          # classify files
D RUN^VMFPIKS         # classify fields
```

The heuristic rules are VistA-universal — they work on any
VistA/FileMan system (VEHU, FOIA, production, RPMS).

---

## 7. Known limitations

1. **141 subfiles unclassified** — awaiting inheritance propagation
   from triage-classified parents. Will resolve on next VMPIKS run
   with triage integration.

2. **Sensitivity flags over-report** — .01 NAME fields in System files
   (template names, file names) are flagged as protected person data.
   Needs refinement to distinguish person names from entity names.

3. **VEHU-specific record counts** — file sizes reflect synthetic VEHU
   data, not production volumes. PIKS category assignments are
   structural (from DD metadata) and portable; record counts are not.

4. **Non-FM globals minimal in VEHU** — only 67 non-FM globals found.
   Production systems likely have more (runtime pharmacy/lab data).
   The G-01 through G-06 heuristics exist but weren't heavily exercised.

5. **Package namespace lists are manually maintained** — Tier 4 prefix
   lists (H-14 through H-17) were expanded iteratively during this
   session. New packages or unusual prefixes may not be covered.
   The triage process catches these and feeds improvements back.

6. **Pointer analysis covers simple pointers only** — variable pointers
   (V type) and computed pointers (C type) are not yet extracted.
   These represent additional cross-PIKS relationships not captured
   in the current field-piks analysis.
