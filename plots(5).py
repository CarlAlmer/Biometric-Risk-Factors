import pandas as pd
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
    """
    chart_data = summary[
        ["department", "year", chart_metric]
    ].dropna().copy()

    if chart_data.empty:
        st.info("No comparison data available for the selected departments.")
        return

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
        "mark": {"type": "bar"},
        "encoding": {
            "x": {
                "field": "department",
                "type": "nominal",
                "title": "Department",
                "sort": None,
                "axis": {"labelAngle": 0},
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
                "axis": {"grid": True},
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
    if risk_df.empty:
        st.info("No risk factor data are available.")
        return

    chart_data = risk_df[
        ["Metric", "Percent Flagged"]
    ].dropna().copy()

    chart_spec = {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {
                "field": "Metric",
                "type": "nominal",
                "title": "Risk Factor",
                "sort": None,
                "axis": {"labelAngle": 0},
            },
            "y": {
                "field": "Percent Flagged",
                "type": "quantitative",
                "title": "Percent Flagged (%)",
                "scale": {"domainMin": 0},
            },
            "tooltip": [
                {
                    "field": "Metric",
                    "type": "nominal",
                    "title": "Risk Factor",
                },
                {
                    "field": "Percent Flagged",
                    "type": "quantitative",
                    "title": "Percent Flagged",
                    "format": ".1f",
                },
            ],
        },
    }

    st.vega_lite_chart(
        chart_data,
        chart_spec,
        use_container_width=True,
    )


def risk_factor_count_chart(risk_df):
    """
    Show the number of firefighter records flagged for each of the seven
    current risk factors. The x-axis uses the risk factor names rather than
    numeric 0-7 risk-factor-count categories.
    """
    if risk_df.empty:
        st.info("No risk factor counts are available.")
        return

    required_columns = {"Metric", "Count"}
    if not required_columns.issubset(risk_df.columns):
        st.info("Risk factor counts are not available.")
        return

    chart_data = risk_df[["Metric", "Count"]].dropna().copy()

    if chart_data.empty:
        st.info("No risk factor counts are available.")
        return

    # Keep the same logical order used in the risk-factor table.
    metric_order = [
        "BMI",
        "WAIST",
        "TC",
        "HDL",
        "RTO",
        "GLU",
        "Blood Pressure",
    ]

    chart_spec = {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {
                "field": "Metric",
                "type": "nominal",
                "title": "Risk Factor",
                "sort": metric_order,
                "axis": {"labelAngle": 0},
            },
            "y": {
                "field": "Count",
                "type": "quantitative",
                "title": "Number of Firefighters",
                "scale": {"domainMin": 0},
            },
            "tooltip": [
                {
                    "field": "Metric",
                    "type": "nominal",
                    "title": "Risk Factor",
                },
                {
                    "field": "Count",
                    "type": "quantitative",
                    "title": "Firefighters",
                },
            ],
        },
    }

    st.vega_lite_chart(
        chart_data,
        chart_spec,
        use_container_width=True,
    )

