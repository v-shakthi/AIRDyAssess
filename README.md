# 🧠 AI Readiness & Migration Advisor

> Upload your enterprise documents and receive a **structured AI readiness assessment** — scored across 6 dimensions, with ranked use case candidates, a phased adoption roadmap, and an exportable PDF report. Powered by Claude and LlamaIndex-style RAG.

This project demonstrates how to codify a Solution Architect's consulting methodology as an AI-powered tool — transforming hours of manual analysis into a structured, evidence-based assessment in minutes.

---

## 🏗️ Architecture

```
Enterprise Documents (PDF, DOCX, TXT)
              │
              ▼
┌─────────────────────────────────┐
│      Ingestion Pipeline         │
│  Extract → Clean → Chunk        │
│  → Embed → ChromaDB (per session│
└──────────────┬──────────────────┘
               │  RAG retrieval per dimension
               ▼
┌─────────────────────────────────────────────────────────┐
│              Assessment Engine (Claude)                  │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │
│  │ Dimension  │  │ Use Case   │  │ Executive Synthesis │ │
│  │ Scorer ×6  │  │ Identifier │  │ + Blocker Analysis  │ │
│  └────────────┘  └────────────┘  └────────────────────┘ │
│                       │                                  │
│              ┌─────────▼──────────┐                      │
│              │  Roadmap Builder   │                      │
│              └────────────────────┘                      │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │ Report Generator │
              │  PDF + JSON      │
              └────────┬────────┘
                  ┌────┴────┐
             FastAPI      Streamlit
              REST API    Dashboard
```

---

## ✨ What It Produces

### 6-Dimension Scored Assessment
Each dimension scored 0–10 with maturity label, evidence-backed strengths, gaps, and recommendations:

| Dimension | What's evaluated |
|---|---|
| **Data Readiness** | Data quality, governance, pipelines, catalogues |
| **Technology Infrastructure** | Cloud adoption, MLOps, API maturity, compute |
| **Talent & Skills** | Data scientists, ML engineers, AI literacy |
| **Process & Automation Maturity** | RPA, workflow digitisation, process redesign appetite |
| **Governance & Risk** | AI policy, model risk, compliance, bias monitoring |
| **Strategy & Leadership** | Executive sponsorship, budget, vision clarity |

### Use Case Candidates
Top 5 AI use cases ranked by ROI × feasibility, with AI approach (RAG, Agentic, Predictive, etc.) and prerequisites.

### Phased Adoption Roadmap
3-phase roadmap calibrated to the organisation's maturity — a Nascent org gets a longer foundation phase than an Advanced one.

### Exportable Reports
- **PDF**: Professional multi-page report with score bars, tables, and roadmap
- **JSON**: Full structured output for integration into other systems

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/your-username/ai-readiness-advisor
cd ai-readiness-advisor

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY
```

### 3. Start the API

```bash
python main.py
# Running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 4. Start the dashboard

```bash
streamlit run dashboard/app.py
# Dashboard at http://localhost:8501
```

### 5. Try a demo assessment

Upload the included sample document via the dashboard, or via curl:

```bash
curl -X POST http://localhost:8000/v1/assessment/upload \
  -H "X-API-Key: sk-advisor-demo-001" \
  -F "files=@sample_docs/acme_architecture_overview.txt" \
  -F "organisation_name=Acme Corporation" \
  -F "additional_context=Mid-size financial services firm exploring AI adoption"
```

Then poll for results:
```bash
curl http://localhost:8000/v1/assessment/{session_id} \
  -H "X-API-Key: sk-advisor-demo-001"
```

### 6. Run tests (no API key needed)

```bash
pytest tests/ -v
```

---

## 📁 Project Structure

```
ai-readiness-advisor/
│
├── main.py                        # API server entrypoint
├── config.py                      # Settings (env-driven)
├── models.py                      # All Pydantic schemas + maturity levels
├── requirements.txt
├── .env.example
│
├── ingestion/
│   └── pipeline.py                # PDF/DOCX/TXT extraction, chunking, ChromaDB
│
├── assessment/
│   └── engine.py                  # Claude-powered 4-step assessment orchestrator
│
├── reporting/
│   └── pdf_generator.py           # ReportLab PDF with cover, radar, tables, roadmap
│
├── api/
│   └── app.py                     # FastAPI REST API (upload, poll, download)
│
├── dashboard/
│   └── app.py                     # Streamlit UI (upload → progress → results)
│
├── sample_docs/
│   └── acme_architecture_overview.txt   # Realistic demo document
│
└── tests/
    └── test_advisor.py            # Unit tests (no live API needed)
```

---

## 📡 API Reference

### `POST /v1/assessment/upload`
Upload documents and start an assessment. Returns a `session_id` immediately — assessment runs asynchronously.

**Form fields:**
- `files`: One or more files (PDF, DOCX, TXT, MD)
- `organisation_name`: Name of the enterprise being assessed
- `additional_context`: Optional free-text context (industry, size, goals)

### `GET /v1/assessment/{session_id}`
Poll assessment status. Returns `status` (processing/complete/error), `progress_pct`, and `current_step`.

### `GET /v1/assessment/{session_id}/json`
Download full assessment report as JSON.

### `GET /v1/assessment/{session_id}/pdf`
Download PDF report.

---

## 🧠 Assessment Methodology

The scoring rubric is grounded in industry frameworks:
- **McKinsey AI Maturity Model**
- **Gartner AI Readiness Framework**
- **MIT CISR Digital Business Model**
- **NIST AI Risk Management Framework** (for Governance dimension)

Each dimension is assessed independently using RAG — only evidence found in the uploaded documents is used. Where evidence is sparse, the engine scores conservatively and explicitly flags the gap.

---

## 🏢 Extending for Enterprise Use

| Component | POC | Production |
|---|---|---|
| Document sources | File upload | SharePoint API, Confluence, S3, Google Drive |
| Vector store | ChromaDB (local) | Pinecone, pgvector, Azure AI Search |
| Auth | Single API key | OAuth2 / Azure AD |
| Report storage | Local filesystem | S3 / Azure Blob |
| Assessment history | In-memory | PostgreSQL |
| Concurrent sessions | Thread pool | Celery + Redis |

---

## 🗺️ Roadmap

- [ ] Add **Streamlit file preview** before submission
- [ ] **Comparative assessment** — compare two organisations or time periods
- [ ] **Sector-specific rubrics** (Financial Services, Healthcare, Manufacturing)
- [ ] **PowerPoint export** of the roadmap
- [ ] **Slack/Teams notification** when assessment completes
- [ ] **Assessment history** with trend tracking over time

---

*Built as a portfolio project demonstrating enterprise AI adoption advisory patterns.*
