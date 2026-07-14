"""
Génère de faux documents PDF (factures + constats de sinistre) pour tester
l'agent d'extraction. Aucune donnée réelle — tout est généré aléatoirement.

Usage:
    python generate_test_data.py

Sortie: PDF dans data/sample_docs/
"""

import os
import random
from datetime import datetime, timedelta

from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

fake = Faker("fr_FR")
Faker.seed(42)
random.seed(42)

OUTPUT_DIR = "data/sample_docs"
N_FACTURES = 18
N_CONSTATS = 12

CATEGORIES_OPERATION = ["livraison_biens", "prestation_services", "mixte"]
PRODUITS = [
    ("Prestation de conseil", 450.0),
    ("Licence logicielle annuelle", 1200.0),
    ("Maintenance serveur", 300.0),
    ("Fourniture de matériel industriel", 2800.0),
    ("Formation équipe technique", 950.0),
    ("Développement application sur mesure", 4500.0),
    ("Audit énergétique", 1600.0),
    ("Location matériel de chantier", 780.0),
]


def fake_siren():
    """Génère un faux SIREN valide en format (9 chiffres)."""
    return "".join(str(random.randint(0, 9)) for _ in range(9))


def maybe_missing(value, missing_rate=0.15):
    """Simule des documents imparfaits : un champ manquant de temps en temps.
    Utile pour tester le validator plus tard (détection de mentions absentes)."""
    return "" if random.random() < missing_rate else value


def draw_wrapped_text(c, text, x, y, max_width, font="Helvetica", size=9, leading=12):
    """Dessine du texte avec retour à la ligne simple."""
    c.setFont(font, size)
    words = text.split()
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if c.stringWidth(test_line, font, size) > max_width:
            c.drawString(x, y, line)
            y -= leading
            line = word
        else:
            line = test_line
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def generate_facture(filepath, index):
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    fournisseur_nom = fake.company()
    fournisseur_siren = fake_siren()
    fournisseur_adresse = fake.address().replace("\n", ", ")

    client_nom = fake.company()
    client_siren = maybe_missing(fake_siren())
    client_adresse_fact = fake.address().replace("\n", ", ")
    livraison_diff = random.random() < 0.3
    client_adresse_livraison = fake.address().replace("\n", ", ") if livraison_diff else ""

    numero_facture = f"FAC-{2026}-{1000 + index}"
    date_emission = fake.date_between(start_date="-90d", end_date="today")
    date_echeance = date_emission + timedelta(days=30)
    categorie = random.choice(CATEGORIES_OPERATION)
    tva_debits = random.random() < 0.2

    n_lignes = random.randint(1, 4)
    lignes = random.sample(PRODUITS, n_lignes)

    # --- En-tête ---
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, fournisseur_nom)
    y -= 8 * mm
    c.setFont("Helvetica", 9)
    y = draw_wrapped_text(c, fournisseur_adresse, 20 * mm, y, 80 * mm)
    c.drawString(20 * mm, y, f"SIREN : {fournisseur_siren}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, y, f"FACTURE N° {numero_facture}")
    y -= 8 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"Date d'émission : {date_emission.strftime('%d/%m/%Y')}")
    y -= 5 * mm
    c.drawString(20 * mm, y, f"Date d'échéance : {date_echeance.strftime('%d/%m/%Y')}")
    y -= 5 * mm
    cat_label = {
        "livraison_biens": "Livraison de biens",
        "prestation_services": "Prestation de services",
        "mixte": "Livraison de biens et prestation de services",
    }[categorie]
    c.drawString(20 * mm, y, f"Catégorie d'opération : {cat_label}")
    y -= 5 * mm
    if tva_debits:
        c.drawString(20 * mm, y, "TVA acquittée sur les débits")
        y -= 5 * mm
    y -= 5 * mm

    # --- Client ---
    c.setFont("Helvetica-Bold", 10)
    c.drawString(120 * mm, height - 25 * mm, "Facturé à :")
    c.setFont("Helvetica", 9)
    yc = height - 30 * mm
    c.drawString(120 * mm, yc, client_nom)
    yc -= 5 * mm
    yc = draw_wrapped_text(c, client_adresse_fact, 120 * mm, yc, 70 * mm)
    if client_siren:
        c.drawString(120 * mm, yc, f"SIREN : {client_siren}")
        yc -= 5 * mm
    if livraison_diff:
        c.drawString(120 * mm, yc, "Adresse de livraison :")
        yc -= 5 * mm
        yc = draw_wrapped_text(c, client_adresse_livraison, 120 * mm, yc, 70 * mm)

    y -= 5 * mm

    # --- Tableau des lignes ---
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y, "Description")
    c.drawString(120 * mm, y, "Qté")
    c.drawString(140 * mm, y, "PU HT")
    c.drawString(165 * mm, y, "TVA")
    y -= 3 * mm
    c.line(20 * mm, y, 190 * mm, y)
    y -= 6 * mm

    montant_ht = 0.0
    c.setFont("Helvetica", 9)
    for desc, prix in lignes:
        qte = random.randint(1, 3)
        total_ligne = prix * qte
        montant_ht += total_ligne
        c.drawString(20 * mm, y, desc)
        c.drawString(120 * mm, y, str(qte))
        c.drawString(140 * mm, y, f"{prix:,.2f} EUR")
        c.drawString(165 * mm, y, "20%")
        y -= 6 * mm

    taux_tva = 0.20
    montant_tva = round(montant_ht * taux_tva, 2)
    montant_ttc = round(montant_ht + montant_tva, 2)

    y -= 5 * mm
    c.line(120 * mm, y, 190 * mm, y)
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(120 * mm, y, "Total HT :")
    c.drawString(160 * mm, y, f"{montant_ht:,.2f} EUR")
    y -= 6 * mm
    c.drawString(120 * mm, y, "Total TVA (20%) :")
    c.drawString(160 * mm, y, f"{montant_tva:,.2f} EUR")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(120 * mm, y, "Total TTC :")
    c.drawString(160 * mm, y, f"{montant_ttc:,.2f} EUR")

    c.showPage()
    c.save()


def generate_constat(filepath, index):
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    numero_police = f"POL-{fake.random_int(min=100000, max=999999)}"
    numero_sinistre = f"SIN-{2026}-{2000 + index}"
    date_sinistre = fake.date_between(start_date="-60d", end_date="today")
    date_declaration = date_sinistre + timedelta(days=random.randint(0, 5))

    assure_nom = fake.name()
    assure_adresse = fake.address().replace("\n", ", ")

    types_sinistre = [
        "Dégât des eaux", "Incendie", "Bris de glace",
        "Vol avec effraction", "Catastrophe naturelle", "Choc / collision",
    ]
    type_sinistre = random.choice(types_sinistre)
    montant_estime = round(random.uniform(500, 15000), 2)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, y, "CONSTAT DE SINISTRE")
    y -= 12 * mm

    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, f"N° de sinistre : {numero_sinistre}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"N° de police : {numero_police}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Date du sinistre : {date_sinistre.strftime('%d/%m/%Y')}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Date de déclaration : {date_declaration.strftime('%d/%m/%Y')}")
    y -= 10 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Assuré")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, assure_nom)
    y -= 5 * mm
    y = draw_wrapped_text(c, assure_adresse, 20 * mm, y, 160 * mm)
    y -= 8 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Nature du sinistre")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, y, type_sinistre)
    y -= 8 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Description des dommages")
    y -= 6 * mm
    y = draw_wrapped_text(c, fake.paragraph(nb_sentences=3), 20 * mm, y, 160 * mm)
    y -= 8 * mm

    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Montant estimé des dommages")
    y -= 6 * mm
    c.setFont("Helvetica", 11)
    c.drawString(20 * mm, y, f"{montant_estime:,.2f} EUR")

    c.showPage()
    c.save()


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for i in range(N_FACTURES):
        filepath = os.path.join(OUTPUT_DIR, f"facture_{i+1:02d}.pdf")
        generate_facture(filepath, i)

    for i in range(N_CONSTATS):
        filepath = os.path.join(OUTPUT_DIR, f"constat_{i+1:02d}.pdf")
        generate_constat(filepath, i)

    print(f"{N_FACTURES} factures et {N_CONSTATS} constats générés dans {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()