import json
from typing import Dict, Any, List, Optional
from app.integrations.base_adapter import EHRProvider
from app.integrations.canonical import (
    CanonicalMedicalRecord, CanonicalAllergy, CanonicalMedication,
    CanonicalCondition, CanonicalObservation, CanonicalProcedure
)

class FHIRProvider(EHRProvider):
    def __init__(self, source_name: str = "City General Hospital", base_url: Optional[str] = None):
        self.source_name = source_name
        self.base_url = base_url

    def get_source_name(self) -> str:
        return self.source_name

    def get_protocol(self) -> str:
        return "FHIR R4"

    def validate_record(self, raw_data: Any) -> bool:
        """Validate if data is valid JSON or dict and contains resourceType."""
        if isinstance(raw_data, str):
            try:
                raw_data = json.loads(raw_data)
            except Exception:
                return False
        if not isinstance(raw_data, dict):
            return False
        return "resourceType" in raw_data

    def search_patient(self, query: str, dob: Optional[str] = None) -> List[Dict[str, Any]]:
        # Ready for external FHIR server query when base_url is configured with credentials
        return []

    def retrieve_patient(self, external_id: str) -> Optional[Dict[str, Any]]:
        return None

    def retrieve_records(self, patient_identifier: str) -> List[Dict[str, Any]]:
        return []

    def normalize_record(self, raw_data: Any) -> CanonicalMedicalRecord:
        """Parse FHIR Bundle or individual FHIR resource into CanonicalMedicalRecord."""
        if isinstance(raw_data, str):
            payload = json.loads(raw_data)
        else:
            payload = raw_data

        canonical = CanonicalMedicalRecord(
            source_name=self.source_name,
            format="FHIR R4 JSON",
            raw_payload=json.dumps(payload, indent=2) if isinstance(payload, dict) else str(payload)
        )

        # Handle Bundle or single resource
        resources = []
        if payload.get("resourceType") == "Bundle":
            for entry in payload.get("entry", []):
                res = entry.get("resource")
                if res:
                    resources.append(res)
        else:
            resources.append(payload)

        for res in resources:
            r_type = res.get("resourceType")

            # 1. Patient
            if r_type == "Patient":
                canonical.external_id = res.get("id")
                # Name
                names = res.get("name", [])
                if names:
                    primary_name = names[0]
                    given = " ".join(primary_name.get("given", []))
                    family = primary_name.get("family", "")
                    canonical.full_name = f"{given} {family}".strip()
                canonical.dob = res.get("birthDate")
                
                # Check for blood group extension if present
                for ext in res.get("extension", []):
                    if "blood-group" in ext.get("url", "").lower():
                        canonical.blood_group = ext.get("valueString")

            # 2. AllergyIntolerance
            elif r_type == "AllergyIntolerance":
                codeable = res.get("code", {})
                coding = codeable.get("coding", [{}])[0]
                substance = coding.get("display") or codeable.get("text") or "Unknown substance"
                severity = res.get("criticality") or "moderate"
                date_val = res.get("recordedDate") or res.get("onsetDateTime")
                canonical.allergies.append(CanonicalAllergy(
                    substance=substance,
                    severity=severity,
                    recorded_date=str(date_val) if date_val else None,
                    source_system=self.source_name
                ))

            # 3. MedicationRequest or MedicationStatement
            elif r_type in ["MedicationRequest", "MedicationStatement"]:
                med_code = res.get("medicationCodeableConcept", {})
                coding = med_code.get("coding", [{}])[0]
                med_name = coding.get("display") or med_code.get("text") or "Prescribed Medication"
                dosage_instructions = res.get("dosageInstruction", [])
                dose_text = dosage_instructions[0].get("text") if dosage_instructions else None
                canonical.medications.append(CanonicalMedication(
                    name=med_name,
                    dosage=dose_text,
                    source_system=self.source_name
                ))

            # 4. Condition
            elif r_type == "Condition":
                codeable = res.get("code", {})
                coding = codeable.get("coding", [{}])[0]
                cond_name = coding.get("display") or codeable.get("text") or "Recorded Condition"
                onset = res.get("onsetDateTime") or res.get("recordedDate")
                canonical.conditions.append(CanonicalCondition(
                    display_name=cond_name,
                    onset_date=str(onset) if onset else None,
                    source_system=self.source_name
                ))

            # 5. Observation (e.g. Labs / Vitals)
            elif r_type == "Observation":
                codeable = res.get("code", {})
                coding = codeable.get("coding", [{}])[0]
                test_name = coding.get("display") or codeable.get("text") or "Laboratory Observation"
                val_quantity = res.get("valueQuantity", {})
                if val_quantity:
                    val_str = f"{val_quantity.get('value')} {val_quantity.get('unit', '')}".strip()
                else:
                    val_str = str(res.get("valueString", ""))
                
                # Check blood group observation
                if "blood group" in test_name.lower() or "blood type" in test_name.lower():
                    canonical.blood_group = val_str or res.get("valueCodeableConcept", {}).get("text")

                canonical.observations.append(CanonicalObservation(
                    test_name=test_name,
                    value=val_str,
                    unit=val_quantity.get("unit"),
                    source_system=self.source_name
                ))

            # 6. Procedure
            elif r_type == "Procedure":
                codeable = res.get("code", {})
                coding = codeable.get("coding", [{}])[0]
                proc_name = coding.get("display") or codeable.get("text") or "Surgical Procedure"
                perf_date = res.get("performedDateTime")
                canonical.procedures.append(CanonicalProcedure(
                    procedure_name=proc_name,
                    performed_date=str(perf_date) if perf_date else None,
                    source_system=self.source_name
                ))

            # 7. Encounter
            elif r_type == "Encounter":
                enc_type = res.get("class", {}).get("display") or "Clinical Encounter"
                period_start = res.get("period", {}).get("start", "")
                canonical.recent_events.append(f"{enc_type} — {period_start[:10] if period_start else 'Recent'}")

        return canonical
