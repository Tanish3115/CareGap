import os
import sys
import tempfile
from pathlib import Path
import pytest

# Configure before importing application modules; never touch the workspace database.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-only-key-with-at-least-thirty-two-characters"
os.environ["ENVIRONMENT"] = "test"

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.config import settings
from app.main import app
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor, DoctorVerificationStatus
from app.core.security import hash_password, create_access_token
from app.services.session_service import issue_session
from app.services.storage_service import storage_service
from app.core.limiter import limiter

limiter.enabled = False

# Configure isolated in-memory test database
SQLALCHEMY_DATABASE_URL = os.environ.get("CAREGAP_TEST_DATABASE_URL", "sqlite:///:memory:")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    **({"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
       if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}),
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _):
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture(autouse=True)
def setup_test_storage(tmp_path, monkeypatch):
    """Use a temporary folder for file storage during testing."""
    monkeypatch.setattr(storage_service, "base_dir", tmp_path.resolve())
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
        patient_code="A001",
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
        patient_code="A002",
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
def patient_token(patient_user, db_session):
    token = issue_session(db_session, patient_user)
    db_session.commit()
    return token


@pytest.fixture
def second_patient_token(second_patient_user, db_session):
    token = issue_session(db_session, second_patient_user)
    db_session.commit()
    return token


@pytest.fixture
def doctor_token(doctor_user, db_session):
    token = issue_session(db_session, doctor_user)
    db_session.commit()
    return token
