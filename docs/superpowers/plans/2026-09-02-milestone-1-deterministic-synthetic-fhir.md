# Milestone 1 Deterministic Synthetic FHIR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a fresh 20-patient synthetic FHIR R4 dataset with deterministic IDs and bytes, 10–20 chronological encounters per patient, independently verified references, eight explicit data-quality rules, and a reproducible dataset hash.

**Architecture:** Keep the existing Pydantic FHIR subset and seeded generator. Add a read-only quality layer that reloads emitted NDJSON instead of trusting generator counters, a deterministic manifest over managed artifacts, and a validation CLI that returns a nonzero exit code for any failed rule. Generation replaces only its managed output paths so reruns cannot inherit stale patient bundles.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, Ruff, strict mypy, JSON transaction Bundles, NDJSON.

**Spec:** `docs/IMPLEMENTATION_PLAN.md` Stage 2 and `docs/BUILD_PLAN.md` Milestone 1.

## Global Constraints

- Scope stays at the approved 20-patient Milestone 1 dataset; the additional Milestone 2 archetype files already present are preserved but not expanded.
- Default verification seed is `20260830`, reference date is `2026-08-30`, and encounter bounds are 10–20 inclusive.
- Generated primary identifiers remain deterministic and human-readable; no random UUIDs are introduced.
- The quality engine validates serialized artifacts independently and never accepts the generator's in-memory registry as proof.
- The generator may replace only `bundles/`, `ndjson/`, `dataset_manifest.json`, and `data_quality_summary.json` beneath its configured output directory.
- Existing tracked `artifacts/` are not overwritten during verification; fresh evidence uses an isolated output directory.
- The worktree contains pre-existing user changes, so this plan does not create commits or alter unrelated files.

---

### Task 1: Reject invalid generation contracts

**Files:**
- Modify: `libs/synthetic/config.py`
- Test: `libs/synthetic/tests/test_generator.py`

**Interfaces:**
- Produces: validated `EncounterConfig(min_per_patient: int, max_per_patient: int)`
- Produces: validated `GenerationConfig(patient_count: int, history_years: int, reference_date: date)`

- [ ] **Step 1: Write failing configuration tests**

Add literal tests that reject zero patients, zero history, zero encounter bounds, and `min_per_patient > max_per_patient`, and that accept the exact Milestone 1 boundary values.

```python
@pytest.mark.parametrize(
    "kwargs",
    [
        {"patient_count": 0},
        {"history_years": 0},
        {"encounters": {"min_per_patient": 0, "max_per_patient": 20}},
        {"encounters": {"min_per_patient": 21, "max_per_patient": 20}},
    ],
)
def test_generation_config_rejects_invalid_bounds(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GenerationConfig(**kwargs)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.venv/bin/pytest libs/synthetic/tests/test_generator.py -q`

Expected: the new invalid configurations are accepted, so the test fails.

- [ ] **Step 3: Add field constraints and cross-field validation**

Use `Field(ge=1)` for counts/history and an `after` model validator that rejects a maximum below the minimum. Add `reference_date: date = date(2026, 8, 30)` and make the runner consume it.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest libs/synthetic/tests/test_generator.py -q`

Expected: PASS.

---

### Task 2: Track every serialized FHIR reference

**Files:**
- Modify: `libs/synthetic/registry.py`
- Modify: `libs/synthetic/encounter_gen.py`
- Test: `libs/synthetic/tests/test_generator.py`

**Interfaces:**
- Produces: `ResourceRegistry.register_resource(resource_type: str, resource_id: str, payload: dict[str, Any]) -> str`
- Consumes: `libs.fhir.references.extract_references`

- [ ] **Step 1: Write a failing nested-reference test**

Register an Observation and a DiagnosticReport payload whose nested `result` references the Observation. Assert that `reference_count == 1`, then register a report pointing to a missing Observation and assert validation fails.

- [ ] **Step 2: Run the focused registry test and verify RED**

Expected: FAIL because `register_resource` does not exist.

- [ ] **Step 3: Implement generic reference registration**

`register_resource` first calls `register`, then walks the serialized payload with `extract_references` and records every target. Replace the hand-maintained subject/encounter/requester branches in `generate_encounters` with this interface for Encounter and archetype resources.

- [ ] **Step 4: Verify GREEN and run generator tests**

Run: `.venv/bin/pytest libs/synthetic/tests/test_generator.py -q`

Expected: PASS and no reference count regressions.

---

### Task 3: Build the independent eight-rule quality engine

**Files:**
- Create: `libs/quality/__init__.py`
- Create: `libs/quality/models.py`
- Create: `libs/quality/reader.py`
- Create: `libs/quality/rules.py`
- Create: `libs/quality/runner.py`
- Create: `libs/quality/tests/__init__.py`
- Create: `libs/quality/tests/test_quality.py`

**Interfaces:**
- Produces: `DatasetSnapshot` containing resources, full IDs, bundle encounter counts, manifest, and parse failures
- Produces: `RuleResult(name, status, checked, failures, details)`
- Produces: `ValidationReport(status, dataset_hash, rules, summary)`
- Produces: `validate_dataset(output_dir: Path, *, write_report: bool = True) -> ValidationReport`

- [ ] **Step 1: Write failing real-artifact rule tests**

Generate a two-patient dataset once per test fixture, then mutate copied NDJSON/bundle inputs to prove each named break is detected:

1. malformed or model-invalid resource → `schema_validation` fails;
2. repeated full resource ID → `duplicate_ids` fails;
3. missing target → `reference_resolution` fails;
4. encounter end before start or before birth → `temporal_consistency` fails;
5. a Coding without system/code → `coded_values` fails;
6. too few encounters for the manifest bounds → `encounter_count` fails;
7. Metformin/Lisinopril request without its prerequisite Condition → `clinical_scenario_consistency` fails;
8. valid data → `aggregate_distribution` passes with literal patient and resource counts.

Every test asserts the observable rule result, not an internal helper or mock.

- [ ] **Step 2: Run quality tests and verify RED**

Run: `.venv/bin/pytest libs/quality/tests/test_quality.py -q`

Expected: collection/import failure because the quality package does not exist.

- [ ] **Step 3: Implement typed quality models and artifact reader**

The reader loads all `ndjson/*.ndjson`, all patient transaction bundles, and `dataset_manifest.json`. It retains JSON/Pydantic parsing failures as data so validation returns a report instead of crashing on the first bad record.

- [ ] **Step 4: Implement the eight rules**

Rules derive expectations from serialized resources and manifest literals. Reference resolution recursively inspects every `reference`. Temporal checks parse ISO dates and compare Encounter periods with Patient birth dates. Clinical consistency maps RxNorm `6809` to SNOMED `44054006` and RxNorm `29046` to SNOMED `38341003` per patient.

- [ ] **Step 5: Implement orchestration and report writing**

`validate_dataset` runs all eight rules, sets overall status to `pass` only when every rule passes, and writes deterministic JSON with sorted keys and a trailing newline.

- [ ] **Step 6: Verify GREEN**

Run: `.venv/bin/pytest libs/quality/tests/test_quality.py -q`

Expected: all deliberate-failure and valid-dataset tests pass.

---

### Task 4: Emit a deterministic manifest and eliminate stale outputs

**Files:**
- Create: `libs/synthetic/manifest.py`
- Modify: `libs/synthetic/runner.py`
- Modify: `libs/synthetic/tests/test_generator.py`

**Interfaces:**
- Produces: `build_dataset_manifest(output_dir: Path, config: GenerationConfig) -> dict[str, Any]`
- Produces: `dataset_manifest.json` with configuration, per-file SHA-256 values, file/resource counts, and a canonical `dataset_hash`

- [ ] **Step 1: Write failing rerun and fixed-hash tests**

Run three patients and then two patients into the same directory. Assert exactly three bundle files remain (`shared.json` plus two patients). Generate the reference 20-patient dataset twice and assert both manifests contain the same fixed 64-character `dataset_hash`.

- [ ] **Step 2: Run focused tests and verify RED**

Expected: stale patient bundle remains and `dataset_manifest.json` is absent.

- [ ] **Step 3: Implement precise managed-output replacement**

Before generation, remove only the four managed outputs named in Global Constraints. Never remove the configured output root or unrelated siblings.

- [ ] **Step 4: Implement deterministic manifest hashing**

Hash each relative file name, a NUL separator, and file bytes in sorted order. The aggregate dataset hash covers Bundles and NDJSON, while the manifest stores the exact generation configuration and reference date separately.

- [ ] **Step 5: Integrate independent validation**

After writing Bundles, NDJSON, and the manifest, call `validate_dataset`. Preserve the existing top-level DQ summary fields for downstream compatibility, add `status`, `dataset_hash`, and the eight typed rule results, and raise if any rule fails.

- [ ] **Step 6: Verify GREEN and mutation strength**

Run the focused tests, then temporarily alter one generated byte and confirm validation fails; restore the fixture and confirm it passes.

---

### Task 5: Add the validation CLI and reliable Make targets

**Files:**
- Create: `pipelines/validate.py`
- Modify: `pipelines/generate.py`
- Modify: `Makefile`
- Test: `tests/test_generation_commands.py`

**Interfaces:**
- Produces: `python -m pipelines.validate --input <directory>`
- Produces: `make generate PATIENTS=20 SEED=20260830 OUTPUT=<directory>`
- Produces: `make validate OUTPUT=<directory>`

- [ ] **Step 1: Write failing subprocess contract tests**

Generate a small valid dataset and assert the validator exits 0 and prints all eight passing rule names. Corrupt a reference and assert exit 1. Assert `make --dry-run generate` and `make --dry-run validate` pass the configured output directory.

- [ ] **Step 2: Run command tests and verify RED**

Expected: FAIL because `pipelines.validate` is missing and Make does not pass `OUTPUT` to validation.

- [ ] **Step 3: Implement the CLI**

Parse `--input`, call `validate_dataset`, print a concise rule table and dataset hash, and return exit 1 for invalid/missing artifacts without a traceback.

- [ ] **Step 4: Align generator and Make commands**

The generation CLI prints the dataset hash and overall DQ status. Make uses the project-selected Python interpreter and forwards `PATIENTS`, `SEED`, and `OUTPUT` consistently.

- [ ] **Step 5: Verify GREEN**

Run: `.venv/bin/pytest tests/test_generation_commands.py -q`

Expected: PASS.

---

### Task 6: Verify the three initial scenario state machines

**Files:**
- Create: `libs/synthetic/tests/test_initial_archetypes.py`
- Modify only if a failing behavior requires it: `libs/synthetic/archetypes/healthy.py`, `diabetes.py`, `hypertension.py`

**Interfaces:**
- Verifies: Healthy vital ranges and required coding
- Verifies: diabetes observations precede Condition/Metformin and post-diagnosis monitoring follows
- Verifies: two elevated hypertension visits precede Condition/Lisinopril and treated monitoring follows

- [ ] **Step 1: Add deterministic state-transition tests**

Use fixed timestamps, `random.Random` seeds, a local deterministic ID closure, and real `PatientState`. Assert resource types, codes, chronology, and literal physiological bounds.

- [ ] **Step 2: Run the tests**

If a test fails, use systematic debugging to trace the state transition and add the smallest production fix after confirming the root cause. If all pass, the tests characterize and protect the already-present behavior without changing it.

- [ ] **Step 3: Run all synthetic and quality tests**

Run: `.venv/bin/pytest libs/fhir/tests libs/synthetic/tests libs/quality/tests -q`

Expected: PASS.

---

### Task 7: Produce fresh Milestone 1 evidence and synchronize trackers

**Files:**
- Create: `docs/evidence/milestone-1-verification.md`
- Modify: `docs/BUILD_PLAN.md`
- Modify: `docs/FINISH_LINE_TRACKER.md`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `README.md`

**Interfaces:**
- Produces: requirement-by-requirement evidence with exact commands, counts, hash, and limitations

- [ ] **Step 1: Run a fresh isolated reference generation**

Run `make generate PATIENTS=20 SEED=20260830 OUTPUT=<new temporary directory>` and record duration, resource counts, encounter distribution, and dataset hash.

- [ ] **Step 2: Run independent validation**

Run `make validate OUTPUT=<same directory>` and require all eight named rules to pass.

- [ ] **Step 3: Verify fixed reproducibility**

Generate the same configuration into a second new directory and compare manifest `dataset_hash` values and complete managed-artifact tree hashes.

- [ ] **Step 4: Run the full repository gate**

Run: `make check`

Expected: Ruff, formatting, strict mypy, all pytest suites, ESLint, TypeScript, and Next.js production build pass.

- [ ] **Step 5: Audit every Milestone 1 deliverable and exit criterion**

Map configuration, IDs, demographics, pools, encounters, three scenarios, serialization, reference validation, DQ report, exact count, encounter bounds, zero dangling references, and deterministic hash to direct file/runtime evidence.

- [ ] **Step 6: Update documentation**

Mark Milestone 1 complete only after the audit has direct evidence for every row. Correct the historical implementation tracker so checked boxes reflect current verification rather than intent.
