"""RiskSignal Streamlit app. Entry point:

    streamlit run src/risksignal/ui/app.py

The UI talks only to the FastAPI backend (default http://127.0.0.1:8000, override with the
RISKSIGNAL_API_URL environment variable). Start the backend first:

    uvicorn risksignal.api.main:app --reload

All data are synthetic and the model is illustrative.
"""

import streamlit as st

from risksignal.ui.components import footer, sidebar_status
from risksignal.ui.theme import apply_theme
from risksignal.ui.views.assistant import render_assistant
from risksignal.ui.views.overview import render_overview
from risksignal.ui.views.scenario_lab import render_scenario_lab
from risksignal.ui.views.system_explorer import render_system_explorer


def main() -> None:
    st.set_page_config(page_title="RiskSignal", layout="wide", initial_sidebar_state="collapsed")
    apply_theme()
    sidebar_status()
    pages = [
        st.Page(render_assistant, title="Assistant", url_path="assistant", default=True),
        st.Page(render_overview, title="Overview", url_path="overview"),
        st.Page(render_system_explorer, title="System Explorer", url_path="system-explorer"),
        st.Page(render_scenario_lab, title="Scenario Analysis", url_path="scenario-lab"),
    ]
    navigation = st.navigation(pages, position="top")
    navigation.run()
    footer(pages)


main()
