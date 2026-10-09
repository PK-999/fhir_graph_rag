# FHIRGraph portfolio release

The user has authorized finishing the personal mock-healthcare portfolio project and the remaining work described in the project review. The deliverable is a reproducible, reviewed release demonstrating synthetic FHIR generation, validation, persistent ingestion, a reference graph, grounded retrieval and optional local-model evidence selection, source provenance, evaluation, and an inspectable portfolio walkthrough.

## Release gates

1. Root Git repository contains the frontend and all required source/tests; generated datasets are untracked without deleting local copies. A release branch and clean checkout reproduce installation, build, tests, and the demo. Publish reviewed changes to the existing public `PK-999/fhir_graph_rag` repository and verify GitHub Actions.
2. Expand the strict query catalog with evaluated medication cohorts and patient lab history plus common complete-question paraphrases. Preserve abstention for unsupported filters and clinical advice. Optional local Ollama summaries must use structured claims whose exact resource IDs, FHIR paths, and values validate against retrieved evidence; no unchecked clinical prose becomes an answer.
3. Validate serialized resources against pinned official FHIR R4 structural schemas, and distinguish that from full profile/terminology conformance. Resolve or explicitly diagnose supported relative, same-service absolute, bundle URN, and contained references without inventing graph edges. Preserve exact source representations and existing clinical query semantics.
4. Stream graph transformation in bounded batches after a complete preflight identity/reference check. Add content-bound ingestion checkpoints with safe same-dataset resumption and failure detection. Persist resource hash, source artifact/location, dataset hash, transformation version and stage-confirmed target/run information for resource provenance. Retain the single-dataset guard; new datasets use isolated stores rather than destructive replacement.
5. Ingest and reconcile 1,000 patients in an isolated live Compose project, recording duration, resources, store counts, and observed resource use. Test interrupted-stage recovery. Preserve the existing 100-patient stack and all volumes. Do not claim a 100,000-patient benchmark.
6. Deliver a case study, architecture/tradeoffs, measured evidence, walkthrough recording and a public portfolio presentation. Public presentation can be a static evidence-backed site with the recorded local demo; the interactive healthcare stack remains local unless a suitable hosting destination is configured. No paid services or real patient data are required.

## Work boundaries

Independent implementation areas are grounded retrieval (`libs/rag`, assistant route/evaluator); FHIR validation/reference handling (`libs/fhir`, `libs/quality`, standalone validation command); ingestion/provenance (`pipelines`, graph loader, audit schema). The coordinator owns integration, release tooling, provenance API/UI, frontend presentation, CI, benchmarks, documentation and delivery.

Existing credentials, original artifacts, Git history, and persistent Docker volumes must be preserved. There is no wholesale reset, force push, history rewrite, paid model switch, or assertion of complete FHIR conformance. Public release must contain no credentials or local connection history.

## Verification

Behavior changes use failing tests followed by implementation and passing tests. Independent raw-FHIR expectations cover every intent, complete page traversal, displayed facts, claims, and source drift. Integration tests exercise actual stores, checkpoint recovery, provenance hashes, persistent HAPI resources and graph reconciliation. Fresh review and all quality/browser/container gates precede publishing. Release documentation states exactly what was measured and what remains outside this personal-project scope.
