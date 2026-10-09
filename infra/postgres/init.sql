-- FHIRGraph PostgreSQL initialization
-- This runs automatically on first container start
-- HAPI owns its tables here; portfolio audit tables stay in public.
CREATE SCHEMA IF NOT EXISTS hapi;

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
    action          VARCHAR(20) NOT NULL,  -- 'upserted' after a complete successful stage
    target_system   VARCHAR(32) NOT NULL,  -- 'hapi_fhir', 'neo4j'
    error_message   TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Idempotent upgrade for audit tables on an existing persistent volume.
-- Historical rows retain NULL evidence rather than inferred provenance.
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS canonical_id TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS source_artifact TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS source_location TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS source_line INTEGER;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS dataset_hash VARCHAR(64);
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS transformer_version VARCHAR(64);
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS target_identity TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS confirmed_stage VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_ingestion_canonical_id ON ingestion_events(canonical_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingestion_confirmed_event
ON ingestion_events(run_id, target_system, resource_type, resource_id, confirmed_stage);

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
