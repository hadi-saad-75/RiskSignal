"""Supporting monitoring, RCSA, diagnostic and review features for Risk Investigator."""

import json
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from risksignal.ui.api_client import ApiClient
from risksignal.ui.charts import dependency_figure, kri_figure
from risksignal.ui.components import call_api
from risksignal.ui.formatting import (
    LOSS_UNIT_NOTICE,
    METRIC_LABELS,
    display_prose,
    extract_simulation_metadata,
    format_amount,
    format_decimal,
    label_for,
)
from risksignal.text import normalize_prose


def load_workpaper(client: ApiClient, system_id: str, refresh: bool = False) -> dict[str, Any] | None:
    key = f"workbench_evidence_{system_id}"
    if refresh:
        st.session_state.pop(key, None)
    if key not in st.session_state:
        result = call_api(client.workpaper, system_id)
        if result is None:
            return None
        st.session_state[key] = result
    return st.session_state[key]


def _ordered_snapshot(workpaper: dict[str, Any]) -> list[dict[str, Any]]:
    priority = {"unusual_increase": 0, "flat_baseline_increase": 0,
                "insufficient_history": 2, "gapped_history": 2, "within_baseline": 3}
    series = [item for item in workpaper["monitoring"]["series"] if item["data_status"] != "not_applicable"]

    def rank(item: dict[str, Any]) -> int:
        signal = item["latest"]["signal"] if item["latest"] else None
        if signal in ("unusual_increase", "flat_baseline_increase"):
            return 0
        if item["data_status"] in ("missing", "stale") or item["latest"] is None:
            return 1
        return priority.get(signal, 2)

    return sorted(
        series,
        key=rank,
    )[:3]


def monitoring_context(workpaper: dict[str, Any]) -> str:
    """Pass the same compact, current monitoring cues shown in the UI to the agent."""
    signals = []
    for item in _ordered_snapshot(workpaper):
        latest = item["latest"]
        value = format_decimal(latest["value"]) if latest else "no observation"
        signal = label_for(latest["signal"] if latest else item["data_status"])
        if item["data_status"] != "current":
            signal += f", {label_for(item['data_status'])} data"
        date = latest["date"] if latest else "no date"
        signals.append(f"- {label_for(item['kri_name'])}: {value} on {date}, {signal}")
    detail = "\n".join(signals) if signals else "- No applicable monitoring observations are available."
    return (
        f"Operational monitoring context for {workpaper['system_id']} as of {workpaper['as_of_date']}:\n"
        f"{detail}\nTreat these past-only review signals as prioritisation cues, not appetite breaches or "
        "predictions. Verify them against source evidence and explain any data-quality limitations."
    )


def render_monitoring_snapshot(workpaper: dict[str, Any]) -> None:
    st.subheader("System context")
    st.caption(
        "Latest indicator observations. Review prompts, not forecasts or approved risk limits."
    )
    series = _ordered_snapshot(workpaper)
    if not series:
        st.info("No applicable monitoring observations are available for this system.")
        return
    columns = st.columns(len(series), gap="medium")
    for column, item in zip(columns, series):
        latest = item["latest"]
        signal = label_for(latest["signal"]) if latest else label_for(item["data_status"])
        if item["data_status"] != "current":
            signal += f", {label_for(item['data_status'])} data"
        column.metric(
            label_for(item["kri_name"]),
            format_decimal(latest["value"]) if latest else "No observation",
            delta=signal,
            delta_color="off",
            help=(
                f"Latest observation: {latest['date']}. Past-only monitoring status."
                if latest else "No current observation. Missing data are not evidence of low risk."
            ),
        )
    st.caption(f"Monitoring snapshot date: {workpaper['as_of_date']}.")


def render_workbench_support(
    client: ApiClient,
    workpaper: dict[str, Any],
    investigation: dict[str, Any] | None = None,
) -> None:
    st.caption(f"Evidence as of {workpaper['as_of_date']}. Use Refresh evidence to reload this session's snapshot.")
    profile_column, incidents_column, kri_column = st.columns(3, gap="small")
    with profile_column:
        with st.expander("System details", key="evidence_profile", on_change="rerun") as panel:
            if panel.open:
                profile = workpaper["profile"]
                st.write(profile["system"]["description"])
                st.caption(f"Inventory criticality: {profile['system']['criticality']}. "
                           "This is a recorded classification, not a simulation result.")
                st.write(f"Primary process: {profile['primary_process']['name']}")
                st.json(profile, expanded=False)
    with incidents_column:
        with st.expander("Incidents", key="evidence_incidents", on_change="rerun") as panel:
            if panel.open:
                months = st.slider("Incident history (months)", 3, 60, 12, key="evidence_incident_months")
                incidents = workpaper["incidents"] if months == 12 else call_api(
                    client.incidents, workpaper["system_id"], months,
                )
                if incidents is None:
                    return
                st.caption(
                    f"Window: after {incidents['window_start_exclusive']} through "
                    f"{incidents['window_end_inclusive']}."
                )
                st.dataframe([
                    {"ID": i["incident_id"], "Date": i["date"], "Category": label_for(i["category"]),
                     "Description": i["description"], "Loss (synthetic units)": i["financial_loss"],
                     "Recorded severity": i["severity"]}
                    for i in incidents["incidents"]
                ], hide_index=True, alt="Recent synthetic incidents")
    with kri_column:
        with st.expander("KRI history", key="evidence_kris", on_change="rerun") as panel:
            if panel.open:
                _monitoring(workpaper["monitoring"], client, workpaper["system_id"])

    controls_column, vendors_column, activity_column = st.columns(3, gap="small")
    with controls_column:
        with st.expander("Controls", key="evidence_controls", on_change="rerun") as panel:
            if panel.open:
                st.caption("A review status is not evidence that a control works or has failed.")
                st.dataframe([
                    {"ID": c["control_id"], "Control": c["name"], "Review status": c["review_status"],
                     "Last review": c["last_review_date"]}
                    for c in workpaper["controls"]["controls"]
                ], hide_index=True, alt="Controls and their recorded review dates")
                st.json(workpaper["controls"], expanded=False)
    with vendors_column:
        with st.expander("Vendors and connected systems", key="evidence_dependencies", on_change="rerun") as panel:
            if panel.open:
                _dependencies(workpaper["dependencies"])
    with activity_column:
        if investigation:
            if extract_simulation_metadata(investigation["tool_activity"]):
                with st.expander("Simulation results", key="evidence_simulation", on_change="rerun") as panel:
                    if panel.open:
                        render_simulation_metadata(investigation["tool_activity"])
            with st.expander("Retrieved evidence and tool activity", key="evidence_tools", on_change="rerun") as panel:
                if panel.open:
                    _tool_activity(investigation["tool_activity"])

    review_column, advanced_column = st.columns(2, gap="small")
    with review_column:
        with st.expander("Review notes and evidence export", key="evidence_review", on_change="rerun") as panel:
            if panel.open:
                _review(workpaper)
    with advanced_column:
        with st.expander("Advanced checks and review questions", key="evidence_advanced", on_change="rerun") as panel:
            if panel.open:
                _rcsa(workpaper)
                _diagnostics(workpaper["diagnostics"])
                _draft_summary(client, workpaper)


def _draft_summary(client: ApiClient, workpaper: dict[str, Any]) -> None:
    """Optional RCSA draft, bound to the evidence snapshot rather than a second main workflow."""
    fingerprint = workpaper["evidence_sha256"]
    key = f"workbench_ai_result_{fingerprint}"
    if st.button("Draft AI evidence summary", key=f"workbench_ai_{fingerprint}"):
        st.session_state.pop(key, None)
        response = call_api(client.chat, f"Prepare an RCSA evidence summary for {workpaper['system_id']}. "
                            "Use get_risk_workpaper, cite sources and explain gaps. Do not assign ratings.",
                            [], include_tool_outputs=True)
        if response is not None:
            matching = any(a["tool_name"] == "get_risk_workpaper" and
                           (a.get("output") or {}).get("evidence_sha256") == fingerprint
                           for a in response["tool_activity"])
            if matching and response["status"] == "completed":
                st.session_state[key] = response
            else:
                st.error("No completed summary with matching workpaper evidence was returned. "
                         "Refresh evidence before retrying. No draft was retained.")
    if response := st.session_state.get(key):
        kind = "Scripted local draft (mock provider)" if response["provider"] == "mock" else "AI-generated draft"
        st.info(f"{kind}. Check the sources. This draft is not an approval.")
        st.markdown(normalize_prose(response["final_response"]))
        for warning in response["warnings"]:
            st.warning(normalize_prose(warning))


def render_simulation_metadata(activities: list[dict[str, Any]]) -> None:
    meta = extract_simulation_metadata(activities)
    if meta is None:
        st.write("No quantitative simulation was run in this investigation.")
        return
    columns = st.columns(4, gap="medium")
    columns[0].metric("λ (incidents per year)", format_decimal(meta["lambda_used"]))
    columns[1].metric("μ", format_decimal(meta["severity_mu"], 3))
    columns[2].metric("σ", format_decimal(meta["severity_sigma"], 3))
    columns[3].metric("Simulations / seed", f"{meta['number_of_simulations']:,} / {meta['random_seed']}")
    st.caption(
        "λ is expected annual incident count. μ and σ are the mean and standard deviation of log-losses. "
        "The model is illustrative and uses synthetic data."
    )
    st.caption(LOSS_UNIT_NOTICE)
    st.caption(
        f"λ source: {meta['lambda_source']}. Severity fitted to {meta['severity_losses_used']} losses "
        f"(data source: {meta['severity_data_source']})."
    )
    rows = [
        {
            "Metric": metric_label,
            "Baseline": format_amount(meta["baseline_metrics"][key]),
            **({"Stress": format_amount(meta["stress_metrics"][key])} if meta["stress_metrics"] else {}),
        }
        for key, metric_label in METRIC_LABELS
    ]
    st.dataframe(rows, hide_index=True, width="stretch", alt="Simulation results from the investigation tools")


def _tool_activity(activities: list[dict[str, Any]]) -> None:
    if not activities:
        st.write("No tools were called.")
        return
    for activity in activities:
        st.markdown(
            normalize_prose(f"**{activity['step']}. {activity['status'].capitalize()}:** {activity['summary']}")
        )
        with st.container():
            st.caption(
                f"Started: {activity['started_at']}, duration: "
                f"{format_decimal(activity['duration_ms'], 0)} ms, status: {activity['status']}."
            )
            st.markdown("**Input**")
            st.json(display_prose(activity["tool_input"]))
            if activity.get("output") is not None:
                st.markdown("**Tool output**")
                st.json(display_prose(activity["output"]), expanded=False)


def _monitoring(result: dict[str, Any], client: ApiClient, system_id: str) -> None:
    st.caption("Review one indicator at a time. Missing or stale data do not mean low risk.")
    names = [s["kri_name"] for s in result["series"]]
    selected = st.selectbox("Inspect KRI evidence", names, format_func=label_for, key="workbench_kri")
    series = next(s for s in result["series"] if s["kri_name"] == selected)
    if series["applicability_basis"]:
        st.info(series["applicability_basis"])
    months = st.slider("KRI history (months)", 3, 60, 12, key="evidence_kri_months")
    points = [{"Date": p["date"], "Value": p["value"], "Review signal": label_for(p["signal"])}
              for p in series["history"][-months:]]
    if points:
        history = call_api(client.kri, system_id, months)
        if history is None:
            return
        descriptive = next(s for s in history["series"] if s["kri_name"] == selected)
        st.plotly_chart(kri_figure(descriptive), theme=None, alt="Selected KRI history and descriptive window mean")
        st.caption("The dashed line is this window's mean, not a risk limit or a projected trend.")
        st.dataframe(points[-12:], hide_index=True, alt="Latest twelve KRI observations")
        if st.checkbox("Show descriptive window summary", key="evidence_kri_summary"):
            st.json(descriptive, expanded=False)
    else:
        st.info("No observations are available for this indicator.")
    if st.checkbox("Show monitoring methodology", key="evidence_kri_method"):
        for item in result["limitations"]:
            st.write(item)
        st.dataframe(series["history"], hide_index=True, alt="Detailed KRI calculation history")
        st.json({"source_refs": series["source_refs"], "policy_version": result["policy_version"]})


def _rcsa(workpaper: dict[str, Any]) -> None:
    st.subheader("Evidence-led control challenge")
    st.warning(
        "RCSA preparation only. Review status is not control effectiveness. Inherent/residual risk ratings "
        "require approved methodology, owners and test evidence not present here."
    )
    for question in workpaper["review_questions"]:
        with st.container(border=True):
            st.markdown(f"**{question['topic']}**")
            st.write(question["question"])
            st.caption("Sources: " + (", ".join(question["source_refs"]) or "No control records available"))


def _dependencies(result: dict[str, Any]) -> None:
    st.subheader("System dependencies")
    st.caption("Direct vendors and supported processes")
    st.dataframe([{"ID": v["vendor_id"], "Vendor": v["name"]} for v in result["vendors"]],
                 hide_index=True, alt="Direct vendors")
    st.dataframe([{"ID": p["process_id"], "Process": p["name"], "Primary": p["is_primary"]}
                  for p in result["supported_processes"]], hide_index=True, alt="Supported processes")
    vendors = [
        {
            "Shared vendor": entry["vendor"]["name"],
            "Other dependent systems": ", ".join(system["system_id"] for system in entry["other_systems"]),
        }
        for entry in result["shared_vendors"]
    ]
    if vendors:
        st.dataframe(vendors, hide_index=True, width="stretch", alt="Shared vendors and connected systems")
    else:
        st.caption("No shared direct vendors were recorded for this system.")
    related = [
        {
            "System": entry["system"]["system_id"],
            "Relationship": ", ".join(relation["explanation"] for relation in entry["relationships"]),
        }
        for entry in result["related_systems"]
    ]
    if related:
        st.dataframe(related, hide_index=True, width="stretch", alt="Related systems and evidence relationships")
    links = ([{"Direction": "Depends on", "System": link["system"]["system_id"], "Hops": link["hops"],
               "Via": ", ".join(link["via_system_ids"])} for link in result["upstream_systems"]]
             + [{"Direction": "Used by", "System": link["system"]["system_id"], "Hops": link["hops"],
                 "Via": ", ".join(link["via_system_ids"])} for link in result["downstream_systems"]])
    if links:
        st.dataframe(links, hide_index=True, alt="Upstream and downstream system connections")
    if result["indirect_vendors"]:
        st.dataframe([{"Vendor": v["vendor"]["name"], "Through system": v["via_system_id"], "Hops": v["hops"]}
                      for v in result["indirect_vendors"]], hide_index=True, alt="Indirect vendors")
    st.plotly_chart(dependency_figure(result["system_id"], result), theme=None,
                    alt="Recorded system dependencies, not causal relationships")
    st.caption("A shared dependency is a structural connection to investigate, not evidence of causation.")


def _diagnostics(result: dict[str, Any]) -> None:
    st.subheader("Temporal frequency-severity diagnostics")
    st.caption(
        f"Training: {result['training_start']} to {result['training_end_inclusive']} inclusive. "
        f"Holdout: after {result['training_end_inclusive']} through {result['holdout_end_inclusive']}. "
        "The holdout never enters fitting or bank-wide pooling."
    )
    if result["status"] != "evaluated":
        st.warning("Not estimable: " + result["limitations"][0])
    else:
        columns = st.columns(3)
        columns[0].metric("Training incidents (system)", result["training_incidents"])
        columns[1].metric("Holdout incidents (system)", result["holdout_incidents"])
        columns[2].metric("Expected holdout count (model)", format_decimal(result["expected_holdout_count"]))
        st.write({
            "Frequency basis": result["frequency_method"],
            "Severity basis": result["severity_source"],
            "Positive losses used for severity fit": result["severity_training_losses"],
            "Conditional count reference interval (95%)": result["count_reference_interval_95"],
            "Training monthly count variance / mean": result["monthly_count_variance_to_mean"],
            "Training individual-loss P95 (synthetic units)": format_amount(result["severity_p95"]),
            "Holdout positive losses": result["holdout_positive_losses"],
            "Holdout positive losses above training P95": result["holdout_losses_above_p95"],
        })
    for item in result["limitations"]:
        st.caption(item)


def _review(workpaper: dict[str, Any]) -> None:
    fingerprint = workpaper["evidence_sha256"]
    reviews_key = f"workbench_reviews_{fingerprint}"
    reviews = st.session_state.setdefault(reviews_key, [])
    st.subheader("Human review notes")
    st.caption(
        "Notes remain in this session until downloaded. They do not update controls, attest effectiveness "
        "or approve/close a risk. Use a demo role label, not personal or confidential information."
    )
    with st.form(f"workbench_review_{fingerprint}"):
        role = st.text_input("Reviewer role", max_chars=80, key=f"workbench_role_{fingerprint}")
        note = st.text_area(
            "Evidence gaps and next investigation steps", max_chars=4000, key=f"workbench_note_{fingerprint}",
        )
        submitted = st.form_submit_button("Record review note")
    if submitted:
        if not role.strip() or not note.strip():
            st.error("Enter a reviewer role and an evidence review note. Nothing was recorded.")
        else:
            reviews.append({
                "reviewer_role": role.strip(), "note": note.strip(),
                "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence_sha256": fingerprint, "status": "note_only_not_signoff",
            })
            st.success("Review note recorded in this session. Download the workpaper to retain it.")
    if reviews:
        st.dataframe(reviews, hide_index=True, width="stretch", alt="Session-local human review notes")
    st.code(fingerprint, language=None)
    st.caption(
        "SHA-256 fingerprints the API evidence only. It is not a digital signature, authenticated reviewer "
        "identity or immutable audit log."
    )
    exported = {"evidence": workpaper, "human_review_notes": reviews, "status": "draft_not_approved"}
    st.download_button(
        "Download evidence and review notes (JSON)",
        json.dumps(exported, indent=2, ensure_ascii=True, allow_nan=False),
        file_name=f"{workpaper['system_id']}_risk_workpaper.json",
        mime="application/json",
        key="workbench_download",
    )
    with st.expander("Full source evidence and limitations"):
        st.json(display_prose(workpaper))
