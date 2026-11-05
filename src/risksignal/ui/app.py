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
from risksignal.ui.views.introduction import render_introduction
from risksignal.ui.views.scenario_lab import render_scenario_lab
from risksignal.ui.views.system_explorer import render_system_explorer
from risksignal.ui.views.way_forward import render_way_forward


def main() -> None:
    st.set_page_config(page_title="RiskSignal", layout="wide", initial_sidebar_state="collapsed")
    apply_theme()
    sidebar_status()
    pages = {
        "System Explorer": st.Page(render_system_explorer, title="System Explorer", url_path="system-explorer"),
        "Scenario Analysis": st.Page(render_scenario_lab, title="Scenario Analysis", url_path="scenario-lab"),
        "Assistant": st.Page(render_assistant, title="Assistant", url_path="assistant"),
        "Way forward: AI assistant": st.Page(
            render_way_forward, title="Way forward: AI assistant", url_path="way-forward",
        ),
    }
    introduction = st.Page(
        lambda: render_introduction(pages),
        title="Introduction",
        url_path="introduction",
        default=True,
    )
    navigation_pages = [introduction, *pages.values()]
    navigation = st.navigation(navigation_pages, position="top")
    navigation.run()
    footer(navigation_pages)


main()
