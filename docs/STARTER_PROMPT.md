# Exact Bootstrap Prompt for Gemini / Antigravity

Use this after copying the repository specification files into the repo.

```text
You are the lead engineer for FHIRGraph.

First read ./GEMINI.md.

Then read only:
- ./docs/ARCHITECTURE.md
- ./docs/DATA_GENERATION_SPEC.md
- ./docs/ENGINEERING_STANDARDS.md
- ./docs/BUILD_PLAN.md

Do not build the whole product in one pass.

Start with Milestone 0 and Milestone 1 only.

Your immediate objective is to create a clean repository foundation and implement a deterministic synthetic FHIR R4 generator that can first generate 20 test patients and later scale to exactly 1,000 patients with 10–20 encounters each.

Requirements:
- deterministic seed;
- stable resource IDs;
- shared Organization and Practitioner pools;
- chronological encounters;
- realistic but explicitly synthetic clinical scenario templates;
- FHIR R4 Patient, Encounter, Condition, Observation, Medication, MedicationRequest initially;
- global resource registry;
- automatic extraction/checking of all internal References;
- zero dangling references;
- duplicate-ID validation;
- temporal-consistency validation;
- output as per-patient FHIR Bundles plus NDJSON;
- data-quality summary JSON;
- unit and integration tests;
- same-seed reproducibility/hash test.

Use Python 3.12+, Pydantic, pytest and Ruff.
Prefer small typed modules.
Do not hard-code 1,000 patient records.
Do not use an LLM to generate runtime clinical records.
Do not silently ignore invalid data.

Before editing:
1. inspect the repo;
2. give me a concise implementation plan and proposed file tree;
3. identify any dependency you intend to add and why.

Then implement the milestone.
After implementation run the relevant lint/tests and report:
- files changed;
- commands run;
- test results;
- generated resource counts for a 20-patient smoke test;
- dangling-reference count;
- next recommended milestone.

Do not start frontend, Neo4j, GraphRAG, or HAPI integration yet unless required for the generator contract.
```
