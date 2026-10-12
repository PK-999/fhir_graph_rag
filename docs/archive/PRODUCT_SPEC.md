# Product Specification

> **Approved finish-line direction (2026-09-01):** Target 100,000 synthetic patients on a workstation-first deployment. The primary persona is a clinical informatics researcher; the secondary persona is a practicing clinician. Research and Clinical views share the same evidence-backed data. Detailed decisions and release criteria are in [`superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md`](superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md).

## Product
**FHIRGraph** — a synthetic healthcare data intelligence and knowledge-graph platform.

## Audience
- **Primary:** Clinical informatics researchers
- **Secondary:** Practicing clinicians
- Supporting: data engineers, healthcare interoperability engineers, data architects, governance/data-quality teams, and technical reviewers

## Core value proposition
FHIRGraph converts realistic synthetic FHIR R4 records into an explainable healthcare knowledge graph that connects clinical events, terminology, provenance, quality, enterprise metadata, and AI-assisted exploration.

## Required demo capabilities

### 1. Dashboard
Show:
- patient count
- encounter count
- conditions
- observations
- medication requests
- procedures
- graph node/edge counts
- DQ pass rate
- latest ingestion run

### 2. Patient search
Search by:
- synthetic patient ID
- name
- age range
- gender
- condition

### 3. Patient 360
Tabs:
- Summary
- Timeline
- Knowledge Graph
- FHIR JSON
- Provenance

Summary includes:
- demographics
- active conditions
- current medications
- recent observations
- allergies
- recent encounters

### 4. Timeline
Chronological display of:
- encounters
- conditions
- medications
- observations/labs
- procedures

### 5. Graph Explorer
Interactive expansion by node and relationship.
Required filters:
- node type
- relationship type
- date range
- graph depth

### 6. Cohort Builder
Support AND filters such as:
- age > N
- condition
- medication
- observation code
- observation threshold
- encounter type

### 7. Data Quality
Show:
- resource counts
- referential-integrity pass rate
- schema validation pass rate
- missing-code statistics
- invalid timeline statistics
- failed records with reason

### 8. Lineage
Trace:
Business term -> EDM attribute -> FHIR element -> FHIR resource instance -> ingestion run -> source.

### 9. AI Assistant
Natural-language questions use typed plans, deterministic parameterized compilation, bounded read-only graph execution, and an immutable fact ledger.
Every factual answer must show evidence references. The versioned evaluation suite must contain at least 100 representative questions, achieve at least 95% correct plans and answers, reject 100% of mutation attempts, and provide evidence for 100% of factual results.

Example:
"Show diabetic patients whose latest HbA1c is above 8 and who have an active Metformin prescription."

## Non-goals for V1
- clinical decision support
- diagnosis recommendation
- real patient data
- write-back to EHR systems
- complete support for every FHIR resource
- production HIPAA certification

## Safety statement
The UI must visibly state:
**Synthetic demonstration data only. Not for clinical care or medical decision-making.**

## V1 FHIR resources
Required:
- Patient
- Encounter
- Condition
- Observation
- MedicationRequest
- Medication
- Procedure
- AllergyIntolerance
- DiagnosticReport
- ServiceRequest
- Practitioner
- Organization

Optional later:
- CarePlan
- Immunization
- Coverage
- Claim

## Flagship demonstration
1. Search a patient.
2. Open Patient 360.
3. Show diabetes condition and HbA1c trend.
4. Expand the graph to medication and encounter.
5. Ask why the patient appears connected to Metformin.
6. Show evidence resources and provenance.
7. Trace HbA1c from business term to `Observation.valueQuantity`.
8. Build a cohort of diabetes + elevated HbA1c + Metformin.
