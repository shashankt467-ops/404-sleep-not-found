from typing import List, Dict, Any, Optional
from datetime import datetime
from app.integrations.canonical import CanonicalMedicalRecord

def detect_medical_conflicts(
    patient_id: str,
    records: List[CanonicalMedicalRecord]
) -> List[Dict[str, Any]]:
    """
    Detect genuine clinical conflicts across heterogeneous medical records.
    Never silently assumes or overwrites discrepant values.
    Returns structured conflict objects with severity and clinical advisories.
    """
    conflicts = []

    if len(records) < 2:
        return conflicts

    # 1. Blood Group Conflicts
    blood_groups = {}
    for r in records:
        if r.blood_group and r.blood_group not in ["—", "Unknown", "None", ""]:
            bg_clean = r.blood_group.strip().upper()
            if bg_clean not in blood_groups:
                blood_groups[bg_clean] = []
            blood_groups[bg_clean].append(r)

    if len(blood_groups) > 1:
        types = list(blood_groups.keys())
        rec_a = blood_groups[types[0]][0]
        rec_b = blood_groups[types[1]][0]
        conflicts.append({
            "id": f"cnf-bg-{patient_id}",
            "patient_id": patient_id,
            "field": "Blood Group",
            "severity": "high",
            "a": {
                "source": rec_a.source_name,
                "value": types[0],
                "date": rec_a.ingested_at.strftime("%d %b %Y") if hasattr(rec_a, "ingested_at") else "Recent"
            },
            "b": {
                "source": rec_b.source_name,
                "value": types[1],
                "date": rec_b.ingested_at.strftime("%d %b %Y") if hasattr(rec_b, "ingested_at") else "Recent"
            },
            "status": "UNRESOLVED",
            "clinical_advisory": f"Blood group differs between {rec_a.source_name} ({types[0]}) and {rec_b.source_name} ({types[1]}). Immediate serological cross-match required before transfusion."
        })

    # 2. Allergy Conflicts (Critical: Allergy reported vs No known allergy)
    allergies_by_source = {}
    for r in records:
        source = r.source_name
        allergy_names = [a.substance.strip().lower() for a in r.allergies if a.substance]
        allergies_by_source[source] = (r, allergy_names)

    sources = list(allergies_by_source.keys())
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            src_a, (rec_a, list_a) = sources[i], allergies_by_source[sources[i]]
            src_b, (rec_b, list_b) = sources[j], allergies_by_source[sources[j]]

            has_no_allergy_a = any("none" in a or "no known" in a for a in list_a) or len(list_a) == 0
            has_no_allergy_b = any("none" in b or "no known" in b for b in list_b) or len(list_b) == 0

            # Discrepancy: One lists specific allergy (like Penicillin), other lists None
            specific_a = [a for a in list_a if "none" not in a and "no known" not in a]
            specific_b = [b for b in list_b if "none" not in b and "no known" not in b]

            if specific_a and has_no_allergy_b:
                val_a_str = ", ".join([a.title() for a in specific_a]) + " Allergy — YES"
                val_b_str = "Known Allergies — NONE recorded"
                conflicts.append({
                    "id": f"cnf-al-{patient_id}-{i}-{j}",
                    "patient_id": patient_id,
                    "field": "Allergy",
                    "severity": "critical",
                    "a": {
                        "source": src_a,
                        "value": val_a_str,
                        "date": rec_a.ingested_at.strftime("%d %b %Y") if hasattr(rec_a, "ingested_at") else "Recent"
                    },
                    "b": {
                        "source": src_b,
                        "value": val_b_str,
                        "date": rec_b.ingested_at.strftime("%d %b %Y") if hasattr(rec_b, "ingested_at") else "Recent"
                    },
                    "status": "UNRESOLVED",
                    "clinical_advisory": f"{src_a} records active allergy ({', '.join(specific_a).title()}), whereas {src_b} reports no known allergies. Clinical verification required before administering related compounds."
                })
            elif specific_b and has_no_allergy_a:
                val_b_str = ", ".join([b.title() for b in specific_b]) + " Allergy — YES"
                val_a_str = "Known Allergies — NONE recorded"
                conflicts.append({
                    "id": f"cnf-al-{patient_id}-{j}-{i}",
                    "patient_id": patient_id,
                    "field": "Allergy",
                    "severity": "critical",
                    "a": {
                        "source": src_b,
                        "value": val_b_str,
                        "date": rec_b.ingested_at.strftime("%d %b %Y") if hasattr(rec_b, "ingested_at") else "Recent"
                    },
                    "b": {
                        "source": src_a,
                        "value": val_a_str,
                        "date": rec_a.ingested_at.strftime("%d %b %Y") if hasattr(rec_a, "ingested_at") else "Recent"
                    },
                    "status": "UNRESOLVED",
                    "clinical_advisory": f"{src_b} records active allergy ({', '.join(specific_b).title()}), whereas {src_a} reports no known allergies. Clinical verification required before administering related compounds."
                })

    # 3. Critical Medication Discrepancies (Anticoagulants / High Risk Meds)
    high_risk_meds = ["warfarin", "clopidogrel", "heparin", "apixaban", "rivaroxaban", "dabigatran", "insulin"]
    meds_by_source = {}
    for r in records:
        source = r.source_name
        m_list = [m.name.strip().lower() for m in r.medications if m.name]
        meds_by_source[source] = (r, m_list)

    sources = list(meds_by_source.keys())
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            src_a, (rec_a, list_a) = sources[i], meds_by_source[sources[i]]
            src_b, (rec_b, list_b) = sources[j], meds_by_source[sources[j]]

            for hrm in high_risk_meds:
                in_a = any(hrm in m for m in list_a)
                in_b = any(hrm in m for m in list_b)
                if in_a != in_b:
                    present_src = src_a if in_a else src_b
                    present_rec = rec_a if in_a else rec_b
                    absent_src = src_b if in_a else src_a
                    absent_rec = rec_b if in_a else rec_a
                    conflicts.append({
                        "id": f"cnf-med-{patient_id}-{hrm}",
                        "patient_id": patient_id,
                        "field": "Medication",
                        "severity": "medium",
                        "a": {
                            "source": present_src,
                            "value": hrm.title(),
                            "date": present_rec.ingested_at.strftime("%d %b %Y") if hasattr(present_rec, "ingested_at") else "Recent"
                        },
                        "b": {
                            "source": absent_src,
                            "value": "Not listed / missing in record",
                            "date": absent_rec.ingested_at.strftime("%d %b %Y") if hasattr(absent_rec, "ingested_at") else "Recent"
                        },
                        "status": "UNRESOLVED",
                        "clinical_advisory": f"Critical medication '{hrm.title()}' recorded at {present_src} but absent at {absent_src}. Verify ongoing dosing before prescribing or performing invasive procedures."
                    })

    return conflicts
