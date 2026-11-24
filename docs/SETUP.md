# FinSage Setup Guide

## Prerequisites

- Python 3.13
- SAP HANA Cloud, XSUAA, and the configured database credentials
- A Gemini API key for semantic retrieval and grounded policy answers

## Local setup

From the repository root, create and activate a virtual environment, then install
the backend and frontend dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r code\requirements.txt
```

Create a root-level `.env` using your own service credentials. Do not commit this
file. Start the backend from `code/`:

```powershell
Set-Location code
uvicorn app.main:app --reload
```

In another terminal, activate the same environment and start Streamlit:

```powershell
Set-Location code
python -m streamlit run frontend/streamlit_app.py
```

Run automated tests from the repository root:

```powershell
python -m pytest -q code\tests
```

## Cloud Foundry

The backend, frontend, and Application Router manifests are in `deploy/`.
From the repository root, use:

```powershell
cf push -f deploy\manifest.yml
cf push -f deploy\manifest-frontend.yml
cf push -f deploy\manifest-approuter.yml
```

The MTA descriptor is `deploy/mta.yaml`. It binds existing HANA, XSUAA, and
database-credential services; it does not create or alter those services.
See [the full project README](README.md) for database setup, authentication,
policy ingestion, and deployment details.
