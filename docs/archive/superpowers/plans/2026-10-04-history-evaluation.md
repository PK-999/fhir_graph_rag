# Grounded history and evaluation continuation

User intent remains a complete personal portfolio project for mock FHIR → graph → grounded retrieval. This continuation improves existing patient-history retrieval and independently verifies all shipped question intents. Work stays local; existing credentials, data, volumes, and uncommitted changes are preserved.

## Design

History lists directly linked patient resources, limited by the strict plan. Each supported resource contributes its recorded event time: Observation/DiagnosticReport effectiveDateTime, Encounter period.start, Condition onsetDateTime (recordedDate fallback), MedicationRequest/ServiceRequest authoredOn, Procedure performedDateTime, and AllergyIntolerance recordedDate. Dates are labeled by their exact FHIR field; they do not imply when treatment was actually taken. Sort chronologically across offsets, newest first; undated resources follow, with canonical IDs breaking ties. Missing patients yield no rows; a patient without history retains a patient row and citation.

The independent NDJSON oracle will verify history resource identity/order, patient association, recorded date fields, and evidence. Expand live cases with hypertension, combined diabetes/lab/medication filters, threshold equality, zero matches, missing-patient history, and unsupported-filter abstention. Verify the bounded HAPI proxy against independently expected resource fields, so source citations must resolve to the same facts rather than merely have a plausible URL. Each distinct cited resource is fetched once per evaluation.

The assistant gets a runnable patient-history example, and history rows expose clear resource/date labels while evidence retains exact source fields. Setup/handoff documentation records reproducible results and actual remaining limits. No new services, paid models, public deployment, or Git commits are needed.

## Implementation checklist

- [x] Add failing oracle/evidence and browser regressions for dated history and runnable examples.
- [x] Add recorded history times to owned Cypher and exact date citations; keep strict plan and bounded results.
- [x] Expand the independent oracle/cases and validate live source resources; test drift, failed source fetch, and incorrect patient association.
- [x] Verify native setup configuration preservation, live Docker queries, complete quality gates, and browser flows.
- [x] Obtain independent final review, fix material findings, and update documentation/evidence.

## Execution record

Inline implementation. Existing portfolio spec remains authoritative. The source proxy check is an additional grounding gate, not full FHIR profile validation. Final review uses the requesting-code-review skill. Work occurs in the existing dirty workspace because it contains the previously delivered demo; no isolated checkout or staging of source changes.

## Completion evidence — 2026-10-05

`make check` passed: 233 Python tests, Ruff/formatting/strict mypy, frontend lint/types/unit test, and production build. `make verify-demo` passed readiness, 17 independent cases, 246 distinct cited FHIR sources, and the live history/source browser walkthrough. Twelve controlled Chromium regressions passed. The dataset and stored resource/reference counts stayed unchanged.

Observed RED→GREEN: missing history date citations/order, unreadable placeholder example, source-value/identity/patient drift, allergy patient references, and nanosecond truncation. An actual compiled latest-lab sort was wrong for equal instants with different offsets; epoch seconds and nanoseconds now precede the ID tie break. Allergy lookup and citations were checked in an always-rolled-back transaction, leaving the demo unchanged.

Independent review found the old browser example assertion, source-patient drift, allergy membership, and nanosecond oracle precision gaps; all were fixed and re-reviewed with no remaining material code findings.

Ruling: the original design said directly linked resources; standard AllergyIntolerance.patient references are included alongside subject references. Standard top-level reference properties and DISTINCT prevent unrelated nested links and duplicate records. History remains bounded to the requested record limit (maximum100), and source checks validate cited fields/association rather than full upstream conformance.

No source changes were staged or committed. Native setup preservation was already verified in the preceding demo milestone; this continuation adds `make verify-demo` for reproducible handoff checks.
