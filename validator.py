"""
Valide les champs extraits par extractor.py : cohérence des montants, format
du SIREN, mentions obligatoires de la réforme facturation électronique 2026.

N'utilise aucun appel LLM — uniquement des règles déterministes. C'est ce qui
distingue un pipeline fiable d'une confiance aveugle dans le modèle.
"""

from datetime import datetime


def _est_siren_valide(siren: str) -> bool:
    """Un SIREN valide fait exactement 9 chiffres."""
    return bool(siren) and siren.isdigit() and len(siren) == 9


def _parse_date(date_str: str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def validate_facture(data: dict) -> list[dict]:
    """Retourne une liste d'anomalies détectées sur une facture.
    Chaque anomalie : {"champ": ..., "gravite": "erreur"|"avertissement", "message": ...}"""
    issues = []

    # --- Cohérence des montants ---
    ht = data.get("montant_ht", 0) or 0
    tva = data.get("montant_tva", 0) or 0
    ttc = data.get("montant_ttc", 0) or 0

    if ht and tva and ttc:
        ecart = abs((ht + tva) - ttc)
        if ecart > 0.02:  # tolérance d'arrondi de 2 centimes
            issues.append({
                "champ": "montant_ttc",
                "gravite": "erreur",
                "message": f"Incohérence : HT ({ht}) + TVA ({tva}) = {ht + tva:.2f}, "
                           f"différent du TTC déclaré ({ttc}).",
            })

    if ttc == 0:
        issues.append({
            "champ": "montant_ttc",
            "gravite": "erreur",
            "message": "Montant TTC manquant ou nul.",
        })

    # --- Cohérence des dates ---
    date_emission = _parse_date(data.get("date_emission", ""))
    date_echeance = _parse_date(data.get("date_echeance", ""))
    if date_emission and date_echeance and date_echeance < date_emission:
        issues.append({
            "champ": "date_echeance",
            "gravite": "erreur",
            "message": "La date d'échéance est antérieure à la date d'émission.",
        })
    if not date_emission:
        issues.append({
            "champ": "date_emission",
            "gravite": "erreur",
            "message": "Date d'émission manquante ou mal formatée.",
        })

    # --- Mentions obligatoires réforme facturation électronique 2026 ---
    if not _est_siren_valide(data.get("fournisseur_siren", "")):
        issues.append({
            "champ": "fournisseur_siren",
            "gravite": "avertissement",
            "message": "SIREN fournisseur absent ou invalide (doit faire 9 chiffres).",
        })
    if not _est_siren_valide(data.get("client_siren", "")):
        issues.append({
            "champ": "client_siren",
            "gravite": "avertissement",
            "message": "SIREN client absent ou invalide — obligatoire dès sept. 2026 "
                       "(réforme facturation électronique).",
        })
    if data.get("categorie_operation") in ("", None, "non_applicable"):
        issues.append({
            "champ": "categorie_operation",
            "gravite": "avertissement",
            "message": "Catégorie d'opération non détectée — mention obligatoire "
                       "dès sept. 2026.",
        })

    return issues


def validate_constat(data: dict) -> list[dict]:
    """Retourne une liste d'anomalies détectées sur un constat de sinistre."""
    issues = []

    if not data.get("numero_police"):
        issues.append({
            "champ": "numero_police",
            "gravite": "erreur",
            "message": "Numéro de police manquant.",
        })

    montant = data.get("montant_ttc", 0) or 0
    if montant <= 0:
        issues.append({
            "champ": "montant_ttc",
            "gravite": "erreur",
            "message": "Montant estimé des dommages manquant ou nul.",
        })

    if not _parse_date(data.get("date_emission", "")):
        issues.append({
            "champ": "date_emission",
            "gravite": "erreur",
            "message": "Date manquante ou mal formatée.",
        })

    return issues


def validate_document(data: dict) -> dict:
    """Point d'entrée principal : dispatche vers la bonne validation selon le type
    de document, et retourne un résumé exploitable par l'UI Streamlit."""
    type_doc = data.get("type_document", "")

    if type_doc == "facture":
        issues = validate_facture(data)
    elif type_doc == "constat_sinistre":
        issues = validate_constat(data)
    else:
        issues = [{
            "champ": "type_document",
            "gravite": "avertissement",
            "message": f"Type de document non reconnu : '{type_doc}'.",
        }]

    nb_erreurs = sum(1 for i in issues if i["gravite"] == "erreur")
    statut = "invalide" if nb_erreurs > 0 else ("attention" if issues else "valide")

    return {
        "statut": statut,  # "valide" | "attention" | "invalide"
        "nb_erreurs": nb_erreurs,
        "nb_avertissements": sum(1 for i in issues if i["gravite"] == "avertissement"),
        "anomalies": issues,
    }


if __name__ == "__main__":
    # Test rapide avec les résultats réels obtenus sur facture_01.pdf et constat_01.pdf
    facture_test = {
        "type_document": "facture",
        "fournisseur_nom": "Laurent et Fils",
        "fournisseur_siren": "104332181",
        "client_nom": "Rey Bodin S.A.S.",
        "client_siren": "",
        "date_emission": "2026-05-10",
        "date_echeance": "2026-06-09",
        "categorie_operation": "mixte",
        "montant_ht": 7030.0,
        "montant_tva": 1406.0,
        "montant_ttc": 8436.0,
    }
    print("--- Facture ---")
    print(validate_document(facture_test))

    constat_test = {
        "type_document": "constat_sinistre",
        "numero_police": "POL-273061",
        "date_emission": "2026-07-04",
        "montant_ttc": 9479.28,
    }
    print("--- Constat ---")
    print(validate_document(constat_test))