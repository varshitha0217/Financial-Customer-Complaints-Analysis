# Financial Customer Complaints Analysis

## Project overview

This project cleans and analyzes the supplied financial customer complaints data. It documents the data-quality decisions, validates response-service KPIs, presents evidence-based findings and recommendations, and provides SQL and Power BI implementation materials.

## Project structure

| File | Purpose |
|---|---|
| `lecture-file.csv` | Original source data; retained unchanged. |
| `analyze_complaints.py` | Reproducible cleaning, validation, Excel, PDF, and preview generation pipeline. |
| `requirements.txt` | Python package requirements for rerunning the pipeline. |
| `financial_complaints_cleaned.csv` | Cleaned analysis-ready data, with two derived response-day fields. |
| `Financial_Complaints_Cleaning_and_Analysis.xlsx` | Cleaned data, detailed cleaning log, KPI validation, and issue/product/company/month/channel summaries. |
| `analysis_queries.sql` | 12 explained MySQL 8+ analysis queries and a suggested table schema. |
| `Analysis_Report.pdf` | Analysis scope, cleaning and validation, KPIs, five findings, three recommendations, and limitations. |
| `PowerBI_DAX_Measures.txt` | DAX measures, date-table setup, formatting, and dashboard layout instructions. |
| `PowerBI_Dashboard_Guide.md` | Beginner-friendly Power BI Desktop import, typing, model, measure, visual, slicer, and save instructions. |
| `Dashboard_Preview.png` | Static dashboard preview; not an interactive Power BI report. |
| `AI_USAGE.md` | AI assistance and verification disclosure. |

## Tools

- Python 3.12
- pandas for CSV processing and independent KPI calculations
- openpyxl for Excel formatting
- ReportLab for the analysis PDF
- Matplotlib for the static dashboard preview
- MySQL 8+ for the supplied SQL analyses
- Power BI Desktop for the interactive report (manual authoring required)

## Reproduce the cleaning and analysis

From this folder, install the listed dependencies and execute:

```powershell
python -m pip install -r requirements.txt
python analyze_complaints.py
```

The script reads `lecture-file.csv` and rebuilds the cleaned CSV, Excel workbook, PDF, and PNG preview. It checks the source SHA-256 before and after processing and does not write to the original CSV. The source fingerprint observed in this run is:

`723f382c22156e7d845b33c363c4918cbfaf701d17efdca5fdf7945a7e501406`

### Cleaning and validation decisions

1. Read the original 5,000-row, 14-column CSV without changing it.
2. Removed 25 exact duplicate rows (identical across all original fields), leaving 4,975 rows.
3. Trimmed leading/trailing whitespace and collapsed repeated whitespace in text fields.
4. Standardized categorical labels to title case and state abbreviations to uppercase. Company-name capitalization follows the most common original spelling, preserving names such as `BluePeak Bank`.
5. Parsed received, due, and response dates as `YYYY-MM-DD`. Nonblank invalid dates are rejected; expected blank response dates for open cases remain missing.
6. Added `days_to_response` = response date minus received date, and `days_late` = positive days after due date (zero if early or on time). Both fields are blank for open complaints.
7. Validated unique complaint IDs, status/date consistency, nonnegative response duration, and the supplied timely flag against response and due dates.
8. Kept missing state and response-date values; no values were imputed.

## Verified dataset and KPIs

The cleaned data has 4,975 unique complaint IDs: 4,665 closed and 310 open. The response date is present for all closed records and absent for all open records. There are 49 missing state values and zero nonblank unparseable dates. The supplied timely-response flag matches the date-based due-date check for every closed record.

| KPI | Verified result |
|---|---:|
| Total complaints | 4,975 |
| Open / closed complaints | 310 / 4,665 |
| Average / median response time | 8.76 / 8 days |
| Timely closed responses | 4,202 / 4,665 (90.08%) |
| Late closed responses | 463 (9.92%) |
| Missing state values | 49 |

Definitions, checks, and additional counts are in the workbook's `KPI_Validation` sheet. The timely-response denominator is **closed complaints**. Average and median response times include only records with a response date.

## Evidence-based findings

1. Credit Card (1,191) and Checking Or Savings Account (1,054) complaints together account for 2,245 complaints (45.13%).
2. Unexpected Fees is the most common issue: 545 complaints (10.95%).
3. Overall timely response is 90.08% (4,202 of 4,665 closed); 463 closed cases were late. Mean response time is 8.76 days and median is 8 days.
4. Mortgage timely performance is 81.18% (496 of 611 closed), 8.90 percentage points below the overall rate; 115 Mortgage responses were late.
5. Timely performance ranges from 81.80% at Atlas Consumer Finance (481/588 closed timely) to 94.14% at OakBridge Services (562/597), a 12.33-point difference.

## Practical recommendations

1. Review fee disclosures, billing rules, and complaint handling for Unexpected Fees; monitor the category volume and rate after operational changes. The count identifies a priority but does not prove a cause.
2. Pilot an end-to-end Mortgage workflow review with due-date risk alerts and assigned escalation owners; compare progress to the observed 81.18% timely baseline.
3. Have lower-timeliness companies analyze late cases by issue and process step, and compare workflows with higher-performing peers. Track timely rate, late count, and response duration using consistent definitions.

These are descriptive findings, not evidence of causation. Company/product comparisons are not adjusted for case mix. October 2026 contains records only through October 15 and is a partial month.

## SQL analysis

`analysis_queries.sql` contains 12 commented queries: data/ID reconciliation, status, product and issue mix, average/median response time, timely-rate validation, product and company service performance, month/channel/state distributions, and open-case age. Import the cleaned CSV into MySQL using the suggested schema at the top of the file, preserving blanks as `NULL`, then run the queries.

## Power BI

Follow `PowerBI_Dashboard_Guide.md` for click-by-click instructions, correct data types, verified KPI baselines, chart field mappings, and slicer setup. `PowerBI_DAX_Measures.txt` contains the measures and DAX reference. `Dashboard_Preview.png` is a static image. **An interactive `.pbix` file is not included**; it must be created and saved in Power BI Desktop.

## AI usage

See `AI_USAGE.md` for the assistance scope and verification record.
