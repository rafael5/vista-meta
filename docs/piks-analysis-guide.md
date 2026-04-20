# PIKS Analysis Guide

Classification results and analytical findings from the vista-meta
PIKS classification of VEHU's FileMan data structures.

Last updated: 2026-04-19
Spec: docs/vista-meta-spec-v0.4.md § 11
Research log: vista/export/RESEARCH.md (RF-001 through RF-027)

---

## 1. What is PIKS and why does it exist?

VistA is a 40-year-old integrated system: 8,261 FileMan files, ~70,000
fields, and 486 globals spanning clinical care, facility management,
terminology, and the plumbing that runs the MUMPS process itself.
Treating it as a single undifferentiated "database" makes every
downstream task harder — exchange, modernization, security review,
migration, reporting — because a lab result, a provider SSN, an ICD
code, and a TaskMan queue entry have almost nothing in common beyond
living in `^` globals on the same disk.

**PIKS is the top-level cut** that separates these four kinds of data
before any schema modeling, FHIR mapping, or migration planning begins.
It is deliberately coarse: four buckets, assigned by audience and
purpose rather than by package or global. Once every file carries a
PIKS label, each bucket can be handled by the people, tools, rules,
and retention policies that suit it — instead of applying a single
one-size-fits-all policy to the whole system.

### 1.1 The four categories

| Category | What it holds | Primary audience |
|---|---|---|
| **P** (Patient) | Clinical care data about identified individuals — demographics, encounters, problems, diagnoses, medications, allergies, labs, vitals, imaging, notes, orders, consults, billing, consents | Clinicians, patients, care coordinators, HIEs, payers |
| **I** (Institution) | Who and where the care happens — facilities, divisions, wards, clinics, rooms, beds, **providers/staff (File 200)**, teams, schedules, procurement, assets | Administrators, schedulers, HR, VISN leadership, finance |
| **K** (Knowledge) | Reference content that is not about any one patient — terminologies (ICD, CPT, LOINC, RxNorm, Lexicon), code tables, formularies, templates, reminders, order dialogs, clinical decision rules | Clinical informaticists, coding specialists, terminology stewards, standards bodies |
| **S** (System) | VistA's own plumbing — Kernel, FileMan meta, option/menu tree, protocols, HL7 routing, security keys, TaskMan queues, error logs, site parameters | IT staff, VistA developers, release managers, security/audit |

### 1.2 Security, regulation, retention, and rate of change

These properties are not incidental — they are the reason the cut
exists. Each category has a fundamentally different profile:

| Property | **P** Patient | **I** Institution | **K** Knowledge | **S** System |
|---|---|---|---|---|
| Sensitivity | **Protected** (PHI) | Operational / PII-bearing (staff) | Public or licensed | Operational, some secrets |
| Governing regime | HIPAA, 42 CFR Part 2, state PHI law, VA directives | HR law, contracting rules, FOIA carve-outs | Terminology licenses (CPT, SNOMED), copyright | SecOps policy, FISMA, internal IT |
| Retention | **Long-term / lifetime+** (legal record of care) | Medium-term (employment, contract life) | Versioned, supersede-in-place | Short/rolling (logs rotate, config moves forward) |
| Immutability | **Immutable** once recorded — appended, never edited in place; prior state must remain auditable | Corrigible — staff move, rooms get renamed | Versioned — new code set replaces old, history matters for lookback | Mutable — config changes are the norm |
| Rate of change | Continuous append, rare correction | Slow (org chart, staff roster) | Episodic (quarterly/annual releases) | Anywhere from static (keys) to ephemeral (queues, logs) |
| Portability | Per-patient export (C-CDA, FHIR Bundle) | Site-specific; rarely portable as a whole | Universal by design — terminologies cross sites and systems | Site-specific; not portable |
| Distinguishing constraint | **Must be exchangeable, storable, and retrievable for decades, and must remain faithful to what actually happened** | Reflects current-state org reality | Must be versionable and cite-able | Must be reproducible enough to restore a running system |

**P is the outlier, and the reason PIKS leads with it.** Patient data
is the only slice that is simultaneously highly regulated, lifetime-
retained, append-only/immutable in its historical record, and
*required* to move between institutions on demand (continuity of care,
HIE, VA↔DoD, VA↔community). I, K, and S do not share that combination.
I changes with the org. K is replaced by new versions. S is rebuilt
from config. Only P must travel with the person and stay truthful to
what was recorded, forever.

### 1.3 What PIKS lets you do

Having the label on every file turns a monolithic VistA database into
four independently-manageable slices:

- **Extract by category.** "Give me every patient's complete record"
  becomes a defined operation over the P slice. "Give me the facility
  and staff directory" is an I-slice export. "Give me the site's
  terminology bindings" is a K-slice export. Each targets a different
  consumer and uses a different format (FHIR Bundle, org chart/NPI
  feed, code system release).
- **Exchange and interoperate.** P is the slice that crosses
  institutional boundaries under HIPAA and TEFCA. Labeling it cleanly
  is the prerequisite for a migration or HIE extract that doesn't
  accidentally leak staff SSNs (I) or bundle site-specific TaskMan
  state (S).
- **Diff and compare across sites.** Two VistA instances can be
  compared K-to-K (do they use the same ICD release, the same order
  dialogs?) and I-to-I (org structure, staffing mix) without having
  to touch P at all. This is how you benchmark sites or spot drift.
- **Merge and standardize.** K is the slice where standardization
  actually matters and is achievable — a national formulary, a single
  terminology server, shared reminder definitions. Attempting to
  "standardize" P or I across sites is the wrong goal; they are
  inherently local and longitudinal.
- **Route to the right owners.** Clinical informatics owns K.
  Facilities/HR owns I. IT/SecOps owns S. Clinicians and HIM own P.
  PIKS lets each group work on its slice without stepping on the
  others, and lets governance policies attach to the right scope.
- **Apply the right storage and protection.** P warrants encrypted
  long-term archival with audit, legal hold, and break-glass access.
  S warrants backup of current config and rolling log retention. K
  warrants a versioned content repository. I sits between. A single
  storage policy for "the database" over-protects S and under-serves P.
- **Migrate and modernize in waves.** A VistA-to-Cerner/Oracle or
  VistA-to-FHIR effort can sequence work by PIKS: freeze and migrate
  K first (reference), then I (org), then stream P (longitudinal
  clinical history), and finally decommission S. Without the cut,
  every migration is "move everything at once."
- **Scope security and audit.** Cross-PIKS pointer analysis (§4.4)
  shows exactly where one category touches another. **S→P** edges are
  the high-priority review set for unauthorized PHI exposure; **K→P**
  edges should be near-zero in a clean architecture and are worth
  auditing when they appear.

Everything else in this document — heuristics, triage, the cross-PIKS
matrix, File 200's reclassification — is in service of getting this
top-level cut right, because every downstream model (conceptual,
logical, physical) inherits from it.

---

## 2. PIKS distribution

### 2.1 By file count (8,261 files)

```
  P (Patient)      3,203  37.2%  ████████████████████████▌
  I (Institution)  2,896  34.9%  ██████████████████████▊
  K (Knowledge)    1,140  13.3%  ████████▋
  S (System)         881  10.2%  ██████▋
  (unclassified)     141   1.7%  █▏
                   ─────
                   8,261
```

### 2.2 By field count (69,809 fields)

```
  I (Institution) 32,107  46.0%  ██████████████████████████████
  P (Patient)     26,787  38.4%  █████████████████████████
  K (Knowledge)    5,748   8.2%  █████▍
  S (System)       5,157   7.4%  ████▊
                  ──────
                  69,809
```

Institution dominates by field count because File 200 (NEW PERSON)
has 203 fields and 1,551 entries, with many subfiles — the
provider/staff data structure is wider than most clinical files.

### 2.3 By record count (top 10 largest tables)

```
  ICD DRG PDX (83.51)         1,000,000  K  ████████████████████
  EXPRESSIONS (757.01)        1,000,000  K  ████████████████████
  RXNORM CONCEPTS (129.22)    1,000,000  K  ████████████████████
  RXNORM ATTRIBUTES (129.21)  1,000,000  K  ████████████████████
  SEMANTIC MAP (757.1)          961,809  K  ███████████████████▎
  CONCEPT USAGE (757.001)       905,353  K  ██████████████████▏
  MAJOR CONCEPT MAP (757)       905,272  K  ██████████████████
  CODES (757.02)                855,576  K  █████████████████▏
  SUBSETS (757.21)              604,572  K  ████████████▏
  RXNORM NAMES (129.2)         565,257  K  ███████████▎
```

Knowledge dominates by record count — terminology tables (Lexicon,
RxNorm, ICD) account for the bulk of the database by row volume.

---

## 3. Classification methodology

### 3.1 Automated heuristics (95.7% of files)

```
  H-05  (subfile inherit)     4,869  ████████████████████████████████████████
  H-14  (Patient package)       603  █████
  H-06  (ptr → Patient)         360  ███
  H-09  (ptr → File 200)        338  ██▊
  H-08  (ptr → Institution)     283  ██▎
  H-10  (Patient global)        236  ██
  H-15  (Institution package)   202  █▋
  H-12  (Knowledge global)      197  █▋
  H-02  (FileMan meta → S)      127  █
  H-13  (System global)         119  █
  H-39  (orphan → S)            114  ▉
  H-11  (Institution global)     98  ▊
  H-16  (Knowledge package)      85  ▋
  H-20  (name → K)               79  ▋
  H-17  (System package)         74  ▋
```

### 3.2 By confidence level

```
  Certain    4,999  61.4%  ████████████████████████████████████████
  Moderate   1,311  16.1%  ██████████▌
  High       1,293  15.9%  ██████████▍
  Low          517   6.4%  ███▍
             ─────
             8,120  classified
```

### 3.3 Manual triage (4.3% of files)

| Triage category | Count | Method |
|---|---|---|
| B (package batch) | 174 | Global prefix → known package → PIKS |
| C (individual) | 42 | Domain knowledge, file name, pointer analysis |
| A (vestigial) | 1 | Empty file, no pointers → S |

### 3.4 Traceability

Every classification records:
- `piks_method`: which heuristic (H-01 to H-40) or `manual`/`manual-package`
- `piks_evidence`: the specific data that triggered it

Example: File 52 (PRESCRIPTION) → `piks=P, method=H-06, evidence=field=.02 PATIENT points to file 2`

---

## 4. Key structural findings

### 4.1 VistA's most-referenced files (pointer hubs)

```
  File 200  NEW PERSON           1,244 ptrs in  I  ████████████████████████████████████████
  File 2    PATIENT                379 ptrs in  P  ████████████▎
  File 4    INSTITUTION            321 ptrs in  I  ██████████▍
  File 44   HOSPITAL LOCATION      248 ptrs in  I  ████████
  File 5    STATE                  124 ptrs in  K  ████
  File 80   ICD DIAGNOSIS          117 ptrs in  K  ███▊
  File 40.8 MED CENTER DIVISION     85 ptrs in  I  ██▊
  File 50   DRUG                    83 ptrs in  K  ██▋
  File 60   LABORATORY TEST         81 ptrs in  K  ██▋
  File 3.5  DEVICE                  73 ptrs in  S  ██▍
```

**RF-004/RF-008**: File 200 (NEW PERSON) is VistA's structural center —
3.3x more referenced than PATIENT. It holds staff/provider PII (1,462
SSNs, 1,151 DOBs) and was reclassified from S to I because it describes
WHO works at the facility, not system configuration.

### 4.2 Scale and hierarchy

| Metric | Value |
|---|---|
| Total FileMan files | 8,261 |
| Top-level files | 2,954 |
| Subfiles (multiples) | 5,307 |
| Top:sub ratio | 1:1.8 |
| Total fields | 69,809 |
| Widest file | Generic Code Sheet (2,603 fields) |
| Largest table | ICD DRG PDX (1M records), Lexicon (905K) |

### 4.3 Field data types

```
  FREE TEXT         20,538  29.4%  █████████████████████████████▍
  SET OF CODES      12,476  17.9%  █████████████████▉
  POINTER           11,900  17.0%  █████████████████
  NUMERIC           11,792  16.9%  ████████████████▉
  DATE               6,300   9.0%  █████████
  OTHER              3,429   4.9%  ████▉
  WORD PROCESSING    1,427   2.0%  ██
  COMPUTED           1,022   1.5%  █▌
  MUMPS                754   1.1%  █
  VARIABLE POINTER     171   0.2%  ▏
```

11,900 POINTER fields + 171 VARIABLE POINTER fields = 12,071 pointer
relationships in the database. These are the cross-file wiring of VistA.

### 4.4 Cross-PIKS pointer matrix

3,868 pointer fields cross PIKS boundaries — how the four data
categories interconnect:

```
                    ┌──────── Target PIKS ────────┐
                    P        I        K        S
Source   P          —      1,477      433      308
PIKS     I        560        —        524      231
         K         23       129        —        70
         S         36        58        19       —
```

```
  P→I   1,477  ██████████████████████████████████████▎  patient → provider/facility
  I→P     560  ██████████████▌                          staff → patient data
  I→K     524  █████████████▌                           facility → terminology
  P→K     433  ███████████▏                             clinical → coding (FHIR binding)
  P→S     308  ███████▉                                 patient → system config
  I→S     231  ██████                                   institution → system
  K→I     129  ███▎                                     knowledge → institution
  K→S      70  █▊                                       knowledge → system
  S→I      58  █▌                                       system → facility
  S→P      36  ▉                                        system → patient (security)
  K→P      23  ▋                                        knowledge → patient (investigate)
  S→K      19  ▌                                        system → knowledge
```

**Key insights:**
- **P→I (1,477)** is the dominant pattern: every clinical encounter,
  order, and note references who did it (provider) and where (facility).
- **S→P (36)** is the true security concern scope — much smaller than
  the original 461 (inflated by File 200 misclassification, RF-008/RF-009).
- **K→P (23)** should be zero in a clean architecture. These 23 fields
  are either misclassified files or genuine anomalies worth investigating.
- **P→K (433)** are the FHIR terminology binding points — clinical data
  coded with ICD, CPT, drug codes, lab test definitions.

### 4.5 FileMan coverage

```
  FileMan-described   418  86.0%  ████████████████████████████████████████
  Non-FileMan          67  13.8%  ██████▍
  Scratch/temp          1   0.2%  ▏
                      ───
                      486  total globals
```

Non-FM globals are mostly small utility/reference data in VEHU.
Pharmacy and Lab globals ARE FileMan-described in this distribution
(RF-002).

### 4.6 File 200 (NEW PERSON) — the structural hub (RF-008)

File 200 is VistA's most-referenced file and a critical PIKS finding.

| Property | Value |
|---|---|
| Entries | 1,551 |
| Fields | 203 |
| Inbound pointers | 1,244 (3.3x more than PATIENT) |
| PIKS | **I** (Institution) — was S, reclassified per RF-008 |
| Sensitivity | **Protected** — 1,462 SSNs, 1,151 DOBs |
| Contains patients? | **No** — staff/providers only |

```
  Staff roles in File 200:
  Providers      323  ██████████████████████
  Other          654  ███████████████████████████████████████████
  Clerks         218  ██████████████▎
  Technicians    127  ████████▍
  Nurses          81  █████▍
  Pharmacists     56  ███▋
  Programmers     37  ██▍
```

**Impact of reclassification**: S category dropped from 32% to 10%.
Cross-PIKS S→P dropped from 461 to 36. The original S classification
inflated System's apparent size because 1,244 files pointing to
File 200 were classified S by H-09.

---

## 5. Data files

All data is in `vista/export/data-model/` (the FileMan PIKS slice):

| File | Rows | Size | Description |
|---|---|---|---|
| `vista-fileman-piks-comprehensive.csv` | 69,840 | 9.2 MB | **Primary output**: every file + field with all PIKS annotations (22 columns) |
| `files.tsv` | 8,261 | 1.2 MB | File inventory from ^DD/^DIC |
| `piks.tsv` | 7,904 | 450 KB | Automated PIKS classifications |
| `piks-triage.tsv` | 217 | 12 KB | Manual triage classifications |
| `field-piks.tsv` | 69,809 | 4.2 MB | Field-level PIKS with cross-PIKS flags |

Project research log is one level up at `vista/export/RESEARCH.md` (RF-001 through RF-027, covering both the data-model/ PIKS work and the code-model/ routine/package/XINDEX work).

### Comprehensive CSV column order

| # | Column | Example | Description |
|---|---|---|---|
| 1 | file_number | 2 | FileMan file number |
| 2 | field_number | .104 | Field number within file |
| 3 | field_name | PROVIDER | Field name from ^DD |
| 4 | data_type | POINTER | FREE-TEXT, SET, POINTER, NUMERIC, DATE, etc. |
| 5 | field_piks | P | PIKS of this field (inherited from file) |
| 6 | file_piks | P | PIKS of the containing file |
| 7 | file_piks_method | H-01 | Which heuristic classified the file |
| 8 | file_piks_confidence | certain | certain / high / moderate / low |
| 9 | ref_piks | I | For pointer fields: PIKS of the target file |
| 10 | cross_piks | Y | Y if field_piks != ref_piks |
| 11-22 | | | file_name, global_root, parent_file, counts, evidence, pointer target, sensitivity |

---

## 6. How to use this data

### Query the comprehensive CSV

```bash
# All cross-PIKS pointer fields
head -1 vista/export/data-model/vista-fileman-piks-comprehensive.csv && \
  grep ",Y," vista/export/data-model/vista-fileman-piks-comprehensive.csv

# Patient→Knowledge fields (FHIR terminology bindings)
awk -F',' '$5=="P" && $9=="K" && $10=="Y"' \
  vista/export/data-model/vista-fileman-piks-comprehensive.csv

# All fields in File 2 (PATIENT)
awk -F',' '$1=="2"' vista/export/data-model/vista-fileman-piks-comprehensive.csv

# Files with sensitivity flags
awk -F',' '$22=="Y"' vista/export/data-model/vista-fileman-piks-comprehensive.csv

# System→Patient fields (security review)
awk -F',' '$5=="S" && $9=="P" && $10=="Y"' \
  vista/export/data-model/vista-fileman-piks-comprehensive.csv
```

### Run the classifier on a fresh VistA system

```bash
# Inside the container:
D RUN^VMFILES         # extract file inventory → files.tsv
D RUN^VMPIKS          # classify files → piks.tsv
D RUN^VMFPIKS         # classify fields → field-piks.tsv
```

The heuristic rules are VistA-universal — they work on any
VistA/FileMan system (VEHU, FOIA, production, RPMS).

---

## 7. Research findings summary

| # | Finding | Status |
|---|---|---|
| RF-001 | mupip load silently fails on paths with spaces — 94% of globals not loaded | verified, fix applied |
| RF-002 | 86% of VEHU globals are FileMan-described; non-FM is minimal | verified |
| RF-003 | 8,261 files, widest = 2,603 fields, 1:1.8 top:sub ratio | verified |
| RF-004 | File 200 most-referenced (1,244 ptrs), 3.3x more than PATIENT | verified |
| RF-005 | H-05 (inheritance) classifies 59% of files; Tier 2 is strongest signal | verified |
| RF-006 | 98.3% PIKS classification achieved (auto 95.7% + triage 2.6%) | verified |
| RF-007 | Cross-PIKS matrix: 3,868 cross-category pointer fields | verified (updated RF-009) |
| RF-008 | File 200 is staff/provider PII, not system data → reclassified S to I | verified |
| RF-009 | Cross-PIKS matrix recalculated: S→P dropped 461→36, S dropped 32%→10% | verified |

---

## 8. Known limitations

1. **141 subfiles unclassified** — awaiting inheritance from triage parents.

2. **Sensitivity flags over-report** — .01 NAME fields in System files
   flag entity names (templates, files) as person names.

3. **VEHU-specific record counts** — PIKS category assignments are structural
   (from DD metadata) and portable; record counts reflect synthetic VEHU data.

4. **Simple pointers only** — variable pointers (171 fields) and computed
   pointers not yet analyzed for cross-PIKS patterns.

5. **Package namespace lists manually maintained** — Tier 4 prefix lists
   were expanded iteratively. New packages may not be covered.

6. **File 200 cascade** — reclassifying File 200 from S to I changed
   the entire distribution. Any file with >1,000 inbound pointers has
   outsized classification influence. Future anchor reclassifications
   should be tested for cascade impact before committing.
