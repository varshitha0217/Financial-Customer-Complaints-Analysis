# AI Usage and Verification

## AI assistance

AI assistance was used to review the project folder, identify inconsistencies in existing documentation and analysis, propose analysis structure, draft SQL/DAX guidance, and help implement the reproducible Python pipeline and project documentation. AI assistance did not supply or augment the customer complaint records. No external data or credentials were used.

## Code-based verification performed

- Executed `analyze_complaints.py` against the original `lecture-file.csv`.
- Confirmed 5,000 input rows, 25 exact duplicate rows, 4,975 retained records, and 4,975 unique complaint IDs.
- Compared source and cleaned fields; preserved company-name capitalization from the source rather than applying destructive title casing to proper names.
- Parsed date fields and checked that there are zero unparseable nonblank dates; preserved 310 expected missing response dates and 49 missing states.
- Independently compared the supplied timely-response flag with `date_company_responded <= response_due_date` for all closed cases: zero mismatches.
- Recomputed open/closed/responded counts, average/median/minimum/maximum response duration, timely counts/rate, and late counts/rate directly from parsed dates.
- Generated the cleaned CSV, Excel workbook, PDF report, and dashboard preview from the same Python pipeline.
- Confirmed the source file's SHA-256 before and after execution: `723f382c22156e7d845b33c363c4918cbfaf701d17efdca5fdf7945a7e501406`.

## Verification boundaries and remaining manual checks

- The Python pipeline and its outputs were executed and checked locally.
- SQL is written for MySQL 8+ and has not been run against a live MySQL server in this project folder.
- DAX has been drafted but has not been validated inside Power BI Desktop.
- The static PNG is generated locally; no interactive `.pbix` is present. Create the interactive report in Power BI Desktop and verify its visuals, filters, and measure values against the Excel `KPI_Validation` sheet.

AI-generated narrative and recommendations are not independent evidence. All numeric claims in the report are computed from the supplied data; operational owners should review recommendations before implementation.
