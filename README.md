# HC-04 — Emergency Medical Information Interoperability Platform

HC-04 is a real-world, production-ready Emergency Medical Information Interoperability application designed to allow authorized trauma physicians, EMTs, and emergency responders to securely retrieve, harmonize, and synthesize critical patient health records from heterogeneous hospital systems (FHIR R4, HL7 v2, CSV/JSON) under strict zero-trust authorization and automated audit logging.

---

## 1. System Architecture

```
[Trauma Physician / EMT]
          │
          ▼
[Zero-Trust Authorization Guard] ── (Requester, Verified Role, Patient, Purpose, Break-Glass)
          │
          ▼
[HC-04 Interoperability API Gateway] (FastAPI)
          │
    ┌─────┴─────────────────────────┐
    ▼                               ▼
[Local Clinical DB]         [External EHR Connector Network]
(PostgreSQL / SQLAlchemy)    ├── FHIR R4 Provider (City General, GMC)
                             ├── HL7 v2 Provider (Apollo Medical Center)
                             └── CSV / JSON Provider (Metro Trauma, Labs, Pharmacy)
          │
          ▼
[Canonical Medical Record Engine]
          │
    ┌─────┴─────────────────────────┐
    ▼                               ▼
[Identity Resolution Engine]   [Clinical Conflict Detection Engine]
(Probabilistic & Deterministic  (Allergy, Blood Group, Anticoagulant Discrepancies)
 Matching: >90% MATCHED)
          │
          ▼
[Grounded Emergency Summary Generator]
(Strictly derived from evidence; zero hallucination; source traceability)
          │
          ▼
[Authorized Emergency Clinician Console] & [Immutable Audit Trail]
```

---

## 2. Complete Folder Structure

```
ECHLEON/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin.py           # Doctor verification, suspension, orgs
│   │   │   ├── audit.py           # Immutable audit log stream & query
│   │   │   ├── auth.py            # Login, Doctor/EMT registration, tokens
│   │   │   ├── conflicts.py       # Cross-source conflict detection & resolution
│   │   │   ├── ehr.py             # Live EHR network query & imports
│   │   │   ├── emergency.py       # Emergency summary, break-glass session
│   │   │   ├── identity.py        # Patient identity matching algorithms
│   │   │   ├── patients.py        # Registration, crypto ID, OTP portal
│   │   │   ├── records.py         # Clinical records CRUD & versioning
│   │   │   └── stats.py           # Real-time system telemetry
│   │   ├── core/
│   │   │   ├── audit_logger.py    # Immutable audit logging helper
│   │   │   ├── config.py          # Pydantic Settings & environment loader
│   │   │   ├── security.py        # Bcrypt password hashing & JWT tokens
│   │   │   └── zero_trust.py      # Contextual policy guard & dependencies
│   │   ├── db/
│   │   │   ├── base.py            # SQLAlchemy Base model
│   │   │   ├── init_db.py         # Table creation & seed runner
│   │   │   └── session.py         # Engine & session dependency
│   │   ├── integrations/
│   │   │   ├── base_adapter.py    # EHRProvider abstract interface
│   │   │   ├── canonical.py       # Canonical Medical Record data model
│   │   │   ├── csv_json/          # CSV & JSON ingestion adapter
│   │   │   ├── fhir/              # FHIR R4 Bundle parser
│   │   │   └── hl7/               # HL7 v2.5.1 ER7 message parser
│   │   ├── models/
│   │   │   ├── audit.py           # AuditLog model
│   │   │   ├── conflict.py        # Conflict model
│   │   │   ├── consent.py         # ConsentPolicy model
│   │   │   ├── ehr_source.py      # EHRSource & EHRRecord models
│   │   │   ├── emergency.py       # EmergencyCase & AccessSession (Break-Glass)
│   │   │   ├── medical_record.py  # MedicalRecord & RecordVersion models
│   │   │   ├── patient.py         # Patient, PatientAccessOtp, Relationship
│   │   │   └── user.py            # User, Professional, Organization
│   │   ├── schemas/               # Pydantic validation schemas
│   │   ├── services/
│   │   │   ├── conflict_detector.py # Allergy, blood group & med conflict logic
│   │   │   ├── emergency_synth.py   # Grounded emergency summary synthesizer
│   │   │   ├── identity_matcher.py  # Multi-factor identity matching
│   │   │   └── patient_id_gen.py    # Unpredictable non-sequential ID generator
│   │   └── main.py                # FastAPI entrypoint, middleware, static mount
│   ├── seed/
│   │   └── dev_seed.py            # Development & evaluation seed data
│   ├── tests/
│   │   └── test_full_suite.py     # Automated pytest test suite
│   └── requirements.txt           # Python dependencies
├── frontend/
│   └── index.html                 # Connected single-page application
├── docker-compose.yml             # Docker compose configuration (PostgreSQL + FastAPI)
├── Dockerfile                     # Container build file
├── run_server.py                  # Local runner script
├── .env.example                   # Environment configuration template
└── README.md                      # Complete system documentation
```

---

## 3. Database Schema

The database utilizes relational models in PostgreSQL (or SQLite locally):

| Table | Purpose | Key Columns |
|---|---|---|
| `users` | Accounts & credentials | `id`, `email`, `phone`, `password_hash`, `role`, `account_status`, `last_login` |
| `professionals` | Healthcare provider license data | `id`, `user_id`, `full_name`, `reg_number`, `licensing_authority`, `organization_id`, `verification_status` |
| `organizations` | Hospitals, clinics, EMS orgs | `id`, `name`, `org_type`, `registration_info`, `status` |
| `patients` | Patient demographic records | `id` (`HC04-PAT-XXXX-XXXX`), `full_name`, `dob`, `sex`, `phone`, `blood_group`, `allergies`, `existing_conditions`, `priority` |
| `patient_access_otps` | Patient portal OTP verification | `id`, `patient_id`, `otp_code`, `expires_at`, `is_used` |
| `doctor_patient_relationships` | Treating physician linkages | `id`, `doctor_id`, `patient_id`, `organization_id`, `relationship_type` |
| `medical_records` | Active clinical records | `id`, `patient_id`, `provider_id`, `record_type`, `clinical_data` (JSON), `source`, `author` |
| `record_versions` | Immutable version trail | `id`, `record_id`, `version_num`, `previous_value`, `new_value`, `changed_by`, `reason`, `timestamp` |
| `ehr_sources` | Network hospital registries | `id`, `name`, `protocol`, `format`, `status`, `last_sync`, `security_info` |
| `ehr_records` | Ingested cross-source payloads | `id`, `source_id`, `patient_identifier`, `format`, `raw_payload`, `normalized_payload` |
| `conflicts` | Medical discrepancies | `id`, `patient_id`, `field_name`, `severity`, `source_a`, `value_a`, `source_b`, `value_b`, `status` |
| `emergency_cases` | Active trauma admissions | `id`, `case_number`, `patient_id`, `priority`, `status`, `assigned_team` |
| `access_sessions` | Break-glass override sessions | `id`, `requester_id`, `patient_id`, `purpose`, `break_glass`, `start_time`, `expiry_time`, `is_active` |
| `audit_logs` | Immutable audit trail | `id`, `timestamp`, `user_id`, `user_name`, `role`, `patient_id`, `action`, `purpose`, `result` |

---

## 4. Test Credentials (LOCAL DEVELOPMENT ONLY)

| Role | Username / Email | Password | Status | Permissions |
|---|---|---|---|---|
| **Administrator** | `admin@hc04.health` | `Admin@12345` | `VERIFIED` | Full governance, professional verification, suspension, audit trail |
| **Trauma Physician** | `dr.rahul@hospital.example` | `Doctor@12345` | `VERIFIED` | Register patients, add records, EHR query, emergency summary, resolve conflicts, break-glass |
| **Pending Doctor** | `dr.priya@hospital.example` | `Doctor@12345` | `PENDING_VERIFICATION` | Clinical access blocked until verified by Administrator |
| **EMT (Paramedic)** | `emt.arun@emergency.example` | `Emt@12345` | `VERIFIED` | Emergency-critical triage summary, critical allergy/medication alerts |
| **Patient Access** | `HC04-PAT-1024` (Arjun Kumar) | *(OTP sent on request)* | `VERIFIED` | Patient health summary, visit history, access audit trail |

---

## 5. Quick Start Instructions

### Option A: Local Python Run (Windows / macOS / Linux)

1. Ensure dependencies are installed in virtual environment:
   ```bash
   .\venv\Scripts\python.exe -m pip install -r backend/requirements.txt
   ```
2. Start the unified server:
   ```bash
   .\venv\Scripts\python.exe run_server.py
   ```
3. Open your browser:
   - **Full Application Console**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - **Interactive OpenAPI / Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Option B: Docker Compose Run (PostgreSQL + FastAPI)

```bash
docker-compose up --build
```
Access at [http://localhost:8000/](http://localhost:8000/).

---

## 6. Running Automated Tests

Run pytest across all functional suites:
```bash
$env:PYTHONPATH="backend"
.\venv\Scripts\pytest.exe backend/tests -v
```

Verified test coverage:
- `test_health_check`: Gateway telemetry and readiness
- `test_doctor_registration_and_verification_workflow`: Full doctor onboarding, pending verification gatekeeper, and admin verification approval
- `test_patient_registration_cryptographic_id_and_otp_access`: Unpredictable non-sequential ID generation (`HC04-PAT-XXXX-XXXX`), QR token, and OTP patient login
- `test_medical_record_creation_and_versioning`: Clinical record creation and immutable versioning
- `test_fhir_hl7_csv_adapters`: FHIR R4 Bundle parsing, HL7 v2 (MSH, PID, PV1, AL1, OBX) parsing, and CSV normalization
- `test_conflict_detection_and_emergency_summary`: Blood group discordance, penicillin allergy conflicts, and evidence-grounded emergency summaries
- `test_break_glass_emergency_access_and_audit`: Temporary 15-minute expiring emergency sessions and permanent audit logging

---

## 7. External Integrations & Configuration Notice (Requirement #52)

In compliance with real-world healthcare architectural standards, external hospital infrastructure connections are modeled via clean provider interfaces:
- **FHIR R4**: Uses `FHIRProvider` configurable with `FHIR_BASE_URL`, `FHIR_CLIENT_ID`, and `FHIR_CLIENT_SECRET`.
- **HL7 v2**: Uses `HL7Provider` configurable with `HL7_ENDPOINT_HOST` and `HL7_ENDPOINT_PORT` via MLLP/TCP.
- **National Registry**: Configurable with verification endpoint URL. When no national medical council registry endpoint is provided, the admin verification workflow is enforced.
- Seed data is stored cleanly in `backend/seed/dev_seed.py` and strictly separated from production business logic.
