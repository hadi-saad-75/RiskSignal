"""RiskSignal editorial design system.

One place for the visual language of the dashboard: colour and type tokens, the global
stylesheet injected into Streamlit, and the Plotly template used by every chart.

Principles: white, black and neutral surfaces; a warm brown accent used only for small details
(CTA text, arrows, index numerals, active states); a refined serif for display typography and a
disciplined grotesk for everything functional; hierarchy built from scale, spacing and thin
rules rather than boxes, shadows or colour.
"""

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ----------------------------------------------------------------------------- tokens

BACKGROUND = "#FFFFFF"
SURFACE = "#FAF9F6"
TEXT = "#090909"
TEXT_SECONDARY = "#454545"
TEXT_MUTED = "#8F8F8A"
DIVIDER = "#D8D6D1"
BORDER_STRONG = "#171717"
ACCENT = "#9A6848"
ACCENT_SECONDARY = "#A97552"
# Semantic colours, deliberately desaturated; used only where a status must be distinguished.
NEGATIVE = "#8C3B2E"
POSITIVE = "#4F6B4A"

SERIF = '"Canela", "Editorial New", "Tiempos Headline", "Instrument Serif", "Cormorant Garamond", serif'
SANS = '"Neue Haas Grotesk Text", "Helvetica Neue", "Suisse Intl", "Inter", Arial, sans-serif'
FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1"
    "&family=Inter:wght@400;500;600;700&display=swap"
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
  --rs-serif: __SERIF__;
  --rs-sans: __SANS__;
  --rs-pad: clamp(1.25rem, 4.4vw, 4.5rem);
  --rs-section: clamp(3.5rem, 7vw, 7rem);
  --rs-h1: clamp(2.875rem, 1.6rem + 5.2vw, 7.25rem);
  --rs-h2: clamp(2.375rem, 1.5rem + 3.4vw, 5rem);
  --rs-h3: clamp(2.25rem, 1.6rem + 2.2vw, 3.5rem);
  --rs-figure: clamp(2.5rem, 1.9rem + 1.8vw, 3.75rem);
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
  max-width: 1440px;
  padding: calc(4.5rem + clamp(1.25rem, 2.5vw, 2rem)) var(--rs-pad) 0;
}
[data-testid="stDecoration"] { display: none; }
::selection { background: var(--rs-text); color: var(--rs-bg); }

/* ---------- masthead: wordmark + top navigation */
[data-testid="stHeader"] {
  background: var(--rs-bg);
  border-bottom: 1px solid var(--rs-divider);
  height: 4.5rem;
}
[data-testid="stHeader"]::before {
  content: "RiskSignal";
  font-family: var(--rs-serif);
  font-size: 1.875rem;
  letter-spacing: -0.03em;
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
  top: 1.35rem;
  right: var(--rs-pad);
  width: 2.25rem;
  height: 2.25rem;
  border: 1px solid var(--rs-strong) !important;
  border-radius: 999px !important;
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

/* ---------- display typography (serif) */
h1, h2, h3, h4,
[data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {
  font-family: var(--rs-serif) !important;
  font-weight: 400 !important;
  color: var(--rs-text);
  letter-spacing: -0.032em;
}
[data-testid="stHeading"] h1, h1 {
  font-size: var(--rs-h1) !important;
  line-height: 0.94 !important;
  padding: 0 0 0.25rem;
  letter-spacing: -0.038em;
}
[data-testid="stHeading"] h2, h2 { font-size: var(--rs-h2) !important; line-height: 0.98 !important; padding: 0; }
[data-testid="stHeading"] h3, h3 { font-size: var(--rs-h3) !important; line-height: 1.0 !important; padding: 0; }
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

/* ---------- editorial primitives */
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
  font-family: var(--rs-serif);
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
  font-size: clamp(1.0625rem, 0.95rem + 0.35vw, 1.25rem) !important;
  line-height: 1.45 !important;
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
  font-family: var(--rs-serif);
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
  font-family: var(--rs-serif) !important;
  font-size: var(--rs-figure) !important;
  font-weight: 400 !important;
  line-height: 1.02 !important;
  letter-spacing: -0.035em;
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

/* ---------- buttons: pill, hairline border, brown label + arrow */
button[data-testid^="stBaseButton"] {
  border-radius: 999px !important;
  border: 1px solid var(--rs-strong) !important;
  background: transparent !important;
  color: var(--rs-accent) !important;
  box-shadow: none !important;
  min-height: 3rem;
  padding: 0.65rem 1.5rem !important;
  transition: background-color 160ms ease, color 160ms ease;
}
button[data-testid^="stBaseButton"] p {
  font-family: var(--rs-sans);
  font-size: 0.9375rem !important;
  font-weight: 600;
  letter-spacing: 0;
  color: inherit !important;
}
button[data-testid="stBaseButton-primary"] p::after { content: "\\2192"; margin-left: 0.6em; display: inline-block; transition: transform 160ms ease; }
button[data-testid^="stBaseButton"]:hover { background: var(--rs-surface) !important; color: var(--rs-text) !important; }
button[data-testid="stBaseButton-primary"]:hover p::after { transform: translateX(0.25em); }
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
  border-radius: 0 !important;
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

/* ---------- tabs: text with a hairline, brown active marker */
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
.rs-sidebar-mark { font-family: var(--rs-serif) !important; font-size: 2rem !important; letter-spacing: -0.03em; line-height: 1 !important; color: var(--rs-text) !important; margin: 0 0 1.5rem; }

/* ---------- footer */
.st-key-rs_footer {
  margin-top: var(--rs-section);
  padding: clamp(2.5rem, 5vw, 4rem) 0 clamp(2.5rem, 5vw, 4rem);
  border-top: 1px solid var(--rs-strong);
}
.rs-footer-mark { font-family: var(--rs-serif) !important; font-size: clamp(2.5rem, 1.8rem + 2vw, 4rem) !important; letter-spacing: -0.035em; line-height: 0.95 !important; margin: 0 0 1rem; color: var(--rs-text) !important; }
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
[data-testid="stBottomBlockContainer"] { max-width: 1440px; padding: 1rem var(--rs-pad) 1.5rem !important; }
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
        "__NEGATIVE__": NEGATIVE, "__POSITIVE__": POSITIVE, "__SERIF__": SERIF, "__SANS__": SANS,
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

CHART_SANS = "Inter, Helvetica Neue, Arial, sans-serif"
CHART_SERIF = "Instrument Serif, Cormorant Garamond, serif"
# Applied as explicit layout properties (not only as a template) so that no host theme can override it.
PLOTLY_LAYOUT: dict = {
    "font": {"family": CHART_SANS, "size": 13, "color": TEXT_SECONDARY},
    "title": {"font": {"family": CHART_SERIF, "size": 26, "color": TEXT}, "x": 0, "xanchor": "left",
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
    """Apply the editorial chart style, then any figure-specific layout on top."""
    figure.update_layout(template=PLOTLY_TEMPLATE, **PLOTLY_LAYOUT)
    figure.update_layout(**layout)
    return figure
