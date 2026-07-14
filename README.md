# AI Document Extraction Agent

Extract structured data from invoices and insurance claim documents (PDF) using Claude's API — with automatic validation and a bridge toward France's 2026 e-invoicing mandate.

![Status](https://img.shields.io/badge/status-MVP-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## The problem

Companies in manufacturing, energy, and insurance still process invoices and claims manually — copying amounts, dates, and reference numbers from PDFs into spreadsheets or ERPs one field at a time. It's slow, error-prone, and about to become a compliance issue: starting September 2026, French businesses must be able to handle structured e-invoicing formats, yet most incoming documents will remain unstructured PDFs for years during the transition.

## What this does

1. **Upload** one or more PDF invoices or insurance claims through a Streamlit interface
2. **Extract** structured fields (amounts, dates, SIREN numbers, line items, policy numbers...) via Claude's API using forced structured output — not free-text parsing
3. **Validate** the extraction with deterministic rules (amount consistency, date logic, missing mandatory fields) — the LLM's output is never trusted blindly
4. **Export** results as CSV, or as a Factur-X-style XML (Cross Industry Invoice format) for invoices — a bridge toward France's structured e-invoicing requirement

## Demo

*(90-second video walkthrough: [link to your Loom])*

![Screenshot placeholder](docs/screenshot.png)

## Why this isn't just "call an LLM and hope"

- **Forced structured output** — the extraction schema is enforced via Claude's tool-use API, not parsed from free-text, which eliminates a whole class of formatting errors.
- **Layout-aware PDF parsing** — two-column invoice layouts (supplier info left, client info right) can confuse naive text extraction and cause fields to be misattributed. This was caught during testing and fixed with layout-aware extraction rather than papering over it in the prompt.
- **A validation layer that doesn't use the LLM** — SIREN format, amount totals (HT + VAT = TTC), and date logic are checked with plain Python rules. If the model gets something wrong, the validator catches it instead of silently trusting the output.
- **No hallucinated fields** — the system prompt explicitly instructs the model to leave a field empty rather than invent a plausible-looking value, which matters a lot more for a SIREN number or an invoice amount than it does for a chatbot answer.

## Tech stack

| Component | Choice | Why |
|---|---|---|
| Extraction | Anthropic Claude API (tool use) | Reliable structured output via forced schema |
| PDF parsing | `pdfplumber` (layout-aware) | Handles multi-column invoice layouts correctly |
| Interface | Streamlit | Fast to build, good enough for internal tooling / demos |
| Validation | Plain Python (no LLM) | Deterministic checks the model can't talk its way around |
| Test data | `reportlab` + `faker` | 30 synthetic invoices/claims, no real data used |

## Project structure

```
ai-document-extraction-agent/
├── app.py                  # Streamlit interface
├── extractor.py             # PDF text extraction + Claude API call
├── validator.py              # Rule-based validation (no LLM)
├── facturx_export.py         # Factur-X-style CII XML export
├── generate_test_data.py     # Synthetic test document generator
├── data/sample_docs/         # Generated test PDFs
├── requirements.txt
└── .env.example
```

## Setup

```bash
git clone https://github.com/anass1h/ai-document-extraction-agent.git
cd ai-document-extraction-agent
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env  # then add your ANTHROPIC_API_KEY
```

Get an API key at [console.anthropic.com](https://console.anthropic.com).

## Usage

**Generate test documents** (optional — sample PDFs are already included):
```bash
python generate_test_data.py
```

**Run the app:**
```bash
streamlit run app.py
```

**Or test extraction from the command line:**
```bash
python extractor.py data/sample_docs/facture_01.pdf
```

## A note on the Factur-X export

The XML export follows the real Cross Industry Invoice (CII) structure and namespaces used by Factur-X, and covers the four fields France's 2026 reform makes mandatory (supplier/client SIREN, delivery address, operation category, VAT-on-debits option). It's built as a proof-of-concept bridge, not a certified EN16931 output — a production deployment submitting to an official *Plateforme Agréée* would need full XSD/Schematron validation via the official `factur-x` library.

## Data & privacy

All sample documents in `data/sample_docs/` are synthetically generated (`generate_test_data.py`, seeded for reproducibility). No real client, company, or personal data is used anywhere in this repository.

## Roadmap / possible extensions

- OCR fallback for scanned (non-text) PDFs
- Batch processing via CLI for larger volumes
- Confidence scores per extracted field
- Full EN16931 validation via the official `factur-x` library

## About

Built by Anass — freelance AI/automation developer with a background spanning manufacturing, energy, and insurance (SMABTP). Available for document processing, extraction pipelines, and LLM-powered automation on Upwork.