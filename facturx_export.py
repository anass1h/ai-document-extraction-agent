"""
Génère un export XML au format Cross Industry Invoice (CII) — la structure
XML utilisée par Factur-X — à partir des champs extraits par extractor.py.

Objectif : montrer le pont entre "PDF non structuré" et "format attendu par
une Plateforme Agréée" dans le cadre de la réforme facturation électronique
2026/2027. Ce module produit un XML au profil simplifié (proche du profil
MINIMUM/BASIC de Factur-X) — utile comme preuve de concept et comme base de
travail, mais une certification EN16931 complète nécessiterait la librairie
officielle `factur-x` avec validation XSD/Schematron avant tout usage en
production réelle avec une Plateforme Agréée.
"""

from xml.etree import ElementTree as ET
from xml.dom import minidom

NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def _q(prefix: str, tag: str) -> str:
    return f"{{{NS[prefix]}}}{tag}"


def _date_cii(date_str: str) -> str:
    """Convertit YYYY-MM-DD (sortie extractor.py) vers le format CII AAAAMMJJ."""
    if not date_str or len(date_str) != 10:
        return ""
    return date_str.replace("-", "")


def build_cii_xml(data: dict) -> bytes:
    """Construit le XML CII à partir d'un dict issu de extractor.extract_fields().
    Ne s'applique qu'aux documents de type 'facture' (le format Factur-X est
    spécifique à la facturation, pas aux constats de sinistre)."""
    if data.get("type_document") != "facture":
        raise ValueError("L'export Factur-X ne s'applique qu'aux factures.")

    root = ET.Element(_q("rsm", "CrossIndustryInvoice"))

    # --- Contexte / profil ---
    context = ET.SubElement(root, _q("rsm", "ExchangedDocumentContext"))
    guideline = ET.SubElement(context, _q("ram", "GuidelineSpecifiedDocumentContextParameter"))
    ET.SubElement(guideline, _q("ram", "ID")).text = (
        "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:minimum"
    )

    # --- En-tête du document ---
    doc = ET.SubElement(root, _q("rsm", "ExchangedDocument"))
    ET.SubElement(doc, _q("ram", "ID")).text = data.get("numero_document", "")
    ET.SubElement(doc, _q("ram", "TypeCode")).text = "380"  # 380 = facture commerciale
    issue_dt = ET.SubElement(doc, _q("ram", "IssueDateTime"))
    dt_string = ET.SubElement(issue_dt, _q("udt", "DateTimeString"))
    dt_string.set("format", "102")
    dt_string.text = _date_cii(data.get("date_emission", ""))

    # Mentions "catégorie d'opération" et "TVA sur les débits" (réforme 2026)
    # ajoutées en note légale — approche pragmatique tant que ces mentions
    # n'ont pas de BT dédié largement adopté par les Plateformes Agréées.
    if data.get("categorie_operation"):
        note = ET.SubElement(doc, _q("ram", "IncludedNote"))
        ET.SubElement(note, _q("ram", "Content")).text = (
            f"Catégorie d'opération : {data['categorie_operation']}"
        )
    if data.get("tva_sur_debits"):
        note = ET.SubElement(doc, _q("ram", "IncludedNote"))
        ET.SubElement(note, _q("ram", "Content")).text = "TVA acquittée sur les débits"

    # --- Transaction ---
    transaction = ET.SubElement(root, _q("rsm", "SupplyChainTradeTransaction"))

    # Lignes de facture (BG-25)
    for i, ligne in enumerate(data.get("lignes", []), start=1):
        item = ET.SubElement(transaction, _q("ram", "IncludedSupplyChainTradeLineItem"))
        line_doc = ET.SubElement(item, _q("ram", "AssociatedDocumentLineDocument"))
        ET.SubElement(line_doc, _q("ram", "LineID")).text = str(i)
        product = ET.SubElement(item, _q("ram", "SpecifiedTradeProduct"))
        ET.SubElement(product, _q("ram", "Name")).text = ligne.get("description", "")
        agreement = ET.SubElement(item, _q("ram", "SpecifiedLineTradeAgreement"))
        price = ET.SubElement(agreement, _q("ram", "NetPriceProductTradePrice"))
        ET.SubElement(price, _q("ram", "ChargeAmount")).text = str(ligne.get("prix_unitaire", 0))
        delivery = ET.SubElement(item, _q("ram", "SpecifiedLineTradeDelivery"))
        ET.SubElement(delivery, _q("ram", "BilledQuantity")).text = str(ligne.get("quantite", 0))

    # Vendeur / Acheteur (BG-4 / BG-7)
    agreement = ET.SubElement(transaction, _q("ram", "ApplicableHeaderTradeAgreement"))

    seller = ET.SubElement(agreement, _q("ram", "SellerTradeParty"))
    ET.SubElement(seller, _q("ram", "Name")).text = data.get("fournisseur_nom", "")
    if data.get("fournisseur_siren"):
        seller_org = ET.SubElement(seller, _q("ram", "SpecifiedLegalOrganization"))
        seller_id = ET.SubElement(seller_org, _q("ram", "ID"))
        seller_id.set("schemeID", "0002")  # 0002 = SIREN (référentiel INSEE)
        seller_id.text = data["fournisseur_siren"]

    buyer = ET.SubElement(agreement, _q("ram", "BuyerTradeParty"))
    ET.SubElement(buyer, _q("ram", "Name")).text = data.get("client_nom", "")
    if data.get("client_siren"):
        buyer_org = ET.SubElement(buyer, _q("ram", "SpecifiedLegalOrganization"))
        buyer_id = ET.SubElement(buyer_org, _q("ram", "ID"))
        buyer_id.set("schemeID", "0002")
        buyer_id.text = data["client_siren"]

    # Livraison (BG-15) — uniquement si adresse différente de facturation
    delivery_header = ET.SubElement(transaction, _q("ram", "ApplicableHeaderTradeDelivery"))
    if data.get("adresse_livraison"):
        ship_to = ET.SubElement(delivery_header, _q("ram", "ShipToTradeParty"))
        ET.SubElement(ship_to, _q("ram", "Name")).text = data.get("client_nom", "")
        address = ET.SubElement(ship_to, _q("ram", "PostalTradeAddress"))
        ET.SubElement(address, _q("ram", "LineOne")).text = data["adresse_livraison"]

    # Règlement / montants (BG-22)
    settlement = ET.SubElement(transaction, _q("ram", "ApplicableHeaderTradeSettlement"))
    ET.SubElement(settlement, _q("ram", "InvoiceCurrencyCode")).text = "EUR"

    if data.get("date_echeance"):
        payment_terms = ET.SubElement(settlement, _q("ram", "SpecifiedTradePaymentTerms"))
        due_dt = ET.SubElement(payment_terms, _q("ram", "DueDateDateTime"))
        due_string = ET.SubElement(due_dt, _q("udt", "DateTimeString"))
        due_string.set("format", "102")
        due_string.text = _date_cii(data["date_echeance"])

    summation = ET.SubElement(settlement, _q("ram", "SpecifiedTradeSettlementHeaderMonetarySummation"))
    ET.SubElement(summation, _q("ram", "TaxBasisTotalAmount")).text = str(data.get("montant_ht", 0))
    tax_total = ET.SubElement(summation, _q("ram", "TaxTotalAmount"))
    tax_total.set("currencyID", "EUR")
    tax_total.text = str(data.get("montant_tva", 0))
    ET.SubElement(summation, _q("ram", "GrandTotalAmount")).text = str(data.get("montant_ttc", 0))
    ET.SubElement(summation, _q("ram", "DuePayableAmount")).text = str(data.get("montant_ttc", 0))

    # --- Sérialisation avec indentation lisible ---
    raw = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="utf-8")
    return pretty


if __name__ == "__main__":
    facture_test = {
        "type_document": "facture",
        "fournisseur_nom": "Laurent et Fils",
        "fournisseur_siren": "104332181",
        "client_nom": "Rey Bodin S.A.S.",
        "client_siren": "",
        "adresse_livraison": "42, rue Éric Gillet, 13467 Texier",
        "numero_document": "FAC-2026-1000",
        "date_emission": "2026-05-10",
        "date_echeance": "2026-06-09",
        "categorie_operation": "mixte",
        "tva_sur_debits": False,
        "montant_ht": 7030.0,
        "montant_tva": 1406.0,
        "montant_ttc": 8436.0,
        "lignes": [
            {"description": "Fourniture de matériel industriel", "quantite": 1, "prix_unitaire": 2800.0},
        ],
    }
    xml_bytes = build_cii_xml(facture_test)
    print(xml_bytes.decode("utf-8"))