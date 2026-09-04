import pandas as pd


METRIC_COLUMNS = ["BMI", "WAIST", "TC", "HDL", "RTO", "GLU", "SYS", "DIA"]

# Blood pressure is intentionally treated as ONE risk factor.
# A record is flagged for BP risk only when BOTH:
#   SYS >= 130 AND DIA >= 80
RISK_RULES = {
    "BMI": (30, "high"),
    "WAIST": (40, "high"),
    "TC": (200, "high"),
    "HDL": (40, "low"),
    "RTO": (5, "high"),
    "GLU": (100, "high"),
    "BP": ((130, 80), "both_high"),
}


def prepare_numeric_columns(df):
    out = df.copy()
    for col in METRIC_COLUMNS + ["Age", "year"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def add_risk_flags(df):
    out = df.copy()

    for metric, (cutoff, direction) in RISK_RULES.items():
        if metric == "BP":
            if "SYS" in out.columns and "DIA" in out.columns:
                sys_cutoff, dia_cutoff = cutoff
                out["BP_risk"] = (
                    (out["SYS"] >= sys_cutoff)
                    & (out["DIA"] >= dia_cutoff)
                )
            continue

        if metric not in out.columns:
            continue

        if direction == "high":
            out[f"{metric}_risk"] = out[metric] >= cutoff
        else:
            out[f"{metric}_risk"] = out[metric] < cutoff

    risk_cols = [c for c in out.columns if c.endswith("_risk")]
    out["risk_factor_count"] = out[risk_cols].sum(axis=1) if risk_cols else 0
    return out


def risk_percent(df, metric):
    if df.empty:
        return None

    cutoff, direction = RISK_RULES[metric]

    if metric == "BP":
        if "SYS" not in df.columns or "DIA" not in df.columns:
            return None

        values = df[["SYS", "DIA"]].dropna()
        if values.empty:
            return None

        sys_cutoff, dia_cutoff = cutoff
        return (
            (values["SYS"] >= sys_cutoff)
            & (values["DIA"] >= dia_cutoff)
        ).mean() * 100

    if metric not in df.columns:
        return None

    values = df[metric].dropna()

    if values.empty:
        return None

    if direction == "high":
        return (values >= cutoff).mean() * 100

    return (values < cutoff).mean() * 100


def summarize_by_department(df):
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["department", "year"], dropna=False)

    summary = grouped.agg(
        Records=("id", "count"),
        Avg_Age=("Age", "mean"),
        Avg_BMI=("BMI", "mean"),
        Avg_WAIST=("WAIST", "mean"),
        Avg_TC=("TC", "mean"),
        Avg_HDL=("HDL", "mean"),
        Avg_RTO=("RTO", "mean"),
        Avg_GLU=("GLU", "mean"),
        Avg_SYS=("SYS", "mean"),
        Avg_DIA=("DIA", "mean"),
        Avg_Risk_Factors=("risk_factor_count", "mean"),
    ).reset_index()

    for metric in RISK_RULES:
        summary[f"Pct_{metric}_Risk"] = grouped.apply(
            lambda g, m=metric: risk_percent(g, m),
            include_groups=False
        ).values

    return summary


def apply_filters(df, departments, years, age_range):
    out = df.copy()

    if departments:
        out = out[out["department"].isin(departments)]

    if years:
        out = out[out["year"].isin(years)]

    if "Age" in out.columns and age_range:
        out = out[(out["Age"] >= age_range[0]) & (out["Age"] <= age_range[1])]

    return out


def style_risk(val):
    try:
        v = float(val)
        if v >= 50:
            return "color: #C8102E; font-weight: 700"
        if v >= 25:
            return "color: #B36B00; font-weight: 700"
    except Exception:
        pass
    return ""
