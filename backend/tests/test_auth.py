import pytest


def test_register_patient_success(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newpatient@caregap.io",
            "password": "Password123!",
            "full_name": "Clara Oswald",
            "role": "patient",
            "phone": "+15551234567",
            "gender": "female",
            "blood_group": "B+",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newpatient@caregap.io"
    assert data["full_name"] == "Clara Oswald"
    assert data["role"] == "patient"
    assert "id" in data


def test_register_doctor_success(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newdoctor@caregap.io",
            "password": "Password123!",
            "full_name": "Dr. Sarah Adams",
            "role": "doctor",
            "license_number": "LIC-998877",
            "specialization": "Cardiology",
            "hospital_affiliation": "City Hospital",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "doctor"


def test_register_doctor_missing_license_fails(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad_doctor@caregap.io",
            "password": "Password123!",
            "full_name": "Dr. No License",
            "role": "doctor",
        },
    )
    assert response.status_code == 400
    assert "license_number" in response.json()["detail"]


def test_register_duplicate_email_fails(client, patient_user):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": patient_user.email,
            "password": "Password123!",
            "full_name": "Duplicate User",
            "role": "patient",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_success(client, patient_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": patient_user.email,
            "password": "PatientSecure123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "patient"
    assert data["user_id"] == patient_user.id


def test_login_invalid_password_fails(client, patient_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": patient_user.email,
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_me_endpoint_authenticated(client, patient_token, patient_user):
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == patient_user.id
    assert data["email"] == patient_user.email
    assert "patient" in data
    assert data["patient"]["blood_group"] == "O+"


def test_me_endpoint_unauthenticated_fails(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

