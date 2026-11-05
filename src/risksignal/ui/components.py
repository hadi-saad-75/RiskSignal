"""Shared Streamlit components: API access, banner, error handling, answer rendering and the
editorial layout primitives (page header, section header, ruled lists, footer)."""

from html import escape
from typing import Any, Callable, Sequence, TypeVar

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from risksignal.ui.api_client import ApiClient, ApiRequestError, ApiUnavailableError
from risksignal.ui.formatting import BANNER_TEXT, SIMULATION_NOTICE, split_sections
from risksignal.text import normalize_prose

T = TypeVar("T")

DEFAULT_SYSTEM = "PAYMENT_ENGINE_01"
START_API_HELP = (
    "Generate the data with `python -m risksignal.data.generator`, start the backend with "
    "`uvicorn risksignal.api.main:app --reload`, or set `RISKSIGNAL_API_URL` if it runs elsewhere."
)
LLM_HELP = (
    "The Overview, System Explorer, and Scenario Analysis pages do not require a language-model API key. "
    "The Assistant requires `ANTHROPIC_API_KEY`, set in the environment or a `.env` file before "
    "starting the API. To use the deterministic mock provider, set "
    "`RISKSIGNAL_LLM_PROVIDER=mock`."
)


def get_api_client() -> ApiClient:
    """One client per browser session. Tests can place their own in ``st.session_state['api_client']``."""
    if "api_client" not in st.session_state:
        st.session_state["api_client"] = ApiClient()
    return st.session_state["api_client"]


def banner() -> None:
    with st.container(key="rs_banner"):
        st.warning(f"**{BANNER_TEXT}**")


# ----------------------------------------------------------------------------- editorial layout


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def eyebrow(index: str, label: str) -> None:
    """Brown index numeral, a short hairline and an uppercase label, e.g. '01 ---- OVERVIEW'."""
    html(f'<div class="rs-eyebrow"><span class="rs-index">{escape(index)}</span>'
         f'<span class="rs-line"></span><span>{escape(label)}</span></div>')


def lead(text: str) -> None:
    html(f'<p class="rs-lead">{escape(normalize_prose(text))}</p>')


def label(text: str) -> None:
    """Small uppercase sans label used above lists, tables and figures."""
    html(f'<p class="rs-label">{escape(text)}</p>')


def statement(text: str) -> None:
    """Large sans statement (24 to 34px) for a key sentence."""
    html(f'<p class="rs-statement">{escape(text)}</p>')


def rule(subtle: bool = False) -> None:
    html(f'<div class="rs-rule{" rs-rule--subtle" if subtle else ""}"></div>')


def spacer() -> None:
    html('<div class="rs-spacer"></div>')


def page_header(index: str, label: str, title: str, intro: str | None = None,
                intro_below: bool = False) -> DeltaGenerator:
    """Oversized serif title across seven of twelve columns, with the sans introduction either
    beside it (bottom-aligned, offset by one column) or set below it on the right-hand side.
    Returns the right-hand column so a page can add more supporting content there."""
    eyebrow(index, label)
    if intro_below:
        st.title(title)
        _, aside = st.columns([5, 7], gap="large")
    else:
        main, _, aside = st.columns([7, 1, 4], vertical_alignment="top", gap="small")
        with main:
            st.title(title)
    if intro:
        with aside:
            html('<div class="rs-hero-offset"></div>')
            lead(intro)
    return aside


def section_header(title: str, intro: str | None = None, index: str | None = None,
                   subtle: bool = False, tag: str | None = None) -> DeltaGenerator:
    """A rule, then a large serif section title with optional supporting copy to its right.
    ``tag`` adds a small status label above the title, for example "In development".
    Returns the right-hand column."""
    rule(subtle)
    spacer()
    main, _, aside = st.columns([7, 1, 4], vertical_alignment="bottom")
    with main:
        if index:
            html(f'<span class="rs-index">{escape(index)}</span>')
        if tag:
            html(f'<span class="rs-tag">{escape(tag)}</span>')
        st.subheader(title)
    if intro:
        with aside:
            lead(intro)
    spacer()
    return aside


def ruled_list(items: Sequence[tuple[str, str]]) -> None:
    """Items with a hairline on the left: a semibold title and a short description."""
    rows = "".join(
        f"<li><b>{escape(normalize_prose(title))}</b><span>{escape(normalize_prose(body))}</span></li>"
        for title, body in items
    )
    html(f'<ul class="rs-list">{rows}</ul>')


def footer(pages: Sequence[Any]) -> None:
    """Editorial footer: wordmark and statement, page links and method notes in ruled columns."""
    with st.container(key="rs_footer"):
        intro, _, explore, method = st.columns([5, 1, 3, 3], gap="large")
        with intro:
            html('<p class="rs-footer-mark">RiskSignal</p>')
            html('<p class="rs-footer-note">A research prototype for investigating technology operational '
                 'risk with deterministic tools and an illustrative loss model.</p>')
        with explore, st.container(key="rs_footer_col_explore"):
            html('<p class="rs-label">Explore</p>')
            for page in pages:
                st.page_link(page)
        with method, st.container(key="rs_footer_col_method"):
            html('<p class="rs-label">Method</p>')
            html('<p class="rs-footer-note">Poisson frequency, Lognormal severity, Monte Carlo aggregation. '
                 'Language-model output is checked against tool results.</p>')
        html(f'<p class="rs-footer-legal">{escape(BANNER_TEXT)} Fictional Atlas Bank data only.</p>')


def simulation_notice() -> None:
    st.info(SIMULATION_NOTICE)


def show_request_error(error: ApiRequestError) -> None:
    """Explain an API error to the user in plain language. Never shows technical detail."""
    if error.error_type == "llm_unavailable":
        st.error(normalize_prose(f"The language model is unavailable. {error.message}"))
        st.info(LLM_HELP)
    elif error.error_type == "data_unavailable":
        st.error(normalize_prose(f"{error.message}\n\n{START_API_HELP}"))
    else:
        extra = f" Did you mean: {', '.join(error.suggestions)}?" if error.suggestions else ""
        st.error(normalize_prose(f"{error.message}{extra}"))


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
        html('<p class="rs-sidebar-mark">RiskSignal</p>')
        html('<p class="rs-label">Connection</p>')
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
        format_func=lambda i: f"{i} · {details[i]['name']} ({details[i]['criticality']})",
    )
    st.session_state["selected_system"] = choice
    return choice


def is_structured(text: str) -> bool:
    """True when the answer uses the investigation headings (Observed evidence, ...)."""
    return any(title not in ("Answer", "Summary") for title, _ in split_sections(text))


def render_answer(text: str, key: str = "rs_sections") -> None:
    """Show the agent's answer as numbered editorial sections, each body set against a hairline.
    ``key`` must be unique on the page when several answers are shown."""
    for number, (title, body) in enumerate(split_sections(text), start=1):
        html(f'<div class="rs-answer-head"><span class="rs-index">{number:02d}</span>'
             f'<span class="rs-title">{escape(title)}</span></div>')
        with st.container(key=f"{key}_body_{number}"):
            st.markdown(body or "_(empty)_")
