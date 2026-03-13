# Patient File Specification (HDF5)

**Version:** 0.1.0-draft
**Last updated:** 2026-03-13

---

## Overview

Each patient in the archive is stored as a single HDF5 (`.h5`) file. The file is self-describing and self-contained — all patient data (imaging volumes, time-series measurements, clinical notes, chart review extractions, and metadata) lives in one place.

Every patient file follows the same group skeleton. Not all groups will be populated for every patient; the structure is consistent but the content is heterogeneous. A patient may have CT and MRI data, or only EHR records, depending on what has arrived so far.

---

## Naming Convention

Files are named by coded patient ID: `patient_XXX.h5` (e.g., `patient_001.h5`). Patient IDs follow the format `P001`, `P002`, etc.

---

## File Layout

```
patient_XXX.h5
│
├── [top-level attributes]
├── demographics/
├── imaging/
│   └── {modality}_{date}/
├── data/
│   └── {data_type}/
├── Notes/
│   └── note_{NNNN}/
├── chart_review/
│   ├── human/
│   │   └── note_{NNNN}/
│   └── llm/
│       └── note_{NNNN}/
├── genomics/
│   └── {assay}_{date}/
└── changelog/
```

---

## Top-Level Attributes

These attributes are attached directly to the root of the HDF5 file. All are **required**.

| Attribute        | Type          | Example                              | Description                                      |
|------------------|---------------|--------------------------------------|--------------------------------------------------|
| `patient_id`     | string        | `"P001"`                             | Coded study identifier                           |
| `tags`           | list[string]  | `["lung_ca", "smoker", "stage3"]`    | Freeform tags for cohort filtering               |
| `active_irbs`    | list[string]  | `["IRB-2025-001", "IRB-2025-003"]`   | IRB protocols the patient is currently enrolled in |
| `irb_history`    | list[string]  | `["IRB-2024-010"]`                   | IRB protocols the patient was previously enrolled in |
| `created_date`   | string        | `"2026-01-15"`                       | ISO 8601 date the file was first created         |

---

## Groups

### `demographics/`

**Required.** Created when the patient file is first generated.

Stored as group-level attributes (not datasets).

| Attribute   | Type   | Example                              | Description              |
|-------------|--------|--------------------------------------|--------------------------|
| `age`       | int    | `64`                                 | Patient age              |
| `sex`       | string | `"M"`                                | `"M"` or `"F"`          |
| `diagnosis` | string | `"Non-small cell lung carcinoma"`    | Primary diagnosis        |
| `staging`   | string | `"Stage III"`                        | Disease staging, if applicable |

---

### `imaging/`

**Optional.** Populated when imaging data is ingested.

Each imaging session is a subgroup named `{modality}_{scan_date}` (e.g., `ct_2026-03-10`, `mri_2026-05-15`).

#### Subgroup: `{modality}_{date}/`

**Datasets:**

| Dataset   | Dtype   | Shape                        | Description               |
|-----------|---------|------------------------------|---------------------------|
| `volume`  | int16   | `[num_slices, rows, cols]`   | The imaging volume array  |

Typical shapes: CT volumes are `[slices, 512, 512]`; MRI volumes are `[slices, 256, 256]`.

**Attributes:**

| Attribute          | Type          | Example              | Description                          |
|--------------------|---------------|----------------------|--------------------------------------|
| `modality`         | string        | `"CT"`               | Imaging modality (`"CT"`, `"MRI"`, etc.) |
| `scan_date`        | string        | `"2026-03-10"`       | ISO 8601 date of the scan            |
| `num_slices`       | int           | `300`                | Number of slices in the volume       |
| `voxel_spacing_mm` | list[float]   | `[0.5, 0.5, 1.0]`   | Voxel dimensions in mm `[x, y, z]`  |
| `body_region`      | string        | `"chest"`            | Anatomical region                    |
| `source_irb`       | string        | `"IRB-2025-001"`     | IRB protocol that provided this data |

---

### `data/`

**Optional.** Populated when structured EHR or measurement data is ingested.

Each data type is a subgroup named by type (e.g., `pft`, `glucose`). The internal structure varies depending on whether the data type is a single-point measurement or a time-series.

#### Single-point measurement example: `data/pft/`

All values stored as group-level attributes.

| Attribute        | Type   | Example         | Description                      |
|------------------|--------|-----------------|----------------------------------|
| `fev1`           | float  | `2.1`           | Measured value                   |
| `fvc`            | float  | `3.4`           | Measured value                   |
| `fev1_fvc_ratio` | float  | `0.62`          | Derived ratio                    |
| `test_date`      | string | `"2026-03-12"`  | ISO 8601 date of the test        |

#### Time-series example: `data/glucose/`

**Datasets:**

| Dataset       | Dtype   | Shape    | Description                    |
|---------------|---------|----------|--------------------------------|
| `timestamps`  | float64 | `[N]`   | Timestamp array                |
| `values`      | float64 | `[N]`   | Corresponding measurement values |

**Attributes:**

| Attribute          | Type   | Example         | Description                          |
|--------------------|--------|-----------------|--------------------------------------|
| `session_date`     | string | `"2026-03-10"`  | ISO 8601 date of the session         |
| `sampling_rate_hz` | float  | `1.0`           | Sampling frequency in Hz             |
| `device`           | string | `"Dexcom G7"`   | Recording device                     |

---

### `Notes/`

**Optional.** Populated when clinical notes are ingested.

Each note is a subgroup named `note_{NNNN}` with a zero-padded four-digit identifier (e.g., `note_0001`, `note_0002`).

#### Subgroup: `note_{NNNN}/`

**Datasets:**

| Dataset | Dtype                  | Description        |
|---------|------------------------|--------------------|
| `text`  | variable-length string | Full note content  |

**Attributes:**

| Attribute  | Type   | Example          | Description                                  |
|------------|--------|------------------|----------------------------------------------|
| `author`   | string | `"Dr. Smith"`    | Note author                                  |
| `date`     | string | `"2026-03-10"`   | ISO 8601 date                                |
| `category` | string | `"radiology"`    | Note category (`"radiology"`, `"pathology"`, `"general"`, etc.) |
| `reviewed` | bool   | `true`           | Whether the note has been reviewed           |

---

### `chart_review/`

**Optional.** Populated when structured chart review extractions are performed. Contains two parallel subgroups separating human and LLM extractions.

#### `chart_review/human/note_{NNNN}/`

Each subgroup corresponds to a note in `Notes/` by matching the note ID.

| Attribute      | Type   | Example              | Description                             |
|----------------|--------|----------------------|-----------------------------------------|
| `tumor_size_cm`| float  | *(varies)*           | Extracted tumor size (dataset or attr)   |
| `location`     | string | `"right upper lobe"` | Extracted anatomical location            |
| `reviewer`     | string | `"Dr. Chen"`         | Human reviewer name                      |
| `review_date`  | string | `"2026-04-15"`       | ISO 8601 date of the review              |

#### `chart_review/llm/note_{NNNN}/`

Same extracted fields as the human review, with model provenance attributes instead of reviewer identity.

| Attribute      | Type   | Example              | Description                             |
|----------------|--------|----------------------|-----------------------------------------|
| `tumor_size_cm`| float  | *(varies)*           | Extracted tumor size (dataset or attr)   |
| `model`        | string | `"claude-opus-4-6"`  | LLM model used for extraction            |
| `run_date`     | string | `"2026-04-10"`       | ISO 8601 date the extraction was run     |

---

### `genomics/`

**Optional.** Metadata and external file paths only — raw genomic data is stored outside the `.h5` file due to size.

Each assay is a subgroup named `{assay}_{date}` (e.g., `wgs_2026-07-15`).

#### Subgroup: `{assay}_{date}/`

| Attribute              | Type   | Example                              | Description                              |
|------------------------|--------|--------------------------------------|------------------------------------------|
| `sequencing_platform`  | string | `"Illumina NovaSeq"`                 | Sequencing platform                      |
| `coverage`             | int    | `30`                                 | Sequencing coverage depth                |
| `reference_genome`     | string | `"GRCh38"`                           | Reference genome build                   |
| `vcf_path`             | string | `"/genomics_archive/P001/variants/"` | Path to variant call files               |
| `bam_path`             | string | `"/genomics_archive/P001/aligned/"`  | Path to aligned reads                    |

---

### `changelog/`

**Required.** Created when the patient file is first generated and updated on every modification.

| Attribute       | Type          | Example                                  | Description                                   |
|-----------------|---------------|------------------------------------------|-----------------------------------------------|
| `last_modified` | string        | `"2026-05-10"`                           | ISO 8601 date of the most recent modification |
| `history`       | list[string]  | `["2026-01-15: created", "2026-03-10: imaging ingested"]` | Timestamped modification log   |

---

## Required vs Optional Groups

| Group            | Required | Created at              |
|------------------|----------|-------------------------|
| *(root attrs)*   | Yes      | File creation           |
| `demographics/`  | Yes      | File creation           |
| `changelog/`     | Yes      | File creation           |
| `imaging/`       | No       | Imaging ingestion       |
| `data/`          | No       | EHR / measurement ingestion |
| `Notes/`         | No       | Note ingestion          |
| `chart_review/`  | No       | Chart review extraction |
| `genomics/`      | No       | Genomics metadata ingestion |

---

## Date Format

All dates use **ISO 8601** format: `YYYY-MM-DD` (e.g., `"2026-03-10"`).

---

## String Encoding

All string attributes and datasets use **UTF-8** encoding.

---

## Data Stored Externally

The following data types are **not** embedded in the `.h5` file due to size. They are referenced by path only:

- Whole genome sequencing (WGS) raw data — referenced via `vcf_path` and `bam_path` in `genomics/`
- Video data
- Digital pathology images
