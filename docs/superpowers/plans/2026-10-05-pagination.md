# Grounded result pagination implementation plan

**Goal:** Retrieve complete cohorts and recorded patient histories across bounded pages, with exact evidence on each page and independent verification of completeness.

**Design:** Keep the existing four strict query intents. Add a transport-level nonnegative integer `offset` to assistant requests; it is not a model plan field. Owned templates use stable ordering, `SKIP`, and a `limit + 1` lookahead. Responses expose `pagination` with offset, page limit, has_more, and next_offset. The UI appends a page using the previously returned explicit plan, deduplicates evidence, and retains loaded results after a failed page request. No total count or database snapshot is implied.

**Scope:** Existing local synthetic dataset and services; preserve source files, credentials, volumes, and prior uncommitted work. No new dependency, paid service, public deployment, or commit. Offset pagination is appropriate for this registered local dataset; mutations between requests can change page membership. Streaming ingestion and new question intents remain separate work.

## Tasks

- [x] Add failing API tests for lookahead exclusion from results/evidence, full/final/empty pages, explicit-plan continuation, and invalid offsets. Implement bounded compiler pagination and additive response metadata.
- [x] Add independent evaluator regressions for 101 patients, more than 100 history records, premature termination, repeated/wrong pages, invalid continuation, later-page source drift, and failed continuation. Follow complete cases across pages; retain parser coverage and remove the old 100-patient refusal.
- [x] Add failing browser tests for appending ordered results/evidence, retrying a failed page without losing results, and resetting on a new question. Implement Load more and extend the live walkthrough to traverse all 80 first-patient records.
- [x] Run the full quality gate, controlled browser suite, and live readiness/evaluation/browser checks. Obtain a fresh independent code review, fix material findings, and refresh current documentation and portable evidence.

## Review focus

- Lookahead rows must never become returned facts or citations.
- Exact page boundaries must end without an unnecessary extra page.
- History pages may repeat the Patient ID but must not duplicate resource IDs.
- Failed continuation must retain earlier rows and the same retry offset.
- Evaluation must fail on false has_more, unsafe/nonadvancing offsets, duplicates, missing later rows, and later-page source drift.

## Completion evidence

Completed 2026-10-05 in the existing working tree, preserving the earlier uncommitted project work. No commit, push, service reset, or dataset replacement was performed.

- API regressions failed before offset support and passed after lookahead slicing/metadata were implemented.
- Independent oracle/traversal regressions failed before pagination support and passed after complete-page validation. Advertised parser cases now also traverse complete results while their first request still tests parsing.
- Browser Load more/retry/reset regressions failed before the UI change and passed afterwards. Wrong-offset, repeated-row, changed-plan, and empty-page checks were separately observed failing before continuation guards.
- Fresh read-only independent review found three material gaps: unchecked initial plans, unchecked displayed fact columns, and acceptance of an empty continuation after a promised next row. Each was reproduced by a failing regression and corrected. Expanded independent expectations include patient names, condition code/display, lab code/status/display, medication code, and history display/date field. Follow-up source mutation cases pass.
- Removing the old dataset cap exposed a collision in the missing-patient case's fixed candidate range. A 101-patient collision fixture reproduced `StopIteration`; using patient count plus one candidates fixed it, with the regression passing.
- `make check`: 262 Python tests pass, Ruff/formatting/mypy pass, frontend lint/types/unit/production build pass.
- `make browser-check`: 19 controlled Chromium regressions pass.
- `make verify-demo`: readiness passes; 17 cases traverse 39 pages with 246 distinct cited FHIR source checks; the live browser retrieves all 80 first-patient history rows across four pages and retains one Patient citation.
- Actual owned queries passed in an always-rolled-back Neo4j fixture: patient listing201 rows/3 pages; condition cohort101 rows/2 pages; latest lab with active medication101 rows/2 pages, with and without the condition filter; history103 rows/2 pages. Node count remains7957 before and after. HAPI and run audit were not changed by the fixture.

Portable results and the current screenshot are in [portfolio verification](../../evidence/portfolio-verification.json) and [browser capture](../../evidence/portfolio-demo.png). Offset pagination assumes the registered dataset remains unchanged between requests; it is not a snapshot or a larger-scale performance claim. The separate cohort builder and patient-detail projections remain bounded.
