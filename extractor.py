"""
Agent d'extraction de documents (factures / constats de sinistre) via l'API Claude.

Lit le texte d'un PDF, l'envoie à Claude avec un schéma structuré (tool use),
et retourne un dictionnaire Python avec les champs extraits.
"""

import os
import json

import pdfplumber
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-5"  # rapport qualité/prix solide pour de l'extraction

# --- Schéma de sortie attendu (aligné sur la réforme facturation électronique 2026) ---
EXTRACTION_TOOL = {
    "name": "enregistrer_extraction",
    "description": "Enregistre les champs structurés extraits d'une facture ou d'un constat de sinistre.",
    "input_schema": {
        "type": "object",
        "properties": {
            "type_document": {
                "type": "string",
                "enum": ["facture", "constat_sinistre", "autre"],
            },
            "fournisseur_nom": {"type": "string"},
            "fournisseur_siren": {"type": "string", "description": "9 chiffres, vide si absent du document"},
            "client_nom": {"type": "string"},
            "client_siren": {"type": "string", "description": "9 chiffres, vide si absent du document"},
            "adresse_livraison": {"type": "string", "description": "vide si identique à l'adresse de facturation"},
            "numero_document": {"type": "string", "description": "numéro de facture ou de sinistre"},
            "numero_police": {"type": "string", "description": "uniquement pour les constats de sinistre"},
            "date_emission": {"type": "string", "description": "format YYYY-MM-DD"},
            "date_echeance": {"type": "string", "description": "format YYYY-MM-DD, vide si non applicable"},
            "categorie_operation": {
                "type": "string",
                "enum": ["livraison_biens", "prestation_services", "mixte", "non_applicable"],
            },
            "tva_sur_debits": {"type": "boolean"},
            "montant_ht": {"type": "number"},
            "montant_tva": {"type": "number"},
            "montant_ttc": {"type": "number"},
            "lignes": {
                "type": "array",
                "description": "lignes de facture, vide pour un constat de sinistre",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantite": {"type": "number"},
                        "prix_unitaire": {"type": "number"},
                    },
                },
            },
        },
        "required": [
            "type_document", "fournisseur_nom", "client_nom",
            "numero_document", "date_emission", "montant_ttc",
        ],
    },
}

SYSTEM_PROMPT = """Tu es un agent d'extraction de documents spécialisé dans les factures \
et les constats de sinistre en France. Extrait uniquement les informations présentes \
dans le texte fourni. Si un champ est absent du document, laisse-le vide ("" pour le \
texte, 0 pour les nombres) plutôt que d'inventer une valeur. N'invente jamais de SIREN, \
de montant ou de date qui ne figure pas explicitement dans le texte."""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrait le texte brut d'un PDF en préservant la mise en page (colonnes).
    Important pour les documents à deux colonnes (fournisseur / client) où une
    extraction "à plat" pourrait mélanger les champs des deux blocs."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(layout=True)
            if page_text:
                text += page_text + "\n"
    return text


def extract_fields(pdf_path: str) -> dict:
    """Envoie le texte du PDF à Claude et retourne les champs extraits sous forme de dict."""
    document_text = extract_text_from_pdf(pdf_path)

    if not document_text.strip():
        raise ValueError(f"Aucun texte extractible dans {pdf_path} (PDF scanné ? OCR requis)")

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        thinking={"type": "disabled"},  # extraction simple, pas besoin de raisonnement
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "enregistrer_extraction"},
        messages=[
            {
                "role": "user",
                "content": f"Voici le texte extrait d'un document PDF :\n\n{document_text}",
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "enregistrer_extraction":
            result = block.input
            result["_fichier_source"] = os.path.basename(pdf_path)
            return result

    raise RuntimeError("Claude n'a pas retourné de résultat structuré (tool_use manquant).")


if __name__ == "__main__":
    # Test rapide sur un seul fichier
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <chemin_vers_pdf>")
        sys.exit(1)

    result = extract_fields(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))