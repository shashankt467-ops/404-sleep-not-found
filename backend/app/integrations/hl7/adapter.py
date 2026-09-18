from typing import Dict, Any, List, Optional
from app.integrations.base_adapter import EHRProvider
from app.integrations.canonical import (
    CanonicalMedicalRecord, CanonicalAllergy, CanonicalMedication,
    CanonicalCondition, CanonicalObservation, CanonicalProcedure
)

class HL7Provider(EHRProvider):
    """
    HL7 v2.x ER7 message parser.
    Supports standard ADT (A01, A08) and ORU (R01) message structures with:
    - MSH (Message Header)
    - PID (Patient Identification)
    - PV1 (Patient Visit)
    - AL1 (Patient Allergy Information)
    - DG1 (Diagnosis)
    - OBX (Observation / Result)
    """

    def __init__(self, source_name: str = "Apollo Medical Center"):
        self.source_name = source_name

    def get_source_name(self) -> str:
        return self.source_name

    def get_protocol(self) -> str:
        return "HL7 v2.5 (ER7)"

    def validate_record(self, raw_data: Any) -> bool:
        if not isinstance(raw_data, str):
            return False
        # Must begin with MSH segment
        lines = [line.strip() for line in raw_data.strip().splitlines() if line.strip()]
        return len(lines) > 0 and lines[0].startswith("MSH")

    def search_patient(self, query: str, dob: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def retrieve_patient(self, external_id: str) -> Optional[Dict[str, Any]]:
        return None

    def retrieve_records(self, patient_identifier: str) -> List[Dict[str, Any]]:
        return []

    def normalize_record(self, raw_data: str) -> CanonicalMedicalRecord:
        """Parse HL7 ER7 pipe-delimited message into CanonicalMedicalRecord."""
        canonical = CanonicalMedicalRecord(
            source_name=self.source_name,
            format="HL7 v2 (ER7)",
            raw_payload=raw_data
        )

        lines = [line.strip() for line in raw_data.strip().splitlines() if line.strip()]
        for line in lines:
            parts = line.split("|")
            seg_name = parts[0]

            # PID: Patient Identification
            if seg_name == "PID":
                # PID-3: Patient Identifier List
                if len(parts) > 3 and parts[3]:
                    id_subparts = parts[3].split("^")
                    canonical.external_id = id_subparts[0]
                    canonical.patient_id = id_subparts[0]

                # PID-5: Patient Name (Family^Given^Middle)
                if len(parts) > 5 and parts[5]:
                    name_parts = parts[5].split("^")
                    family = name_parts[0] if len(name_parts) > 0 else ""
                    given = name_parts[1] if len(name_parts) > 1 else ""
                    canonical.full_name = f"{given} {family}".strip()

                # PID-7: Date/Time of Birth (YYYYMMDD)
                if len(parts) > 7 and parts[7]:
                    dob_raw = parts[7][:8]
                    if len(dob_raw) == 8:
                        canonical.dob = f"{dob_raw[6:8]}/{dob_raw[4:6]}/{dob_raw[:4]}"
                    else:
                        canonical.dob = dob_raw

            # AL1: Patient Allergy Information
            elif seg_name == "AL1":
                # AL1-3: Allergy Code/Mnemonic/Description (Code^Description)
                allergy_desc = "Unknown allergy"
                if len(parts) > 3 and parts[3]:
                    al_parts = parts[3].split("^")
                    allergy_desc = al_parts[1] if len(al_parts) > 1 else al_parts[0]

                severity = "moderate"
                if len(parts) > 4 and parts[4]:
                    severity = parts[4]

                canonical.allergies.append(CanonicalAllergy(
                    substance=allergy_desc,
                    severity=severity,
                    source_system=self.source_name
                ))

            # DG1: Diagnosis Information
            elif seg_name == "DG1":
                diag_desc = "Recorded Diagnosis"
                if len(parts) > 3 and parts[3]:
                    dg_parts = parts[3].split("^")
                    diag_desc = dg_parts[1] if len(dg_parts) > 1 else dg_parts[0]

                canonical.conditions.append(CanonicalCondition(
                    display_name=diag_desc,
                    source_system=self.source_name
                ))

            # OBX: Observation / Result
            elif seg_name == "OBX":
                test_name = "Observation"
                if len(parts) > 3 and parts[3]:
                    obx_parts = parts[3].split("^")
                    test_name = obx_parts[1] if len(obx_parts) > 1 else obx_parts[0]

                test_val = parts[5] if len(parts) > 5 else ""
                unit_str = parts[6] if len(parts) > 6 else ""

                if "blood group" in test_name.lower() or "blood type" in test_name.lower():
                    canonical.blood_group = test_val

                canonical.observations.append(CanonicalObservation(
                    test_name=test_name,
                    value=f"{test_val} {unit_str}".strip(),
                    unit=unit_str,
                    source_system=self.source_name
                ))

            # PV1: Patient Visit
            elif seg_name == "PV1":
                visit_type = parts[2] if len(parts) > 2 else "Emergency"
                admit_date = parts[44][:8] if len(parts) > 44 and parts[44] else "Recent"
                canonical.recent_events.append(f"{visit_type} visit — {admit_date}")

        return canonical
