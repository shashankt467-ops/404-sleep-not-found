import csv
import io
import json
from typing import Dict, Any, List, Optional
from app.integrations.base_adapter import EHRProvider
from app.integrations.canonical import (
    CanonicalMedicalRecord, CanonicalAllergy, CanonicalMedication,
    CanonicalCondition, CanonicalObservation, CanonicalProcedure
)

class CSVJSONProvider(EHRProvider):
    def __init__(self, source_name: str = "Regional Diagnostic Lab"):
        self.source_name = source_name

    def get_source_name(self) -> str:
        return self.source_name

    def get_protocol(self) -> str:
        return "CSV / Structured JSON"

    def validate_record(self, raw_data: Any) -> bool:
        if isinstance(raw_data, (dict, list)):
            return True
        if isinstance(raw_data, str):
            # Check if JSON
            try:
                json.loads(raw_data)
                return True
            except Exception:
                pass
            # Check if CSV (has at least header row)
            return len(raw_data.strip().splitlines()) >= 1
        return False

    def search_patient(self, query: str, dob: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def retrieve_patient(self, external_id: str) -> Optional[Dict[str, Any]]:
        return None

    def retrieve_records(self, patient_identifier: str) -> List[Dict[str, Any]]:
        return []

    def normalize_record(self, raw_data: Any) -> CanonicalMedicalRecord:
        """Parse structured JSON or CSV into CanonicalMedicalRecord."""
        canonical = CanonicalMedicalRecord(
            source_name=self.source_name,
            format="CSV/JSON",
            raw_payload=str(raw_data)
        )

        # 1. JSON handling
        if isinstance(raw_data, dict) or (isinstance(raw_data, str) and raw_data.strip().startswith("{")):
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            canonical.external_id = data.get("patient_id") or data.get("id")
            canonical.full_name = data.get("name") or data.get("full_name")
            canonical.dob = data.get("dob") or data.get("date_of_birth")
            canonical.blood_group = data.get("blood_group") or data.get("bloodGroup")

            # Allergies
            for a in data.get("allergies", []):
                substance = a if isinstance(a, str) else a.get("substance", "Unknown")
                canonical.allergies.append(CanonicalAllergy(substance=substance, source_system=self.source_name))

            # Medications
            for m in data.get("medications", []):
                med_name = m if isinstance(m, str) else m.get("name", "Medication")
                canonical.medications.append(CanonicalMedication(name=med_name, source_system=self.source_name))

            # Conditions
            for c in data.get("conditions", []):
                cond_name = c if isinstance(c, str) else c.get("name", "Condition")
                canonical.conditions.append(CanonicalCondition(display_name=cond_name, source_system=self.source_name))

            # Observations/Labs
            labs = data.get("labs", {})
            if isinstance(labs, dict):
                for k, v in labs.items():
                    canonical.observations.append(CanonicalObservation(
                        test_name=k, value=str(v), source_system=self.source_name
                    ))

            return canonical

        # 2. CSV handling
        if isinstance(raw_data, str):
            reader = csv.DictReader(io.StringIO(raw_data.strip()))
            for row in reader:
                # Normalize keys to lowercase stripped
                row_norm = {k.lower().strip(): v.strip() for k, v in row.items() if k}
                
                if not canonical.full_name:
                    canonical.full_name = row_norm.get("name") or row_norm.get("patient_name")
                if not canonical.dob:
                    canonical.dob = row_norm.get("dob") or row_norm.get("date_of_birth")
                if not canonical.blood_group and row_norm.get("blood_group"):
                    canonical.blood_group = row_norm.get("blood_group")

                # Parse test and value if lab CSV
                test_name = row_norm.get("test_name") or row_norm.get("observation") or row_norm.get("lab")
                test_val = row_norm.get("result") or row_norm.get("value")
                unit = row_norm.get("unit")
                if test_name and test_val:
                    canonical.observations.append(CanonicalObservation(
                        test_name=test_name,
                        value=f"{test_val} {unit or ''}".strip(),
                        unit=unit,
                        source_system=self.source_name
                    ))

                # Parse medication or allergy
                if row_norm.get("medication"):
                    canonical.medications.append(CanonicalMedication(
                        name=row_norm.get("medication"),
                        dosage=row_norm.get("dosage"),
                        source_system=self.source_name
                    ))

                if row_norm.get("allergy"):
                    canonical.allergies.append(CanonicalAllergy(
                        substance=row_norm.get("allergy"),
                        source_system=self.source_name
                    ))

        return canonical
