"""Top-level synthetic data generation runner.

Orchestrates: pools → patients → encounters → archetypes → validation → output.
"""

from __future__ import annotations

import json
import random
from datetime import date
from pathlib import Path

from libs.fhir.bundle import build_transaction_bundle
from libs.fhir.models.base import FHIRResource
from libs.fhir.ndjson import write_ndjson
from libs.synthetic.archetypes.ari import ARIArchetype
from libs.synthetic.archetypes.asthma import AsthmaArchetype
from libs.synthetic.archetypes.base import ClinicalArchetype
from libs.synthetic.archetypes.ckd import CKDArchetype
from libs.synthetic.archetypes.copd import COPDArchetype
from libs.synthetic.archetypes.diabetes import DiabetesArchetype
from libs.synthetic.archetypes.healthy import HealthyArchetype
from libs.synthetic.archetypes.hyperlipidemia import HyperlipidemiaArchetype
from libs.synthetic.archetypes.hypertension import HypertensionArchetype
from libs.synthetic.archetypes.ihd import IHDArchetype
from libs.synthetic.archetypes.msk_injury import MskInjuryArchetype
from libs.synthetic.archetypes.obesity import ObesityArchetype
from libs.synthetic.archetypes.pregnancy import PregnancyArchetype
from libs.synthetic.config import GenerationConfig
from libs.synthetic.demographics import generate_patient
from libs.synthetic.encounter_gen import generate_encounters
from libs.synthetic.id_factory import IdFactory
from libs.synthetic.pools import create_organization_pool, create_practitioner_pool
from libs.synthetic.registry import ResourceRegistry

# All available archetypes
ALL_ARCHETYPES: list[ClinicalArchetype] = [
    HealthyArchetype(),
    DiabetesArchetype(),
    HypertensionArchetype(),
    HyperlipidemiaArchetype(),
    ObesityArchetype(),
    PregnancyArchetype(),
    MskInjuryArchetype(),
    AsthmaArchetype(),
    COPDArchetype(),
    CKDArchetype(),
    IHDArchetype(),
    ARIArchetype(),
]


def run_generation(config: GenerationConfig) -> dict:
    """Run the full synthetic data generation pipeline.

    Returns a data quality summary dict.
    """
    rng = random.Random(config.seed)
    id_factory = IdFactory()
    registry = ResourceRegistry()
    output_dir = Path(config.output_dir)
    reference_date = date(2026, 8, 30)

    # ── 1. Create shared pools ──
    org_count = rng.randint(8, 12)
    pract_count = rng.randint(50, 80)

    organizations = create_organization_pool(org_count, id_factory, rng)
    practitioners = create_practitioner_pool(pract_count, organizations, id_factory, rng)

    # Register shared resources
    for org in organizations:
        registry.register("Organization", org.id)
    for pract in practitioners:
        registry.register("Practitioner", pract.id)

    all_patients: list[FHIRResource] = []
    all_resources_flat: list[FHIRResource] = []  # for NDJSON
    encounter_counts: list[int] = []

    # ── 2. Generate patients ──
    for patient_seq in range(1, config.patient_count + 1):
        # Create patient
        patient = generate_patient(patient_seq, id_factory, rng, reference_date)
        registry.register("Patient", patient.id)
        all_patients.append(patient)

        # Calculate age
        age = (reference_date - patient.birthDate).days // 365 if patient.birthDate else 30

        # Assign archetypes (0–3)
        num_archetypes = rng.choices([0, 1, 2, 3], weights=[0.1, 0.4, 0.35, 0.15], k=1)[0]
        compatible = [a for a in ALL_ARCHETYPES if a.is_compatible(patient.gender or "unknown", age)]
        # Always include healthy as base
        selected = [HealthyArchetype()]
        if num_archetypes > 0 and compatible:
            extra = rng.sample(compatible, min(num_archetypes, len(compatible)))
            for a in extra:
                if a.name != "healthy":
                    selected.append(a)

        # Generate encounters and linked resources
        encounter_resources = generate_encounters(
            patient_id=patient.id,
            patient_birth_date=patient.birthDate or date(1990, 1, 1),
            patient_gender=patient.gender or "unknown",
            patient_age=age,
            archetypes=selected,
            practitioners=practitioners,
            organizations=organizations,
            id_factory=id_factory,
            registry=registry,
            rng=rng,
            config_encounters_min=config.encounters.min_per_patient,
            config_encounters_max=config.encounters.max_per_patient,
            config_history_years=config.history_years,
            patient_seq=patient_seq,
            reference_date=reference_date,
        )

        # Count encounters
        enc_count = sum(1 for r in encounter_resources if r.resourceType == "Encounter")
        encounter_counts.append(enc_count)

        # Collect all resources for this patient
        patient_resources = [patient, *encounter_resources]
        all_resources_flat.extend(patient_resources)

        # ── Write per-patient Bundle ──
        bundle = build_transaction_bundle(
            patient_resources,
            bundle_id=f"bundle-{patient.id}",
        )
        bundle_path = output_dir / "bundles" / f"{patient.id}.json"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        with bundle_path.open("w") as f:
            json.dump(bundle.model_dump(exclude_none=True), f, indent=2, default=str)

    # ── 3. Add shared resources to flat list ──
    shared_resources: list[FHIRResource] = [*organizations, *practitioners]  # type: ignore[list-item]
    all_resources_flat = [*shared_resources, *all_resources_flat]

    # Write shared resources bundle
    shared_bundle = build_transaction_bundle(shared_resources, bundle_id="bundle-shared")
    shared_path = output_dir / "bundles" / "shared.json"
    with shared_path.open("w") as f:
        json.dump(shared_bundle.model_dump(exclude_none=True), f, indent=2, default=str)

    # ── 4. Write NDJSON by resource type ──
    ndjson_dir = output_dir / "ndjson"
    resources_by_type: dict[str, list[FHIRResource]] = {}
    for r in all_resources_flat:
        resources_by_type.setdefault(r.resourceType, []).append(r)
    for rtype, resources in resources_by_type.items():
        write_ndjson(resources, ndjson_dir / f"{rtype}.ndjson")

    # ── 5. Validate ──
    registry.validate()  # raises on dangling references

    # ── 6. Build DQ summary ──
    dq_summary = {
        "seed": config.seed,
        "patient_count": config.patient_count,
        "encounter_count": sum(encounter_counts),
        "resource_counts": registry.resource_counts,
        "total_resources": registry.total_count(),
        "dangling_references": len(registry.get_dangling_references()),
        "duplicate_ids": len(registry.get_duplicate_ids()),
        "reference_count": registry.reference_count,
        "encounters_per_patient": {
            "min": min(encounter_counts),
            "max": max(encounter_counts),
            "mean": round(sum(encounter_counts) / len(encounter_counts), 1),
        },
        "validation_failures": [],
    }

    # Write DQ summary
    dq_path = output_dir / "data_quality_summary.json"
    dq_path.parent.mkdir(parents=True, exist_ok=True)
    with dq_path.open("w") as f:
        json.dump(dq_summary, f, indent=2)

    return dq_summary
