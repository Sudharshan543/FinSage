# FinSage – Agentic AI Accounts-Payable & Expense-Compliance Copilot

## 1. Project Overview

FinSage is an Agentic AI-powered finance assistant designed to support accounts-payable operations, employee expense compliance, invoice monitoring, and finance policy question answering.

The application uses SAP HANA Cloud as its primary database and vector retrieval engine. It combines a Python FastAPI backend, a Streamlit frontend, and Gemini embeddings for semantic policy search and Gemini text generation for grounded policy Q&A. Structured finance answers are assembled by FinSage from HANA data.

FinSage helps finance teams retrieve policy information, identify invoice compliance issues, review expense exceptions, and perform controlled finance actions.

## 2. Key Features

- **Finance Policy Q&A:** Answers finance and expense-policy questions using retrieved policy documents.
- **Evidence-Based Responses:** Provides source documents, chunk references, and effective dates. Similarity scores are shown only for semantic retrieval; lexical fallback is labeled separately.
- **Invoice Monitoring:** Displays invoice summaries and compliance risk information.
- **Invoice Triage:** Identifies duplicate invoices, missing purchase orders, and invoices above approved PO amounts. The stored schema has no separate PO currency, so amount comparisons assume the invoice currency.
- **Vendor Invoice History:** Summarizes invoice counts and totals by currency; contractual payment terms and a vendor-master workflow are not implemented.
- **Expense Compliance Screening:** Applies India/INR reference limits only when duration is recorded. Other regions/currencies and unsupported categories are reported as not verifiable; receipt status is submitter-reported, not document-verified.
- **Expense Exception Management:** Records expense exceptions for finance review.
- **Invoice Flagging:** Allows invoices to be flagged for compliance review.
- **Explicit Confirmation:** Requires confirmation before executing write operations.
- **Regional Filtering:** Separates finance policy retrieval by region.
- **Agent Tracing:** Generates trace IDs for agent requests.
- **Evaluation Framework:** Evaluates intent, evidence availability, expected keywords, and citation presence. It does not certify factual correctness.

## 3. Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | Streamlit |
| Database | SAP HANA Cloud |
| Vector Search | SAP HANA Cloud Vector Engine |
| Answer generation | Gemini for verified policy Q&A; FinSage logic for structured finance data |
| Embeddings | Gemini Embedding API |
| Database Connectivity | hdbcli |
| Authentication | SAP BTP XSUAA through SAP Application Router |
| Deployment Target | SAP BTP Cloud Foundry |
| API Documentation | FastAPI Swagger UI |

**AI service note:** Gemini embeddings are used for policy search when available, and Gemini generates policy answers from verified excerpts. If embedding retrieval falls back to keyword search, citations identify that method rather than presenting a synthetic similarity score. If Gemini generation fails, FinSage uses a currency-aware policy-text fallback and labels it in the frontend. Structured finance responses use FinSage logic and HANA data.
When a user asks for an average hotel market cost but the evidence only states a reimbursement cap, FinSage says that the average is not provided and identifies the cap as a policy limit, not an average.

## 4. Project Architecture

The application follows this high-level architecture:

1. User submits a finance question or action through Streamlit.
2. FastAPI receives and processes the request.
3. The agent identifies the request intent.
4. Relevant finance information is retrieved from SAP HANA Cloud.
5. Retrieved evidence is ranked and verified.
6. Gemini generates policy answers from verified excerpts; FinSage builds structured finance answers from HANA data.
7. Source citations and agent trace information are returned.
8. For write operations, explicit confirmation is required before database changes.

Architecture and runtime diagrams are maintained in [`design/`](../design/):
[solution architecture](../design/solution-architecture.md),
[HANA ER diagram](../design/hana-er-diagram.md), and
[agent flow](../design/agent-flow.md).

## 4.1 Individual-User Authentication Architecture

FinSage uses SAP Application Router as the browser entry point:

1. The user opens the public Application Router URL.
2. Application Router starts the SAP XSUAA login flow.
3. XSUAA issues an authorization-code token representing the individual SAP user.
4. Application Router forwards the bearer token to Streamlit. Streamlit sends it
   server-to-server to FastAPI's HTTPS route; the token is not exposed to browser code.
5. FastAPI validates the token with XSUAA, checks `grant_type`, and authorizes scopes.
6. Streamlit never stores or requests client secrets and never creates client-credentials tokens.

`deploy/xs-app.json` defines the Application Router's protected UI and API routes.
`deploy/manifest-frontend.yml` points Streamlit to the FastAPI HTTPS route, and
`deploy/manifest-approuter.yml` deploys the Application Router. The FastAPI middleware:

- returns HTTP 401 when the bearer token is missing or invalid;
- rejects `client_credentials` tokens for individual-user operations;
- allows read endpoints for `FinanceViewer`, `FinanceApprover`, or `FinanceAdmin`;
- allows write endpoints for `FinanceApprover` or `FinanceAdmin`;
- never trusts a role or user identity supplied in a request body.

## 5. Project Structure

```text
FinSage/
├── code/
│   ├── app/
│   │   ├── main.py
│   │   ├── agent.py
│   │   ├── models.py
│   │   ├── db.py
│   │   ├── ingestion.py
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── agent_tracing.py
│   │   ├── evaluation_runner.py
│   │   ├── auth.py
│   │   ├── tools/
│   │   │   ├── retriever.py
│   │   │   ├── keyword_retriever.py
│   │   │   ├── reranker.py
│   │   │   ├── verifier.py
│   │   │   ├── finance.py
│   │   │   ├── invoice.py
│   │   │   ├── invoice_triage.py
│   │   │   ├── exception.py
│   │   │   └── expense_compliance.py
│   │   ├── agent_router.py       # compatibility alias
│   │   └── __init__.py
│   ├── frontend/
│   │   └── streamlit_app.py
│   ├── data/
│   │   ├── documents/
│   │   └── demo_policies/
│   ├── tests/
│   ├── scripts/
│   ├── .streamlit/
│   ├── requirements.txt
│   ├── runtime.txt
│   ├── Procfile
│   └── .cfignore
├── db/
│   ├── schema.sql
│   └── migrations/
├── deploy/
│   ├── manifest.yml
│   ├── manifest-frontend.yml
│   ├── manifest-approuter.yml
│   ├── mta.yaml
│   ├── xs-security.json
│   ├── xs-app.json
│   ├── package.json
│   └── package-lock.json
├── design/
├── docs/
│   ├── README.md
│   └── SETUP.md
├── eval/
│   ├── evaluation_questions.json
│   └── evaluation_report*.json
├── demo/
├── presentation/
├── .gitignore
└── README.md
```

The root-level legacy import modules under `code/app/` re-export their
implementations from `code/app/tools/` so existing tests and callers continue
to work while new code uses the organized paths.

## 6. SAP HANA Cloud Database

FinSage uses SAP HANA Cloud for structured finance data and vector-based document retrieval.

The primary database tables are:

### FINSAGE_DOCUMENT_CHUNKS
Stores finance policy document chunks and their embeddings.

### FINSAGE_INVOICES
Stores invoice information, vendor details, purchase-order information, payment status, and compliance flags.

### FINSAGE_EXPENSE_EXCEPTIONS
Stores employee expense exceptions, reasons, reported severity/approval status,
duration, and submitter-reported receipt status.

For an existing HANA database, apply
`db/migrations/001_expense_compliance_details.sql` as `DBADMIN` before deploying
the updated backend. This repository change does not apply the migration to HANA.
The updated `db/schema.sql` includes these fields for new installations.

The document embedding column uses a 1536-dimensional REAL_VECTOR.

Agent execution traces are stored in the `FINSAGE_AGENT_TRACES` table. Each request
is inserted with `RUNNING` status and updated with its final status, decision, and
trace stages when processing completes. Trace summaries identify the request type
without storing or returning the raw user question. Existing raw summaries are
redacted by the read endpoint; this does not delete historical database values.
These traces are durable in HANA rather than stored in the Cloud Foundry container
filesystem.

Invoice flag events are stored in `FINSAGE_INVOICE_FLAGS`, separately from the
invoice's current status, so the reason and timestamp for each flag can be reviewed.
The **HANA Logs** page displays recent agent traces, invoice flag events, and expense
exceptions from HANA. The **AI Finance Copilot** displays whether Gemini generated
each answer; this status is response metadata shown in the frontend, not stored in
HANA. Policy answers are generated from verified policy excerpts; invoice and
expense responses are assembled by FinSage from HANA data.

For USA-region testing only, the following files contain fictional sample rules
and are explicitly not approved company policies:

- `code/data/documents/policies/USA_DEMO_ONLY_TRAVEL_POLICY.txt`
- `code/data/documents/policies/USA_DEMO_ONLY_VENDOR_ONBOARDING_POLICY.txt`

Ingest one demo document at a time:

```powershell
Set-Location code
python -m app.ingestion --file USA_DEMO_ONLY_TRAVEL_POLICY.txt
python -m app.ingestion --file USA_DEMO_ONLY_VENDOR_ONBOARDING_POLICY.txt
Set-Location ..
```

Each command generates Gemini embeddings and writes or updates that document's
chunks in HANA. Do not use either demo policy for real finance decisions; replace
them with approved USA policies before production use.

Before deploying the invoice-flag history feature, run the following as `DBADMIN`
in HANA Cloud, then grant the backend database user access:

```sql
CREATE COLUMN TABLE DBADMIN.FINSAGE_INVOICE_FLAGS (
    CASE_REF NVARCHAR(36) PRIMARY KEY,
    INVOICE_ID NVARCHAR(100) NOT NULL,
    REASON NCLOB NOT NULL,
    STATUS NVARCHAR(30) NOT NULL,
    FLAGGED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

GRANT SELECT, INSERT ON DBADMIN.FINSAGE_INVOICE_FLAGS TO FINSAGE_APP;
```

## 7. Installation and Local Setup

### Prerequisites

- Python 3.13.x (the version declared in `runtime.txt`)
- Visual Studio Code
- SAP BTP account
- SAP HANA Cloud instance
- Google Gemini API key

### Step 1: Clone or open the project

Open the FinSage project directory in Visual Studio Code.

### Step 2: Create a virtual environment

```powershell
python -m venv venv
```

### Step 3: Activate the environment

```powershell
.\venv\Scripts\Activate.ps1
```

### Step 4: Install dependencies

```powershell
pip install -r code\requirements.txt
```

### Step 5: Configure environment variables

Create a `.env` file in the project root.

Configure the following credentials using your own service details:

```env
HANA_HOST=your_hana_host
HANA_PORT=443
HANA_USER=your_hana_user
HANA_PASSWORD=your_hana_password

GEMINI_API_KEY=your_gemini_api_key
```

Never commit `.env` or expose database credentials and API keys.

### Step 6: Start the backend

```powershell
Set-Location code
uvicorn app.main:app --reload
```

Backend URL:

http://127.0.0.1:8000

Swagger documentation:

http://127.0.0.1:8000/docs

Health endpoint:

http://127.0.0.1:8000/health

### Step 7: Start the frontend

Open another VS Code terminal, activate the virtual environment, and run:

```powershell
Set-Location code
python -m streamlit run frontend/streamlit_app.py
```

## 7.1 Local Authentication Tests

```powershell
.\venv\Scripts\Activate.ps1
python -m pytest -q code\tests\test_auth.py
Set-Location code
python -m app.evaluation_runner
Set-Location ..
```

The authentication tests use a mocked XSUAA context and mocked finance actions;
they do not read or write HANA and do not replace live Cloud Foundry role testing.
The evaluation runner calls the configured HANA/Gemini path and writes
`eval/evaluation_report.latest.json`. Run it only when those services are
intentionally available. Individual-user login requires the Application Router.

## 7.2 SAP BTP Cockpit Configuration

1. Open the existing `finsage-xsuaa` service instance and update it using `deploy/xs-security.json`.
2. Open **Security > Role Collections** and verify `FinanceViewer`, `FinanceApprover`,
   and `FinanceAdmin` role collections exist.
3. In each role collection, open **Edit > Roles** and add the matching role template
   from application `finsage-finance-copilot`.
4. Assign the appropriate role collection to each SAP user:
   - Viewer users: `FinanceViewer`
   - Approvers: `FinanceApprover`
   - Administrators: `FinanceAdmin`
5. Verify the application route `finsage.cfapps.ap21.hana.ondemand.com` is registered
   by the App Router application.
6. The App Router enables WebSockets for Streamlit page updates and uses secure
   `SameSite=None` cookies for the XSUAA callback.
7. `.streamlit/config.toml` explicitly allows the App Router and frontend origins
   for Streamlit WebSockets while keeping CORS and XSRF protection enabled. Update
   this allowlist if either Cloud Foundry hostname changes.
8. The frontend calls FastAPI through its direct HTTPS route using the authenticated
   user's bearer token. Keep `FINSAGE_API_URL` pointed at the backend app route.
9. Run the `FINSAGE_AGENT_TRACES` table definition from `db/schema.sql` in the
   `DBADMIN` schema before using agent requests and the Production Agent Traces view.
10. Do not add passwords or tokens to environment variables, source files, or manifests.

## 7.3 SAP BTP Deployment

Deploy in this order:

```powershell
cf update-service finsage-xsuaa -c deploy\xs-security.json

cf push -f deploy\manifest.yml
cf push -f deploy\manifest-frontend.yml
cf push -f deploy\manifest-approuter.yml
```

If the XSUAA service must be created instead of updated:

```powershell
cf create-service xsuaa application finsage-xsuaa -c deploy\xs-security.json
```

After deployment, open:

```text
https://finsage.cfapps.ap21.hana.ondemand.com
```

The frontend calls FastAPI directly over HTTPS using the signed-in user's bearer token.
The API route remains protected by FastAPI XSUAA validation.

Use separate SAP users to verify Viewer, Approver, and Admin access. For a safe Viewer
write-denial check in Streamlit, use a clearly nonexistent invoice ID; never use a real
invoice just to test permissions.

## 8. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Application health check |
| POST | `/agent/ask` | Ask finance-related questions |
| POST | `/agent/flag-invoice` | Flag an invoice for compliance review |
| POST | `/agent/log-exception` | Record an expense exception |

Additional invoice and expense dashboard endpoints support the Streamlit interface.

## 9. Security and Compliance

FinSage includes the following security controls:

- SAP XSUAA security configuration.
- OAuth2-based authentication design.
- Finance Viewer, Finance Approver, and Finance Admin role templates.
- Backend authorization checks for protected operations.
- Explicit confirmation before invoice flagging.
- Explicit confirmation before expense exception submission.
- Regional policy filtering.
- Evidence verification before policy answers are returned.
- Refusal when sufficient supporting evidence is unavailable.

**Previously reported live status:** Cloud Foundry login, logout, account switching,
and Viewer write denial were reported earlier. This repository audit did not
independently re-check those live behaviors. The configured architecture passes the
individual user's token from Streamlit to FastAPI over HTTPS; no client secret or
bearer token is stored in browser code.

**Test boundary:** Local authentication tests use mocked XSUAA and finance actions.
They do not validate live token signatures, Cloud Foundry role assignments, or
production-scale/security behavior. Live FinanceAdmin authorization remains outstanding.

## 10. Evaluation Results

The current evaluation dataset contains 31 finance-related questions, including a
USA demo-policy case and citation-presence checks.

`eval/evaluation_report.json` is a historical 30-question result. It is not a
current run or a production accuracy guarantee. The evaluation runner writes a new
result to `eval/evaluation_report.latest.json` so the historical report is
preserved.

The runner checks intent, evidence availability, expected keywords, and citation
presence. These checks do not prove factual correctness or citation accuracy.

Evaluation requires the relevant policy chunks in HANA and the configured Gemini
service for semantic retrieval/generation. Do not interpret a saved report as live
deployment verification.

## 11. Project Completion and Remaining Work

The previous approximately 85% completion estimate was an engineering estimate,
not a measured project metric. This audit did not independently validate the live
deployment and found outstanding security, grounding, and compliance limitations.

| Area | Status |
|---|---|
| Finance Copilot, policy citations, and agent traces | Implemented; live evidence quality and trace persistence require verification |
| Invoice monitoring and triage | Implemented; live HANA data and currency assumptions require verification |
| Expense compliance | Limited India/INR screening; not a full approval or receipt-verification workflow |
| SAP HANA Cloud connectivity and finance data | Previously reported connected; not independently checked in this audit |
| SAP BTP Cloud Foundry deployment | Previously reported deployed; no deployment action or live check in this audit |
| Individual XSUAA login/logout and account switching | Verified in the deployed app |
| FinanceViewer/FinanceApprover authorization | Implemented; Viewer write denial confirmed by the user |
| FinanceAdmin live authorization | Requires a separate live account/role verification |
| SAP Joule integration | Not implemented; only planned documentation is described below |

### Remaining work

1. Verify FinanceAdmin access with a dedicated test user in Cloud Foundry.
2. Complete production-readiness checks, including operational monitoring and live
   invalid/expired-token scenarios.
3. Implement and validate a live SAP Joule integration if it remains in project scope.

## 12. SAP Joule Configuration

SAP Joule configuration was identified as a documentation deliverable. A live Joule
connection to FinSage has not been implemented or verified.

## 13. Project Objective

FinSage demonstrates how Agentic AI, retrieval-augmented generation, vector databases, and enterprise application services can be combined to support finance operations with evidence-based answers, compliance controls, and controlled write actions.

**Project:** FinSage  
**Platform:** SAP Business Technology Platform  
**Primary Database:** SAP HANA Cloud  
**Backend:** Python FastAPI  
**Frontend:** Streamlit  
**AI Service:** Google Gemini API
