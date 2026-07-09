import streamlit as st


def metric_distribution_chart(df, metric):
    chart_df = df[[metric]].dropna()
    if not chart_df.empty:
        st.bar_chart(chart_df[metric].value_counts().sort_index())
    else:
        st.info("No values available for this metric.")


def department_comparison_chart(summary, chart_metric):
    chart_data = summary.pivot_table(
        index="department",
        columns="year",
        values=chart_metric,
        aggfunc="mean"
    )
    st.bar_chart(chart_data)


def risk_factor_bar_chart(risk_df):
    if not risk_df.empty:
        st.bar_chart(risk_df.set_index("Metric")["Percent Flagged"])


def risk_factor_count_chart(df):
    if "risk_factor_count" in df.columns:
        st.bar_chart(df["risk_factor_count"].value_counts().sort_index())
    else:
        st.info("Risk factor counts are not available.")
