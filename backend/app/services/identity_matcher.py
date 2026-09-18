from typing import Dict, Any, List, Optional
import difflib

def normalize_dob(dob_str: Optional[str]) -> Optional[str]:
    """Normalize common medical DOB formats (DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY) into ISO YYYY-MM-DD."""
    if not dob_str:
        return None
    cleaned = str(dob_str).strip().replace('/', '-').replace('.', '-')
    parts = cleaned.split('-')
    if len(parts) == 3:
        # Check if YYYY-MM-DD
        if len(parts[0]) == 4:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        # Check if DD-MM-YYYY
        elif len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return cleaned.lower()

def calculate_name_similarity(name1: Optional[str], name2: Optional[str]) -> float:
    """Compute normalized token and character similarity between two names."""
    if not name1 or not name2:
        return 0.0
    n1 = str(name1).lower().strip()
    n2 = str(name2).lower().strip()
    if n1 == n2:
        return 1.0

    # Strip honorifics
    honorifics = {"dr.", "dr", "mr.", "mr", "mrs.", "mrs", "ms.", "ms", "patient"}
    tokens1 = [t for t in n1.replace(',', ' ').split() if t not in honorifics]
    tokens2 = [t for t in n2.replace(',', ' ').split() if t not in honorifics]

    if not tokens1 or not tokens2:
        return round(difflib.SequenceMatcher(None, n1, n2).ratio(), 3)

    if " ".join(tokens1) == " ".join(tokens2):
        return 1.0

    set1, set2 = set(tokens1), set(tokens2)
    intersection = set1.intersection(set2)

    if intersection:
        # Check for abbreviation matching in remaining tokens (e.g. 'k.' vs 'kumar')
        rem1 = set1 - intersection
        rem2 = set2 - intersection
        abbr_bonus = 0.0
        for r1 in rem1:
            c1 = r1.rstrip('.')
            for r2 in rem2:
                c2 = r2.rstrip('.')
                if (len(c1) == 1 and c2.startswith(c1)) or (len(c2) == 1 and c1.startswith(c2)):
                    abbr_bonus += 0.85

        effective_matches = len(intersection) + abbr_bonus
        ratio = effective_matches / max(len(set1), len(set2))
        return round(min(1.0, max(0.0, 0.70 + 0.28 * ratio)), 3)

    return round(difflib.SequenceMatcher(None, n1, n2).ratio(), 3)

def match_patient_identity(
    target_patient: Any, # Patient DB model or dict
    candidate_record: Any # CanonicalMedicalRecord or dict
) -> Dict[str, Any]:
    """
    Patient identity matching engine evaluating:
    1. Direct Patient Identifier match
    2. Name similarity (Tokens, Abbreviations, Levenshtein distance)
    3. Date of Birth match (normalized)
    4. Phone / contact overlap
    5. Clinical demographic consistency (blood group)
    Returns:
    - status: MATCHED | POSSIBLE_MATCH | NO_MATCH
    - score: float (0.0 to 100.0)
    - factors: List[str]
    """
    factors = []

    target_id = str(getattr(target_patient, "id", None) or (target_patient.get("id") if isinstance(target_patient, dict) else "")).strip()
    target_name = str(getattr(target_patient, "full_name", None) or (target_patient.get("name") if isinstance(target_patient, dict) else "")).strip()
    target_dob = str(getattr(target_patient, "dob", None) or (target_patient.get("dob") if isinstance(target_patient, dict) else "")).strip()
    target_phone = str(getattr(target_patient, "phone", None) or (target_patient.get("phone") if isinstance(target_patient, dict) else "")).strip()
    target_bg = str(getattr(target_patient, "blood_group", None) or (target_patient.get("blood_group") if isinstance(target_patient, dict) else "")).strip()

    cand_id = str(getattr(candidate_record, "patient_id", None) or (candidate_record.get("patient_id") if isinstance(candidate_record, dict) else "")).strip()
    cand_name = str(getattr(candidate_record, "full_name", None) or (candidate_record.get("name") if isinstance(candidate_record, dict) else "")).strip()
    cand_dob = str(getattr(candidate_record, "dob", None) or (candidate_record.get("dob") if isinstance(candidate_record, dict) else "")).strip()
    cand_phone = str(getattr(candidate_record, "phone", None) or (candidate_record.get("phone") if isinstance(candidate_record, dict) else "")).strip()
    cand_bg = str(getattr(candidate_record, "blood_group", None) or (candidate_record.get("blood_group") or candidate_record.get("bloodGroup") if isinstance(candidate_record, dict) else "")).strip()

    # 1. Identifier match (Up to 45.0 points)
    id_score = 0.0
    if cand_id and target_id:
        if cand_id.upper() == target_id.upper():
            factors.append("Exact Patient Identifier match (+45%)")
            id_score = 45.0
        elif cand_id.upper() in target_id.upper() or target_id.upper() in cand_id.upper():
            factors.append("Partial Identifier token alignment (+32%)")
            id_score = 32.0
        else:
            factors.append("Contradictory Patient Identifier (-35%)")
            id_score = -35.0
    elif target_id:
        factors.append("No candidate ID provided (demographic matching required)")
        id_score = 12.0

    # 2. Date of Birth match (Up to 25.0 points)
    dob_score = 0.0
    norm_target_dob = normalize_dob(target_dob)
    norm_cand_dob = normalize_dob(cand_dob)
    if norm_cand_dob and norm_target_dob:
        if norm_cand_dob == norm_target_dob:
            factors.append("Date of birth identical (+25%)")
            dob_score = 25.0
        else:
            target_year = norm_target_dob.split('-')[0] if '-' in norm_target_dob else ""
            cand_year = norm_cand_dob.split('-')[0] if '-' in norm_cand_dob else ""
            if target_year and cand_year and target_year == cand_year:
                factors.append("Birth year concordant, day/month variance (+12%)")
                dob_score = 12.0
            else:
                factors.append("Discrepant Date of Birth (-25%)")
                dob_score = -25.0
    elif norm_target_dob:
        dob_score = 6.0
        factors.append("Unspecified candidate Date of Birth (+6%)")

    # 3. Name similarity (Up to 25.0 points)
    name_sim = calculate_name_similarity(target_name, cand_name)
    name_score = round(name_sim * 25.0, 1)
    if name_sim >= 0.95:
        factors.append(f"Full name exact/near-exact match ({name_sim:.1%}, +{name_score}%)")
    elif name_sim >= 0.70:
        factors.append(f"Name partial token/initial match ({name_sim:.1%}, +{name_score}%)")
    elif name_sim >= 0.40:
        factors.append(f"Weak name similarity ({name_sim:.1%}, +{name_score}%)")
    else:
        name_score = -15.0
        factors.append(f"Name mismatch ({name_sim:.1%}, -15%)")

    # 4. Secondary Demographics: Phone & Blood Group (Up to 10.0 points)
    demo_score = 0.0
    if cand_phone and target_phone:
        p1 = ''.join(filter(str.isdigit, target_phone))[-10:]
        p2 = ''.join(filter(str.isdigit, cand_phone))[-10:]
        if p1 and p2 and p1 == p2:
            factors.append("Registered phone number match (+6%)")
            demo_score += 6.0
        elif p1 and p2:
            demo_score -= 4.0
            factors.append("Discrepant phone number (-4%)")

    if cand_bg and target_bg and target_bg not in ["Unknown", "—", ""]:
        if cand_bg.upper() == target_bg.upper():
            factors.append(f"Concordant blood group {cand_bg} (+4%)")
            demo_score += 4.0
        else:
            factors.append(f"Contradictory blood group {cand_bg} vs {target_bg} (-10%)")
            demo_score -= 10.0

    raw_score = id_score + dob_score + name_score + demo_score

    # Compute calibrated continuous score according to given data
    if id_score >= 45.0 and dob_score >= 25.0 and name_sim >= 0.95:
        final_score = round(min(99.8, 97.4 + (name_sim - 0.95) * 40.0 + max(0.0, demo_score * 0.25)), 1)
    elif id_score >= 45.0 and dob_score >= 25.0:
        final_score = round(max(84.0, min(96.8, 85.0 + (name_sim * 11.5) + demo_score)), 1)
    elif id_score >= 32.0:
        final_score = round(max(0.0, min(94.5, raw_score)), 1)
    else:
        final_score = round(max(0.0, min(80.0, raw_score * 0.82)), 1)

    if final_score >= 90.0:
        status = "MATCHED"
    elif final_score >= 65.0:
        status = "POSSIBLE_MATCH"
    else:
        status = "NO_MATCH"

    return {
        "status": status,
        "score": final_score,
        "factors": factors,
        "safe_to_merge": (status == "MATCHED")
    }
