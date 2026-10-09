# Pinned HL7 FHIR R4 structural schema

`fhir-r4.schema.json` is the unchanged official HL7 FHIR R4 4.0.1 JSON schema
downloaded from <https://hl7.org/fhir/R4/fhir.schema.json>. `manifest.json` records
the exact SHA-256, byte count, version, source and license. Schema loading fails
if its bytes do not match the pinned hash; validation needs no network access.

HL7 publishes this specification under CC0-1.0:
<https://hl7.org/fhir/R4/license.html>. Copyright 2011+ HL7. HL7 and FHIR are
registered trademarks of Health Level Seven International. Their use does not
imply endorsement by HL7.

Run `python -m pipelines.validate_fhir --input artifacts/demo` for the standalone
structural, identity and reference report. Supply `--service-base-url` explicitly
when absolute references are known to address the same service. The eight-rule
dataset quality validator also runs the pinned structural checks for NDJSON and
every bundle, including shared resources.

The upstream schema omits complex-object type declarations and nonempty-array
constraints. Separate checks enforce those FHIR JSON representation rules from
<https://hl7.org/fhir/R4/json.html>. A new model serialization omits empty arrays;
validation never removes fields or changes existing source payloads. This narrow
serialization correction changes the hashes of newly generated datasets.
All numbers must be finite: Python's decoder accepts bare `NaN` and `Infinity`,
but shared structural validation rejects them recursively with their source
field paths before either ingestion pipeline opens a store.

Passing this check does **not** establish full FHIR conformance. It does not
comprehensively evaluate profiles, FHIRPath invariants, choice exclusivity,
minimum cardinalities, terminology bindings or code membership. The official
schema itself allows some payloads that a full FHIR validator would reject.
Reference handling follows the supported subset of
<https://hl7.org/fhir/R4/references.html>: relative identities, explicit
same-service absolute URLs, scoped bundle fullUrl/URN aliases and contained
fragments. Unknown external URLs are diagnosed and never relabeled as local.
Version-specific references, conditional references, and logical identifiers are
outside this project's local graph resolution contract.
