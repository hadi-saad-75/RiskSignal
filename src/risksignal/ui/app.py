"""RiskSignal Streamlit app. Entry point:

    streamlit run src/risksignal/ui/app.py

The UI talks only to the FastAPI backend (default http://127.0.0.1:8000, override with the
RISKSIGNAL_API_URL environment variable). Start the backend first:

    uvicorn risksignal.api.main:app --reload

All data are synthetic and the model is illustrative.
"""

import streamlit as st

from risksignal.ui.components import sidebar_status
from risksignal.ui.theme import apply_theme
from risksignal.ui.views.assistant import render_assistant
from risksignal.ui.views.product_context import render_introduction
from risksignal.ui.views.scenario_lab import render_scenario_lab
from risksignal.ui.views.way_forward import render_way_forward


def main() -> None:
    st.set_page_config(page_title="RiskSignal", layout="wide", initial_sidebar_state="collapsed")
    apply_theme()
    sidebar_status()
    navigation = st.navigation([
        st.Page(render_introduction, title="Overview", url_path="introduction"),
        st.Page(render_assistant, title="Risk Investigator", default=True),
        st.Page(render_scenario_lab, title="Scenario Analysis", url_path="scenario-lab"),
        st.Page(render_way_forward, title="Way Forward", url_path="way-forward"),
    ], position="top")
    navigation.run()


main()
