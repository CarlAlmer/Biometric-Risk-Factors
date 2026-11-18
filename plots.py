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


def risk_factor_count_chart(df):
    """
    Show how many firefighter records have 0 through 7 total risk factors.

    The dashboard now has exactly seven risk factors:
      1. BMI
      2. Waist
      3. Total Cholesterol
      4. HDL
      5. TC/HDL Ratio
      6. Glucose
      7. Blood Pressure

    If risk_factor_count is unexpectedly missing, reconstruct it from the
    seven current risk flags instead of showing an unavailable message.
    """
    if df.empty:
        st.info("No records are available for the selected filters.")
        return

    chart_df = df.copy()

    if "risk_factor_count" not in chart_df.columns:
        risk_cols = [
            "BMI_risk",
            "WAIST_risk",
            "TC_risk",
            "HDL_risk",
            "RTO_risk",
            "GLU_risk",
            "BP_risk",
        ]

        available_risk_cols = [
            col for col in risk_cols if col in chart_df.columns
        ]

        if not available_risk_cols:
            st.info("Risk factor counts are not available.")
            return

        chart_df["risk_factor_count"] = (
            chart_df[available_risk_cols]
            .fillna(False)
            .astype(int)
            .sum(axis=1)
        )

    counts = (
        chart_df["risk_factor_count"]
        .dropna()
        .astype(int)
        .value_counts()
        .reindex(range(0, 8), fill_value=0)
        .rename_axis("Risk Factor Count")
        .reset_index(name="Firefighters")
    )

    counts["Risk Factor Count"] = counts["Risk Factor Count"].astype(str)

    chart_spec = {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {
                "field": "Risk Factor Count",
                "type": "ordinal",
                "title": "Number of Risk Factors",
                "sort": [str(i) for i in range(8)],
                "axis": {"labelAngle": 0},
            },
            "y": {
                "field": "Firefighters",
                "type": "quantitative",
                "title": "Number of Firefighters",
                "scale": {"domainMin": 0},
            },
            "tooltip": [
                {
                    "field": "Risk Factor Count",
                    "type": "ordinal",
                    "title": "Risk Factors",
                },
                {
                    "field": "Firefighters",
                    "type": "quantitative",
                    "title": "Firefighters",
                },
            ],
        },
    }

    st.vega_lite_chart(
        counts,
        chart_spec,
        use_container_width=True,
    )



def department_risk_heatmap_chart(chart_df, value_column="Count"):
    """Heatmap with labeled cells, including zero counts."""
    if chart_df.empty:
        st.info("No risk factor data for these selections.")
        return
    chart_df = chart_df.copy()
    chart_df["Department / Year"] = chart_df["Department"] + " (" + chart_df["Year"] + ")"
    labels = ["BMI", "Waist", "Total Cholesterol", "HDL", "TC/HDL Ratio", "Glucose", "Blood Pressure"]
    base = {
        "x": {"field": "Department / Year", "type": "nominal", "title": "Department (Year)", "sort": None, "axis": {"labelAngle": -35}},
        "y": {"field": "Risk Factor", "type": "nominal", "title": "Risk Factor", "sort": labels},
    }
    tooltip = [
        {"field": "Department", "type": "nominal"},
        {"field": "Year", "type": "nominal"},
        {"field": "Risk Factor", "type": "nominal"},
        {"field": "Count", "type": "quantitative", "title": "Firefighters flagged"},
        {"field": "Records with Data", "type": "quantitative"},
        {"field": "Percent", "type": "quantitative", "format": ".1f", "title": "Percent flagged"},
    ]
    spec = {
        "height": 300,
        "layer": [
            {"mark": {"type": "rect", "cornerRadius": 3}, "encoding": {
                **base, "color": {"field": value_column, "type": "quantitative",
                    "title": "Firefighters flagged" if value_column == "Count" else "Percent flagged (%)",
                    "scale": {"scheme": "reds", "domainMin": 0}}, "tooltip": tooltip}},
            {"mark": {"type": "text", "fontSize": 12}, "encoding": {
                **base, "text": {"field": value_column, "type": "quantitative", "format": ".0f" if value_column == "Count" else ".1f"},
                "color": {"condition": {"test": f"datum['{value_column}'] > {chart_df[value_column].max() * .55 if chart_df[value_column].notna().any() else 0}", "value": "white"}, "value": "#202020"},
            }},
        ],
    }
    st.vega_lite_chart(chart_df, spec, use_container_width=True)


def department_risk_distribution_chart(distribution_df, value_column="Firefighters"):
    if distribution_df.empty:
        st.info("No records for these selections.")
        return
    chart_df = distribution_df.copy()
    chart_df["Department / Year"] = chart_df["Department"] + " (" + chart_df["Year"] + ")"
    spec = {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "Risk Factors", "type": "ordinal", "sort": list(range(8)), "title": "Number of Risk Factors"},
            "xOffset": {"field": "Department / Year", "type": "nominal"},
            "y": {"field": value_column, "type": "quantitative", "title": "Number of Firefighters" if value_column == "Firefighters" else "Percent of Records (%)", "scale": {"domainMin": 0}},
            "color": {"field": "Department / Year", "type": "nominal", "title": "Department (Year)"},
            "tooltip": [
                {"field": "Department", "type": "nominal"}, {"field": "Year", "type": "nominal"},
                {"field": "Risk Factors", "type": "ordinal"},
                {"field": "Firefighters", "type": "quantitative"},
                {"field": "Percent", "type": "quantitative", "format": ".1f"},
            ],
        },
    }
    st.vega_lite_chart(chart_df, spec, use_container_width=True)
