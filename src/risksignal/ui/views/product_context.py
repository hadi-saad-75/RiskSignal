"""Concise product introduction and optional synthetic source-record browser."""

import streamlit as st

from risksignal.ui.api_client import ApiClient
from risksignal.ui.components import call_api, credits_footer, get_api_client

TABLES = {
    "systems": ("Systems", "The technology inventory: names, criticality and primary business process."),
    "processes": ("Business processes", "The business activities supported by the systems."),
    "vendors": ("Vendors", "The suppliers recorded in the synthetic institution."),
    "controls": ("Controls", "Recorded safeguards and review dates. Review status is not proof of effectiveness."),
    "incidents": ("Incidents", "Dated events, narratives and recorded losses in synthetic monetary units."),
    "kri_observations": ("KRI observations", "Monthly indicator values. These are observations, not predictions."),
    "dependencies": ("Dependencies", "Links between systems, vendors, processes and controls, not causal findings."),
}
PAGE_SIZE = 100


def render_introduction() -> None:
    with st.container(key="rs_intro_hero"):
        st.title("Overview")
        st.caption("RiskSignal: evidence-led Operational Risk investigation.")
    with st.container(border=True, key="rs_intro_current"):
        st.markdown(":material/dataset:")
        st.subheader("Current approach")
        st.write(
            "Analysts can review incident records, control registers, indicator reports and dependency maps. "
            "Spreadsheets, reporting dashboards and loss simulations help organise and analyse this information. "
            "These are useful tools, but connecting the evidence for one investigation still requires analyst judgement."
        )
        st.caption("A simple overview of common approaches, not a claim that every institution works this way.")
    need, goal = st.columns(2, gap="large")
    with need, st.container(border=True, key="rs_intro_card_need"):
        st.markdown(":material/search:")
        st.subheader("The need")
        st.write("When a signal looks unusual, the analyst needs to find the relevant records, understand their "
                 "connections and decide what evidence is missing.")
    with goal, st.container(border=True, key="rs_intro_card_goal"):
        st.markdown(":material/flag:")
        st.subheader("The goal")
        st.write("Connect relevant evidence and help analysts decide what to investigate next. "
                 "The analyst remains responsible for conclusions and action.")
    with st.container(border=True, key="rs_intro_card_idea"):
        st.markdown(":material/lightbulb:")
        st.subheader("The idea")
        st.write("Use an LLM as the investigation interface: it can select approved read-only tools and organise "
                 "their evidence into findings and follow-up questions. Python retrieves records and calculates "
                 "numbers. Monte Carlo supports the optional question: what annual losses could result under "
                 "stated assumptions?")
    with st.container(key="rs_note"):
        st.caption("The data are synthetic Atlas Bank records. The offline mock follows a script, not live LLM reasoning. "
                   "Live LLM quality and real-data predictive performance have not been evaluated.")
    credits_footer()


def render_database(client: ApiClient) -> None:
    with st.container():
        st.write("Inspect the source data used by the prototype. Read-only, fictional Atlas Bank records only.")
        table = st.selectbox("Data table", list(TABLES), format_func=lambda name: TABLES[name][0], key="database_table")
        st.caption(TABLES[table][1])
        st.caption("Shared IDs connect tables: system_id identifies a system, control_id a control, and "
                   "source_id/target_id connect dependency records. No real bank data are included.")
        page = int(st.number_input("Page", min_value=1, value=1, step=1, key=f"database_page_{table}"))
        result = call_api(client.database, table, (page - 1) * PAGE_SIZE, PAGE_SIZE)
        if result is None:
            return
        pages = max(1, (result["total_rows"] + PAGE_SIZE - 1) // PAGE_SIZE)
        if not result["rows"]:
            st.info("This table is empty." if result["total_rows"] == 0 else
                    f"No records on this page. Choose a page from 1 to {pages}.")
            return
        first = result["offset"] + 1
        last = result["offset"] + len(result["rows"])
        st.caption(f"{result['total_rows']:,} records. Showing {first:,}-{last:,}. Page {page} of {pages}. "
                   "Scroll vertically for rows and horizontally for columns. Sorting and search apply to this page.")
        st.dataframe(result["rows"], column_order=result["columns"], height=420, hide_index=True,
                     width="stretch", alt=f"Synthetic {TABLES[table][0].lower()} source records")
        st.caption(result["notice"])


def render_database_page() -> None:
    st.title("Database")
    render_database(get_api_client())
