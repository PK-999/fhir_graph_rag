# Synthetic FHIR Data Generation Specification

## Hard contract
Generate:
- exactly 1,000 patients
- exactly 10–20 encounters per patient
- target mean: ~15 encounters/patient
- approximately 15,000 encounters total
- deterministic output from a configurable seed
- zero unresolved internal FHIR references

## Strategy
Use a **deterministic scenario-driven generator**.

Synthea may be used as:
- a realism reference;
- a source of example distributions;
- an optional seed dataset for comparison/testing.

Do not depend on an LLM to generate patient-level records at runtime.

## Configuration

```yaml
seed: 20260830
patient_count: 1000
encounters:
  min_per_patient: 10
  max_per_patient: 20
history_years: 5
output:
  fhir_version: R4
  bundle_per_patient: true
  ndjson: true
```

## Patient demographics
Generate coherent demographics:
- date of birth
- administrative gender
- synthetic name
- phone/email/address
- marital status where relevant
- preferred language where relevant

Use broad age bands rather than a flat distribution:
- pediatric
- young adult
- adult
- middle-aged
- older adult

The distribution must be configurable. Do not present it as a real-world epidemiological estimate unless sourced.

## Clinical archetypes
Assign each patient 0–3 longitudinal archetypes, constrained by age and sex where applicable.

Initial archetypes:
- generally healthy/preventive
- hypertension
- type 2 diabetes
- hyperlipidemia
- asthma
- COPD
- obesity
- chronic kidney disease
- ischemic heart disease
- pregnancy episode
- acute respiratory infection
- musculoskeletal injury

Use compatibility constraints:
- pregnancy only when biologically/contextually compatible with generated demographics;
- type 2 diabetes prevalence rises with age in the synthetic rules;
- COPD should be rare in children;
- chronic diagnoses persist across later encounters unless resolved.

These are synthetic rules for plausibility, not clinical guidance.

## Encounter generation

### Count
For patient `p`:
```python
encounter_count = rng.randint(10, 20)
```

### Timeline
- produce encounters across the configured lookback period;
- sort chronologically;
- no encounter begins before patient birth;
- `Encounter.period.start <= Encounter.period.end`;
- generate a mix of outpatient, wellness, urgent, emergency, and inpatient encounters;
- inpatient stays may span multiple days;
- avoid impossible overlap unless representing a deliberate hospitalization-related event.

### Encounter-linked resources
Resources created during an encounter reference:
- `subject -> Patient/{id}`
- `encounter -> Encounter/{id}` where the FHIR resource supports it
- practitioner/organization where appropriate

## Clinical state machine
Patient state evolves chronologically.

Example diabetes trajectory:
1. risk/metabolic observations may appear;
2. elevated glucose/HbA1c observations;
3. diabetes Condition;
4. subsequent monitoring;
5. MedicationRequest when scenario indicates treatment;
6. later observations trend within configured bounds.

Never create downstream events before their prerequisites.

## Observations
Support a curated catalog, including:
- body weight
- BMI
- systolic/diastolic BP
- heart rate
- temperature
- glucose
- HbA1c
- cholesterol/lipid values
- creatinine/eGFR where relevant

Each observation definition contains:
```yaml
key:
  code_system:
  code:
  display:
  unit:
  plausible_min:
  plausible_max:
  precision:
```

Observation values must:
- stay within configured plausible synthetic bounds;
- use a stable unit;
- correlate loosely with relevant archetypes;
- change gradually over time unless an acute scenario justifies otherwise.

## Conditions
Use curated SNOMED CT or ICD-coded concepts where licensing/use permits.
Each Condition:
- references Patient;
- may reference Encounter;
- has onset date <= recorded date;
- clinical status evolves consistently.

## Medications
Use a small curated RxNorm-based catalog.

MedicationRequest:
- references Patient;
- references Medication by stable resource ID or uses a codeable concept consistently;
- authoredOn must be on/after relevant diagnosis or encounter when scenario requires it;
- status and intent must be valid;
- do not model medication as clinically guaranteed treatment.

## Procedures / diagnostic reports / service requests
Generate only when scenario templates require them.
Maintain:
`ServiceRequest -> DiagnosticReport/Procedure -> Observation` links where applicable.

## Practitioners and organizations
Create shared reference pools:
- 8–15 organizations
- 50–100 practitioners
- practitioners attached to organizations/specialties
- encounters reuse practitioners instead of creating a new clinician per encounter

## Referential integrity registry
Generation must use an in-memory registry:

```python
registry = {
    "Patient": set(),
    "Encounter": set(),
    "Practitioner": set(),
    ...
}
```

Every reference is registered as an edge:
```python
refs.append(("Observation/o1", "subject", "Patient/p1"))
```

At the end:
```python
for source, field, target in refs:
    assert target in global_resource_index
```

No output is published if any assertion fails.

## Bundle rules
If exporting per-patient Bundles:
- each `entry.fullUrl` must be unique;
- references must resolve to Bundle entries or intentionally shared external resources;
- shared Practitioner/Organization resources should be handled consistently;
- use transaction Bundles for loading to HAPI when useful.

## Validation pipeline
Every generated run must execute:

1. schema validation
2. duplicate resource ID check
3. reference resolution check
4. temporal consistency check
5. coded-value/unit check
6. patient encounter-count assertion
7. clinical-scenario consistency checks
8. aggregate distribution report

### Required assertions

```text
patients == 1000
10 <= encounters_per_patient <= 20
dangling_internal_references == 0
duplicate_resource_ids == 0
encounter_start_after_birth == 100%
observation_subject_resolved == 100%
condition_subject_resolved == 100%
medication_request_subject_resolved == 100%
```

## Quality report
Persist `artifacts/data_quality_summary.json`.

Minimum contents:
```json
{
  "seed": 20260830,
  "patient_count": 1000,
  "encounter_count": 15000,
  "resource_counts": {},
  "dangling_references": 0,
  "duplicate_ids": 0,
  "validation_failures": [],
  "encounters_per_patient": {
    "min": 10,
    "max": 20,
    "mean": 15.0
  }
}
```

## Reproducibility test
Generate 20 patients twice with the same seed and compare canonicalized hashes.
They must match.
