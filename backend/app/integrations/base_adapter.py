from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.integrations.canonical import CanonicalMedicalRecord

class EHRProvider(ABC):
    """
    Abstract interface for multi-hospital EHR integration providers.
    Supports modular extension for FHIR, HL7, CSV, JSON, and future protocols.
    """
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return the friendly name of the hospital or EHR source."""
        pass

    @abstractmethod
    def get_protocol(self) -> str:
        """Return protocol name (e.g. FHIR, HL7 v2, CSV/JSON, NCPDP)."""
        pass

    @abstractmethod
    def search_patient(self, query: str, dob: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search external EHR for matching patient stubs."""
        pass

    @abstractmethod
    def retrieve_patient(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve demographic patient record from source."""
        pass

    @abstractmethod
    def retrieve_records(self, patient_identifier: str) -> List[Dict[str, Any]]:
        """Retrieve clinical records for given patient identifier."""
        pass

    @abstractmethod
    def normalize_record(self, raw_data: Any) -> CanonicalMedicalRecord:
        """Transform raw EHR message/data into the HC-04 canonical format."""
        pass

    @abstractmethod
    def validate_record(self, raw_data: Any) -> bool:
        """Validate format and integrity of the external payload."""
        pass
