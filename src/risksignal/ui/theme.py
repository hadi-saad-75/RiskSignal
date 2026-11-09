"""RiskSignal visual system.

One place for the visual language of the dashboard: colour and type tokens, the global
stylesheet injected into Streamlit, and the Plotly template used by every chart.

Principles: neutral surfaces, a restrained navy accent, readable sans-serif typography and
clear hierarchy. Colour and decoration are reserved for actions and meaningful status.
"""

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ----------------------------------------------------------------------------- tokens

BACKGROUND = "#FFFFFF"
SURFACE = "#F5F7FA"
TEXT = "#172B45"
TEXT_SECONDARY = "#52647A"
TEXT_MUTED = "#65758B"
DIVIDER = "#DFE5EC"
BORDER_STRONG = "#CBD5E1"
ACCENT = "#183153"
ACCENT_SECONDARY = "#2864A0"
# Semantic colours, deliberately desaturated; used only where a status must be distinguished.
NEGATIVE = "#B42318"
POSITIVE = "#067647"

SANS = '"Inter", "Segoe UI", Arial, sans-serif'
FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
)

# ----------------------------------------------------------------------------- stylesheet

_CSS = """
@import url('__FONT_IMPORT__');

:root {
  --rs-bg: __BACKGROUND__;
  --rs-surface: __SURFACE__;
  --rs-text: __TEXT__;
  --rs-text-2: __TEXT_SECONDARY__;
  --rs-muted: __TEXT_MUTED__;
  --rs-divider: __DIVIDER__;
  --rs-strong: __BORDER_STRONG__;
  --rs-accent: __ACCENT__;
  --rs-accent-2: __ACCENT_SECONDARY__;
  --rs-negative: __NEGATIVE__;
  --rs-positive: __POSITIVE__;
  --rs-sans: __SANS__;
  --rs-pad: clamp(1.25rem, 3vw, 3rem);
  --rs-section: clamp(2rem, 4vw, 3.5rem);
  --rs-h1: clamp(2rem, 1.5rem + 1.8vw, 3rem);
  --rs-h2: clamp(1.5rem, 1.25rem + 0.8vw, 1.875rem);
  --rs-h3: clamp(1.125rem, 1rem + 0.35vw, 1.375rem);
  --rs-figure: clamp(1.5rem, 1.25rem + 0.8vw, 1.875rem);
}
@media (min-width: 1680px) { :root { --rs-pad: 5.5rem; } }

/* ---------- canvas */
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: var(--rs-bg);
  color: var(--rs-text);
  font-family: var(--rs-sans);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
[data-testid="stMainBlockContainer"] {
  max-width: 1180px;
  padding: 5rem var(--rs-pad) 2rem;
}
[data-testid="stDecoration"] { display: none; }
::selection { background: var(--rs-text); color: var(--rs-bg); }

/* ---------- masthead: wordmark + top navigation */
[data-testid="stHeader"] {
  background: var(--rs-bg);
  border-bottom: 1px solid var(--rs-divider);
  height: 4rem;
}
[data-testid="stHeader"]::before {
  content: "RiskSignal";
  font-family: var(--rs-sans);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1;
  color: var(--rs-text);
  padding-left: var(--rs-pad);
  padding-right: clamp(1.5rem, 3vw, 3.5rem);
  align-self: center;
  white-space: nowrap;
}
/* sidebar toggle becomes a hairline hamburger at the far right of the masthead */
[data-testid="stExpandSidebarButton"] {
  position: fixed !important;
  top: 1.05rem;
  right: var(--rs-pad);
  width: 2rem;
  height: 2rem;
  border: 1px solid var(--rs-divider) !important;
  border-radius: 0.5rem !important;
  background: var(--rs-bg) !important;
  z-index: 1000;
}
[data-testid="stExpandSidebarButton"] > * { visibility: hidden; }
[data-testid="stExpandSidebarButton"]::before {
  content: "";
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0.875rem;
  height: 1px;
  transform: translate(-50%, -50%);
  background: var(--rs-text);
  box-shadow: 0 -4px 0 var(--rs-text), 0 4px 0 var(--rs-text);
}
[data-testid="stExpandSidebarButton"]:hover { background: var(--rs-surface) !important; }
[data-testid="stTopNavLink"] {
  border-radius: 0;
  background: transparent !important;
  padding: 0.5rem 0;
  margin-right: 1.75rem;
  border-bottom: 1px solid transparent;
}
[data-testid="stTopNavLink"] span, [data-testid="stTopNavLink"] p {
  font-family: var(--rs-sans);
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--rs-text-2);
  letter-spacing: 0;
}
[data-testid="stTopNavLink"]:hover span, [data-testid="stTopNavLink"]:hover p { color: var(--rs-accent); }
[data-testid="stTopNavLink"][aria-current="page"] { border-bottom-color: var(--rs-accent); }
[data-testid="stTopNavLink"][aria-current="page"] span,
[data-testid="stTopNavLink"][aria-current="page"] p { color: var(--rs-text); }
[data-testid="stTopNavLink"] { transition: background-color 160ms ease; }
[data-testid="stTopNavLink"][aria-current="page"] {
  border-radius: 0.5rem 0.5rem 0 0;
  background: rgb(40 100 160 / 7%) !important;
}

/* ---------- headings */
h1, h2, h3, h4,
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
  font-family: var(--rs-sans) !important;
  font-weight: 600 !important;
  color: var(--rs-text);
  letter-spacing: -0.02em;
}
[data-testid="stHeading"] h1, h1 {
  font-size: var(--rs-h1) !important;
  line-height: 1.12 !important;
  padding: 0 0 0.35rem;
  letter-spacing: -0.025em;
}
[data-testid="stHeading"] h2, h2 { font-size: var(--rs-h2) !important; line-height: 1.2 !important; padding: 0; }
[data-testid="stHeading"] h3, h3 { font-size: var(--rs-h3) !important; line-height: 1.3 !important; padding: 0; }
[data-testid="stHeaderActionElements"] { display: none; }

/* ---------- body typography (sans) */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
  font-family: var(--rs-sans);
  font-size: 1.0625rem;
  line-height: 1.5;
  color: var(--rs-text);
}
[data-testid="stMarkdownContainer"] strong { font-weight: 600; }
[data-testid="stMarkdownContainer"] a { color: var(--rs-accent); text-decoration: none; }
[data-testid="stMarkdownContainer"] a:hover { color: var(--rs-text); }
[data-testid="stMarkdownContainer"] code {
  font-size: 0.875em;
  background: var(--rs-surface);
  color: var(--rs-text);
  padding: 0.05em 0.3em;
  border-radius: 0;
}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
  font-family: var(--rs-sans);
  font-size: 0.875rem !important;
  line-height: 1.5;
  color: var(--rs-text-2) !important;
  opacity: 1 !important;
}

/* ---------- layout primitives */
.rs-eyebrow {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 0 0 clamp(1.25rem, 2.5vw, 2rem);
  font-family: var(--rs-sans);
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rs-text-2);
}
.rs-eyebrow .rs-index,
.rs-index {
  font-family: var(--rs-sans);
  font-size: 1.5rem;
  font-weight: 400;
  letter-spacing: -0.02em;
  text-transform: none;
  color: var(--rs-accent);
  line-height: 1;
}
.rs-eyebrow .rs-line { width: 2.5rem; height: 1px; background: var(--rs-strong); }
.rs-lead {
  font-family: var(--rs-sans);
  font-size: clamp(0.9375rem, 0.9rem + 0.15vw, 1rem) !important;
  line-height: 1.55 !important;
  color: var(--rs-text-2) !important;
  margin: 0 0 0.75rem;
  max-width: 34rem;
}
.rs-statement {
  font-family: var(--rs-sans);
  font-size: clamp(1.5rem, 1.1rem + 1.1vw, 2.125rem) !important;
  font-weight: 500;
  line-height: 1.22 !important;
  letter-spacing: -0.015em;
  color: var(--rs-text) !important;
  max-width: 46rem;
}
.rs-label {
  font-family: var(--rs-sans);
  font-size: 0.8125rem !important;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rs-text-2) !important;
  margin: 0 0 0.5rem;
}
.rs-rule { height: 1px; background: var(--rs-strong); border: 0; margin: var(--rs-section) 0 0; }
.rs-tag {
  display: inline-block;
  margin: 0 0 0.9rem;
  padding: 0.3rem 0.75rem;
  border: 1px solid var(--rs-accent);
  border-radius: 999px;
  font-family: var(--rs-sans);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rs-accent);
}
.rs-rule.rs-rule--subtle { background: var(--rs-divider); margin-top: clamp(2rem, 4vw, 3.5rem); }
.rs-spacer { height: clamp(1rem, 2vw, 2rem); }
/* aligns the hero introduction with the cap height of the oversized title beside it */
.rs-hero-offset { height: clamp(0.25rem, 1.4vw, 1.5rem); }
.rs-cta {
  font-family: var(--rs-sans);
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--rs-accent) !important;
  text-decoration: none;
}
.rs-cta::after { content: "\\2192"; margin-left: 0.5em; transition: margin 160ms ease; }
.rs-cta:hover::after { margin-left: 0.8em; }
.rs-list { list-style: none; padding: 0; margin: 0; }
.rs-list li {
  border-left: 1px solid var(--rs-divider);
  padding: 0.125rem 0 0.125rem 1.25rem;
  margin: 0 0 1.25rem;
  font-size: 1rem !important;
}
.rs-list li b { display: block; font-weight: 600; color: var(--rs-text); margin-bottom: 0.15rem; }
.rs-list li span { color: var(--rs-text-2); }
.rs-answer-head {
  display: flex;
  align-items: baseline;
  gap: 1rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--rs-divider);
  margin-top: 1.5rem;
}
.rs-answer-head .rs-title {
  font-family: var(--rs-sans);
  font-size: clamp(1.75rem, 1.4rem + 1vw, 2.5rem);
  letter-spacing: -0.03em;
  line-height: 1;
  color: var(--rs-text);
}
[class*="st-key-rs_sections_"] {
  border-left: 1px solid var(--rs-divider);
  padding-left: 1.25rem;
  margin-left: 2.5rem;
}

/* ---------- notice strip (research banner) */
.st-key-rs_banner [data-testid="stAlertContainer"] {
  border: 0 !important;
  border-top: 1px solid var(--rs-divider) !important;
  border-bottom: 1px solid var(--rs-divider) !important;
  padding: 0.7rem 0 !important;
  margin-bottom: clamp(2.5rem, 5vw, 4.5rem);
}
.st-key-rs_banner [data-testid="stAlertContainer"] p {
  font-size: 0.8125rem !important;
  font-weight: 500;
  color: var(--rs-text-2) !important;
  letter-spacing: 0.01em;
}
.st-key-rs_banner [data-testid="stAlertContainer"] p strong { font-weight: 500; }
.st-key-rs_banner [data-testid="stAlertContainer"] p::before {
  content: "Notice";
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--rs-accent);
  margin-right: 1rem;
}

/* ---------- alerts: rules, not tinted boxes */
[data-testid="stAlertContainer"] {
  background: transparent !important;
  border: 0 !important;
  border-left: 2px solid var(--rs-strong) !important;
  border-radius: 0 !important;
  padding: 0.35rem 0 0.35rem 1.25rem !important;
}
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] li {
  color: var(--rs-text) !important;
  font-size: 0.9375rem !important;
  line-height: 1.5;
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { border-left-color: var(--rs-accent) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { border-left-color: var(--rs-negative) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { border-left-color: var(--rs-positive) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) { border-left-color: var(--rs-muted) !important; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) p { color: var(--rs-text-2) !important; }

/* ---------- figures (st.metric) */
[data-testid="stMetric"] {
  border-left: 1px solid var(--rs-divider);
  padding: 0.25rem 0 0.25rem 1.25rem;
  background: transparent;
}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
  font-family: var(--rs-sans);
  font-size: 0.8125rem !important;
  font-weight: 500;
  color: var(--rs-text-2) !important;
  min-height: 0;
}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div,
[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p {
  font-family: var(--rs-sans) !important;
  font-size: var(--rs-figure) !important;
  font-weight: 600 !important;
  line-height: 1.2 !important;
  letter-spacing: -0.02em;
  color: var(--rs-text) !important;
  font-variant-numeric: lining-nums;
}
[data-testid="stMetricValue"] { padding: 0.5rem 0 0.15rem; }
[data-testid="stMetricDelta"] {
  background: transparent !important;
  padding: 0 !important;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--rs-text-2) !important;
}
[data-testid="stMetricDelta"] div, [data-testid="stMetricDelta"] p {
  color: var(--rs-text-2) !important;
  font-size: 0.875rem !important;
  font-weight: 500;
  line-height: 1.4 !important;
}
[data-testid="stMetricDelta"] svg { color: var(--rs-accent) !important; fill: var(--rs-accent) !important; }

/* ---------- buttons */
button[data-testid^="stBaseButton"] {
  border-radius: 0.5rem !important;
  border: 1px solid var(--rs-divider) !important;
  background: transparent !important;
  color: var(--rs-text) !important;
  box-shadow: none !important;
  min-height: 2.5rem;
  padding: 0.55rem 1rem !important;
  transition: background-color 160ms ease, color 160ms ease;
}
button[data-testid^="stBaseButton"] p {
  font-family: var(--rs-sans);
  font-size: 0.9375rem !important;
  font-weight: 600;
  letter-spacing: 0;
  color: inherit !important;
}
button[data-testid^="stBaseButton"]:hover { background: var(--rs-surface) !important; color: var(--rs-text) !important; }
button[data-testid="stBaseButton-primary"] {
  background: var(--rs-accent) !important;
  border-color: var(--rs-accent) !important;
  color: #FFFFFF !important;
}
button[data-testid="stBaseButton-primary"] p { color: #FFFFFF !important; }
button[data-testid="stBaseButton-primary"]:hover { background: var(--rs-accent-2) !important; color: #FFFFFF !important; }
button[data-testid="stBaseButton-primary"]:hover p { color: #FFFFFF !important; }
button[data-testid^="stBaseButton"]:focus-visible { outline: 2px solid var(--rs-accent); outline-offset: 3px; }
[data-testid="stHeader"] button[data-testid^="stBaseButton"],
[data-testid="stSidebar"] button[data-testid^="stBaseButton-header"],
[data-testid="stSidebarCollapseButton"] button,
button[data-testid="stBaseButton-headerNoPadding"] {
  border: 0 !important;
  min-height: 0;
  padding: 0.25rem !important;
  color: var(--rs-text-2) !important;
}

/* ---------- form controls */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {
  font-family: var(--rs-sans);
  font-size: 0.8125rem !important;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--rs-text-2) !important;
}
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"],
[data-baseweb="textarea"], [data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
[data-testid="stTextArea"] [data-testid="stTextAreaRootElement"], [data-testid="stTextInputRootElement"] {
  border-radius: 0.5rem !important;
  background: var(--rs-bg) !important;
  border-color: var(--rs-divider) !important;
}
[data-baseweb="select"] > div:focus-within, [data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stSelectbox"] [role="group"]:focus-within, [data-testid="stSelectbox"] [role="group"]:hover,
[data-testid="stTextAreaRootElement"]:focus-within,
[data-baseweb="textarea"]:focus-within { border-color: var(--rs-strong) !important; }
[data-baseweb="select"] *, [data-testid="stSelectbox"] [role="group"] *, [data-baseweb="input"] input, input, textarea {
  font-family: var(--rs-sans) !important;
  font-size: 1rem !important;
  color: var(--rs-text) !important;
}
textarea { line-height: 1.5 !important; background: var(--rs-bg) !important; }
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] { background: transparent !important; color: var(--rs-text-2) !important; }
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"] {
  font-family: var(--rs-sans);
  font-size: 0.8125rem;
  color: var(--rs-text-2);
}
[data-testid="stSliderThumbValue"] { color: var(--rs-accent); font-weight: 600; }
[data-testid="stCheckbox"] p { font-size: 0.9375rem !important; text-transform: none; letter-spacing: 0; font-weight: 500; color: var(--rs-text) !important; }
[data-testid="stCheckbox"] label, [data-testid="stCheckbox"] label *, [data-testid="stCheckbox"] p {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  overflow-wrap: anywhere;
}
[data-testid="stNumberInput"] label p {
  text-transform: none !important;
}

/* ---------- tabs: text with a hairline, navy active marker */
[data-testid="stTabs"] [role="tablist"], [data-baseweb="tab-list"] {
  gap: clamp(1.5rem, 3vw, 2.75rem) !important;
  border-bottom: 1px solid var(--rs-divider);
}
[data-testid="stTab"], [data-baseweb="tab"] {
  padding: 0 0 0.9rem !important;
  background: transparent !important;
  position: relative;
}
[data-testid="stTab"] p, [data-baseweb="tab"] p {
  font-family: var(--rs-sans);
  font-size: 0.9375rem !important;
  font-weight: 500;
  color: var(--rs-muted) !important;
  transition: color 160ms ease;
}
[data-testid="stTab"]:hover p, [data-baseweb="tab"]:hover p { color: var(--rs-text) !important; }
[data-testid="stTab"][aria-selected="true"] p, [data-baseweb="tab"][aria-selected="true"] p { color: var(--rs-text) !important; }
[data-testid="stTab"][aria-selected="true"] > div:last-child:empty {
  background-color: var(--rs-accent) !important;
  height: 2px !important;
}
[data-baseweb="tab-highlight"] { background-color: var(--rs-accent) !important; height: 1px !important; }
[data-baseweb="tab-border"] { display: none; }
[data-testid="stTabPanel"], [data-baseweb="tab-panel"] { padding-top: clamp(2rem, 3.5vw, 3.25rem) !important; }

/* ---------- expanders: ruled disclosure rows */
[data-testid="stExpander"] details {
  border: 0 !important;
  border-top: 1px solid var(--rs-divider) !important;
  border-bottom: 1px solid var(--rs-divider) !important;
  border-radius: 0 !important;
  background: transparent !important;
}
[data-testid="stExpander"] + [data-testid="stExpander"] details,
[data-testid="stElementContainer"]:has([data-testid="stExpander"]) + [data-testid="stElementContainer"] [data-testid="stExpander"] details,
[data-testid="stLayoutWrapper"]:has(> [data-testid="stExpander"]) + [data-testid="stLayoutWrapper"] > [data-testid="stExpander"] details { border-top: 0 !important; }
[data-testid="stLayoutWrapper"]:has(> [data-testid="stExpander"]) + [data-testid="stLayoutWrapper"]:has(> [data-testid="stExpander"]) { margin-top: -1rem; }
[data-testid="stExpander"] summary { padding: 1.05rem 0 !important; }
[data-testid="stExpander"] summary p { font-family: var(--rs-sans); font-size: 0.9375rem !important; font-weight: 600; color: var(--rs-text) !important; }
[data-testid="stExpander"] summary:hover p { color: var(--rs-accent) !important; }
[data-testid="stExpander"] summary svg { color: var(--rs-accent) !important; }
[data-testid="stExpanderDetails"] { padding: 0 0 1.5rem !important; }

/* ---------- tables */
[data-testid="stTable"] > div { border: 0 !important; border-radius: 0 !important; }
[data-testid="stTable"] table {
  border-collapse: collapse;
  border: 0;
  width: 100%;
  font-family: var(--rs-sans);
  font-size: 0.9375rem;
}
[data-testid="stTable"] th {
  border: 0 !important;
  border-bottom: 1px solid var(--rs-strong) !important;
  background: transparent !important;
  color: var(--rs-text-2) !important;
  font-size: 0.8125rem;
  font-weight: 600;
  text-align: left;
  padding: 0.6rem 1rem 0.6rem 0 !important;
}
[data-testid="stTable"] td {
  border: 0 !important;
  border-bottom: 1px solid var(--rs-divider) !important;
  padding: 0.75rem 1rem 0.75rem 0 !important;
  color: var(--rs-text);
  font-variant-numeric: tabular-nums;
}
[data-testid="stTable"] tbody th { display: none; }
[data-testid="stTable"] th p { font-size: 0.8125rem !important; font-weight: 600; color: var(--rs-text-2) !important; }
[data-testid="stTable"] td p { font-size: 0.9375rem !important; line-height: 1.4 !important; }
[data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }

/* ---------- json / code */
[data-testid="stJson"], [data-testid="stCode"], pre { background: var(--rs-surface) !important; border-radius: 0 !important; }

/* ---------- sidebar */
[data-testid="stSidebar"] { background: var(--rs-surface); border-right: 1px solid var(--rs-divider); }
[data-testid="stSidebar"] [data-testid="stAlertContainer"] { padding-top: 0.15rem !important; padding-bottom: 0.15rem !important; }
.rs-sidebar-mark { font-family: var(--rs-sans) !important; font-size: 1.5rem !important; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2 !important; color: var(--rs-text) !important; margin: 0 0 1.5rem; }

/* ---------- footer */
.st-key-rs_footer {
  margin-top: var(--rs-section);
  padding: clamp(2.5rem, 5vw, 4rem) 0 clamp(2.5rem, 5vw, 4rem);
  border-top: 1px solid var(--rs-strong);
}
.rs-footer-mark { font-family: var(--rs-sans) !important; font-size: 1.5rem !important; font-weight: 700; letter-spacing: -0.02em; line-height: 1.2 !important; margin: 0 0 1rem; color: var(--rs-text) !important; }
.rs-footer-note { font-size: 0.875rem !important; color: var(--rs-text-2) !important; max-width: 26rem; }
.st-key-rs_footer [data-testid="stPageLink"] a { padding: 0; background: transparent !important; }
.st-key-rs_footer [data-testid="stPageLink"] p { font-size: 0.9375rem !important; color: var(--rs-text) !important; font-weight: 500; }
.st-key-rs_footer [data-testid="stPageLink"] a:hover p { color: var(--rs-accent) !important; }
[class*="st-key-rs_footer_col"] { border-left: 1px solid var(--rs-divider); padding-left: 1.25rem; }
.rs-footer-legal { font-size: 0.8125rem !important; color: var(--rs-muted) !important; margin-top: clamp(2rem, 4vw, 3rem); }

/* ---------- assistant conversation */
.rs-chat-question {
  display: flex;
  align-items: baseline;
  gap: 1.25rem;
  margin-top: clamp(2rem, 4vw, 3rem);
  padding-top: 1.5rem;
  border-top: 1px solid var(--rs-strong);
}
.rs-chat-question p {
  font-family: var(--rs-sans);
  font-size: clamp(1.25rem, 1.05rem + 0.6vw, 1.625rem) !important;
  font-weight: 500;
  line-height: 1.3 !important;
  letter-spacing: -0.01em;
  color: var(--rs-text) !important;
  margin: 0;
  max-width: 52rem;
}
[class*="st-key-rs_chat_answer_"] {
  border-left: 1px solid var(--rs-divider);
  padding-left: 1.5rem;
  margin: 1.25rem 0 0 2.75rem;
  max-width: 62rem;
}
[class*="st-key-rs_chat_answer_"] table { font-size: 0.9375rem; border-collapse: collapse; display: block; overflow-x: auto; max-width: 100%; }
[class*="st-key-rs_chat_answer_"] [data-testid="stMetricValue"],
[class*="st-key-rs_chat_answer_"] [data-testid="stMetricValue"] div,
[class*="st-key-rs_chat_answer_"] [data-testid="stMetricValue"] p {
  font-size: clamp(1.75rem, 1.4rem + 1vw, 2.5rem) !important;
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
}
[data-testid="stExpander"] summary:hover, [data-testid="stExpander"] summary:focus,
[data-testid="stExpander"] summary:focus-visible { background: transparent !important; }
[class*="st-key-rs_chat_answer_"] th { font-weight: 600; color: var(--rs-text-2); border-bottom: 1px solid var(--rs-strong) !important; }
[class*="st-key-rs_chat_answer_"] td, [class*="st-key-rs_chat_answer_"] th {
  border: 0; border-bottom: 1px solid var(--rs-divider); padding: 0.5rem 1rem 0.5rem 0; background: transparent;
  font-variant-numeric: tabular-nums;
}
[class*="st-key-assistant_starter_"] button {
  border: 0 !important;
  border-top: 1px solid var(--rs-divider) !important;
  border-radius: 0 !important;
  justify-content: flex-start !important;
  text-align: left;
  padding: 1.1rem 0 !important;
  min-height: 0;
  color: var(--rs-text) !important;
}
[class*="st-key-assistant_starter_"] button p { font-weight: 500; text-align: left; }
[class*="st-key-assistant_starter_"] button > div,
[class*="st-key-assistant_starter_"] button [data-testid="stMarkdownContainer"] { justify-content: flex-start !important; width: 100%; }
[class*="st-key-assistant_starter_"] button p::after { content: "\\2192"; color: var(--rs-accent); margin-left: 0.6em; }
[class*="st-key-assistant_starter_"] button:hover { background: transparent !important; color: var(--rs-accent) !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: var(--rs-bg) !important; }
[data-testid="stBottomBlockContainer"] { max-width: 1360px; padding: 1rem var(--rs-pad) 1.5rem !important; }
[data-testid="stChatInput"] {
  border: 1px solid var(--rs-strong) !important;
  border-radius: 0 !important;
  background: var(--rs-bg) !important;
}
[data-testid="stChatInput"] > div { background: var(--rs-bg) !important; border-radius: 0 !important; }
[data-testid="stChatInputTextArea"], [data-testid="stChatInput"] textarea {
  font-family: var(--rs-sans) !important;
  font-size: 1.0625rem !important;
  color: var(--rs-text) !important;
  background: var(--rs-bg) !important;
}
[data-testid="stChatInputSubmitButton"] { background: transparent !important; color: var(--rs-accent) !important; }
[data-testid="stChatInputSubmitButton"]:hover { color: var(--rs-text) !important; }
.st-key-rs_chat_input_box { margin-top: 1.5rem; }

/* ---------- introduction and way forward (scoped to their own containers) */
.st-key-rs_intro_hero, .st-key-rs_wf_hero {
  position: relative;
  overflow: hidden;
  padding: clamp(1.5rem, 3vw, 2.5rem) clamp(1.5rem, 3vw, 2.75rem);
  margin-bottom: 1.5rem;
  border: 1px solid var(--rs-divider);
  border-radius: 1rem;
  background:
    radial-gradient(circle at 98% 0%, rgb(40 100 160 / 9%) 0%, transparent 42%),
    linear-gradient(135deg, #FFFFFF 0%, var(--rs-surface) 100%);
  box-shadow: 0 1px 2px rgb(23 43 69 / 4%), 0 8px 24px rgb(23 43 69 / 4%);
}
.st-key-rs_intro_hero::before, .st-key-rs_wf_hero::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, var(--rs-accent) 0%, var(--rs-accent-2) 100%);
}
.st-key-rs_intro_hero [data-testid="stCaptionContainer"] p,
.st-key-rs_wf_hero [data-testid="stCaptionContainer"] p { font-size: 1rem !important; }
.st-key-rs_wf_hero [data-testid="stMarkdownContainer"] p { max-width: 46rem; color: var(--rs-text-2); }
.st-key-rs_intro_current, [class*="st-key-rs_intro_card_"],
[class*="st-key-rs_step_"], .st-key-rs_wf_success {
  border: 1px solid var(--rs-divider) !important;
  border-radius: 0.875rem !important;
  background: #FFFFFF;
  box-shadow: 0 1px 2px rgb(23 43 69 / 4%), 0 8px 24px rgb(23 43 69 / 3%);
  padding: 0.5rem 0.75rem 0.75rem;
  margin-bottom: 0.5rem;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}
.st-key-rs_intro_current:hover, [class*="st-key-rs_intro_card_"]:hover,
[class*="st-key-rs_step_"]:hover, .st-key-rs_wf_success:hover {
  border-color: var(--rs-strong) !important;
  box-shadow: 0 2px 4px rgb(23 43 69 / 5%), 0 12px 28px rgb(23 43 69 / 7%);
}
[class*="st-key-rs_intro_card_"] { border-top: 3px solid var(--rs-accent-2) !important; }
.st-key-rs_intro_current { border-left: 4px solid var(--rs-accent) !important; }
[class*="st-key-rs_step_"] { border-left: 4px solid var(--rs-accent-2) !important; max-width: 62rem; }
.st-key-rs_wf_success {
  max-width: 62rem;
  background: var(--rs-surface);
  border-left: 4px solid var(--rs-accent) !important;
}
.st-key-rs_intro_current [data-testid="stIconMaterial"],
[class*="st-key-rs_intro_card_"] [data-testid="stIconMaterial"] {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.625rem;
  background: rgb(40 100 160 / 10%);
  color: var(--rs-accent-2);
  font-size: 1.4rem !important;
}
.st-key-rs_intro_current h3, [class*="st-key-rs_intro_card_"] h3,
[class*="st-key-rs_step_"] h3, .st-key-rs_wf_success h3 { padding: 0.35rem 0 0.15rem; }
.st-key-rs_intro_current [data-testid="stMarkdownContainer"] p,
[class*="st-key-rs_intro_card_"] [data-testid="stMarkdownContainer"] p,
[class*="st-key-rs_step_"] [data-testid="stMarkdownContainer"] p,
.st-key-rs_wf_success [data-testid="stMarkdownContainer"] p { max-width: 58rem; }
.st-key-rs_note { margin-top: 0.75rem; max-width: 62rem; }
@media (prefers-reduced-motion: reduce) {
  [class*="st-key-rs_intro_"], [class*="st-key-rs_step_"], .st-key-rs_wf_success { transition: none !important; }
}

/* ---------- investigation workspace */
.st-key-rs_investigator [data-testid="stHeading"] h3 {
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--rs-divider);
}
.st-key-rs_investigator [data-testid="stSelectbox"] [role="group"]:focus-within,
.st-key-rs_investigator [data-testid="stTextAreaRootElement"]:focus-within,
.st-key-rs_investigator [data-baseweb="textarea"]:focus-within {
  border-color: var(--rs-accent) !important;
  box-shadow: 0 0 0 3px rgb(40 100 160 / 12%) !important;
}
.st-key-rs_investigator .st-key-agent_investigate button[data-testid="stBaseButton-primary"] {
  box-shadow: 0 2px 6px rgb(24 49 83 / 14%) !important;
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.st-key-rs_investigator .st-key-agent_investigate button[data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgb(24 49 83 / 20%) !important;
}
@media (prefers-reduced-motion: reduce) {
  [data-testid="stTopNavLink"],
  .st-key-rs_investigator .st-key-agent_investigate button[data-testid="stBaseButton-primary"] {
    transition: none !important;
  }
}

/* ---------- responsive */
@media (max-width: 640px) {
  [data-testid="stHeader"]::before { font-size: 1.5rem; padding-right: 1rem; }
  [data-testid="stMetric"] { margin-bottom: 0.5rem; }
  [class*="st-key-rs_sections_"] { margin-left: 0; }
  [class*="st-key-rs_chat_answer_"] { margin-left: 0; padding-left: 1rem; }
  /* empty offset columns only exist for the desktop grid; drop them once columns stack */
  [data-testid="stColumn"]:not(:has([data-testid="stElementContainer"])) { display: none; }
  [data-testid="stHorizontalBlock"] { gap: 1.25rem !important; }
}
"""


def _stylesheet() -> str:
    tokens = {
        "__FONT_IMPORT__": FONT_IMPORT, "__BACKGROUND__": BACKGROUND, "__SURFACE__": SURFACE, "__TEXT__": TEXT,
        "__TEXT_SECONDARY__": TEXT_SECONDARY, "__TEXT_MUTED__": TEXT_MUTED, "__DIVIDER__": DIVIDER,
        "__BORDER_STRONG__": BORDER_STRONG, "__ACCENT__": ACCENT, "__ACCENT_SECONDARY__": ACCENT_SECONDARY,
        "__NEGATIVE__": NEGATIVE, "__POSITIVE__": POSITIVE, "__SANS__": SANS,
    }
    css = _CSS
    for placeholder, value in tokens.items():
        css = css.replace(placeholder, value)
    return css


STYLESHEET = _stylesheet()


def apply_theme() -> None:
    """Inject the global stylesheet. Call once per script run, before any page content."""
    st.html(f"<style>{STYLESHEET}</style>")


# ----------------------------------------------------------------------------- charts

CHART_SANS = "Inter, Segoe UI, Arial, sans-serif"
# Applied as explicit layout properties (not only as a template) so that no host theme can override it.
PLOTLY_LAYOUT: dict = {
    "font": {"family": CHART_SANS, "size": 13, "color": TEXT_SECONDARY},
    "title": {"font": {"family": CHART_SANS, "size": 20, "color": TEXT}, "x": 0, "xanchor": "left",
              "xref": "paper", "y": 0.97, "yanchor": "top"},
    "paper_bgcolor": BACKGROUND,
    "plot_bgcolor": BACKGROUND,
    "colorway": [BORDER_STRONG, ACCENT, TEXT_MUTED, ACCENT_SECONDARY, TEXT_SECONDARY],
    "xaxis": {"showgrid": False, "zeroline": False, "showline": True, "linecolor": BORDER_STRONG, "linewidth": 1,
              "ticks": "outside", "tickcolor": BORDER_STRONG, "ticklen": 4, "automargin": True,
              "tickfont": {"family": CHART_SANS, "size": 12, "color": TEXT_SECONDARY},
              "title": {"font": {"family": CHART_SANS, "size": 12, "color": TEXT_SECONDARY}}},
    "yaxis": {"showgrid": True, "gridcolor": DIVIDER, "griddash": "dot", "zeroline": False, "showline": False,
              "ticks": "", "automargin": True,
              "tickfont": {"family": CHART_SANS, "size": 12, "color": TEXT_SECONDARY},
              "title": {"font": {"family": CHART_SANS, "size": 12, "color": TEXT_SECONDARY}}},
    "legend": {"font": {"family": CHART_SANS, "size": 13, "color": TEXT_SECONDARY}, "bgcolor": "rgba(0,0,0,0)",
               "borderwidth": 0},
    "hoverlabel": {"bgcolor": BACKGROUND, "bordercolor": BORDER_STRONG,
                   "font": {"family": CHART_SANS, "size": 13, "color": TEXT}},
}
PLOTLY_TEMPLATE = go.layout.Template(layout=PLOTLY_LAYOUT)
pio.templates["risksignal"] = PLOTLY_TEMPLATE


def style_figure(figure: go.Figure, **layout: object) -> go.Figure:
    """Apply the minimal chart style, then any figure-specific layout on top."""
    figure.update_layout(template=PLOTLY_TEMPLATE, **PLOTLY_LAYOUT)
    figure.update_layout(**layout)
    return figure
