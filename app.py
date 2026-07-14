"""
Interface Streamlit — Agent d'extraction de documents (factures / constats).

Dépose un ou plusieurs PDF -> extraction via Claude -> validation automatique
-> tableau des résultats -> export CSV.
"""

import os
import tempfile

import pandas as pd
import streamlit as st

from extractor import extract_fields
from validator import validate_document
from facturx_export import build_cii_xml

st.set_page_config(page_title="Agent d'extraction de documents", page_icon="📄", layout="wide")

STATUT_BADGE = {
    "valide": "🟢 Conforme",
    "attention": "🟠 À vérifier",
    "invalide": "🔴 Non conforme",
}

st.title("📄 Agent d'extraction de documents")
st.caption(
    "Dépose des factures ou constats de sinistre en PDF — extraction structurée "
    "via l'API Claude, avec validation automatique (montants, SIREN, mentions "
    "obligatoires réforme facturation électronique 2026)."
)

uploaded_files = st.file_uploader(
    "Dépose un ou plusieurs PDF",
    type=["pdf"],
    accept_multiple_files=True,
)

if "resultats" not in st.session_state:
    st.session_state.resultats = []

if uploaded_files:
    if st.button(f"Lancer l'extraction ({len(uploaded_files)} fichier(s))", type="primary"):
        st.session_state.resultats = []
        progress = st.progress(0.0, text="Démarrage...")

        for i, uploaded_file in enumerate(uploaded_files):
            progress.progress(
                i / len(uploaded_files),
                text=f"Extraction de {uploaded_file.name}...",
            )

            # Streamlit fournit un fichier en mémoire ; extractor.py attend un chemin
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                extraction = extract_fields(tmp_path)
                extraction["_fichier_source"] = uploaded_file.name
                validation = validate_document(extraction)
                st.session_state.resultats.append({
                    "extraction": extraction,
                    "validation": validation,
                    "erreur": None,
                })
            except Exception as e:
                st.session_state.resultats.append({
                    "extraction": None,
                    "validation": None,
                    "erreur": str(e),
                    "fichier": uploaded_file.name,
                })
            finally:
                os.unlink(tmp_path)

        progress.progress(1.0, text="Terminé.")
        progress.empty()

# --- Affichage des résultats ---
if st.session_state.resultats:
    resultats = st.session_state.resultats
    n_ok = sum(1 for r in resultats if r["erreur"] is None)
    n_erreur = len(resultats) - n_ok

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents traités", len(resultats))
    col2.metric("Extraits avec succès", n_ok)
    col3.metric("Échecs d'extraction", n_erreur, delta_color="inverse")

    st.divider()

    # --- Tableau récapitulatif ---
    lignes_tableau = []
    for r in resultats:
        if r["erreur"]:
            lignes_tableau.append({
                "Fichier": r["fichier"],
                "Statut": "❌ Erreur",
                "Type": "-",
                "Montant TTC": "-",
                "Détail": r["erreur"],
            })
        else:
            ext = r["extraction"]
            val = r["validation"]
            lignes_tableau.append({
                "Fichier": ext.get("_fichier_source", ""),
                "Statut": STATUT_BADGE.get(val["statut"], val["statut"]),
                "Type": ext.get("type_document", ""),
                "Montant TTC": f"{ext.get('montant_ttc', 0):,.2f} EUR",
                "Détail": f"{val['nb_erreurs']} erreur(s), {val['nb_avertissements']} avertissement(s)",
            })

    df_tableau = pd.DataFrame(lignes_tableau)
    st.dataframe(df_tableau, use_container_width=True, hide_index=True)

    # --- Détail par document ---
    st.subheader("Détail par document")
    for r in resultats:
        if r["erreur"]:
            with st.expander(f"❌ {r['fichier']} — échec d'extraction"):
                st.error(r["erreur"])
            continue

        ext = r["extraction"]
        val = r["validation"]
        label = f"{STATUT_BADGE.get(val['statut'])} — {ext.get('_fichier_source')}"

        with st.expander(label):
            colA, colB = st.columns([2, 1])

            with colA:
                st.json(ext, expanded=False)

            with colB:
                if val["anomalies"]:
                    st.markdown("**Anomalies détectées :**")
                    for anomalie in val["anomalies"]:
                        icone = "🔴" if anomalie["gravite"] == "erreur" else "🟠"
                        st.markdown(f"{icone} `{anomalie['champ']}` — {anomalie['message']}")
                else:
                    st.success("Aucune anomalie détectée.")

                if ext.get("type_document") == "facture":
                    try:
                        xml_bytes = build_cii_xml(ext)
                        nom_xml = ext.get("numero_document", "facture") + "_facturx.xml"
                        st.download_button(
                            "📤 Export Factur-X (XML)",
                            data=xml_bytes,
                            file_name=nom_xml,
                            mime="application/xml",
                            key=f"facturx_{ext.get('_fichier_source')}",
                            help="Export CII simplifié — préparation à la réforme "
                                 "facturation électronique 2026/2027.",
                        )
                    except Exception as e:
                        st.caption(f"Export Factur-X indisponible : {e}")

    # --- Export CSV ---
    st.divider()
    lignes_export = []
    for r in resultats:
        if r["erreur"]:
            continue
        ligne = {k: v for k, v in r["extraction"].items() if k != "lignes"}
        ligne["statut_validation"] = r["validation"]["statut"]
        ligne["nb_erreurs"] = r["validation"]["nb_erreurs"]
        ligne["nb_avertissements"] = r["validation"]["nb_avertissements"]
        lignes_export.append(ligne)

    if lignes_export:
        df_export = pd.DataFrame(lignes_export)
        csv = df_export.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Exporter en CSV",
            data=csv,
            file_name="extraction_resultats.csv",
            mime="text/csv",
        )
else:
    st.info("Dépose un ou plusieurs fichiers PDF ci-dessus pour commencer.")