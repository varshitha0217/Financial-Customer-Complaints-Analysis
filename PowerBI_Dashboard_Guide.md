# Power BI Dashboard Build Guide

This guide walks through building the Financial Complaints dashboard in Power BI Desktop from the verified cleaned CSV. It does **not** create or imply that a `.pbix` file already exists. Save the finished report yourself from Power BI Desktop.

## Files and verified baseline

- Data source: `financial_complaints_cleaned.csv`
- Measure reference: `PowerBI_DAX_Measures.txt`
- Verified source size: **4,975 rows**, 16 columns, 4,975 unique complaint IDs, no duplicate rows
- Complaint received-date range: **2025-10-01 through 2026-10-15**; October 2026 is partial
- Blank values retained: 49 states and 310 response dates; all 310 missing response dates belong to open cases
- Expected default-filter KPI values:
  - Total Complaints: **4,975**
  - Open Complaints: **310**
  - Closed Complaints: **4,665**
  - Average Response Days: **8.76** (responded cases only)
  - Timely Response Rate: **90.08%** (4,202 of 4,665 closed cases)
  - Late Closed Responses: **463**

Values change when slicers are applied. The values above are the all-data baseline, not a promise that a filtered visual will show those totals.

## 1. Start a report and import the CSV

1. Open **Power BI Desktop**.
2. Select **Home > Get data > Text/CSV**.
3. Browse to `financial_complaints_cleaned.csv` in the project folder and select **Open**.
4. In the preview, confirm the header row is used and the data appears in 16 columns.
5. Select **Transform Data** (recommended) to review and set types before loading.
6. In Power Query, rename the query to `financial_complaints_cleaned` if it has another name. This must match the table name used by the DAX below.
7. Set each column to the type listed in the schema table below. To change one, select its column, then select **Transform > Data Type** (or the data-type icon beside the column name). Choose **Using Locale** for dates if Power BI does not parse the `YYYY-MM-DD` strings correctly; choose **Date** with an appropriate locale.
8. For columns with blanks, keep them as **null**. Do not replace missing response dates, timely flags, or states with guessed values.
9. Select **Home > Close & Apply**.
10. In **Model view**, verify that date columns and numeric columns have the intended types. If necessary, select a column and adjust **Column tools > Data type**.

### Column names and Power BI data types

| # | CSV column | Set type | Notes |
|---:|---|---|---|
| 1 | `complaint_id` | Text | Unique case identifier; set summarization to **Do not summarize**. |
| 2 | `date_received` | Date | Use for the report date slicer and received-month trend. |
| 3 | `financial_product` | Text | Product category. |
| 4 | `issue_category` | Text | Complaint issue category. |
| 5 | `issue_detail` | Text | Issue detail. |
| 6 | `company_name` | Text | Company label. |
| 7 | `state` | Text | State abbreviation; 49 records are blank. |
| 8 | `submission_channel` | Text | Intake channel. |
| 9 | `response_due_date` | Date | Do not connect this to the received-date calendar for this dashboard. |
| 10 | `date_company_responded` | Date | Blank on all 310 open complaints. |
| 11 | `response_status` | Text | `Open` or `Closed`. |
| 12 | `company_response` | Text | Company response outcome/category. |
| 13 | `timely_response` | Text | `Yes` / `No` for closed cases; blank for open cases. |
| 14 | `short_complaint_summary` | Text | Free-text description. |
| 15 | `days_to_response` | Whole number | 1–25 for responded cases; blank for open cases. |
| 16 | `days_late` | Whole number | 0–10 for responded cases; 0 means on time or early; blank for open cases. |

Power BI may initially infer the two day columns as Decimal Number because the CSV has blank values. Change them to **Whole number**; do not fill blanks with zero.

## 2. Add and verify DAX measures

Select the `financial_complaints_cleaned` table in the **Data** or **Model** pane. For each measure, select **Table tools > New measure**, paste the formula, and press Enter. Create these measures exactly as written:

```DAX
Total Complaints =
DISTINCTCOUNT(financial_complaints_cleaned[complaint_id])

Open Complaints =
CALCULATE(
    [Total Complaints],
    financial_complaints_cleaned[response_status] = "Open"
)

Closed Complaints =
CALCULATE(
    [Total Complaints],
    financial_complaints_cleaned[response_status] = "Closed"
)

Responded Complaints =
CALCULATE(
    [Total Complaints],
    FILTER(
        financial_complaints_cleaned,
        NOT ISBLANK(financial_complaints_cleaned[date_company_responded])
    )
)

Average Response Days =
AVERAGE(financial_complaints_cleaned[days_to_response])

Median Response Days =
MEDIANX(
    FILTER(
        financial_complaints_cleaned,
        NOT ISBLANK(financial_complaints_cleaned[days_to_response])
    ),
    financial_complaints_cleaned[days_to_response]
)

Timely Responses =
CALCULATE(
    [Total Complaints],
    financial_complaints_cleaned[response_status] = "Closed",
    financial_complaints_cleaned[timely_response] = "Yes"
)

Timely Response Rate =
DIVIDE([Timely Responses], [Closed Complaints])

Late Closed Responses =
CALCULATE(
    [Total Complaints],
    financial_complaints_cleaned[response_status] = "Closed",
    financial_complaints_cleaned[days_late] > 0
)

Late Response Rate =
DIVIDE([Late Closed Responses], [Closed Complaints])

Missing State Complaints =
CALCULATE(
    [Total Complaints],
    FILTER(
        financial_complaints_cleaned,
        ISBLANK(financial_complaints_cleaned[state])
    )
)

Timely Flag Date Mismatches =
COUNTROWS(
    FILTER(
        financial_complaints_cleaned,
        financial_complaints_cleaned[response_status] = "Closed"
            && (
                (financial_complaints_cleaned[timely_response] = "Yes"
                    && financial_complaints_cleaned[date_company_responded]
                        > financial_complaints_cleaned[response_due_date])
                || (financial_complaints_cleaned[timely_response] = "No"
                    && financial_complaints_cleaned[date_company_responded]
                        <= financial_complaints_cleaned[response_due_date])
            )
    )
)
```

### Why the measures match the checked dataset

- Complaint totals use distinct IDs; the CSV has 4,975 rows and 4,975 unique IDs.
- Average and median response days ignore blank values. The blanks belong to the 310 open cases, so the response-time baseline uses the 4,665 responded/closed cases.
- Timely Response Rate is **timely closed cases divided by all closed cases**, not by total complaints.
- Late Closed Responses counts closed cases with `days_late > 0`; `days_late = 0` includes responses on or before due date.
- The timely-flag/date check returns **0** for the verified data.

### Format the measures

1. Select each measure in the Fields pane.
2. On **Measure tools**, set:
   - `Timely Response Rate` and `Late Response Rate`: **Percentage**, 2 decimal places.
   - `Average Response Days`: **Decimal number**, 2 decimal places.
   - `Median Response Days`: **Whole number** or decimal with 0 places.
   - Count measures: **Whole number**, 0 decimal places.
3. Do not format a percentage measure as a whole number; the underlying rate is a fraction (for example `0.90075`), which should display as `90.08%`.

### Optional response-timing visual helper

A donut chart needs a category legend as well as a numeric value. Create this disconnected helper table from **Table tools > New table**:

```DAX
Response Timing =
DATATABLE(
    "Response Timing", STRING,
    {
        {"Timely"},
        {"Late"}
    }
)
```

Then create this measure from **New measure**:

```DAX
Response Timing Complaints =
SWITCH(
    SELECTEDVALUE('Response Timing'[Response Timing]),
    "Timely", [Timely Responses],
    "Late", [Late Closed Responses],
    BLANK()
)
```

This table is intentionally unrelated to the complaint table. The measure supplies the corresponding verified timely or late count for each legend value. On the donut chart, use `'Response Timing'[Response Timing]` as **Legend** and `[Response Timing Complaints]` as **Values**. The all-data baseline is 4,202 timely and 463 late out of 4,665 closed cases.

## 3. Create a received-date calendar

Using a date table gives the date slicer and month chart a continuous date axis.

1. Select **Modeling > New table**.
2. Paste:

```DAX
Dates =
CALENDAR(
    MIN(financial_complaints_cleaned[date_received]),
    MAX(financial_complaints_cleaned[date_received])
)
```

3. Select the `Dates` table and choose **Table tools > New column**. Add:

```DAX
Month Start =
DATE(YEAR(Dates[Date]), MONTH(Dates[Date]), 1)
```

4. Add another new column:

```DAX
Month Label =
FORMAT(Dates[Date], "yyyy-MM")
```

5. Select `Month Label`, then **Column tools > Sort by column > Month Start**. This ensures months appear chronologically.
6. With the `Dates` table selected, choose **Table tools > Mark as date table > Mark as date table**, and select `Dates[Date]`.
7. Open **Model view**. Drag `Dates[Date]` onto `financial_complaints_cleaned[date_received]`.
8. In the relationship dialog, confirm:
   - Cardinality: **One to many (1:*)**, with `Dates` on the “1” side.
   - Cross-filter direction: **Single**.
   - Relationship is **Active**.
9. Do not relate this one calendar to `date_company_responded` or `response_due_date` for this report. The requested date slicer and monthly trend represent complaint received date. (A separate role-playing date table is needed if you later want response-date slicers.)

## 4. Build the report page

1. Select the report page and rename it **Complaints Overview** (right-click the page tab at the bottom, then **Rename page**).
2. Select a blank area of the canvas. In **Format page**, set a light neutral background and a 16:9 canvas if desired.
3. In the **View** ribbon, turn on **Gridlines** and **Snap to grid** to help align visuals.
4. Add the five KPI cards across the top. Select the **Card** visual from Visualizations, then drag the measure into its **Data/Values** field well. Repeat for each card.
5. Add the six analysis visuals and four slicers using the mappings below.
6. Use **Format visual** (paintbrush) to edit titles, display units, decimal places, labels, and colors.
7. Use **View > Selection pane** or **Format > Align** to keep visual spacing consistent.
8. Add a text box near the trend chart: `October 2026 is partial; source data ends 2026-10-15. Timely response rate = timely closed cases / all closed cases.`

## 5. KPI cards

| Card title | Visual | Field / measure | All-data baseline |
|---|---|---|---:|
| Total Complaints | Card | `[Total Complaints]` | 4,975 |
| Open Complaints | Card | `[Open Complaints]` | 310 |
| Closed Complaints | Card | `[Closed Complaints]` | 4,665 |
| Average Response Days | Card | `[Average Response Days]` | 8.76 |
| Timely Response Rate | Card | `[Timely Response Rate]` | 90.08% |

For each card, set its title to the wording above, use a large callout value, and turn off unnecessary category labels. Keep counts as whole numbers, average days to two decimal places, and the response rate as a two-decimal percentage. Values should recalculate with the slicers.

## 6. Required visuals and field mappings

| Visual title | Recommended visual | Field wells | Sorting / formatting |
|---|---|---|---|
| Complaints by Product | Clustered bar chart | Y-axis: `financial_product`; X-axis/Values: `[Total Complaints]` | Sort descending by `[Total Complaints]`; show data labels; whole-number axis. |
| Complaints by Issue | Clustered bar chart | Y-axis: `issue_category`; X-axis/Values: `[Total Complaints]` | In Filters on this visual, add `issue_category`, set filter type to **Top N**, enter 10, by `[Total Complaints]`, then select **Apply filter**. Sort descending. |
| Monthly Complaint Trend | Line chart (or clustered column chart) | X-axis: `Dates[Month Label]`; Y-axis/Values: `[Total Complaints]` | Use Month Label from Dates, not the raw date text; sort ascending by Month Start; categorical axis. Highlight that Oct-2026 is partial (212 complaints through Oct 15). |
| Timely vs Late Responses | Donut chart | Legend: `'Response Timing'[Response Timing]`; Values: `[Response Timing Complaints]` | Turn on detail labels showing value and percent. Restrict counts to closed cases via the measures. Baseline: Timely 4,202; Late 463. |
| State-wise Complaints | Clustered bar chart | Y-axis: `state`; X-axis/Values: `[Total Complaints]` | Sort descending; show whole-number data labels. Add a note or tooltip for 49 records with missing state; these are blank rather than inferred. |
| Company Performance | Matrix | Rows: `company_name`; Values: `[Closed Complaints]`, `[Timely Response Rate]`, `[Average Response Days]`, `[Late Closed Responses]` | Format rate as percentage, days as 2 decimals, counts as whole numbers. Apply conditional formatting to timely rate; title it clearly and avoid implying causation. |

For the state chart, blank state values may appear as `(Blank)` depending on the visual. Keep that category visible if possible so the 49 missing-state records are not silently presented as known states.

## 7. Add the requested slicers

For each slicer, select a blank area, choose the **Slicer** visual, then drag the indicated field into its field well:

| Slicer title | Field | Suggested slicer style |
|---|---|---|
| Product | `financial_product` | Dropdown |
| State | `state` | Dropdown; retain `(Blank)` as the unknown group |
| Company | `company_name` | Dropdown |
| Received Date | `Dates[Date]` | **Between** date range |

For the date slicer, confirm that the field is `Dates[Date]`, not the text version of the date. If slicers do not filter all relevant visuals, select a slicer, then **Format > Edit interactions** and ensure the visuals show the filter interaction icon rather than “None.” The four slicers should filter the KPI cards and charts, including the connected date calendar.

## 8. Final checks and save

1. Clear all slicer selections (use each slicer's eraser icon) before checking the all-data baseline.
2. Confirm cards show **4,975**, **310**, **4,665**, **8.76**, and **90.08%**.
3. Confirm the timely-versus-late chart shows **4,202 timely** and **463 late**; the two counts add to **4,665 closed**.
4. Confirm the month axis is chronological and ends at **2026-10**. The last month has 212 records and is partial.
5. Confirm the state chart does not silently treat the 49 blanks as a named state.
6. Test each slicer and clear it again. A selected date range or category changes the cards; this is expected.
7. Save with **File > Save As** and choose a location/name such as `Financial_Complaints_Analysis.pbix`.

The PBIX creation and visual checks are your remaining Power BI Desktop steps. This guide and the static `Dashboard_Preview.png` do not constitute an interactive PBIX report.
