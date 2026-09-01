-- FHIRGraph PostgreSQL initialization
-- This runs automatically on first container start

-- Pipeline run tracking
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(64) UNIQUE NOT NULL,
    pipeline_name   VARCHAR(64) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'running',
    config_snapshot JSONB,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

-- Data quality results
CREATE TABLE IF NOT EXISTS data_quality_results (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(64) NOT NULL REFERENCES pipeline_runs(run_id),
    rule_name       VARCHAR(128) NOT NULL,
    passed          BOOLEAN NOT NULL,
    details         JSONB,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ingestion audit trail
CREATE TABLE IF NOT EXISTS ingestion_events (
    id              SERIAL PRIMARY KEY,
    run_id          VARCHAR(64) NOT NULL REFERENCES pipeline_runs(run_id),
    resource_type   VARCHAR(64) NOT NULL,
    resource_id     VARCHAR(128) NOT NULL,
    action          VARCHAR(20) NOT NULL,  -- 'created', 'updated', 'skipped', 'failed'
    target_system   VARCHAR(32) NOT NULL,  -- 'hapi_fhir', 'neo4j'
    error_message   TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lineage mappings: business term → FHIR element
CREATE TABLE IF NOT EXISTS lineage_mappings (
    id                  SERIAL PRIMARY KEY,
    business_domain     VARCHAR(128) NOT NULL,
    business_entity     VARCHAR(128) NOT NULL,
    business_attribute  VARCHAR(128) NOT NULL,
    fhir_resource_type  VARCHAR(64) NOT NULL,
    fhir_element        VARCHAR(128) NOT NULL,
    description         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_dq_results_run_id ON data_quality_results(run_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_run_id ON ingestion_events(run_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_resource ON ingestion_events(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_lineage_domain ON lineage_mappings(business_domain);
CREATE INDEX IF NOT EXISTS idx_lineage_fhir ON lineage_mappings(fhir_resource_type, fhir_element);

-- Seed lineage data for the flagship demo
INSERT INTO lineage_mappings (business_domain, business_entity, business_attribute, fhir_resource_type, fhir_element, description)
VALUES
    ('Clinical', 'Patient Demographics', 'Patient Name', 'Patient', 'Patient.name', 'Patient full name'),
    ('Clinical', 'Patient Demographics', 'Date of Birth', 'Patient', 'Patient.birthDate', 'Patient date of birth'),
    ('Clinical', 'Patient Demographics', 'Gender', 'Patient', 'Patient.gender', 'Administrative gender'),
    ('Clinical', 'Encounters', 'Visit Date', 'Encounter', 'Encounter.period.start', 'Encounter start date'),
    ('Clinical', 'Encounters', 'Visit Type', 'Encounter', 'Encounter.class', 'Encounter classification'),
    ('Clinical', 'Encounters', 'Discharge Date', 'Encounter', 'Encounter.period.end', 'Encounter end date'),
    ('Clinical', 'Diagnoses', 'Condition Code', 'Condition', 'Condition.code', 'Clinical condition SNOMED/ICD code'),
    ('Clinical', 'Diagnoses', 'Onset Date', 'Condition', 'Condition.onsetDateTime', 'When condition first appeared'),
    ('Clinical', 'Diagnoses', 'Clinical Status', 'Condition', 'Condition.clinicalStatus', 'active, recurrence, relapse, inactive, remission, resolved'),
    ('Lab Results', 'Observations', 'Lab Code', 'Observation', 'Observation.code', 'LOINC code for the observation'),
    ('Lab Results', 'Observations', 'Lab Value', 'Observation', 'Observation.valueQuantity.value', 'Numeric result value'),
    ('Lab Results', 'Observations', 'Lab Unit', 'Observation', 'Observation.valueQuantity.unit', 'Unit of measure'),
    ('Lab Results', 'HbA1c', 'HbA1c Value', 'Observation', 'Observation.valueQuantity', 'HbA1c percentage result'),
    ('Pharmacy', 'Medications', 'Drug Code', 'MedicationRequest', 'MedicationRequest.medicationCodeableConcept', 'RxNorm drug code'),
    ('Pharmacy', 'Medications', 'Prescriber', 'MedicationRequest', 'MedicationRequest.requester', 'Prescribing practitioner'),
    ('Pharmacy', 'Medications', 'Status', 'MedicationRequest', 'MedicationRequest.status', 'active, completed, cancelled, etc.'),
    ('Clinical', 'Procedures', 'Procedure Code', 'Procedure', 'Procedure.code', 'CPT/SNOMED procedure code'),
    ('Clinical', 'Allergies', 'Allergen', 'AllergyIntolerance', 'AllergyIntolerance.code', 'Substance causing allergy')
ON CONFLICT DO NOTHING;
