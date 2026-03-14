# Clinical Data Registry — Implementation Guide

## Overview

This project builds a patient-level data archive using HDF5 files as the primary data store. Each patient is a single `.h5` file containing all of their data — imaging volumes, time-series measurements, clinical notes, chart review extractions, and associated metadata. The archive is the source of truth.

A lightweight SQLite registry serves as a queryable index over the archive. It is not the database — it is derived from the `.h5` files by scanning their attributes and can be rebuilt at any time. Think of the `.h5` files as the warehouse and the SQLite registry as the catalog you use to find things in it.

Patient data arrives in batches tied to IRB protocols. Not all data arrives at once — structured records (EHR extractions, chart review data) typically arrive first, imaging later. The system is designed to handle this: patient files are created with whatever data is available, and new data is added to existing files as it comes in.

We use DVC (Data Version Control) to version both the registry and the `.h5` files, allowing us to snapshot the archive's state over time and roll back if needed.

---

## Progress Tracker

<details>
<summary><strong>Phase 1: Define the HDF5 File Specification ✅</strong></summary>

- [x] 1.1 — Draft the patient file specification document
- [x] 1.2 — Define required vs optional groups and attributes
- [x] 1.3 — Define naming conventions and data type standards
- [x] 1.4 — Review spec with supervisor and finalize

</details>

<details>
<summary><strong>Phase 2: Initial Setup</strong></summary>

- [X] 2.1 — Initialize the project repository
- [x] 2.2 — Initialize DVC
- [x] 2.3 — Create the SQLite registry schema
- [ ] 2.4 — Build the registry rebuild script
- [ ] 2.5 — Version the empty registry and archive with DVC

</details>

<details>
<summary><strong>Phase 3: First Data Arrival (IRB 1 & IRB 2)</strong></summary>

- [ ] 3.1 — Generate mock raw data for IRB 1 and IRB 2
- [ ] 3.2 — Build the patient file creation script
- [ ] 3.3 — Build the imaging ingestion script
- [ ] 3.4 — Ingest IRB 1 and IRB 2 into the archive
- [ ] 3.5 — Rebuild the registry and run first summary
- [ ] 3.6 — Version the archive with DVC

</details>

<details>
<summary><strong>Phase 4: Later Data Arrival (IRB 3 + Delayed Imaging)</strong></summary>

- [ ] 4.1 — Generate mock data for IRB 3 (including overlap patients)
- [ ] 4.2 — Ingest IRB 3 into the archive (new patients + updates to existing)
- [ ] 4.3 — Simulate delayed imaging arrival for IRB 1 and IRB 2
- [ ] 4.4 — Ingest delayed imaging into existing patient files
- [ ] 4.5 — Rebuild registry and run reconciliation summary
- [ ] 4.6 — Version the updated archive with DVC

</details>

<details>
<summary><strong>Phase 5: Hardening the System</strong></summary>

- [ ] 5.1 — Consolidate all scripts into the CLI tool
- [ ] 5.2 — Build the validation script
- [ ] 5.3 — Write basic tests
- [ ] 5.4 — Write the file specification document (formal version)
- [ ] 5.5 — Write the runbook / operations guide

</details>

<details>
<summary><strong>Phase 6: Ongoing Operations</strong></summary>

- [ ] Confirm the full workflow runs end-to-end
- [ ] Onboard at least one other team member using the README

</details>

---

<details>
<summary><h2>Project Structure</h2></summary>

```
project/
├── archive/                         # Source of truth — one .h5 file per patient
│   ├── P001.h5
│   ├── P002.h5
│   └── ...
├── incoming/                        # Staging area for raw data before ingestion
│   ├── irb_2025_001/
│   │   ├── manifest.csv
│   │   ├── ehr/
│   │   ├── ct/
│   │   └── mri/
│   ├── irb_2025_002/
│   │   ├── manifest.csv
│   │   ├── ehr/
│   │   ├── ct/
│   │   └── mri/
│   └── irb_2025_003/
│       ├── manifest.csv
│       ├── ehr/
│       ├── ct/
│       └── mri/
├── deliveries/                      # Packaged cohort exports
├── registry/
│   ├── registry.db                  # SQLite query index (derived, rebuildable)
│   └── crosswalk.csv                # Patient ID ↔ MRN mapping (restricted access)
├── spec/
│   ├── file_spec.md                 # HDF5 file structure specification
│   └── data_dictionary.md           # Field definitions and allowed values
├── src/
│   ├── pdb_manager.py               # CLI entry point
│   ├── create_patients.py           # Create new .h5 files from a manifest
│   ├── ingest_imaging.py            # Add imaging data to existing .h5 files
│   ├── ingest_ehr.py                # Add structured EHR/chart review data
│   ├── ingest_notes.py              # Add clinical notes
│   ├── rebuild_registry.py          # Scan archive → rebuild SQLite index
│   ├── validate.py                  # Check .h5 files against spec
│   └── summary.py                   # Database summary and status reports
├── notebooks/
│   ├── 01_generate_mock_data.ipynb
│   ├── 02_explore_archive.ipynb
│   └── 03_query_registry.ipynb
├── tests/
│   └── test_ingestion.py
├── requirements.txt
├── .gitignore
├── .dvc/
└── README.md
```

</details>

<details>
<summary><h2>Patient File Structure (HDF5)</h2></summary>

Every `.h5` file follows the same skeleton. Not all groups will be populated for every patient — the structure is consistent, but the content is heterogeneous.

```
patient_XXX.h5
│
│   # Top-level attributes (always present)
│   patient_id          (string: "P001")
│   tags                (list: ["lung_ca", "smoker", "stage3"])
│   active_irbs         (list: ["IRB-2025-001", "IRB-2025-003"])
│   irb_history         (list: ["IRB-2024-010"])
│   created_date        (string: "2026-01-15")
│
├── demographics/
│   │   age             (attr: 64)
│   │   sex             (attr: "M")
│   │   diagnosis        (attr: "Non-small cell lung carcinoma")
│   │   staging          (attr: "Stage III")
│
├── imaging/
│   ├── ct_2026-03-10/
│   │   │   volume              (dataset: int16 array, shape [slices, 512, 512])
│   │   │   modality            (attr: "CT")
│   │   │   scan_date           (attr: "2026-03-10")
│   │   │   num_slices          (attr: 300)
│   │   │   voxel_spacing_mm    (attr: [0.5, 0.5, 1.0])
│   │   │   body_region         (attr: "chest")
│   │   │   source_irb          (attr: "IRB-2025-001")
│   │
│   └── mri_2026-05-15/
│       │   volume              (dataset: int16 array, shape [slices, 256, 256])
│       │   ...
│
├── data/
│   ├── pft/
│   │   │   fev1                (attr: 2.1)
│   │   │   fvc                 (attr: 3.4)
│   │   │   fev1_fvc_ratio      (attr: 0.62)
│   │   │   test_date           (attr: "2026-03-12")
│   │
│   └── glucose/
│       │   timestamps          (dataset: float64 array)
│       │   values              (dataset: float64 array)
│       │   session_date        (attr: "2026-03-10")
│       │   sampling_rate_hz    (attr: 1.0)
│       │   device              (attr: "Dexcom G7")
│
├── Notes/
│   ├── note_0001/
│   │   │   text                (dataset: variable-length string)
│   │   │   author              (attr: "Dr. Smith")
│   │   │   date                (attr: "2026-03-10")
│   │   │   category            (attr: "radiology")
│   │   │   reviewed            (attr: true)
│   │
│   └── note_0002/
│       │   ...
│
├── chart_review/
│   ├── human/
│   │   └── note_0001/
│   │       │   tumor_size_cm   (dataset or attr)
│   │       │   location        (attr: "right upper lobe")
│   │       │   reviewer        (attr: "Dr. Chen")
│   │       │   review_date     (attr: "2026-04-15")
│   │
│   └── llm/
│       └── note_0001/
│           │   tumor_size_cm   (dataset or attr)
│           │   model           (attr: "claude-opus-4-6")
│           │   run_date        (attr: "2026-04-10")
│
├── genomics/                        # Metadata + paths only (raw data stored externally)
│   └── wgs_2026-07-15/
│       │   sequencing_platform (attr: "Illumina NovaSeq")
│       │   coverage            (attr: 30)
│       │   reference_genome    (attr: "GRCh38")
│       │   vcf_path            (attr: "/genomics_archive/P001/variants/")
│       │   bam_path            (attr: "/genomics_archive/P001/aligned/")
│
└── changelog/
    │   last_modified           (attr: "2026-05-10")
    │   history                 (attr: list of timestamped entries)
```

</details>

<details>
<summary><h2>SQLite Registry Schema</h2></summary>

The registry is a derived, read-only index rebuilt by scanning `.h5` file attributes. It exists solely for querying — it is never the source of truth. If the registry is lost or corrupted, it can be fully regenerated from the archive.

**patients**

| Column | Type | Description |
|---|---|---|
| patient_id | TEXT PK | Coded study ID (e.g., "P001") |
| age | INTEGER | Patient age |
| sex | TEXT | "M" or "F" |
| diagnosis | TEXT | Primary diagnosis |
| staging | TEXT | Disease staging if applicable |
| tags | TEXT | Comma-separated tag list |
| active_irbs | TEXT | Comma-separated active IRB numbers |
| created_date | TEXT | Date the .h5 file was created |
| file_path | TEXT | Path to the .h5 file in the archive |

**imaging**

| Column | Type | Description |
|---|---|---|
| patient_id | TEXT FK | References patients |
| modality | TEXT | "CT", "MRI", etc. |
| scan_date | TEXT | Date of the scan |
| num_slices | INTEGER | Number of slices in the volume |
| voxel_spacing | TEXT | Voxel spacing as string (e.g., "0.5,0.5,1.0") |
| body_region | TEXT | Anatomical region |
| source_irb | TEXT | Which IRB this imaging came from |

**timeseries**

| Column | Type | Description |
|---|---|---|
| patient_id | TEXT FK | References patients |
| data_type | TEXT | "PFT", "glucose", etc. |
| session_date | TEXT | Date of measurement |
| num_samples | INTEGER | Number of data points |
| sampling_rate | REAL | Sampling frequency in Hz (NULL for single measurements) |

**notes**

| Column | Type | Description |
|---|---|---|
| patient_id | TEXT FK | References patients |
| note_id | TEXT | Unique note identifier within the patient file |
| category | TEXT | "radiology", "pathology", "general", etc. |
| date | TEXT | Date of the note |
| author | TEXT | Who wrote the note |
| reviewed | INTEGER | 0 = not reviewed, 1 = reviewed |

**chart_review**

| Column | Type | Description |
|---|---|---|
| patient_id | TEXT FK | References patients |
| note_id | TEXT | Which note this review corresponds to |
| review_type | TEXT | "human" or "llm" |
| reviewer | TEXT | Reviewer name or model identifier |
| review_date | TEXT | Date of the review |

</details>

<details>
<summary><h2>Prerequisites</h2></summary>

- Python 3.9+
- pip packages: `h5py`, `numpy`, `pandas`, `pyyaml`, `dvc` (see `requirements.txt`)
- A basic understanding of SQL for querying the registry
- A basic understanding of HDF5 for working with patient files (see `h5py` documentation)
- DVC installed and initialized in the repo

</details>

---

<details>
<summary><h2>Phase 1: Define the HDF5 File Specification</h2></summary>

This phase produces no code. It produces a document that all future code references.

<details>
<summary><strong>Step 1.1 — Draft the patient file specification</strong></summary>

- Create `spec/file_spec.md`.
- Define the complete group hierarchy (see Patient File Structure above as a starting point).
- For each group, document which attributes are required vs optional.
- For each dataset, document the expected dtype, shape conventions, and compression settings.
- Define naming conventions: how imaging groups are named (`modality_YYYY-MM-DD`), how notes are numbered (`note_XXXX`), how chart reviews link back to notes.

</details>

<details>
<summary><strong>Step 1.2 — Define required vs optional groups and attributes</strong></summary>

- Every patient file MUST have: top-level attributes (`patient_id`, `tags`, `active_irbs`, `created_date`), and the group skeleton (`demographics/`, `imaging/`, `data/`, `Notes/`, `chart_review/`, `changelog/`).
- Groups may be empty if no data of that type exists yet for the patient.
- Define which attributes within each group are required when the group is populated. For example, every entry under `imaging/` must have `modality`, `scan_date`, and `source_irb` — no exceptions.

</details>

<details>
<summary><strong>Step 1.3 — Define naming conventions and data type standards</strong></summary>

- Patient file names: `{patient_id}.h5` (e.g., `P001.h5`).
- Imaging group names: `{modality}_{YYYY-MM-DD}` (e.g., `ct_2026-03-10`).
- Note IDs: `note_{NNNN}` zero-padded (e.g., `note_0001`).
- Dates: always `YYYY-MM-DD` strings.
- Volumes: always stored as `int16` with `gzip` compression and chunking of `(1, height, width)`.
- Tags: always stored as a list of lowercase strings with underscores (e.g., `["lung_ca", "stage3"]`).

</details>

<details>
<summary><strong>Step 1.4 — Review spec with supervisor and finalize</strong></summary>

- Walk through the spec with your supervisor. Confirm the group hierarchy covers the data types your group works with.
- Identify any data types not yet accounted for. Add them now — changing the spec later is much harder than getting it right upfront.
- Sign off on the spec. Once code is written against it, changes require migration effort.

</details>

</details>

---

<details>
<summary><h2>Phase 2: Initial Setup</h2></summary>

<details>
<summary><strong>Step 2.1 — Initialize the project repository</strong></summary>

- Create the directory structure shown in the Project Structure section.
- Run `git init` if not already a git repo.
- Create a `.gitignore` that excludes `archive/`, `incoming/`, `deliveries/`, `registry/registry.db`, `registry/crosswalk.csv`, and `*.h5`. None of these belong in git.
- Run `pip install -r requirements.txt` to install dependencies.

</details>

<details>
<summary><strong>Step 2.2 — Initialize DVC</strong></summary>

- Run `dvc init` inside the project root.
- Configure your DVC remote for versioned snapshots of the archive and registry.
- Run `dvc remote add -d myremote /path/to/your/dvc-storage` for a local remote, or substitute with your cloud URI.
- Commit the DVC config to git: `git add .dvc/ .dvcignore && git commit -m "Initialize DVC"`.

</details>

<details>
<summary><strong>Step 2.3 — Create the SQLite registry schema</strong></summary>

- Write `src/rebuild_registry.py`. This script:
  - Deletes and recreates `registry/registry.db` from scratch every time it runs.
  - Creates the five tables: `patients`, `imaging`, `timeseries`, `notes`, `chart_review`.
  - Walks the `archive/` directory, opens each `.h5` file in read-only mode, reads only the attributes and group structure (no heavy datasets), and populates the corresponding registry tables.
- Run it against an empty archive to verify it creates a valid but empty database.
- This script is idempotent — you can run it at any time to get a fresh registry that exactly reflects the current state of the archive.

</details>

<details>
<summary><strong>Step 2.4 — Build the validation script</strong></summary>

- Write `src/validate.py`. This script:
  - Opens a `.h5` file and checks it against the spec from Phase 1.
  - Verifies all required top-level attributes are present.
  - Verifies all required groups exist (even if empty).
  - For populated groups, verifies required attributes are present and correctly typed.
  - Reports issues per file: missing attributes, unexpected types, malformed names.
  - Supports `--patient P001` for a single file or `--all` for the full archive.
- This is your safety net for every ingestion — run it after any change to the archive.

</details>

<details>
<summary><strong>Step 2.5 — Version the empty registry and archive with DVC</strong></summary>

- Run `dvc add registry/registry.db`.
- Run `git add registry/registry.db.dvc && git commit -m "Empty registry schema"`.
- Run `dvc push`.
- This is your baseline snapshot.

</details>

</details>

---

<details>
<summary><h2>Phase 3: Simulating the First Data Arrival (IRB 1 & IRB 2)</h2></summary>

<details>
<summary><strong>Step 3.1 — Generate mock raw data for IRB 1 and IRB 2</strong></summary>

- Write or update `notebooks/01_generate_mock_data.ipynb` to generate mock data for IRB-2025-001 and IRB-2025-002.
- Each IRB comes with a `manifest.csv` containing: `patient_id`, `age`, `sex`, `diagnosis`, `staging`, `tags`.
- Generate mock EHR extractions (small CSV or JSON files with structured clinical data).
- Generate mock imaging (small numpy arrays saved as `.npy` files to stand in for DICOM volumes — full DICOM parsing is not needed for the mock).
- Place everything in `incoming/irb_2025_001/` and `incoming/irb_2025_002/`.
- IRB 1 has 10 patients. IRB 2 has 10 patients. 4 patients overlap between the two (e.g., P002, P005, P007, P010).
- IRB 1 delivers: EHR for all 10, CT for 6, MRI for 0 (pending).
- IRB 2 delivers: EHR for all 10, CT for 0 (pending), MRI for 7.
- This simulates the reality that data arrives incomplete.

</details>

<details>
<summary><strong>Step 3.2 — Build the patient file creation script</strong></summary>

- Write `src/create_patients.py`. This script:
  - Reads a `manifest.csv` from an incoming IRB directory.
  - For each patient in the manifest:
    - If no `.h5` file exists in `archive/`, creates a new file with the standard skeleton (all required groups, all required top-level attributes, empty data groups).
    - If the `.h5` file already exists (overlap patient), updates the `active_irbs` attribute to include the new IRB number. Does not overwrite existing data.
  - Populates `demographics/` from the manifest columns.
  - Appends a changelog entry for each file created or updated.
- Run against both IRB manifests.
- Verify: `archive/` should contain 16 unique `.h5` files (10 + 10 - 4 overlap). Each file should have the correct `active_irbs` list. Overlap patients should list both IRBs.

</details>

<details>
<summary><strong>Step 3.3 — Build the imaging ingestion script</strong></summary>

- Write `src/ingest_imaging.py`. This script:
  - Takes an incoming IRB directory path as input.
  - Scans the `ct/` and `mri/` subdirectories for available imaging files.
  - Matches each imaging file to a patient (using the filename or a mapping file).
  - Opens the corresponding `.h5` file in append mode.
  - Creates the imaging group (e.g., `imaging/ct_2026-03-10/`), writes the volume dataset with compression and chunking, and sets all required metadata attributes.
  - Appends a changelog entry.
- This script is also used for delayed imaging that arrives later (Phase 4).

</details>

<details>
<summary><strong>Step 3.4 — Ingest IRB 1 and IRB 2 into the archive</strong></summary>

- Run `src/create_patients.py` against `incoming/irb_2025_001/`.
- Run `src/create_patients.py` against `incoming/irb_2025_002/`.
- Run `src/ingest_imaging.py` against `incoming/irb_2025_001/` (ingests 6 CTs).
- Run `src/ingest_imaging.py` against `incoming/irb_2025_002/` (ingests 7 MRIs).
- Write a similar `src/ingest_ehr.py` to handle structured EHR data — run against both IRBs.
- Run `src/validate.py --all` to check every file against the spec.
- Verify: 16 `.h5` files in the archive. 6 have CT imaging. 7 have MRI imaging. All 16 have EHR data. Overlap patients have data from both IRBs.

</details>

<details>
<summary><strong>Step 3.5 — Rebuild the registry and run first summary</strong></summary>

- Run `src/rebuild_registry.py` to populate the SQLite index from the archive.
- Run `src/summary.py` to produce a database overview:
  - Total patients: 16
  - With CT: 6 (all from IRB 1)
  - With MRI: 7 (all from IRB 2)
  - With both CT and MRI: 0 (no patient has both yet)
  - Patients in multiple IRBs: 4
- Query the registry directly to verify specific patients:
  - P002 should have EHR + CT (from IRB 1) but no MRI.
  - P005 should have EHR (from both) + MRI (from IRB 2) but no CT.
- This is your "before" snapshot.

</details>

<details>
<summary><strong>Step 3.6 — Version the archive with DVC</strong></summary>

- Run `dvc add archive/` to track the entire archive directory.
- Run `dvc add registry/registry.db`.
- Run `git add archive.dvc registry/registry.db.dvc && git commit -m "Archive after IRB 1 and IRB 2 ingestion"`.
- Run `dvc push`.
- You now have two snapshots: the empty state and the state after the first two IRBs.

</details>

</details>

---

<details>
<summary><h2>Phase 4: Simulating a Later Data Arrival (IRB 3 + Delayed Imaging)</h2></summary>

<details>
<summary><strong>Step 4.1 — Generate mock data for IRB 3</strong></summary>

- Generate IRB-2025-003 mock data with 10 patients. 6 overlap with previous IRBs (e.g., P002, P005, P007, P010, P011, P016) and 4 are new (P017-P020).
- IRB 3 delivers complete data: EHR, CT, and MRI for all 10 patients.
- Place in `incoming/irb_2025_003/`.

</details>

<details>
<summary><strong>Step 4.2 — Ingest IRB 3 into the archive</strong></summary>

- Run `src/create_patients.py` against `incoming/irb_2025_003/`.
  - 4 new `.h5` files created (P017-P020).
  - 6 existing files updated with `IRB-2025-003` added to `active_irbs`.
- Run all ingestion scripts (EHR, imaging) against `incoming/irb_2025_003/`.
- Verify: archive now has 20 `.h5` files. Overlap patients now have imaging from multiple IRBs (e.g., P002 now has CT from IRB 1 and CT + MRI from IRB 3 — two CT groups with different scan dates).

</details>

<details>
<summary><strong>Step 4.3 — Simulate delayed imaging arrival</strong></summary>

- This simulates the common scenario: IRB 1's MRIs finally arrive two months after the EHR data.
- Generate mock MRI data for the IRB 1 patients who were missing it.
- Place in `incoming/irb_2025_001_supplemental/mri/`.
- Similarly, generate delayed CT data for IRB 2 patients.
- Place in `incoming/irb_2025_002_supplemental/ct/`.

</details>

<details>
<summary><strong>Step 4.4 — Ingest delayed imaging into existing patient files</strong></summary>

- Run `src/ingest_imaging.py` against the supplemental directories.
- This is the key test: the script must correctly open existing `.h5` files and add new imaging groups without disturbing existing data.
- Run `src/validate.py --all` to verify nothing was corrupted.

</details>

<details>
<summary><strong>Step 4.5 — Rebuild registry and run reconciliation summary</strong></summary>

- Run `src/rebuild_registry.py`.
- Run `src/summary.py` and compare against the Phase 3 snapshot:
  - Total patients: 20 (was 16)
  - With CT: should be significantly higher now (IRB 1 had 6, IRB 3 has 10, IRB 2 supplemental added more)
  - With both CT and MRI: should now be non-zero
  - Patients in multiple IRBs: 6
- This is your "after" snapshot. The comparison between before and after demonstrates that the system handles incremental data arrival correctly.

</details>

<details>
<summary><strong>Step 4.6 — Version the updated archive with DVC</strong></summary>

- Run `dvc add archive/`.
- Run `dvc add registry/registry.db`.
- Run `git add archive.dvc registry/registry.db.dvc && git commit -m "Archive after IRB 3 + delayed imaging"`.
- Run `dvc push`.
- You now have three snapshots and can diff between any two.

</details>

</details>

---

<details>
<summary><h2>Phase 5: Hardening the System</h2></summary>

<details>
<summary><strong>Step 5.1 — Consolidate scripts into the CLI tool</strong></summary>

- Write `src/pdb_manager.py` as the single entry point. It should wrap all existing scripts as subcommands:
  - `pdb-manager create-patients --irb-dir incoming/irb_2025_XXX/`
  - `pdb-manager ingest-imaging --irb-dir incoming/irb_2025_XXX/`
  - `pdb-manager ingest-ehr --irb-dir incoming/irb_2025_XXX/`
  - `pdb-manager ingest-notes --irb-dir incoming/irb_2025_XXX/`
  - `pdb-manager rebuild-registry`
  - `pdb-manager validate [--patient P001 | --all]`
  - `pdb-manager summary`
  - `pdb-manager activate-study --irb IRB-2025-004 --patients P001,P002,P003`
  - `pdb-manager close-study --irb IRB-2025-001`
- This is the only interface your successor needs to learn.

</details>

<details>
<summary><strong>Step 5.2 — Expand the validation script</strong></summary>

- Beyond spec compliance, add checks for:
  - Orphaned notes (notes without chart review entries, flagged as informational).
  - Duplicate imaging groups (same modality and date).
  - Patients with empty `active_irbs` that still have data (possibly a closed study that wasn't tagged).
  - Changelog consistency (last_modified matches actual last write).

</details>

<details>
<summary><strong>Step 5.3 — Write basic tests</strong></summary>

- Create `tests/test_ingestion.py`:
  - Create a temporary archive directory with a few mock `.h5` files.
  - Run create_patients and verify file structure matches the spec.
  - Run ingest_imaging and verify imaging groups are correctly written.
  - Run ingest against an existing patient and verify data is appended, not overwritten.
  - Rebuild the registry and verify row counts and foreign key integrity.
  - Run validation and verify no issues on known-good files.
  - Introduce a deliberately malformed file and verify validation catches it.
- Run with `python -m pytest tests/`.

</details>

<details>
<summary><strong>Step 5.4 — Formalize the file specification</strong></summary>

- Expand `spec/file_spec.md` from the Phase 1 draft into a formal, versioned document.
- Include worked examples: what a minimal patient file looks like, what a fully loaded patient file looks like.
- Include the exact `h5py` calls needed to create each group and dataset, so a new developer can reference it directly.

</details>

<details>
<summary><strong>Step 5.5 — Write the runbook / operations guide</strong></summary>

- Create `RUNBOOK.md` with step-by-step instructions for every routine operation:
  - New IRB batch arrives: exact commands in order.
  - Delayed imaging arrives for an existing IRB: exact commands.
  - New study needs to be activated: exact commands.
  - Study closes: exact commands.
  - Something goes wrong: how to diagnose, how to roll back with DVC.
  - Adding a new data type to the spec: what files need to change.
  - Rebuilding the registry from scratch.
- This document, combined with the CLI tool, is what makes the system operable after your departure.

</details>

</details>

---

<details>
<summary><h2>Phase 6: Ongoing Operations</h2></summary>

<details>
<summary><strong>When a new IRB batch arrives</strong></summary>

1. Place the incoming data in `incoming/irb_YYYY_XXX/` with a `manifest.csv`.
2. `pdb-manager create-patients --irb-dir incoming/irb_YYYY_XXX/`
3. `pdb-manager ingest-ehr --irb-dir incoming/irb_YYYY_XXX/`
4. `pdb-manager ingest-imaging --irb-dir incoming/irb_YYYY_XXX/`
5. `pdb-manager validate --all`
6. `pdb-manager rebuild-registry`
7. `pdb-manager summary`
8. Version: `dvc add archive/ registry/registry.db && git add archive.dvc registry/registry.db.dvc && git commit -m "Ingested IRB-YYYY-XXX" && dvc push`

</details>

<details>
<summary><strong>When delayed data arrives for an existing IRB</strong></summary>

1. Place the supplemental data in `incoming/irb_YYYY_XXX_supplemental/`.
2. Run the appropriate ingestion script(s) — imaging, EHR, notes — against the supplemental directory.
3. `pdb-manager validate --all`
4. `pdb-manager rebuild-registry`
5. Version with DVC.

</details>

<details>
<summary><strong>When activating or closing a study</strong></summary>

- Activate: `pdb-manager activate-study --irb IRB-YYYY-XXX --patients P001,P002,...`
- Close: `pdb-manager close-study --irb IRB-YYYY-XXX`
- Both commands update the `active_irbs` and `irb_history` attributes in the relevant `.h5` files, then rebuild the registry.

</details>

<details>
<summary><strong>When checking status</strong></summary>

- `pdb-manager summary` for a high-level overview.
- `pdb-manager validate --all` to check archive health.
- Query `registry/registry.db` directly with SQL for ad hoc questions.

</details>

<details>
<summary><strong>When something goes wrong</strong></summary>

1. Run `pdb-manager validate --all` to identify which files have issues.
2. Check the `changelog` group inside the affected `.h5` file(s) to understand what changed and when.
3. If the archive is corrupted: `git checkout <last-good-commit> archive.dvc && dvc checkout` to restore.
4. If only the registry is wrong: `pdb-manager rebuild-registry` — it's fully derived and costs nothing to regenerate.
5. If you need to rebuild from scratch: delete `registry/registry.db`, run `pdb-manager rebuild-registry`.

</details>

<details>
<summary><strong>When adding a new team member</strong></summary>

1. They clone the git repo.
2. They run `pip install -r requirements.txt`.
3. They run `dvc pull` to get the latest archive and registry.
4. They read this README, the file spec, and the runbook.
5. They're operational.

</details>

</details>

---

<details>
<summary><h2>DVC Cheat Sheet</h2></summary>

| Action | Command |
|---|---|
| Track the archive | `dvc add archive/` |
| Track the registry | `dvc add registry/registry.db` |
| Push to remote | `dvc push` |
| Pull latest version | `dvc pull` |
| View version history | `git log archive.dvc` |
| Restore a previous version | `git checkout <commit> archive.dvc && dvc checkout` |
| See what changed | `dvc diff` |

</details>

---

<details>
<summary><h2>Key Design Decisions</h2></summary>

- **HDF5 files are the source of truth.** Each patient is a single `.h5` file containing all of their data — imaging, measurements, notes, chart reviews, and metadata. The file is self-describing and self-contained.
- **The SQLite registry is derived, not authoritative.** It is rebuilt by scanning `.h5` file attributes and can be regenerated at any time. It exists solely to make the archive queryable without opening every file.
- **One file per patient.** All data for a patient lives in one place. This makes the archive easy to reason about, easy to back up, and easy to validate. A patient file may grow to 1-2 GB with imaging; this is expected and manageable.
- **The file skeleton is consistent; the content is heterogeneous.** Every patient file has the same group structure, but not every group will be populated. Some patients have CT and MRI; others have only EHR data. The structure is defined by the spec; the completeness varies by patient.
- **Data is embedded, not referenced (with exceptions).** Imaging volumes, time-series data, clinical notes, and chart review extractions are stored directly in the `.h5` file. The exceptions are genomics (WGS raw data stored externally due to size), video, and digital pathology — these are referenced by path in the `.h5` file.
- **IRB tracking is an attribute, not a structural boundary.** A patient's `active_irbs` attribute controls visibility. There is one archive, not one archive per study. When a study closes, the IRB is moved from `active_irbs` to `irb_history`. The data stays.
- **The changelog is embedded in each file.** Every `.h5` file carries its own modification history. This provides per-patient provenance independent of any external system.
- **DVC versions the archive and registry.** HDF5 files are binary and change frequently. Git would bloat; DVC handles this efficiently with deduplication and remote storage.
- **All operations go through a single CLI tool.** `pdb-manager` is the only interface needed to create, ingest, validate, query, and manage the archive. This is what makes the system operable by someone who didn't build it.

</details>
