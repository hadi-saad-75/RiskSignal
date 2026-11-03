"""Streamlit Community Cloud entrypoint for the RiskSignal dashboard.

Main file path on Community Cloud: deploy/streamlit_cloud/streamlit_app.py

The dashboard is a pure HTTP client of the RiskSignal API: it imports none of the backend code
(stochastic engine, graph, tools, agent). This file only
  1. reads the API address from ``st.secrets["RISKSIGNAL_API_URL"]`` (falling back to an environment
     variable of the same name, which is convenient for local runs),
  2. makes the ``src`` directory importable (Community Cloud runs from the repository root and puts
     only this file's directory on the path), and
  3. runs the unchanged dashboard (``src/risksignal/ui/app.py``).

Secrets (App settings > Secrets on Community Cloud, or .streamlit/secrets.toml locally, never committed):

    RISKSIGNAL_API_URL = "https://<your-render-service>.onrender.com"

All data are synthetic and all model parameters are illustrative.
"""

import os
import runpy
import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
UI_APP = REPO_ROOT / "src" / "risksignal" / "ui" / "app.py"
SECRET_NAME = "RISKSIGNAL_API_URL"


def read_api_url() -> str | None:
    """The API base URL from Streamlit secrets, else from the environment, else ``None``."""
    try:
        value = st.secrets[SECRET_NAME]
    except (KeyError, FileNotFoundError):  # key absent, or no secrets file at all
        value = os.environ.get(SECRET_NAME)
    return str(value).strip().rstrip("/") if value else None


def show_configuration_error(message: str) -> None:
    st.set_page_config(page_title="RiskSignal")
    st.title("RiskSignal")
    st.error(message)
    st.markdown(
        "Set the secret in **App settings > Secrets** (Streamlit Community Cloud), or in "
        "`.streamlit/secrets.toml` for a local run:\n\n"
        f'```toml\n{SECRET_NAME} = "https://<your-api-host>"\n```'
    )
    st.stop()


api_url = read_api_url()
if api_url is None:
    show_configuration_error(f"The secret `{SECRET_NAME}` is not set, so the dashboard does not know where the API is.")
elif not api_url.startswith(("http://", "https://")):
    show_configuration_error(f"`{SECRET_NAME}` must start with `http://` or `https://`.")
else:
    os.environ[SECRET_NAME] = api_url  # read by the dashboard's API client when the session starts
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))
    # run_path (not import) so the dashboard script executes again on every Streamlit rerun
    runpy.run_path(str(UI_APP), run_name="__main__")
