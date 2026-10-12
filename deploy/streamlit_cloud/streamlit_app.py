"""Streamlit Community Cloud entry point for the RiskSignal dashboard.

Deploy with "Main file path" = deploy/streamlit_cloud/streamlit_app.py and set the secret

    RISKSIGNAL_API_URL = "https://<where-your-RiskSignal-API-runs>"

The dashboard needs the RiskSignal API: Streamlit Cloud runs only this script, so the API must be
hosted separately (see docs/deployment.md). This file only prepares the import path and the API
address, then runs the normal dashboard script.
"""

import os
import runpy
import sys
from pathlib import Path

import streamlit as st

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = REPOSITORY_ROOT / "src"

# The package is not pip-installed on Streamlit Cloud, so make `import risksignal` work.
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

# Use the API address from the app's Secrets, if one is set there.
try:
    api_url = st.secrets["RISKSIGNAL_API_URL"]
except Exception:  # no secrets configured (for example when running locally)
    api_url = None
if api_url:
    os.environ["RISKSIGNAL_API_URL"] = str(api_url)

runpy.run_path(str(SOURCE_DIR / "risksignal" / "ui" / "app.py"), run_name="__main__")
