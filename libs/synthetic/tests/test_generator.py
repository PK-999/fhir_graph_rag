"""Tests for the synthetic data generator."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from libs.synthetic.config import EncounterConfig, GenerationConfig
from libs.synthetic.demographics import generate_patient
from libs.synthetic.id_factory import IdFactory
from libs.synthetic.manifest import build_dataset_manifest
from libs.synthetic.pools import create_organization_pool, create_practitioner_pool
from libs.synthetic.registry import ResourceRegistry
from libs.synthetic.runner import run_generation


class TestIdFactory:
    """Test deterministic ID generation."""

    def test_patient_id_format(self) -> None:
        factory = IdFactory()
        assert factory.patient_id(1) == "p-000001"
        assert factory.patient_id(999) == "p-000999"
        assert factory.patient_id(1000) == "p-001000"

    def test_resource_id_format(self) -> None:
        factory = IdFactory()
        rid = factory.resource_id(1, "Encounter")
        assert rid == "p-000001-e-0001"
        rid2 = factory.resource_id(1, "Encounter")
        assert rid2 == "p-000001-e-0002"

    def test_resource_id_different_patients(self) -> None:
        factory = IdFactory()
        rid1 = factory.resource_id(1, "Observation")
        rid2 = factory.resource_id(2, "Observation")
        assert rid1 != rid2

    def test_shared_id_format(self) -> None:
        factory = IdFactory()
        assert factory.shared_id("Practitioner", 42) == "pract-0042"
        assert factory.shared_id("Organization", 3) == "org-0003"

    def test_determinism(self) -> None:
        f1 = IdFactory()
        f2 = IdFactory()
        for i in range(1, 10):
            assert f1.patient_id(i) == f2.patient_id(i)
            assert f1.resource_id(i, "Encounter") == f2.resource_id(i, "Encounter")


class TestDemographics:
    """Test patient demographics generation."""

    def test_deterministic_demographics(self) -> None:
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        p1 = generate_patient(1, IdFactory(), rng1)
        p2 = generate_patient(1, IdFactory(), rng2)
        assert p1.id == p2.id
        assert p1.gender == p2.gender
        assert p1.birthDate == p2.birthDate

    def test_patient_has_required_fields(self) -> None:
        p = generate_patient(1, IdFactory(), random.Random(42))
        assert p.id == "p-000001"
        assert p.gender in ("male", "female")
        assert p.birthDate is not None
        assert p.name and len(p.name) > 0
        assert p.address and len(p.address) > 0
        assert p.telecom and len(p.telecom) > 0

    def test_birth_date_reasonable(self) -> None:
        ref = date(2026, 8, 30)
        p = generate_patient(1, IdFactory(), random.Random(42), reference_date=ref)
        assert p.birthDate is not None
        assert p.birthDate < ref
        age = (ref - p.birthDate).days // 365
        assert 0 <= age <= 95


class TestResourceRegistry:
    """Test the in-memory resource and reference registry."""

    def test_register_and_count(self) -> None:
        reg = ResourceRegistry()
        reg.register("Patient", "p-000001")
        reg.register("Encounter", "e-0001")
        assert reg.resource_count("Patient") == 1
        assert reg.total_count() == 2

    def test_duplicate_raises(self) -> None:
        reg = ResourceRegistry()
        reg.register("Patient", "p-000001")
        with pytest.raises(ValueError, match="Duplicate"):
            reg.register("Patient", "p-000001")

    def test_dangling_reference_detected(self) -> None:
        reg = ResourceRegistry()
        reg.register("Observation", "o-001")
        reg.add_reference("Observation/o-001", "subject", "Patient/p-999")
        assert len(reg.get_dangling_references()) == 1

    def test_resolved_reference(self) -> None:
        reg = ResourceRegistry()
        reg.register("Patient", "p-001")
        reg.register("Observation", "o-001")
        reg.add_reference("Observation/o-001", "subject", "Patient/p-001")
        assert len(reg.get_dangling_references()) == 0

    def test_validate_raises_on_dangling(self) -> None:
        reg = ResourceRegistry()
        reg.register("Observation", "o-001")
        reg.add_reference("Observation/o-001", "subject", "Patient/missing")
        with pytest.raises(ValueError, match="Referential integrity"):
            reg.validate()

    def test_register_resource_tracks_nested_result_references(self) -> None:
        reg = ResourceRegistry()
        reg.register("Observation", "o-001")

        reg.register_resource(
            "DiagnosticReport",
            "dr-001",
            {
                "resourceType": "DiagnosticReport",
                "id": "dr-001",
                "result": [{"reference": "Observation/o-001"}],
            },
        )

        assert reg.reference_count == 1
        reg.validate()

    def test_register_resource_detects_nested_dangling_references(self) -> None:
        reg = ResourceRegistry()

        reg.register_resource(
            "DiagnosticReport",
            "dr-001",
            {
                "resourceType": "DiagnosticReport",
                "id": "dr-001",
                "result": [{"reference": "Observation/missing"}],
            },
        )

        with pytest.raises(ValueError, match="Observation/missing"):
            reg.validate()


class TestPools:
    """Test shared resource pool creation."""

    def test_organization_pool_size(self) -> None:
        orgs = create_organization_pool(10, IdFactory(), random.Random(42))
        assert len(orgs) == 10

    def test_practitioner_pool_size(self) -> None:
        factory = IdFactory()
        rng = random.Random(42)
        orgs = create_organization_pool(5, factory, rng)
        practs = create_practitioner_pool(50, orgs, factory, rng)
        assert len(practs) == 50


class TestRunner:
    """Test the full generation runner."""

    def test_20_patient_smoke(self, tmp_path: Path) -> None:
        config = GenerationConfig(seed=20260830, patient_count=20, output_dir=str(tmp_path))
        summary = run_generation(config)
        assert summary["patient_count"] == 20
        assert summary["encounters_per_patient"]["min"] >= 10
        assert summary["encounters_per_patient"]["max"] <= 20
        assert summary["dangling_references"] == 0
        assert summary["duplicate_ids"] == 0
        assert (tmp_path / "data_quality_summary.json").exists()
        assert (tmp_path / "bundles").is_dir()
        assert (tmp_path / "ndjson").is_dir()

    def test_reproducibility(self, tmp_path: Path) -> None:
        d1, d2 = tmp_path / "r1", tmp_path / "r2"
        run_generation(GenerationConfig(seed=42, patient_count=5, output_dir=str(d1)))
        run_generation(GenerationConfig(seed=42, patient_count=5, output_dir=str(d2)))
        with (d1 / "data_quality_summary.json").open() as f:
            s1 = json.load(f)
        with (d2 / "data_quality_summary.json").open() as f:
            s2 = json.load(f)
        assert s1 == s2
        for nf in sorted((d1 / "ndjson").glob("*.ndjson")):
            f2 = d2 / "ndjson" / nf.name
            assert f2.exists()
            assert (
                hashlib.sha256(nf.read_bytes()).hexdigest()
                == hashlib.sha256(f2.read_bytes()).hexdigest()
            )

    def test_encounter_count_bounds(self, tmp_path: Path) -> None:
        config = GenerationConfig(seed=12345, patient_count=10, output_dir=str(tmp_path))
        summary = run_generation(config)
        assert summary["encounters_per_patient"]["min"] >= 10
        assert summary["encounters_per_patient"]["max"] <= 20

    def test_rerun_removes_stale_managed_artifacts_only(self, tmp_path: Path) -> None:
        preserved = tmp_path / "keep.txt"
        preserved.write_text("user-owned\n")
        run_generation(GenerationConfig(seed=7, patient_count=3, output_dir=str(tmp_path)))

        run_generation(GenerationConfig(seed=7, patient_count=2, output_dir=str(tmp_path)))

        assert sorted(path.name for path in (tmp_path / "bundles").glob("*.json")) == [
            "p-000001.json",
            "p-000002.json",
            "shared.json",
        ]
        assert preserved.read_text() == "user-owned\n"

    def test_reference_generation_writes_a_repeatable_dataset_hash(self, tmp_path: Path) -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        run_generation(GenerationConfig(seed=20260830, patient_count=20, output_dir=str(first)))
        run_generation(GenerationConfig(seed=20260830, patient_count=20, output_dir=str(second)))

        first_manifest = json.loads((first / "dataset_manifest.json").read_text())
        second_manifest = json.loads((second / "dataset_manifest.json").read_text())

        assert len(first_manifest["dataset_hash"]) == 64
        assert first_manifest["dataset_hash"] == second_manifest["dataset_hash"]
        assert first_manifest == second_manifest
        assert first_manifest["generation"]["patient_count"] == 20
        assert "output_dir" not in first_manifest["generation"]

    def test_generation_report_contains_all_independent_quality_rules(self, tmp_path: Path) -> None:
        summary = run_generation(
            GenerationConfig(seed=20260830, patient_count=2, output_dir=str(tmp_path))
        )

        assert summary["status"] == "pass"
        assert set(summary["rules"]) == {
            "schema_validation",
            "duplicate_ids",
            "reference_resolution",
            "temporal_consistency",
            "coded_values",
            "encounter_count",
            "clinical_scenario_consistency",
            "aggregate_distribution",
        }
        assert json.loads((tmp_path / "data_quality_summary.json").read_text()) == summary


class TestDatasetManifest:
    """The manifest hash must cover relative paths and exact file bytes."""

    def test_hashes_managed_files_in_relative_path_order(self, tmp_path: Path) -> None:
        bundles = tmp_path / "bundles"
        ndjson = tmp_path / "ndjson"
        bundles.mkdir()
        ndjson.mkdir()
        (bundles / "a.json").write_bytes(b"bundle\n")
        (ndjson / "Patient.ndjson").write_bytes(b"patient\n")
        config = GenerationConfig(patient_count=1, output_dir=str(tmp_path))

        manifest = build_dataset_manifest(tmp_path, config)

        expected = hashlib.sha256()
        for relative_path, content in (
            ("bundles/a.json", b"bundle\n"),
            ("ndjson/Patient.ndjson", b"patient\n"),
        ):
            expected.update(relative_path.encode())
            expected.update(b"\0")
            expected.update(content)
            expected.update(b"\0")
        assert manifest["dataset_hash"] == expected.hexdigest()
        assert manifest["files"] == {
            "bundles/a.json": hashlib.sha256(b"bundle\n").hexdigest(),
            "ndjson/Patient.ndjson": hashlib.sha256(b"patient\n").hexdigest(),
        }


class TestGenerationConfig:
    """Generation must reject configurations that cannot satisfy its contract."""

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"patient_count": 0},
            {"history_years": 0},
            {"encounters": {"min_per_patient": 0, "max_per_patient": 20}},
            {"encounters": {"min_per_patient": 21, "max_per_patient": 20}},
        ],
    )
    def test_rejects_invalid_generation_bounds(self, kwargs: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            GenerationConfig(**kwargs)

    def test_accepts_milestone_one_boundary_values(self) -> None:
        config = GenerationConfig(
            patient_count=20,
            history_years=1,
            encounters=EncounterConfig(min_per_patient=10, max_per_patient=20),
        )

        assert config.patient_count == 20
        assert config.encounters.min_per_patient == 10
        assert config.encounters.max_per_patient == 20
