import os
import sys
import tempfile
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.config import settings
from app.main import app
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor, DoctorVerificationStatus
from app.core.security import hash_password, create_access_token

# Configure isolated in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_storage():
    """Use a temporary folder for file storage during testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings.STORAGE_DIR = tmp_dir
        yield


@pytest.fixture
def db_session():
    """Create fresh database tables for each test and tear down after."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def patient_user(db_session):
    """Create a verified test patient."""
    user = User(
        email="patient1@example.com",
        hashed_password=hash_password("PatientSecure123!"),
        full_name="Alice Smith",
        role=UserRole.PATIENT.value,
        phone="+1234567890",
    )
    db_session.add(user)
    db_session.flush()

    patient = Patient(
        user_id=user.id,
        gender="female",
        blood_group="O+",
        emergency_contact="+1987654321",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_patient_user(db_session):
    """Create a second test patient to test unauthorized cross-patient access."""
    user = User(
        email="patient2@example.com",
        hashed_password=hash_password("PatientSecure123!"),
        full_name="Bob Jones",
        role=UserRole.PATIENT.value,
    )
    db_session.add(user)
    db_session.flush()

    patient = Patient(
        user_id=user.id,
        gender="male",
        blood_group="A+",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def doctor_user(db_session):
    """Create a verified test doctor."""
    user = User(
        email="doctor1@example.com",
        hashed_password=hash_password("DoctorSecure123!"),
        full_name="Dr. Gregory House",
        role=UserRole.DOCTOR.value,
    )
    db_session.add(user)
    db_session.flush()

    doctor = Doctor(
        user_id=user.id,
        license_number="MED-12345-US",
        specialization="Internal Medicine",
        hospital_affiliation="Princeton-Plainsboro",
        verification_status=DoctorVerificationStatus.VERIFIED.value,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def patient_token(patient_user):
    return create_access_token(data={"sub": patient_user.id, "email": patient_user.email, "role": patient_user.role})


@pytest.fixture
def second_patient_token(second_patient_user):
    return create_access_token(data={"sub": second_patient_user.id, "email": second_patient_user.email, "role": second_patient_user.role})


@pytest.fixture
def doctor_token(doctor_user):
    return create_access_token(data={"sub": doctor_user.id, "email": doctor_user.email, "role": doctor_user.role})
