"""Page 1: Overview."""

import streamlit as st

from risksignal.ui.components import banner, call_api, get_api_client
from risksignal.ui.formatting import format_amount, label_for


def render_overview() -> None:
    banner()
    st.title("Management overview")
    st.markdown(
        "A concise portfolio view of technology operational-risk evidence. This demonstration uses "
        "fictional Atlas Bank data—not JPMorgan data—and is not a production or decision-making tool."
    )

    overview = call_api(get_api_client().overview, 5)
    if overview is None:
        return
    counts = overview["counts"]

    columns = st.columns(4)
    for column, (label, key) in zip(
        columns,
        [
            ("Incident records", "incidents"),
            ("Recorded loss", "total_recorded_loss"),
            ("Overdue controls", "overdue_controls"),
            ("Systems in scope", "systems"),
        ],
    ):
        column.metric(label, format_amount(counts[key]))
    st.caption(
        f"Synthetic observation window: {counts['data_window_start']} to {counts['data_window_end']}. "
        "Recorded loss is historical and synthetic, not a forecast."
    )

    st.subheader("Latest incidents")
    st.dataframe(
        [{"Date": i["date"], "System": i["system_id"], "Category": label_for(i["category"]),
          "Severity": i["severity"], "Loss": i["financial_loss"]}
         for i in overview["recent_incidents"]],
        hide_index=True, width="stretch",
        column_config={"Loss": st.column_config.NumberColumn("Loss", format="%d")},
    )

    st.caption(
        "Overdue reviews are follow-up items, not evidence that a control has failed. "
        "Use System Explorer, Scenario Analysis, and Investigation for supporting detail."
    )

    with st.expander("Dataset coverage"):
        st.caption(
            f"{format_amount(counts['processes'])} business processes · "
            f"{format_amount(counts['vendors'])} vendors · "
            f"{format_amount(counts['controls'])} controls · "
            f"{format_amount(counts['kri_observations'])} KRI observations"
        )
