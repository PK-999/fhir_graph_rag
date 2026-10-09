"""Shared Practitioner and Organization pools.

Creates a fixed set of practitioners and organizations that are
reused across all patient encounters.
"""

from __future__ import annotations

import random

from libs.fhir.models.datatypes import (
    Address,
    CodeableConcept,
    Coding,
    ContactPoint,
    HumanName,
)
from libs.fhir.models.practitioner import Organization, Practitioner
from libs.synthetic.id_factory import IdFactory

# ── Specialties ──
SPECIALTIES = [
    ("General Practice", "394814009"),
    ("Internal Medicine", "419192003"),
    ("Cardiology", "394579002"),
    ("Endocrinology", "394583002"),
    ("Pulmonology", "418112009"),
    ("Nephrology", "394589003"),
    ("Emergency Medicine", "394576009"),
    ("Obstetrics", "408470005"),
    ("Orthopedics", "394801008"),
    ("Family Medicine", "394738000"),
]

# ── Organization names ──
ORG_NAMES = [
    "Springfield General Hospital",
    "Portland Medical Center",
    "Austin Community Health",
    "Denver Regional Medical Center",
    "Seattle Mercy Hospital",
    "Miami University Hospital",
    "Boston Children's Medical Center",
    "Chicago Memorial Hospital",
    "Phoenix Health Partners",
    "Nashville Community Clinic",
    "Atlanta Medical Associates",
    "Charlotte Family Medicine",
]


def create_organization_pool(
    count: int,
    id_factory: IdFactory,
    rng: random.Random,
) -> list[Organization]:
    """Create a pool of shared Organization resources."""
    orgs = []
    for i in range(1, count + 1):
        org_id = id_factory.shared_id("Organization", i)
        name = ORG_NAMES[(i - 1) % len(ORG_NAMES)]
        org = Organization(
            id=org_id,
            name=name,
            type=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/organization-type",
                            code="prov",
                            display="Healthcare Provider",
                        )
                    ]
                )
            ],
            address=[
                Address(
                    city=name.split()[0],
                    state="US",
                    country="US",
                )
            ],
            telecom=[
                ContactPoint(
                    system="phone",
                    value=f"({rng.randint(200, 999)}) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
                )
            ],
        )
        orgs.append(org)
    return orgs


def create_practitioner_pool(
    count: int,
    organizations: list[Organization],
    id_factory: IdFactory,
    rng: random.Random,
) -> list[Practitioner]:
    """Create a pool of shared Practitioner resources."""
    practitioners = []
    first_names = [
        "Alice",
        "Bob",
        "Carol",
        "David",
        "Elena",
        "Frank",
        "Grace",
        "Henry",
        "Irene",
        "Jack",
        "Karen",
        "Leo",
        "Maria",
        "Nathan",
        "Olivia",
        "Peter",
        "Quinn",
        "Rachel",
        "Samuel",
        "Tina",
        "Uma",
        "Victor",
        "Wendy",
        "Xavier",
    ]
    last_names = [
        "Adams",
        "Baker",
        "Chen",
        "Diaz",
        "Evans",
        "Fisher",
        "Grant",
        "Hayes",
        "Ibrahim",
        "Jensen",
        "Kumar",
        "Lawson",
        "Mitchell",
        "Novak",
        "O'Brien",
        "Patel",
        "Quinn",
        "Reyes",
        "Singh",
        "Turner",
        "Ueda",
        "Vasquez",
        "Walsh",
        "Xu",
    ]

    for i in range(1, count + 1):
        pract_id = id_factory.shared_id("Practitioner", i)
        given = first_names[(i - 1) % len(first_names)]
        family = last_names[(i - 1) % len(last_names)]
        specialty_name, specialty_code = SPECIALTIES[(i - 1) % len(SPECIALTIES)]
        gender = rng.choice(["male", "female"])

        pract = Practitioner(
            id=pract_id,
            name=[HumanName(use="official", family=family, given=[f"Dr. {given}"])],
            gender=gender,
            qualification=[
                {
                    "code": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": specialty_code,
                                "display": specialty_name,
                            }
                        ],
                        "text": specialty_name,
                    }
                }
            ],
        )
        practitioners.append(pract)

    return practitioners
