"""Page 2: System Explorer."""

import streamlit as st

from risksignal.ui.charts import dependency_figure, kri_figure
from risksignal.ui.components import banner, call_api, get_api_client, system_selector
from risksignal.ui.formatting import format_amount, format_decimal, format_percent, label_for


def render_system_explorer() -> None:
    banner()
    st.title("System Explorer")
    st.caption("This page reports synthetic observations; no values on this page are forecasts.")
    client = get_api_client()
    system_id = system_selector(client, "explorer")
    if system_id is None:
        return
    months = st.slider("Months of history", min_value=3, max_value=60, value=12, step=1)

    profile = call_api(client.profile, system_id)
    incidents = call_api(client.incidents, system_id, months)
    kri = call_api(client.kri, system_id, months)
    controls = call_api(client.controls, system_id)
    dependencies = call_api(client.dependencies, system_id)
    if None in (profile, incidents, kri, controls, dependencies):
        return

    tabs = st.tabs(["Profile", "Incidents", "KRIs", "Controls", "Dependencies and related systems"])
    with tabs[0]:
        _profile_tab(profile)
    with tabs[1]:
        _incidents_tab(incidents)
    with tabs[2]:
        _kri_tab(kri)
    with tabs[3]:
        _controls_tab(controls)
    with tabs[4]:
        _dependencies_tab(system_id, dependencies)


def _profile_tab(profile: dict) -> None:
    system, process, meta = profile["system"], profile["primary_process"], profile["metadata"]
    st.subheader(f"{system['name']} ({system['system_id']})")
    st.write(system["description"])
    columns = st.columns(4)
    columns[0].metric("Criticality", system["criticality"].capitalize())
    columns[1].metric("Incidents on record", meta["total_incidents_recorded"])
    columns[2].metric("Controls", meta["number_of_controls"])
    columns[3].metric("KRIs tracked", len(meta["kris_tracked"]))
    st.markdown(f"**Primary business process:** {process['name']} ({process['process_id']}). {process['description']}")
    st.caption(f"Data window: {meta['data_window_start']} to {meta['data_window_end']}. {meta['data_source']}.")


def _incidents_tab(incidents: dict) -> None:
    counts = incidents["counts"]
    st.markdown(f"**{counts['total']} incidents** between {incidents['window_start_exclusive']} (exclusive) "
                f"and {incidents['window_end_inclusive']}.")
    columns = st.columns(3)
    columns[0].metric("Total recorded loss", format_amount(counts["total_financial_loss"]))
    columns[1].metric("Incidents by category", ", ".join(f"{label_for(k)}: {v}" for k, v in counts["by_category"].items()) or "none")
    columns[2].metric("Descriptions mentioning deployment", counts["deployment_keyword_matches"])
    st.caption("The data have no separate cause field. The deployment count is a keyword match on the description.")
    if incidents["incidents"]:
        st.dataframe(
            [{"Date": i["date"], "Incident": i["incident_id"], "Category": label_for(i["category"]),
              "Severity": i["severity"], "Loss": i["financial_loss"], "Description": i["description"]}
             for i in incidents["incidents"]],
            hide_index=True, width="stretch",
            column_config={"Loss": st.column_config.NumberColumn("Loss", format="%d")},
        )
    else:
        st.info("No incidents in this window.")


def _kri_tab(kri: dict) -> None:
    st.caption("Monthly values. Higher values are less favourable for all five indicators. The dashed line is the "
               "window mean. Descriptive only: no trend is projected.")
    columns = st.columns(2)
    for index, series in enumerate(kri["series"]):
        columns[index % 2].plotly_chart(kri_figure(series), width="stretch", key=f"kri_{series['kri_name']}")
    st.dataframe(
        [{"KRI": label_for(s["kri_name"]), "Latest": format_decimal(s["latest_value"]),
          "Window mean": format_decimal(s["window_mean"]), "Min": format_decimal(s["window_min"]),
          "Max": format_decimal(s["window_max"]),
          "Mean vs previous window": format_percent(s["change_vs_previous_window_percent"])}
         for s in kri["series"]],
        hide_index=True, width="stretch",
    )


def _controls_tab(controls: dict) -> None:
    counts = controls["counts_by_review_status"]
    st.markdown("**Review status:** " + (", ".join(f"{k.capitalize()}: {v}" for k, v in counts.items()) or "None"))
    st.caption("An overdue review is a reason to ask questions, not proof that the control has failed.")
    st.dataframe(
        [{"Control": c["control_id"], "Name": c["name"], "Type": c["control_type"],
          "Status": c["review_status"].capitalize(),
          "Last review": c["last_review_date"], "Days since review": c["days_since_last_review"],
          "Description": c["description"]}
         for c in controls["controls"]],
        hide_index=True, width="stretch",
    )


def _dependencies_tab(system_id: str, dependencies: dict) -> None:
    st.plotly_chart(dependency_figure(system_id, dependencies), width="stretch", key="dependency_map")
    st.caption("Related systems share a vendor or a business process with the selected system. This is a shared "
               "exposure worth investigating, not evidence that a failure in one system causes a failure in another.")

    left, right = st.columns(2)
    with left:
        st.markdown("**Vendors**")
        st.dataframe([{"Vendor": v["vendor_id"], "Name": v["name"]} for v in dependencies["vendors"]],
                     hide_index=True, width="stretch")
        st.markdown("**Supported business processes**")
        st.dataframe([{"Process": p["process_id"], "Name": p["name"], "Primary": "yes" if p["is_primary"] else ""}
                      for p in dependencies["supported_processes"]], hide_index=True, width="stretch")
    with right:
        st.markdown("**Vendors shared with other systems**")
        shared = dependencies["shared_vendors"]
        if shared:
            st.dataframe([{"Vendor": s["vendor"]["name"], "Also used by": ", ".join(o["system_id"] for o in s["other_systems"])}
                          for s in shared], hide_index=True, width="stretch")
        else:
            st.write("None.")
        st.markdown("**Depends on / depended on by**")
        links = ([{"Direction": "depends on", "System": link["system"]["system_id"], "Hops": link["hops"],
                   "Via": ", ".join(link["via_system_ids"])} for link in dependencies["upstream_systems"]]
                 + [{"Direction": "depended on by", "System": link["system"]["system_id"], "Hops": link["hops"],
                     "Via": ", ".join(link["via_system_ids"])} for link in dependencies["downstream_systems"]])
        if links:
            st.dataframe(links, hide_index=True, width="stretch")
        else:
            st.write("None.")

    st.markdown("**Related systems and why**")
    if dependencies["related_systems"]:
        st.dataframe(
            [{"System": r["system"]["system_id"], "Criticality": r["system"]["criticality"],
              "Relationship": " ".join(x["explanation"] for x in r["relationships"])}
             for r in dependencies["related_systems"]],
            hide_index=True, width="stretch")
    else:
        st.write("No systems share a vendor or process with this system.")
    if dependencies["indirect_vendors"]:
        st.markdown("**Vendors reached only indirectly**")
        st.dataframe([{"Vendor": v["vendor"]["name"], "Through system": v["via_system_id"], "Hops": v["hops"]}
                      for v in dependencies["indirect_vendors"]], hide_index=True, width="stretch")
