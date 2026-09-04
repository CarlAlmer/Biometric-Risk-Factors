import streamlit as st


def metric_distribution_chart(df, metric):
    chart_df = df[[metric]].dropna()

    if not chart_df.empty:
        st.bar_chart(chart_df[metric].value_counts().sort_index())
    else:
        st.info("No values available for this metric.")


def department_comparison_chart(summary, chart_metric):
    """
    Display department values with each year as a separate side-by-side bar.

    Vega-Lite's xOffset encoding is used instead of st.bar_chart because
    st.bar_chart can stack multiple year series depending on the Streamlit
    version being used by the deployed app.
    """
    chart_data = summary[
        ["department", "year", chart_metric]
    ].dropna().copy()

    if chart_data.empty:
        st.info("No comparison data available for the selected departments.")
        return

    # Treat year as a category so each year receives its own bar and legend item.
    chart_data["year"] = chart_data["year"].astype(int).astype(str)

    metric_labels = {
        "Avg_Risk_Factors": "Average Risk Factors",
        "Avg_BMI": "Average BMI",
        "Avg_WAIST": "Average Waist",
        "Avg_TC": "Average Total Cholesterol",
        "Avg_HDL": "Average HDL",
        "Avg_RTO": "Average TC/HDL Ratio",
        "Avg_GLU": "Average Glucose",
        "Avg_SYS": "Average Systolic BP",
        "Avg_DIA": "Average Diastolic BP",
    }

    y_title = metric_labels.get(
        chart_metric,
        chart_metric.replace("_", " ").title(),
    )

    chart_spec = {
        "mark": {
            "type": "bar",
        },
        "encoding": {
            "x": {
                "field": "department",
                "type": "nominal",
                "title": "Department",
                "sort": None,
                "axis": {
                    "labelAngle": 0,
                },
            },
            "xOffset": {
                "field": "year",
                "type": "nominal",
                "sort": "ascending",
            },
            "y": {
                "field": chart_metric,
                "type": "quantitative",
                "title": y_title,
                "axis": {
                    "grid": True,
                },
            },
            "color": {
                "field": "year",
                "type": "nominal",
                "title": "Year",
                "sort": "ascending",
            },
            "tooltip": [
                {
                    "field": "department",
                    "type": "nominal",
                    "title": "Department",
                },
                {
                    "field": "year",
                    "type": "nominal",
                    "title": "Year",
                },
                {
                    "field": chart_metric,
                    "type": "quantitative",
                    "title": y_title,
                    "format": ".2f",
                },
            ],
        },
    }

    st.vega_lite_chart(
        chart_data,
        chart_spec,
        use_container_width=True,
    )


def risk_factor_bar_chart(risk_df):
    if not risk_df.empty:
        st.bar_chart(risk_df.set_index("Metric")["Percent Flagged"])


def risk_factor_count_chart(df):
    if "risk_factor_count" in df.columns:
        st.bar_chart(df["risk_factor_count"].value_counts().sort_index())
    else:
        st.info("Risk factor counts are not available.")
