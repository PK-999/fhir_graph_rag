# Portfolio release implementation plan

**Goal:** Deliver the complete FHIRGraph portfolio release with reproducible source, evaluated retrieval, stronger validation and resumable ingestion, resource provenance, a 1,000-patient live benchmark, and public presentation.

**Spec:** [Release design](../specs/2026-10-09-portfolio-release-design.md).

**Execution:** Independent backend areas use focused parallel agents under the dispatching-parallel-agents skill. Coordinator implements release/integration and obtains fresh review. This continues existing uncommitted work; creating a clean worktree now would omit that implementation. Final clean-checkout verification follows a reviewed local commit.

## Tasks

- [x] Grounded retrieval: medication cohorts, patient lab history, complete-question paraphrases, strict local-model evidence claims, independent evaluations, and failure/source-drift regressions.
- [x] FHIR validation: pinned official R4 structural validation, explicit reference resolution/diagnostics, independent invalid-resource/reference tests, documentation of conformance limits.
- [x] Ingestion/provenance: streamed graph batches, preflight, content-bound resumable checkpoints, confirmed source hashes/locations and target/run provenance, recovery regressions.
- [x] Integrate provenance API/UI, grounded-summary controls, new supported examples and live browser regressions.
- [x] Release tooling: root frontend tracking, untrack generated artifacts while retaining files, dependency/install reproducibility, clean checkout, and working remote CI.
- [x] Live benchmark: isolated 1,000-patient stack, full ingestion/reconciliation/evaluation, timings/resource observations and interrupted-stage recovery. Preserve original demo.
- [ ] Portfolio delivery: case study, current diagrams/evidence, recorded walkthrough, static public presentation and release instructions.
- [ ] Final independent review, all quality/live/browser gates, publish release branch/PR and confirm remote CI. Resolve all material findings and report any externally blocked delivery step.

## Review focus

- Claims must match exact cited resource, field, and value; untrusted summaries cannot inject clinical statements.
- FHIR validation must distinguish structural validation from full invariants/profile/terminology coverage.
- Reference normalization must preserve source evidence and avoid turning unresolved/external references into invented local edges.
- Checkpoints must bind dataset and batch content, record only committed success, and reject changed inputs or destinations.
- Provenance cannot claim ingestion success for a failed batch/run or equate artifact hashes with live HAPI metadata hashes.
- Clean checkout, Python3.12 CI and the portfolio presentation must use committed source rather than local-only artifacts.

## Execution record

Started 2026-10-09. Existing GitHub origin and authenticated access verified. Docker is currently stopped; coordinator will start it before live gates. Existing work remains in place.

Backend review findings (legacy provenance schema handling and non-finite JSON numbers) are fixed and independently rechecked. Final source gates: 439 Python tests, 122 formatted files, strict typing of 106 sources, frontend lint/types/unit/build and 21 controlled Chromium cases passed. Fresh 1,000-patient ingestion reconciled 80,621 nodes and 174,998 references. The independent raw oracle was indexed by patient after an evaluation bottleneck; 82 evaluation tests preserve its expected outputs. Full scale evaluation, clean checkout and publication verification follow.

Independent checkout: fresh `make setup`, complete `make check` (438 tests before the timing regression), `make lint test` after the fix (439 tests), and all 21 controlled Chromium cases passed. Source hash/provenance is preserved in the final release evidence. The first complete scale evaluation passed 33/33 cases with 1,670 live sources and SIGINT graph replay recovered 512 confirmed batches; a final run measures the corrected validation timer.

Corrected full benchmark passed: validation 51.693s; full existing-data/checkpoint pipeline 240.4s, 33 cases / 493 pages / 1,670 distinct live sources, 20 sequential latency samples (p50 8.2ms, p95 23.3ms), and exact post-SIGINT graph recovery. Raw measurements and the distinct initial fresh-ingestion record are committed as public evidence.

Final source preparation: the restored 100-patient demo passed exact reconciliation, 33 live evaluation cases and the real browser walkthrough. The final MP4 and screenshot were recorded from this stack. The trimmed non-root production API passed readiness, graph retrieval, live source inspection, provenance and version checks. Publication status is recorded by the release PR, GitHub Actions, Pages deployment and v1.0.0 release; this planning snapshot precedes those final external steps.
