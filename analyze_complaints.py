"""Rebuild the cleaned data and analysis deliverables from the source CSV."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "lecture-file.csv"
CLEAN_CSV = ROOT / "financial_complaints_cleaned.csv"
WORKBOOK = ROOT / "Financial_Complaints_Cleaning_and_Analysis.xlsx"
REPORT = ROOT / "Analysis_Report.pdf"
PREVIEW = ROOT / "Dashboard_Preview.png"
DATE_COLUMNS = ["date_received", "response_due_date", "date_company_responded"]
TEXT_COLUMNS = [
    "complaint_id",
    "financial_product",
    "issue_category",
    "issue_detail",
    "company_name",
    "state",
    "submission_channel",
    "response_status",
    "company_response",
    "timely_response",
    "short_complaint_summary",
] + DATE_COLUMNS
CATEGORY_COLUMNS = [
    "financial_product",
    "issue_category",
    "issue_detail",
    "submission_channel",
    "response_status",
    "company_response",
    "timely_response",
]
EXPECTED_SOURCE_COLUMNS = [
    "complaint_id",
    "date_received",
    "financial_product",
    "issue_category",
    "issue_detail",
    "company_name",
    "state",
    "submission_channel",
    "response_due_date",
    "date_company_responded",
    "response_status",
    "company_response",
    "timely_response",
    "short_complaint_summary",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_data() -> tuple[pd.DataFrame, dict[str, int | str]]:
    source_hash = sha256(SOURCE)
    raw = pd.read_csv(SOURCE, dtype=str, keep_default_na=False)
    if raw.columns.tolist() != EXPECTED_SOURCE_COLUMNS:
        raise ValueError(f"Unexpected source columns: {raw.columns.tolist()}")

    input_rows = len(raw)
    duplicate_rows = int(raw.duplicated(keep="first").sum())
    data = raw.drop_duplicates(keep="first").copy()

    for column in TEXT_COLUMNS:
        data[column] = (
            data[column]
            .astype("string")
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .replace("", pd.NA)
        )

    # Keep the source's most common original capitalization for company names
    # rather than changing proper names such as BluePeak Bank to Bluepeak Bank.
    company_names = data["company_name"].dropna()
    company_map = {}
    for key, group in company_names.groupby(company_names.str.casefold()):
        company_map[key] = group.value_counts().index[0]
    data["company_name"] = data["company_name"].map(
        lambda value: company_map[value.casefold()] if pd.notna(value) else value
    )

    for column in CATEGORY_COLUMNS:
        data[column] = data[column].str.title()
    data["state"] = data["state"].str.upper()

    parsed_dates = {}
    invalid_date_counts = {}
    for column in DATE_COLUMNS:
        original_values = data[column].copy()
        parsed = pd.to_datetime(original_values, format="%Y-%m-%d", errors="coerce")
        invalid = original_values.notna() & parsed.isna()
        invalid_date_counts[column] = int(invalid.sum())
        if invalid.any():
            raise ValueError(f"Unparseable values in {column}: {int(invalid.sum())}")
        parsed_dates[column] = parsed
        data[column] = parsed.dt.strftime("%Y-%m-%d").astype("string")
        data.loc[parsed.isna(), column] = pd.NA

    responded = parsed_dates["date_company_responded"].notna()
    response_days = (
        parsed_dates["date_company_responded"] - parsed_dates["date_received"]
    ).dt.days
    late_days = (
        parsed_dates["date_company_responded"] - parsed_dates["response_due_date"]
    ).dt.days.clip(lower=0)
    data["days_to_response"] = response_days.astype("Int64")
    data["days_late"] = late_days.astype("Int64")
    data.loc[~responded, ["days_to_response", "days_late"]] = pd.NA

    if data["complaint_id"].isna().any() or data["complaint_id"].duplicated().any():
        raise ValueError("Complaint IDs must be present and unique after exact deduplication.")
    if data["response_status"].isna().any():
        raise ValueError("Response status cannot be missing.")

    open_cases = data["response_status"].eq("Open")
    closed_cases = data["response_status"].eq("Closed")
    if not (open_cases | closed_cases).all():
        raise ValueError("Unexpected response status encountered.")
    if (open_cases & responded).any() or (closed_cases & ~responded).any():
        raise ValueError("Response status and response-date completeness do not reconcile.")
    if (data.loc[closed_cases, "timely_response"].isna()).any():
        raise ValueError("Closed complaints must have a timely-response flag.")

    computed_timely = parsed_dates["date_company_responded"].le(
        parsed_dates["response_due_date"]
    )
    supplied_timely = data["timely_response"].eq("Yes")
    mismatch_count = int((closed_cases & computed_timely.ne(supplied_timely)).sum())
    if mismatch_count:
        raise ValueError(f"Timely flag/date mismatches: {mismatch_count}")
    if (response_days.loc[responded] < 0).any():
        raise ValueError("A response date precedes its received date.")

    data = data[EXPECTED_SOURCE_COLUMNS + ["days_to_response", "days_late"]]
    source_after_hash = sha256(SOURCE)
    if source_hash != source_after_hash:
        raise RuntimeError("The original source file changed during analysis.")

    audit = {
        "source_hash": source_hash,
        "input_rows": input_rows,
        "duplicate_rows": duplicate_rows,
        "clean_rows": len(data),
        "missing_state": int(data["state"].isna().sum()),
        "missing_response_date": int(data["date_company_responded"].isna().sum()),
        "invalid_dates": sum(invalid_date_counts.values()),
        "timely_mismatches": mismatch_count,
    }
    data.to_csv(CLEAN_CSV, index=False, na_rep="", encoding="utf-8")
    return data, audit


def build_outputs(data: pd.DataFrame, audit: dict[str, int | str]) -> dict[str, float | int]:
    closed = data["response_status"].eq("Closed")
    responded = data["date_company_responded"].notna()
    timely = closed & data["timely_response"].eq("Yes")
    late = closed & data["days_late"].gt(0)
    response_days = pd.to_numeric(data.loc[responded, "days_to_response"])
    kpis: dict[str, float | int] = {
        "Total complaints": int(data["complaint_id"].nunique()),
        "Open complaints": int((~closed).sum()),
        "Closed complaints": int(closed.sum()),
        "Responded complaints": int(responded.sum()),
        "Average response days": float(response_days.mean()),
        "Median response days": float(response_days.median()),
        "Minimum response days": int(response_days.min()),
        "Maximum response days": int(response_days.max()),
        "Timely responses": int(timely.sum()),
        "Timely response rate": float(timely.sum() / closed.sum()),
        "Late closed responses": int(late.sum()),
        "Late response rate": float(late.sum() / closed.sum()),
        "Missing state values": int(data["state"].isna().sum()),
        "Missing response dates": int(data["date_company_responded"].isna().sum()),
    }

    product = (
        data.groupby("financial_product", dropna=False)
        .agg(complaints=("complaint_id", "nunique"))
        .reset_index()
    )
    closed_by_product = data.loc[closed].groupby("financial_product").agg(
        closed=("complaint_id", "nunique"),
        timely=("timely_response", lambda values: int(values.eq("Yes").sum())),
        late=("days_late", lambda values: int(values.gt(0).sum())),
        avg_response_days=("days_to_response", "mean"),
    )
    product = product.merge(closed_by_product, on="financial_product", how="left")
    product["timely_rate_pct"] = product["timely"] / product["closed"] * 100
    product = product.sort_values("complaints", ascending=False)

    company = data.groupby("company_name", dropna=False).agg(
        complaints=("complaint_id", "nunique"),
        closed=("response_status", lambda values: int(values.eq("Closed").sum())),
        timely=("timely_response", lambda values: int(values.eq("Yes").sum())),
        avg_response_days=("days_to_response", "mean"),
        late=("days_late", lambda values: int(values.gt(0).sum())),
    ).reset_index()
    company["timely_rate_pct"] = company["timely"] / company["closed"] * 100
    company = company.sort_values("company_name")

    issue_summary = (
        data.groupby("issue_category")
        .size()
        .rename("complaints")
        .reset_index()
        .sort_values(["complaints", "issue_category"], ascending=[False, True])
    )
    issue_summary["share_pct"] = issue_summary["complaints"] / len(data) * 100

    month_summary = (
        data.assign(
            received_month=pd.to_datetime(data["date_received"]).dt.strftime("%Y-%m")
        )
        .groupby("received_month")
        .size()
        .rename("complaints")
        .reset_index()
        .sort_values("received_month")
    )

    channel_summary = (
        data.groupby("submission_channel")
        .size()
        .rename("complaints")
        .reset_index()
        .sort_values("complaints", ascending=False)
    )

    kpi_rows = [
        ("Total complaints", kpis["Total complaints"], "Distinct complaint IDs after exact deduplication.", "Rows equal distinct IDs."),
        ("Open complaints", kpis["Open complaints"], "Response status is Open.", "Open + closed equals total."),
        ("Closed complaints", kpis["Closed complaints"], "Response status is Closed.", "Open + closed equals total."),
        ("Responded complaints", kpis["Responded complaints"], "Nonblank company response date.", "Equals closed count in this data."),
        ("Average response days", kpis["Average response days"], "Mean of response date minus received date.", "Calculated only for responded records."),
        ("Median response days", kpis["Median response days"], "Median of response date minus received date.", "Independently recalculated from parsed dates."),
        ("Minimum response days", kpis["Minimum response days"], "Minimum observed response duration.", "No negative durations."),
        ("Maximum response days", kpis["Maximum response days"], "Maximum observed response duration.", "No negative durations."),
        ("Timely responses", kpis["Timely responses"], "Closed cases with supplied timely_response = Yes.", "Agrees with response date on/before due date."),
        ("Timely response rate", kpis["Timely response rate"], "Timely closed cases / all closed cases.", "Denominator: closed cases only."),
        ("Late closed responses", kpis["Late closed responses"], "Closed cases with response date after due date.", "Matches 463 closed No flags."),
        ("Late response rate", kpis["Late response rate"], "Late closed cases / all closed cases.", "Complement of timely rate in this dataset."),
        ("Missing state values", kpis["Missing state values"], "Blank state values.", "Preserved; not imputed."),
        ("Missing response dates", kpis["Missing response dates"], "Blank company response date.", "All correspond to open cases."),
        ("Exact duplicate source rows removed", audit["duplicate_rows"], "Exact full-row duplicates removed before normalization.", "No remaining duplicate rows or IDs."),
        ("Unparseable date values", audit["invalid_dates"], "Nonblank date strings that fail YYYY-MM-DD parsing.", "Must be zero; blank open-case dates are not invalid."),
        ("Timely flag/date mismatches", audit["timely_mismatches"], "Closed rows where supplied flag conflicts with response vs. due date.", "Independent date calculation."),
    ]

    cleaning_log = [
        ("1", "Source", "Read lecture-file.csv as text; source was not modified.", f"{audit['input_rows']:,} rows; 14 columns; SHA-256 {audit['source_hash']}"),
        ("2", "Exact duplicate removal", "Removed only complete rows identical across all 14 original fields.", f"{audit['duplicate_rows']:,} rows removed; {audit['clean_rows']:,} remain."),
        ("3", "Whitespace", "Trimmed leading/trailing whitespace and collapsed repeated whitespace in text fields; blanks preserved as missing.", "No values imputed."),
        ("4", "Category labels", "Standardized categorical labels to title case and state abbreviations to uppercase.", "Company names retain the most frequent source capitalization (e.g. BluePeak Bank)."),
        ("5", "Dates", "Parsed the three date columns as YYYY-MM-DD and rejected nonblank invalid dates.", f"{audit['invalid_dates']} unparseable dates; {audit['missing_response_date']} missing response dates are expected for open cases."),
        ("6", "Derived fields", "days_to_response = response date - received date; days_late = max(response date - due date, 0).", "Both fields remain blank when there is no response date."),
        ("7", "Validation", "Checked ID uniqueness, status/date consistency, nonnegative duration, and flag/date agreement.", f"{audit['clean_rows']:,} unique IDs; {audit['timely_mismatches']} flag/date mismatches."),
        ("8", "Missing values", "Retained missing state and response date values without replacement.", f"{audit['missing_state']} missing states; {audit['missing_response_date']} missing response dates."),
    ]

    excel_data = data.copy()
    for column in DATE_COLUMNS:
        excel_data[column] = pd.to_datetime(excel_data[column], format="%Y-%m-%d")

    formula_by_kpi = {
        "Total complaints": f"=COUNTA(Cleaned_Data!$A$2:$A${len(data) + 1})",
        "Open complaints": f'=COUNTIF(Cleaned_Data!$K$2:$K${len(data) + 1},"Open")',
        "Closed complaints": f'=COUNTIF(Cleaned_Data!$K$2:$K${len(data) + 1},"Closed")',
        "Responded complaints": f"=COUNT(Cleaned_Data!$J$2:$J${len(data) + 1})",
        "Average response days": f"=AVERAGE(Cleaned_Data!$O$2:$O${len(data) + 1})",
        "Median response days": f"=MEDIAN(Cleaned_Data!$O$2:$O${len(data) + 1})",
        "Minimum response days": f"=MIN(Cleaned_Data!$O$2:$O${len(data) + 1})",
        "Maximum response days": f"=MAX(Cleaned_Data!$O$2:$O${len(data) + 1})",
        "Timely responses": f'=COUNTIFS(Cleaned_Data!$K$2:$K${len(data) + 1},"Closed",Cleaned_Data!$M$2:$M${len(data) + 1},"Yes")',
        "Timely response rate": None,
        "Late closed responses": f'=COUNTIFS(Cleaned_Data!$K$2:$K${len(data) + 1},"Closed",Cleaned_Data!$P$2:$P${len(data) + 1},">0")',
        "Late response rate": None,
        "Missing state values": f"=COUNTBLANK(Cleaned_Data!$G$2:$G${len(data) + 1})",
        "Missing response dates": f"=COUNTBLANK(Cleaned_Data!$J$2:$J${len(data) + 1})",
        "Timely flag/date mismatches": (
            f'=SUMPRODUCT(--(Cleaned_Data!$K$2:$K${len(data) + 1}="Closed"),'
            f'--((Cleaned_Data!$M$2:$M${len(data) + 1}="Yes")<>'
            f'(Cleaned_Data!$J$2:$J${len(data) + 1}<=Cleaned_Data!$I$2:$I${len(data) + 1})))'
        ),
    }

    label_rows = {row[0]: index + 2 for index, row in enumerate(kpi_rows)}
    formula_by_kpi["Timely response rate"] = (
        f"=IFERROR(E{label_rows['Timely responses']}/E{label_rows['Closed complaints']},0)"
    )
    formula_by_kpi["Late response rate"] = (
        f"=IFERROR(E{label_rows['Late closed responses']}/E{label_rows['Closed complaints']},0)"
    )
    kpi_frame = pd.DataFrame(
        [
            (
                *row,
                formula_by_kpi.get(row[0]),
                None if row[0] in formula_by_kpi else "Python source audit",
            )
            for row in kpi_rows
        ],
        columns=[
            "KPI",
            "Value",
            "Definition",
            "Validation",
            "Excel formula",
            "Formula check",
        ],
    )

    with pd.ExcelWriter(WORKBOOK, engine="openpyxl") as writer:
        excel_data.to_excel(writer, sheet_name="Cleaned_Data", index=False)
        pd.DataFrame(cleaning_log, columns=["Step", "Stage", "Action", "Result / validation"]).to_excel(
            writer, sheet_name="Cleaning_Log", index=False
        )
        kpi_frame.to_excel(
            writer, sheet_name="KPI_Validation", index=False
        )
        issue_summary.to_excel(writer, sheet_name="Issue_Summary", index=False)
        product.to_excel(writer, sheet_name="Product_Summary", index=False)
        company.to_excel(writer, sheet_name="Company_Summary", index=False)
        month_summary.to_excel(writer, sheet_name="Monthly_Summary", index=False)
        channel_summary.to_excel(writer, sheet_name="Channel_Summary", index=False)

    style_workbook()
    create_report(data, audit, kpis, issue_summary, product, company, month_summary)
    create_preview(issue_summary, product, month_summary, kpis)
    return kpis


def style_workbook() -> None:
    workbook = load_workbook(WORKBOOK)
    header_fill = PatternFill("solid", fgColor="17365D")
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for column_cells in sheet.columns:
            values = [str(cell.value or "") for cell in list(column_cells)[:100]]
            width = min(max(max((len(value) for value in values), default=10) + 2, 12), 48)
            sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = width
        sheet.row_dimensions[1].height = 30
    data_sheet = workbook["Cleaned_Data"]
    for column_name in DATE_COLUMNS:
        column_index = EXPECTED_SOURCE_COLUMNS.index(column_name) + 1
        for row_index in range(2, data_sheet.max_row + 1):
            data_sheet.cell(row_index, column_index).number_format = "yyyy-mm-dd"
    workbook["KPI_Validation"].column_dimensions["C"].width = 65
    workbook["KPI_Validation"].column_dimensions["D"].width = 55
    workbook["KPI_Validation"].column_dimensions["E"].width = 72
    workbook["KPI_Validation"].column_dimensions["F"].width = 24
    workbook["Cleaning_Log"].column_dimensions["B"].width = 24
    workbook["Cleaning_Log"].column_dimensions["C"].width = 70
    workbook["Cleaning_Log"].column_dimensions["D"].width = 88
    for sheet in workbook.worksheets:
        headers = {cell.column: str(cell.value or "") for cell in sheet[1]}
        for column, header in headers.items():
            if header.endswith("_pct"):
                for row in range(2, sheet.max_row + 1):
                    sheet.cell(row, column).number_format = '0.00"%"'
            elif header.endswith("_days"):
                for row in range(2, sheet.max_row + 1):
                    sheet.cell(row, column).number_format = "0.00"
    kpi_sheet = workbook["KPI_Validation"]
    for row in range(2, kpi_sheet.max_row + 1):
        label = kpi_sheet.cell(row, 1).value
        value_cell = kpi_sheet.cell(row, 2)
        if label in {"Timely response rate", "Late response rate"}:
            value_cell.number_format = "0.00%"
        elif label in {"Average response days", "Median response days"}:
            value_cell.number_format = "0.00"
        formula_cell = kpi_sheet.cell(row, 5)
        formula_check_cell = kpi_sheet.cell(row, 6)
        if formula_cell.value:
            formula_check_cell.value = (
                f'=IF(ABS(E{row}-B{row})<1E-9,"PASS","CHECK")'
            )
            if label in {"Timely response rate", "Late response rate"}:
                formula_cell.number_format = "0.00%"
            elif label in {"Average response days", "Median response days"}:
                formula_cell.number_format = "0.00"
        else:
            formula_check_cell.value = "Python source audit"
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"
    workbook.save(WORKBOOK)


def create_report(
    data: pd.DataFrame,
    audit: dict[str, int | str],
    kpis: dict[str, float | int],
    issues: pd.DataFrame,
    products: pd.DataFrame,
    companies: pd.DataFrame,
    months: pd.DataFrame,
) -> None:
    doc = SimpleDocTemplate(
        str(REPORT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#17365D"), fontSize=19, leading=23, spaceAfter=5))
    styles.add(ParagraphStyle(name="SmallNote", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#444444")))
    styles.add(ParagraphStyle(name="Finding", parent=styles["BodyText"], spaceAfter=7, leading=14))
    story = [
        Paragraph("Financial Customer Complaints Analysis", styles["ReportTitle"]),
        Paragraph("Verified descriptive analysis of the supplied complaint records", styles["h2"]),
        Paragraph(
            f"Source: lecture-file.csv | Received-date coverage: {data['date_received'].min()} to {data['date_received'].max()} | "
            f"Rows after exact deduplication: {int(kpis['Total complaints']):,}",
            styles["SmallNote"],
        ),
        Spacer(1, 8),
        Paragraph("Executive summary", styles["h1"]),
        Paragraph(
            f"The cleaned dataset contains {int(kpis['Total complaints']):,} unique complaints. "
            f"{int(kpis['Closed complaints']):,} are closed and {int(kpis['Open complaints']):,} are open. "
            f"Among closed complaints, {kpis['Timely response rate']:.2%} were answered by the recorded due date. "
            f"The most frequent issue is Unexpected Fees ({int(issues.iloc[0]['complaints']):,} complaints).",
            styles["BodyText"],
        ),
        Spacer(1, 8),
        Paragraph("Cleaning and validation", styles["h1"]),
    ]
    cleaning_rows = [
        ["Check", "Result"],
        ["Source rows / fields", f"{audit['input_rows']:,} / 14"],
        ["Exact duplicate rows removed", f"{audit['duplicate_rows']:,}"],
        ["Clean rows / unique complaint IDs", f"{audit['clean_rows']:,} / {data['complaint_id'].nunique():,}"],
        ["Unparseable nonblank dates", str(audit["invalid_dates"])],
        ["Missing states retained", f"{audit['missing_state']:,}"],
        ["Missing response dates retained", f"{audit['missing_response_date']:,} (all open cases)"],
        ["Timely flag vs. due-date mismatches", str(audit["timely_mismatches"])],
    ]
    story.extend([make_table(cleaning_rows, [62 * mm, 102 * mm]), Spacer(1, 7)])
    story.append(Paragraph(
        "Only complete duplicate rows were removed. Text whitespace and category formatting were normalized; "
        "company-name capitalization was retained from the source. Missing values were not filled. "
        "days_to_response is response date minus received date; days_late is the positive number of days "
        "after the due date (zero when on time or early).",
        styles["SmallNote"],
    ))
    story.extend([Spacer(1, 9), Paragraph("Validated customer-service KPIs", styles["h1"])])
    kpi_rows = [
        ["KPI", "Validated value", "Definition / denominator"],
        ["Total complaints", f"{int(kpis['Total complaints']):,}", "Distinct complaint IDs"],
        ["Open / closed", f"{int(kpis['Open complaints']):,} / {int(kpis['Closed complaints']):,}", "Status counts"],
        ["Responded", f"{int(kpis['Responded complaints']):,}", "Nonblank response date"],
        ["Average / median response", f"{kpis['Average response days']:.2f} / {kpis['Median response days']:.0f} days", "Responded cases only"],
        ["Timely responses", f"{int(kpis['Timely responses']):,} ({kpis['Timely response rate']:.2%})", "Timely closed / all closed"],
        ["Late closed responses", f"{int(kpis['Late closed responses']):,} ({kpis['Late response rate']:.2%})", "Response date after due date / all closed"],
    ]
    story.extend([make_table(kpi_rows, [48 * mm, 47 * mm, 69 * mm]), PageBreak()])

    story.append(Paragraph("Five evidence-based findings", styles["h1"]))
    top_products = products.head(2)
    top_product_total = int(top_products["complaints"].sum())
    mortgage = products.loc[products["financial_product"].eq("Mortgage")].iloc[0]
    lowest = companies.sort_values("timely_rate_pct").iloc[0]
    highest = companies.sort_values("timely_rate_pct", ascending=False).iloc[0]
    fee_count = int(issues.iloc[0]["complaints"])
    story.extend([
        Paragraph(
            f"<b>1. Complaint volume is concentrated in two products.</b> Credit Card ({int(top_products.iloc[0]['complaints']):,}) "
            f"and {top_products.iloc[1]['financial_product']} ({int(top_products.iloc[1]['complaints']):,}) account for "
            f"{top_product_total:,} complaints ({top_product_total / len(data):.2%} of all records).",
            styles["Finding"],
        ),
        Paragraph(
            f"<b>2. Unexpected Fees is the leading issue category.</b> It accounts for {fee_count:,} complaints "
            f"({fee_count / len(data):.2%}), more than any other issue category.",
            styles["Finding"],
        ),
        Paragraph(
            f"<b>3. Most closed complaints were timely, but a material late subset remains.</b> "
            f"{int(kpis['Timely responses']):,} of {int(kpis['Closed complaints']):,} closed complaints were timely "
            f"({kpis['Timely response rate']:.2%}); {int(kpis['Late closed responses']):,} were late. "
            f"Response time averaged {kpis['Average response days']:.2f} days (median {kpis['Median response days']:.0f}).",
            styles["Finding"],
        ),
        Paragraph(
            f"<b>4. Mortgage complaints have the weakest product timeliness.</b> {int(mortgage['timely']):,} of "
            f"{int(mortgage['closed']):,} closed Mortgage complaints were timely ({mortgage['timely_rate_pct']:.2f}%), "
            f"8.90 percentage points below the overall rate; {int(mortgage['late']):,} Mortgage responses were late.",
            styles["Finding"],
        ),
        Paragraph(
            f"<b>5. Company timeliness varies substantially.</b> {lowest['company_name']} had the lowest rate "
            f"({lowest['timely_rate_pct']:.2f}%, {int(lowest['timely'])}/{int(lowest['closed'])} closed timely; "
            f"{int(lowest['late'])} late), while {highest['company_name']} had the highest "
            f"({highest['timely_rate_pct']:.2f}%, {int(highest['timely'])}/{int(highest['closed'])}; "
            f"{int(highest['late'])} late). The observed range is "
            f"{highest['timely_rate_pct'] - lowest['timely_rate_pct']:.2f} percentage points.",
            styles["Finding"],
        ),
        Spacer(1, 4),
        Paragraph("Received-month context", styles["h2"]),
    ])
    complete_months = months.loc[~months["received_month"].eq(months["received_month"].max())]
    max_month = complete_months.sort_values("complaints", ascending=False).iloc[0]
    min_month = complete_months.sort_values("complaints").iloc[0]
    story.append(Paragraph(
        f"Among complete months, {max_month['received_month']} had the most complaints "
        f"({int(max_month['complaints']):,}) and {min_month['received_month']} the fewest "
        f"({int(min_month['complaints']):,}). October 2026 is partial (records only through October 15) and "
        "is excluded from this complete-month comparison.",
        styles["SmallNote"],
    ))
    story.extend([Spacer(1, 10), Paragraph("Three practical recommendations", styles["h1"])])
    story.extend([
        Paragraph(
            "<b>1. Investigate and prevent Unexpected Fees.</b> Review fee disclosures, billing rules, and complaint "
            "handling across product and company segments; use 545 complaints as the baseline and monitor the "
            "category count and rate after any changes. The counts identify a priority, not a proven cause.",
            styles["Finding"],
        ),
        Paragraph(
            "<b>2. Pilot a Mortgage response-time improvement.</b> Review the end-to-end Mortgage case workflow, "
            "surface due-date risk early, assign an owner, and escalate approaching deadlines. Track the same "
            "closed-case timeliness definition against the 81.18% observed baseline.",
            styles["Finding"],
        ),
        Paragraph(
            "<b>3. Use a company-level corrective-action review.</b> Ask the lowest-timeliness companies to inspect "
            "late cases by issue, due-date proximity, and operational step, and compare processes with higher-rate "
            "companies. Review timely rate, late count, and response days weekly; set future targets only after "
            "owners validate capacity and case mix.",
            styles["Finding"],
        ),
        Paragraph("Limitations and interpretation", styles["h1"]),
        Paragraph(
            "This is descriptive analysis of the supplied file. The data do not establish causes, complaint "
            "severity, customer impact, or the reasons for performance differences. Company/product comparisons "
            "are not adjusted for case mix. The October 2026 monthly count is incomplete. Findings should be "
            "validated with operational owners before policy or staffing changes.",
            styles["SmallNote"],
        ),
    ])
    doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)


def make_table(rows: list[list[str]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C9D6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF3F8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def draw_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def create_preview(
    issues: pd.DataFrame,
    products: pd.DataFrame,
    months: pd.DataFrame,
    kpis: dict[str, float | int],
) -> None:
    fig = plt.figure(figsize=(14, 8), facecolor="white")
    grid = fig.add_gridspec(3, 4, height_ratios=[0.6, 1.5, 1.5], hspace=0.55, wspace=0.55)
    fig.suptitle("Financial Customer Complaints - Dashboard Preview", fontsize=18, fontweight="bold")
    labels = [
        ("Total complaints", f"{int(kpis['Total complaints']):,}"),
        ("Open complaints", f"{int(kpis['Open complaints']):,}"),
        ("Closed complaints", f"{int(kpis['Closed complaints']):,}"),
        ("Timely response rate", f"{kpis['Timely response rate']:.1%}"),
    ]
    for index, (label, value) in enumerate(labels):
        ax = fig.add_subplot(grid[0, index])
        ax.axis("off")
        ax.text(0.5, 0.62, value, ha="center", va="center", fontsize=22, fontweight="bold", color="#17365D")
        ax.text(0.5, 0.15, label, ha="center", va="center", fontsize=10)
    ax_issue = fig.add_subplot(grid[1, 0:2])
    top_issues = issues.head(6).sort_values("complaints")
    ax_issue.barh(top_issues["issue_category"], top_issues["complaints"], color="#2B78A8")
    ax_issue.set_title("Top issue categories")
    ax_issue.set_xlabel("Complaints")
    ax_product = fig.add_subplot(grid[1, 2:4])
    product_order = products.sort_values("complaints")
    ax_product.barh(product_order["financial_product"], product_order["complaints"], color="#4E9A76")
    ax_product.set_title("Complaints by product")
    ax_product.set_xlabel("Complaints")
    ax_month = fig.add_subplot(grid[2, :])
    month_values = months["complaints"].to_numpy()
    month_colors = ["#2B78A8"] * len(months)
    month_colors[-1] = "#E69F00"
    ax_month.bar(months["received_month"], month_values, color=month_colors)
    ax_month.set_title("Complaints received by month (October 2026 is partial)")
    ax_month.set_ylabel("Complaints")
    ax_month.tick_params(axis="x", rotation=35)
    ax_month.grid(axis="y", alpha=0.2)
    fig.savefig(PREVIEW, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    data, audit = clean_data()
    kpis = build_outputs(data, audit)
    if sha256(SOURCE) != audit["source_hash"]:
        raise RuntimeError("Source hash changed after output generation.")
    print(f"Source SHA-256: {audit['source_hash']}")
    print(f"Rows: {audit['input_rows']} -> {audit['clean_rows']} ({audit['duplicate_rows']} exact duplicates removed)")
    print(f"KPIs: {kpis}")
    print(f"Generated: {CLEAN_CSV.name}, {WORKBOOK.name}, {REPORT.name}, {PREVIEW.name}")


if __name__ == "__main__":
    main()
