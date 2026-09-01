"""Demographics generator — names, DoB, gender, address, contact info.

Uses seeded RNG for full determinism.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from libs.fhir.models.datatypes import Address, ContactPoint, HumanName
from libs.fhir.models.patient import Patient
from libs.synthetic.id_factory import IdFactory

# ── Name pools ──
FIRST_NAMES_MALE = [
    "James", "Robert", "John", "Michael", "David", "William", "Richard", "Joseph",
    "Thomas", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Steven",
    "Andrew", "Paul", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Timothy",
    "Ronald", "Edward", "Jason", "Jeffrey", "Ryan", "Jacob", "Nicholas",
]

FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth", "Susan",
    "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra",
    "Ashley", "Dorothy", "Kimberly", "Emily", "Donna", "Michelle", "Carol",
    "Amanda", "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen",
    "Hill", "Flores",
]

CITIES = [
    ("Springfield", "IL"), ("Portland", "OR"), ("Austin", "TX"), ("Denver", "CO"),
    ("Seattle", "WA"), ("Miami", "FL"), ("Boston", "MA"), ("Chicago", "IL"),
    ("Phoenix", "AZ"), ("Nashville", "TN"), ("Atlanta", "GA"), ("Charlotte", "NC"),
]

STREETS = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd",
    "Elm St", "Washington Blvd", "Park Ave", "Lake Dr", "River Rd",
]

# ── Age band distribution (configurable weights) ──
AGE_BANDS = [
    # (label, min_age, max_age, weight)
    ("pediatric", 0, 17, 0.10),
    ("young_adult", 18, 30, 0.15),
    ("adult", 31, 45, 0.25),
    ("middle_aged", 46, 64, 0.30),
    ("older_adult", 65, 90, 0.20),
]


def generate_patient(
    patient_seq: int,
    id_factory: IdFactory,
    rng: random.Random,
    reference_date: date | None = None,
) -> Patient:
    """Generate a single synthetic Patient with coherent demographics."""
    if reference_date is None:
        reference_date = date(2026, 8, 30)

    patient_id = id_factory.patient_id(patient_seq)

    # Gender
    gender = rng.choice(["male", "female"])

    # Age band
    bands, weights = zip(*[(b, b[3]) for b in AGE_BANDS], strict=True)
    band = rng.choices(bands, weights=weights, k=1)[0]
    age = rng.randint(band[1], band[2])

    # Date of birth
    birth_date = reference_date - timedelta(days=age * 365 + rng.randint(0, 364))

    # Name
    if gender == "male":
        given_name = rng.choice(FIRST_NAMES_MALE)
    else:
        given_name = rng.choice(FIRST_NAMES_FEMALE)
    family_name = rng.choice(LAST_NAMES)

    # Address
    city, state = rng.choice(CITIES)
    street_num = rng.randint(100, 9999)
    street = rng.choice(STREETS)

    # Contact
    phone = f"({rng.randint(200,999)}) {rng.randint(200,999)}-{rng.randint(1000,9999)}"
    email = f"{given_name.lower()}.{family_name.lower()}{rng.randint(1,99)}@example.com"

    return Patient(
        id=patient_id,
        name=[HumanName(use="official", family=family_name, given=[given_name])],
        gender=gender,
        birthDate=birth_date,
        address=[
            Address(
                use="home",
                line=[f"{street_num} {street}"],
                city=city,
                state=state,
                postalCode=f"{rng.randint(10000,99999)}",
                country="US",
            )
        ],
        telecom=[
            ContactPoint(system="phone", value=phone, use="home"),
            ContactPoint(system="email", value=email),
        ],
    )
