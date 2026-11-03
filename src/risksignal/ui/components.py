"""Shared Streamlit components: API access, banner, error handling and answer rendering."""

from typing import Any, Callable, TypeVar

import streamlit as st

from risksignal.ui.api_client import ApiClient, ApiRequestError, ApiUnavailableError
from risksignal.ui.formatting import BANNER_TEXT, SECTION_COLORS, SIMULATION_NOTICE, split_sections

T = TypeVar("T")

DEFAULT_SYSTEM = "PAYMENT_ENGINE_01"
START_API_HELP = (
    "Generate the data with `python -m risksignal.data.generator`, start the backend with "
    "`uvicorn risksignal.api.main:app --reload`, or set `RISKSIGNAL_API_URL` if it runs elsewhere."
)
LLM_HELP = (
    "The Overview, System Explorer, and Scenario Analysis pages do not require a language-model API key. "
    "The investigation page requires `ANTHROPIC_API_KEY`, set in the environment or a `.env` file before "
    "starting the API. To use the deterministic mock provider, set "
    "`RISKSIGNAL_LLM_PROVIDER=mock`."
)


def get_api_client() -> ApiClient:
    """One client per browser session. Tests can place their own in ``st.session_state['api_client']``."""
    if "api_client" not in st.session_state:
        st.session_state["api_client"] = ApiClient()
    return st.session_state["api_client"]


def banner() -> None:
    st.warning(f"**{BANNER_TEXT}**")


def simulation_notice() -> None:
    st.info(SIMULATION_NOTICE)


def show_request_error(error: ApiRequestError) -> None:
    """Explain an API error to the user in plain language. Never shows technical detail."""
    if error.error_type == "llm_unavailable":
        st.error(f"The language model is unavailable. {error.message}")
        st.info(LLM_HELP)
    elif error.error_type == "data_unavailable":
        st.error(f"{error.message}\n\n{START_API_HELP}")
    else:
        extra = f" Did you mean: {', '.join(error.suggestions)}?" if error.suggestions else ""
        st.error(f"{error.message}{extra}")


def call_api(function: Callable[..., T], *args: Any, **kwargs: Any) -> T | None:
    """Call the API. Shows a clear message and returns ``None`` on an API error; stops the page
    if the API cannot be reached at all. The UI never crashes with a traceback."""
    try:
        return function(*args, **kwargs)
    except ApiUnavailableError as error:
        st.error(f"{error} {START_API_HELP}")
        st.stop()
    except ApiRequestError as error:
        show_request_error(error)
        return None


def sidebar_status() -> None:
    """Small connection panel in the sidebar."""
    client = get_api_client()
    with st.sidebar:
        st.markdown("**RiskSignal**")
        try:
            health = client.health()
        except ApiUnavailableError:
            st.error("API unavailable")
            st.caption(client.base_url)
            return
        (st.success if health["status"] == "ok" else st.warning)(f"API {health['status']}")
        st.caption(client.base_url)
        st.caption(f"Database: {'available' if health['database_available'] else 'unavailable'}")
        st.caption(
            f"Language model: {health['llm_provider']} "
            f"({'configured' if health['llm_configured'] else 'not configured'})"
        )
        st.caption("All data are synthetic.")


def system_selector(client: ApiClient, page_key: str, label: str = "System") -> str | None:
    """Select a system. The choice is remembered when moving between pages."""
    result = call_api(client.systems)
    if result is None:
        return None
    systems = result["systems"]
    ids = [s["system_id"] for s in systems]
    details = {s["system_id"]: s for s in systems}
    remembered = st.session_state.get("selected_system", DEFAULT_SYSTEM)
    choice = st.selectbox(
        label, ids, index=ids.index(remembered) if remembered in ids else 0, key=f"system_{page_key}",
        format_func=lambda i: f"{i} — {details[i]['name']} ({details[i]['criticality']})",
    )
    st.session_state["selected_system"] = choice
    return choice


def render_answer(text: str) -> None:
    """Show the agent's answer with each section under its own coloured badge and box."""
    for title, body in split_sections(text):
        st.badge(title, color=SECTION_COLORS.get(title, "gray"))
        with st.container(border=True):
            st.markdown(body or "_(empty)_")
