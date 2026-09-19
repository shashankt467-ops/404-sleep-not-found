"""
HC-04 DEVELOPMENT SEED DATA
============================
WARNING: This file contains ONLY development and evaluation seed data.
Do NOT use test credentials in production environments.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json

from app.core.security import hash_password
from app.models.user import User, Professional, Organization, UserRole, AccountStatus
from app.models.patient import Patient, DoctorPatientRelationship
from app.models.medical_record import MedicalRecord, RecordVersion
from app.models.ehr_source import EHRSource, EHRRecord
from app.models.conflict import Conflict
from app.models.emergency import EmergencyCase
from app.models.audit import AuditLog

def seed_database(db: Session):
    """Seed the database with initial development organizations, users, patients, and EHR sources."""
    # Check if already seeded
    if db.query(Organization).count() > 0:
        return

    print("[DEV SEED] Initializing development seed data...")

    # 1. Organizations
    org_city = Organization(id="org-city-gen", name="City General Hospital", org_type="Hospital", contact_email="contact@citygeneral.org")
    org_apollo = Organization(id="org-apollo", name="Apollo Medical Center", org_type="Hospital", contact_email="admin@apollomed.org")
    org_gmc = Organization(id="org-gmc", name="Government Medical College", org_type="Hospital")
    org_trauma = Organization(id="org-trauma", name="Metro Trauma Centre", org_type="Trauma Center")
    org_lab = Organization(id="org-lab", name="Regional Diagnostic Lab", org_type="Diagnostic Lab")
    org_pharm = Organization(id="org-pharm", name="Metro Pharmacy Network", org_type="Pharmacy Network")
    org_ems = Organization(id="org-ems", name="City Emergency Response Service", org_type="EMS")

    db.add_all([org_city, org_apollo, org_gmc, org_trauma, org_lab, org_pharm, org_ems])
    db.commit()

    # 2. EHR Sources
    sources = [
        EHRSource(id="src-city-general", name="City General Hospital", protocol="FHIR", format="JSON", status="Connected", last_sync="2 min ago", security_info="Secure (mTLS)"),
        EHRSource(id="src-apollo", name="Apollo Medical Center", protocol="HL7 v2", format="HL7-ER7", status="Connected", last_sync="6 min ago", security_info="Secure (mTLS)"),
        EHRSource(id="src-gmc", name="Government Medical College", protocol="FHIR", format="JSON", status="Connected", last_sync="4 min ago", security_info="Secure (mTLS)"),
        EHRSource(id="src-metro-trauma", name="Metro Trauma Centre", protocol="Custom API", format="CSV/JSON", status="Connected", last_sync="1 min ago", security_info="Secure (mTLS)"),
        EHRSource(id="src-reg-lab", name="Regional Diagnostic Lab", protocol="FHIR", format="JSON", status="Connected", last_sync="9 min ago", security_info="Secure (mTLS)"),
        EHRSource(id="src-pharmacy", name="Metro Pharmacy Network", protocol="NCPDP", format="JSON", status="Connected", last_sync="12 min ago", security_info="Secure (mTLS)")
    ]
    db.add_all(sources)
    db.commit()

    # 3. Users: Admin, Verified Doctor, Pending Doctor, Verified EMT
    admin_user = User(
        id="usr-admin", email="admin@hc04.health",
        password_hash=hash_password("Admin@12345"),
        role=UserRole.ADMIN, account_status=AccountStatus.VERIFIED
    )
    doc_user = User(
        id="usr-doc-rahul", email="dr.rahul@hospital.example",
        phone="+91 98765 43210",
        password_hash=hash_password("Doctor@12345"),
        role=UserRole.DOCTOR, account_status=AccountStatus.VERIFIED
    )
    doc_pending = User(
        id="usr-doc-priya", email="dr.priya@hospital.example",
        phone="+91 98111 22334",
        password_hash=hash_password("Doctor@12345"),
        role=UserRole.DOCTOR, account_status=AccountStatus.PENDING_VERIFICATION
    )
    emt_user = User(
        id="usr-emt-arun", email="emt.arun@emergency.example",
        phone="+91 98444 55667",
        password_hash=hash_password("Emt@12345"),
        role=UserRole.EMT, account_status=AccountStatus.VERIFIED
    )

    db.add_all([admin_user, doc_user, doc_pending, emt_user])
    db.commit()

    # Professionals
    prof_doc = Professional(
        id="prof-rahul", user_id=doc_user.id, full_name="Dr. Rahul Kumar",
        dob="15/08/1982", reg_number="MED-8829104", licensing_authority="State Medical Council",
        organization_id=org_city.id, department="Emergency Medicine",
        professional_email=doc_user.email, phone=doc_user.phone,
        verification_status=AccountStatus.VERIFIED,
        credentials_file="Dr_Rahul_Medical_Council_Cert.pdf"
    )
    prof_pending = Professional(
        id="prof-priya", user_id=doc_pending.id, full_name="Dr. Priya Sharma",
        dob="22/04/1990", reg_number="MED-9938120", licensing_authority="National Medical Commission",
        organization_id=org_apollo.id, department="Trauma Surgery",
        professional_email=doc_pending.email, phone=doc_pending.phone,
        verification_status=AccountStatus.PENDING_VERIFICATION,
        credentials_file="Dr_Priya_Board_Certification.pdf"
    )
    prof_emt = Professional(
        id="prof-arun", user_id=emt_user.id, full_name="Arun Verma (EMT-24)",
        reg_number="EMT-44029", licensing_authority="National EMS Board",
        organization_id=org_ems.id, department="Trauma Ambulance Unit 4",
        professional_email=emt_user.email, phone=emt_user.phone,
        verification_status=AccountStatus.VERIFIED,
        credentials_file="Arun_Paramedic_License.pdf"
    )
    db.add_all([prof_doc, prof_pending, prof_emt])
    db.commit()

    # 4. Standard Patients
    pat1 = Patient(
        id="HC04-PAT-1024", full_name="Arjun Kumar", dob="14/02/2004", sex="Male",
        phone="+91 98765 11024", emergency_contact="Kavita Kumar (+91 98765 11025)",
        email="shashankt467@gmail.com",
        blood_group="O+", allergies=json.dumps(["Penicillin"]),
        existing_conditions=json.dumps(["Diabetes"]),
        priority="HIGH PRIORITY", status="Active",
        registered_by_doctor_id=doc_user.id, primary_org_id=org_city.id
    )
    pat2 = Patient(
        id="HC04-PAT-1039", full_name="Meera Iyer", dob="02/11/1988", sex="Female",
        phone="+91 98765 11039", emergency_contact="Suresh Iyer (+91 98765 11040)",
        blood_group="B+", allergies=json.dumps(["Sulfa drugs"]),
        existing_conditions=json.dumps(["Hypothyroidism"]),
        priority="MEDIUM PRIORITY", status="Active",
        registered_by_doctor_id=doc_user.id, primary_org_id=org_gmc.id
    )
    pat3 = Patient(
        id="HC04-PAT-1055", full_name="Farhan Sheikh", dob="29/06/1975", sex="Male",
        phone="+91 98765 11055", emergency_contact="Amina Sheikh (+91 98765 11056)",
        blood_group="AB-", allergies=json.dumps(["Latex", "Iodine contrast"]),
        existing_conditions=json.dumps(["Coronary artery disease", "Chronic kidney disease"]),
        priority="CRITICAL", status="Active",
        registered_by_doctor_id=doc_user.id, primary_org_id=org_city.id
    )
    pat4 = Patient(
        id="HC04-PAT-1067", full_name="Lakshmi Menon", dob="21/03/1996", sex="Female",
        phone="+91 98765 11067", emergency_contact="Ramesh Menon (+91 98765 11068)",
        blood_group="O-", allergies=json.dumps(["None recorded"]),
        existing_conditions=json.dumps([]),
        priority="LOW PRIORITY", status="Resolved",
        registered_by_doctor_id=doc_user.id, primary_org_id=org_gmc.id
    )
    pat5 = Patient(
        id="HC04-PAT-1081", full_name="David Fernandes", dob="08/12/1960", sex="Male",
        phone="+91 98765 11081", emergency_contact="Mary Fernandes (+91 98765 11082)",
        blood_group="A-", allergies=json.dumps(["Aspirin"]),
        existing_conditions=json.dumps(["Type 2 diabetes", "Hypertension"]),
        priority="HIGH PRIORITY", status="Active",
        registered_by_doctor_id=doc_user.id, primary_org_id=org_city.id
    )
    db.add_all([pat1, pat2, pat3, pat4, pat5])
    db.commit()

    # 5. Doctor-Patient relationships
    for p in [pat1, pat2, pat3, pat4, pat5]:
        rel = DoctorPatientRelationship(doctor_id=doc_user.id, patient_id=p.id, organization_id=org_city.id)
        db.add(rel)
    db.commit()

    # 6. Medical Records for Pat1 (Arjun Kumar)
    m1 = MedicalRecord(
        patient_id=pat1.id, provider_id=doc_user.id, organization_id=org_city.id,
        record_type="Emergency Visit",
        clinical_data={
            "complaint": "Acute motor vehicle collision, chest contusion",
            "findings": "Hemodynamically stable, GCS 15. INR 2.8 on warfarin therapy.",
            "notes": "Emergency admission after highway collision. Anticoagulated."
        },
        source="City General Hospital", author="Dr. Rahul Kumar"
    )
    db.add(m1)
    db.commit()

    v1 = RecordVersion(
        record_id=m1.id, version_num=1, previous_value=None,
        new_value=m1.clinical_data, changed_by="Dr. Rahul Kumar", reason="Emergency Admission Note"
    )
    db.add(v1)
    db.commit()

    # 7. EHR Records across disparate sources for Pat1
    # Source A: City General (FHIR)
    ehr1 = EHRRecord(
        source_id="src-city-general",
        external_patient_id="CGH-PAT-8819",
        patient_identifier=pat1.id,
        format="FHIR JSON",
        raw_payload="""{"resourceType":"Bundle","type":"collection","entry":[{"resource":{"resourceType":"Patient","name":[{"family":"Kumar","given":["Arjun"]}],"birthDate":"2004-02-14"}},{"resource":{"resourceType":"AllergyIntolerance","code":{"coding":[{"display":"Penicillin"}]},"criticality":"high"}},{"resource":{"resourceType":"MedicationRequest","medicationCodeableConcept":{"coding":[{"display":"Warfarin"}]}}},{"resource":{"resourceType":"Condition","code":{"coding":[{"display":"Diabetes"}]}}},{"resource":{"resourceType":"Procedure","code":{"coding":[{"display":"Cardiac stent — 2025"}]}}},{"resource":{"resourceType":"Observation","code":{"coding":[{"display":"Hemoglobin"}]},"valueQuantity":{"value":10.2,"unit":"g/dL"}}},{"resource":{"resourceType":"Observation","code":{"coding":[{"display":"INR"}]},"valueQuantity":{"value":2.8}}}]}""",
        normalized_payload={
            "name": "Arjun Kumar", "dob": "14/02/2004", "bloodGroup": "O+",
            "allergies": ["Penicillin"], "medications": ["Warfarin"],
            "conditions": ["Diabetes"], "surgeries": ["Cardiac stent — 2025"],
            "labs": {"Hemoglobin": "10.2 g/dL", "INR": "2.8"}
        }
    )
    # Source B: Apollo Medical Center (HL7 v2) - Intentionally discrepant blood group and allergy
    ehr2 = EHRRecord(
        source_id="src-apollo",
        external_patient_id="APO-99120",
        patient_identifier=pat1.id,
        format="HL7 v2 (ER7)",
        raw_payload="""MSH|^~\\&|APOLLO|EHR|HC04|GATEWAY|202609171200||ADT^A08|MSG001|P|2.5\nPID|1||APO-99120||Kumar^Arjun||20040214|M\nAL1|1|DA|NO^No known allergies|U\nOBX|1|ST|BLOOD_GROUP||A+||||||F\nDG1|1||I10^Hypertension||20260917""",
        normalized_payload={
            "name": "Arjun K.", "dob": "14/02/2004", "bloodGroup": "A+",
            "allergies": ["None recorded"], "medications": ["Metformin"],
            "conditions": ["Hypertension"], "surgeries": [],
            "labs": {}
        }
    )
    # Source E: Regional Diagnostic Lab (CSV/JSON)
    ehr3 = EHRRecord(
        source_id="src-reg-lab",
        external_patient_id="LAB-00192",
        patient_identifier=pat1.id,
        format="CSV/JSON",
        raw_payload="""patient_id,name,dob,blood_group,test_name,value,unit\nHC04-PAT-1024,A. Kumar,14/02/2004,O+,Hemoglobin,10.2,g/dL\nHC04-PAT-1024,A. Kumar,14/02/2004,O+,INR,2.8,""",
        normalized_payload={
            "name": "A. Kumar", "dob": "14/02/2004", "bloodGroup": "O+",
            "allergies": [], "medications": [], "conditions": [], "surgeries": [],
            "labs": {"Hemoglobin": "10.2 g/dL", "INR": "2.8"}
        }
    )
    # Source F: Metro Pharmacy Network (NCPDP JSON)
    ehr4 = EHRRecord(
        source_id="src-pharmacy",
        external_patient_id="RX-8812",
        patient_identifier=pat1.id,
        format="NCPDP JSON",
        raw_payload="""{"patient_id":"HC04-PAT-1024","medications":[{"name":"Warfarin"},{"name":"Metformin"}]}""",
        normalized_payload={
            "name": "Arjun Kumar", "dob": "14/02/2004", "bloodGroup": "—",
            "allergies": [], "medications": ["Warfarin", "Metformin"], "conditions": [], "surgeries": [],
            "labs": {}
        }
    )
    db.add_all([ehr1, ehr2, ehr3, ehr4])
    db.commit()

    # 8. Seed Clinical Conflicts for Pat1
    cnf1 = Conflict(
        id="cnf-al-1024", patient_id=pat1.id, field_name="Allergy", severity="critical",
        source_a="City General Hospital", value_a="Penicillin Allergy — YES", date_a="18 Sep 2026",
        source_b="Apollo Medical Center", value_b="Known Allergies — NONE", date_b="17 Sep 2026",
        status="UNRESOLVED"
    )
    cnf2 = Conflict(
        id="cnf-bg-1024", patient_id=pat1.id, field_name="Blood Group", severity="high",
        source_a="City General Hospital", value_a="O+", date_a="18 Sep 2026",
        source_b="Apollo Medical Center", value_b="A+", date_b="17 Sep 2026",
        status="UNRESOLVED"
    )
    cnf3 = Conflict(
        id="cnf-med-1024", patient_id=pat1.id, field_name="Medication", severity="medium",
        source_a="City General Hospital", value_a="Warfarin", date_a="18 Sep 2026",
        source_b="Apollo Medical Center", value_b="Not listed", date_b="17 Sep 2026",
        status="UNRESOLVED"
    )
    db.add_all([cnf1, cnf2, cnf3])
    db.commit()

    # 9. Emergency Cases
    c1 = EmergencyCase(
        id="emg-case-1024", case_number="EMG-2026-00124", patient_id=pat1.id,
        priority="HIGH PRIORITY", status="Active", assigned_team="Trauma Team A",
        chief_complaint="High-velocity collision, chest trauma, on oral anticoagulation"
    )
    c2 = EmergencyCase(
        id="emg-case-1039", case_number="EMG-2026-00131", patient_id=pat2.id,
        priority="MEDIUM PRIORITY", status="Active", assigned_team="Trauma Team B",
        chief_complaint="Fall with mild head injury"
    )
    c3 = EmergencyCase(
        id="emg-case-1055", case_number="EMG-2026-00118", patient_id=pat3.id,
        priority="CRITICAL", status="Active", assigned_team="Trauma Team A",
        chief_complaint="Acute coronary syndrome with hyperkalemia"
    )
    db.add_all([c1, c2, c3])
    db.commit()

    # 10. Initial Audit Logs
    db.add_all([
        AuditLog(timestamp=datetime.now(timezone.utc), user_id=doc_user.id, user_name="Dr. Rahul Kumar", role="Physician", patient_id=pat1.id, action="EHR_QUERY", purpose="Emergency Trauma Care", result="Allowed"),
        AuditLog(timestamp=datetime.now(timezone.utc), user_id=emt_user.id, user_name="Arun Verma (EMT-24)", role="EMT", patient_id=pat1.id, action="EMERGENCY_SUMMARY", purpose="Field Triage", result="Allowed"),
        AuditLog(timestamp=datetime.now(timezone.utc), user_id=doc_user.id, user_name="Dr. Rahul Kumar", role="Physician", patient_id=pat1.id, action="CONFLICT_VIEWED", purpose="Pre-intervention Crosscheck", result="Allowed")
    ])
    db.commit()

    print("[DEV SEED] Database successfully populated with realistic development seed data.")
