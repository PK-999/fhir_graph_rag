# FHIRGraph

**FHIRGraph** is a comprehensive, open-source healthcare knowledge graph platform that transforms synthetic FHIR R4 clinical data into an interactive Neo4j graph and a relational metadata store.

## Architecture

FHIRGraph is composed of several independent components orchestrated together:
- **Synthetic Generator**: A deterministic Python engine generating longitudinal FHIR R4 bundles (Patients, Encounters, Conditions, Medications, etc.).
- **Graph Transformer**: Converts nested FHIR JSON into a flattened canonical graph model (`Nodes` and `Edges`).
- **Neo4j Graph Database**: Stores the clinical relationships (e.g., `Patient -> HAS_SUBJECT -> Condition`).
- **PostgreSQL Metadata**: Tracks pipeline lineage, data quality rules, and ingestion run provenance.
- **FastAPI Backend**: A high-performance async API wrapping the databases, providing REST endpoints, Cypher generation, and AI intent classification.
- **Next.js Frontend**: A modern, responsive React UI featuring a Dashboard, Patient 360, Cytoscape.js Graph Explorer, Cohort Builder, and an AI Assistant.

## Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)
- Node.js 18+ (for local UI development)

## Quick Start (Docker)

1. **Start the Infrastructure**
   ```bash
   make infra
   ```
   *This starts Neo4j (7687) and PostgreSQL (5432).*

2. **Run the Full Pipeline Orchestration**
   This single command generates the synthetic data, loads it into HAPI FHIR (if configured) and Neo4j, and performs reconciliation.
   ```bash
   source .venv/bin/activate
   python -m pipelines.run_all
   ```

3. **Start the Backend API**
   ```bash
   cd apps/api
   uvicorn app.main:app --reload --port 8000
   ```

4. **Start the Frontend Application**
   ```bash
   cd apps/web
   npm run dev
   ```
   Navigate to `http://localhost:3000`.

---

## The Flagship Demonstration

Follow these 8 steps to explore the capabilities of FHIRGraph:

1. **Dashboard**: Open `http://localhost:3000` to see the dataset overview and graph topology metrics.
2. **Patient Registry**: Click **Patients** in the sidebar to view the synthetic cohort.
3. **Patient 360**: Click **View 360** on any patient to see their demographics and longitudinal timeline summary.
4. **Graph Integration**: Inside Patient 360, navigate to the **Graph View** tab and launch the Explorer.
5. **Graph Explorer**: In the Explorer, you will see the patient node and its first-degree connections (Encounters, Conditions). Adjust the depth slider to 2 or 3 to traverse deeper semantic relationships.
6. **Cohort Builder**: Click **Cohorts**, enter a SNOMED code (e.g. `44054006` for Diabetes), and execute the query to dynamically find matching populations.
7. **Lineage**: Click **Lineage** to trace how high-level business terms (like "Birth Date") map to the underlying FHIR schema (`Patient.birthDate`).
8. **AI Assistant**: Click **AI Assistant** and type exactly: 
   > *"Show diabetic patients whose latest HbA1c is above 8 and who have an active Metformin prescription"*
   
   The assistant will classify the intent, generate a safe Cypher query, return the patient counts, and display clickable **Evidence Cards** directly linking to the relevant patient records.

---

## Observability

The API is fully instrumented:
- **Metrics**: Available at `http://localhost:8000/metrics` (Prometheus format).
- **Tracing**: OpenTelemetry is configured for the FastAPI app.
- **Logging**: Structured JSON logging is enabled via `structlog`.
