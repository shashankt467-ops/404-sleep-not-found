import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

# Ensure backend root in path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.security import hash_password
from app.models.user import User, Professional, Organization, UserRole, AccountStatus
from app.models.patient import Patient
from app.models.ehr_source import EHRSource, EHRRecord
from app.models.conflict import Conflict
from app.models.emergency import EmergencyCase
from app.integrations.fhir.adapter import FHIRProvider
from app.integrations.hl7.adapter import HL7Provider
from app.integrations.csv_json.adapter import CSVJSONProvider
from app.services.identity_matcher import match_patient_identity
from app.services.conflict_detector import detect_medical_conflicts

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"

def test_doctor_registration_and_verification_workflow():
    import uuid
    uid_suffix = uuid.uuid4().hex[:6]
    test_email = f"sarah.{uid_suffix}@test.hospital"
    test_reg = f"MED-TEST-{uid_suffix}"
    # 1. Register new doctor
    reg_payload = {
        "full_name": "Dr. Sarah Jenkins",
        "dob": "10/10/1985",
        "reg_number": test_reg,
        "licensing_authority": "Medical Council",
        "hospital_name": "Metro General Hospital",
        "department": "Trauma Care",
        "email": test_email,
        "phone": "+91 99999 11111",
        "password": "Password@123",
        "credentials_file": "License_SJ.pdf"
    }
    r = client.post("/api/auth/doctor/register", json=reg_payload)
    assert r.status_code == 201
    assert r.json()["account_status"] == "PENDING_VERIFICATION"
    user_id = r.json()["user_id"]

    # 2. Try logging in while PENDING_VERIFICATION -> Login succeeds but clinical permissions blocked
    login_payload = {"email": test_email, "password": "Password@123"}
    r_login = client.post("/api/auth/login", json=login_payload)
    assert r_login.status_code == 200
    token = r_login.json()["access_token"]
    assert r_login.json()["account_status"] == "PENDING_VERIFICATION"

    # Clinical endpoint must DENY access to unverified doctor!
    r_clinical = client.get("/api/patients", headers={"Authorization": f"Bearer {token}"})
    assert r_clinical.status_code == 403
    assert "awaiting administrator verification" in r_clinical.json()["detail"]

    # 3. Admin logs in
    r_admin_login = client.post("/api/auth/login", json={"email": "admin@hc04.health", "password": "Admin@12345"})
    assert r_admin_login.status_code == 200
    admin_token = r_admin_login.json()["access_token"]

    # 4. Admin views pending verifications
    r_pending = client.get("/api/admin/verifications?status_filter=PENDING_VERIFICATION", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_pending.status_code == 200
    found_prof = next((p for p in r_pending.json() if p["reg_number"] == test_reg), None)
    assert found_prof is not None
    prof_id = found_prof["id"]

    # 4b. Admin opens and inspects credential verification document
    r_doc = client.get(f"/api/admin/verifications/{prof_id}/document", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_doc.status_code == 200
    doc_data = r_doc.json()
    assert doc_data["credentials_file"] == "License_SJ.pdf"
    assert doc_data["reg_number"] == test_reg
    assert "SHA256:" in doc_data["digital_signature"]
    assert doc_data["registry_cross_reference"]["council_status"] == "AUTHENTICATED & ACTIVE"

    # 5. Admin verifies the doctor
    r_verify = client.post(f"/api/admin/verifications/{prof_id}", json={"action": "VERIFY"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r_verify.status_code == 200
    assert r_verify.json()["new_status"] == "VERIFIED"

    # 6. Doctor logs in again -> now VERIFIED, clinical access GRANTED!
    r_login_verified = client.post("/api/auth/login", json=login_payload)
    assert r_login_verified.status_code == 200
    verified_token = r_login_verified.json()["access_token"]
    assert r_login_verified.json()["account_status"] == "VERIFIED"

    r_clinical_granted = client.get("/api/patients", headers={"Authorization": f"Bearer {verified_token}"})
    assert r_clinical_granted.status_code == 200

def test_patient_registration_cryptographic_id_and_otp_access():
    # Login as verified doctor Dr. Rahul
    r_doc = client.post("/api/auth/login", json={"email": "dr.rahul@hospital.example", "password": "Doctor@12345"})
    doc_token = r_doc.json()["access_token"]

    # Register new patient
    new_pat_payload = {
        "full_name": "Rohan Sharma",
        "dob": "12/05/1995",
        "sex": "Male",
        "phone": "+91 98888 77777",
        "emergency_contact": "Anita Sharma (+91 98888 77778)",
        "blood_group": "B+",
        "allergies": ["Sulfa"],
        "existing_conditions": ["Asthma"],
        "priority": "HIGH PRIORITY",
        "initial_notes": "Admitted following respiratory distress."
    }
    r_pat = client.post("/api/patients", json=new_pat_payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert r_pat.status_code == 201
    pat_data = r_pat.json()
    pat_id = pat_data["id"]

    # Verify ID format: non-sequential, unpredictable HC04-PAT-XXXX-XXXX
    assert pat_id.startswith("HC04-PAT-")
    assert len(pat_id.split("-")) >= 3
    assert pat_id != "PATIENT001" and pat_id != "PATIENT002"
    assert "qr_token" in pat_data

    # Patient Access Flow (Patient ID + OTP)
    # Step 1: Request OTP
    r_otp = client.post(f"/api/patients/{pat_id}/request-otp")
    assert r_otp.status_code == 200
    otp_code = r_otp.json()["dev_otp"]

    # Step 2: Verify OTP
    r_verify_otp = client.post(f"/api/patients/{pat_id}/verify-otp?otp_code={otp_code}")
    assert r_verify_otp.status_code == 200
    patient_token = r_verify_otp.json()["access_token"]

    # Step 3: Patient views own portal summary
    r_portal = client.get(f"/api/patients/{pat_id}/portal", headers={"Authorization": f"Bearer {patient_token}"})
    assert r_portal.status_code == 200
    portal_data = r_portal.json()
    assert portal_data["name"] == "Rohan Sharma"
    assert "access_history" in portal_data

def test_medical_record_creation_and_versioning():
    r_doc = client.post("/api/auth/login", json={"email": "dr.rahul@hospital.example", "password": "Doctor@12345"})
    doc_token = r_doc.json()["access_token"]

    # Add medical record for Arjun Kumar (HC04-PAT-1024)
    rec_payload = {
        "record_type": "Diagnosis",
        "clinical_data": {"condition": "Hypertension Stage 2", "bp": "160/100 mmHg"},
        "source": "City General Hospital"
    }
    r_add = client.post("/api/patients/HC04-PAT-1024/records", json=rec_payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert r_add.status_code == 201
    record_id = r_add.json()["id"]

    # Update record with versioning reason
    update_payload = {
        "clinical_data": {"condition": "Hypertension Controlled", "bp": "128/82 mmHg"},
        "reason": "Antihypertensive dosage adjusted, blood pressure improved"
    }
    r_upd = client.put(f"/api/records/{record_id}", json=update_payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert r_upd.status_code == 200

    # Retrieve version history
    r_hist = client.get(f"/api/records/{record_id}/history", headers={"Authorization": f"Bearer {doc_token}"})
    assert r_hist.status_code == 200
    history = r_hist.json()
    assert len(history) >= 2
    assert history[0]["version_num"] == 2
    assert history[0]["reason"] == "Antihypertensive dosage adjusted, blood pressure improved"

def test_fhir_hl7_csv_adapters():
    # 1. Test FHIR R4 Bundle Parser
    fhir_bundle = """{
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "P-101", "name": [{"family": "Doe", "given": ["John"]}], "birthDate": "1980-01-01"}},
            {"resource": {"resourceType": "AllergyIntolerance", "code": {"coding": [{"display": "Penicillin"}]}}},
            {"resource": {"resourceType": "MedicationRequest", "medicationCodeableConcept": {"coding": [{"display": "Warfarin"}]}}}
        ]
    }"""
    fhir_provider = FHIRProvider("Test Hospital")
    canonical_fhir = fhir_provider.normalize_record(fhir_bundle)
    assert canonical_fhir.full_name == "John Doe"
    assert canonical_fhir.allergies[0].substance == "Penicillin"
    assert canonical_fhir.medications[0].name == "Warfarin"

    # 2. Test HL7 v2 Parser
    hl7_msg = "MSH|^~\\&|HOSP|EMR|||20260918||ADT^A01|001|P|2.5\nPID|1||HL7-8899||Smith^Jane||19750512|F\nAL1|1|DA|Latex allergy\nOBX|1|ST|BLOOD GROUP||AB+||||||F"
    hl7_provider = HL7Provider("Apollo Hospital")
    canonical_hl7 = hl7_provider.normalize_record(hl7_msg)
    assert canonical_hl7.full_name == "Jane Smith"
    assert canonical_hl7.blood_group == "AB+"
    assert canonical_hl7.allergies[0].substance == "Latex allergy"

    # 3. Test CSV Parser
    csv_data = "patient_id,name,dob,blood_group,test_name,value,unit\nCSV-01,Bob Brown,1992-04-10,O-,Troponin,0.05,ng/mL"
    csv_provider = CSVJSONProvider("Regional Lab")
    canonical_csv = csv_provider.normalize_record(csv_data)
    assert canonical_csv.full_name == "Bob Brown"
    assert canonical_csv.blood_group == "O-"
    assert canonical_csv.observations[0].test_name == "Troponin"

def test_conflict_detection_and_emergency_summary():
    r_doc = client.post("/api/auth/login", json={"email": "dr.rahul@hospital.example", "password": "Doctor@12345"})
    doc_token = r_doc.json()["access_token"]

    # Query conflicts for Arjun Kumar (HC04-PAT-1024)
    r_conflicts = client.get("/api/patients/HC04-PAT-1024/conflicts", headers={"Authorization": f"Bearer {doc_token}"})
    assert r_conflicts.status_code == 200
    conflicts = r_conflicts.json()
    assert len(conflicts) >= 2
    # Verify critical allergy conflict detected
    allergy_conflict = next((c for c in conflicts if c["field"] == "Allergy"), None)
    assert allergy_conflict is not None
    assert allergy_conflict["severity"] == "critical"

    # Generate Emergency Summary
    r_sum = client.post("/api/emergency-summary/HC04-PAT-1024", headers={"Authorization": f"Bearer {doc_token}"})
    assert r_sum.status_code == 200
    sum_data = r_sum.json()
    assert sum_data["patient_name"] == "Arjun Kumar"
    assert "anticoagulant" in sum_data["ai_synthesis"].lower() or "warfarin" in sum_data["ai_synthesis"].lower()
    assert "clinical verification required" in sum_data["safety_disclaimer"].lower()

def test_break_glass_emergency_access_and_audit():
    r_doc = client.post("/api/auth/login", json={"email": "dr.rahul@hospital.example", "password": "Doctor@12345"})
    doc_token = r_doc.json()["access_token"]

    # Activate Break-Glass Emergency Access
    bg_payload = {
        "patient_id": "HC04-PAT-1024",
        "reason": "Severe trauma collision, patient unconscious",
        "case_id": "EMG-2026-00124",
        "break_glass": True
    }
    r_bg = client.post("/api/emergency/access", json=bg_payload, headers={"Authorization": f"Bearer {doc_token}"})
    assert r_bg.status_code == 200
    assert r_bg.json()["break_glass"] is True
    assert r_bg.json()["expires_in_seconds"] == 15 * 60

    # Verify audit trail contains the break-glass event
    r_audit = client.get("/api/audit-logs?patient_id=HC04-PAT-1024", headers={"Authorization": f"Bearer {doc_token}"})
    assert r_audit.status_code == 200
    logs = r_audit.json()
    assert any("BREAK_GLASS" in l["action"] for l in logs)
