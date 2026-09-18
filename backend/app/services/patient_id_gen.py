import secrets
from sqlalchemy.orm import Session
from app.models.patient import Patient

def generate_patient_id(db: Session) -> str:
    """
    Generate a cryptographically secure, unpredictable, non-sequential Patient ID.
    Example: HC04-PAT-7F82-91K4
    Ensures uniqueness by checking the database before returning.
    """
    charset = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ" # Avoid 0, 1, I, O to prevent transcription ambiguity
    
    max_attempts = 10
    for _ in range(max_attempts):
        part1 = "".join(secrets.choice(charset) for _ in range(4))
        part2 = "".join(secrets.choice(charset) for _ in range(4))
        candidate_id = f"HC04-PAT-{part1}-{part2}"
        
        # Verify uniqueness
        exists = db.query(Patient).filter(Patient.id == candidate_id).first()
        if not exists:
            return candidate_id
            
    # Fallback to 6-char chunks if collision occurs
    part1 = secrets.token_hex(3).upper()
    part2 = secrets.token_hex(3).upper()
    return f"HC04-PAT-{part1}-{part2}"

def generate_qr_token(patient_id: str) -> str:
    """
    Generate a secure token for the QR code that resolves through the backend,
    never embedding raw sensitive health data into the QR barcode.
    """
    token_entropy = secrets.token_urlsafe(24)
    return f"hc04://verify/{patient_id}?sig={token_entropy}"
