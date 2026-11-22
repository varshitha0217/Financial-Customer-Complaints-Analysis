-- Financial Customer Complaints Analysis
-- Dialect: MySQL 8+. Import financial_complaints_cleaned.csv into a table
-- named financial_complaints. The database and table intentionally share a
-- name. CSV-derived reference checks in comments are not SQL execution results.
-- Column names and order match the 16-column cleaned CSV.

-- Create/select the requested database, then create the import table once.
CREATE DATABASE IF NOT EXISTS financial_complaints
    CHARACTER SET utf8mb4;
USE financial_complaints;

CREATE TABLE IF NOT EXISTS financial_complaints (
    complaint_id VARCHAR(32) NOT NULL PRIMARY KEY,
    date_received DATE NOT NULL,
    financial_product VARCHAR(100) NOT NULL,
    issue_category VARCHAR(100) NOT NULL,
    issue_detail VARCHAR(150) NOT NULL,
    company_name VARCHAR(150) NOT NULL,
    state CHAR(2) NULL,
    submission_channel VARCHAR(40) NOT NULL,
    response_due_date DATE NOT NULL,
    date_company_responded DATE NULL,
    response_status VARCHAR(20) NOT NULL,
    company_response VARCHAR(80) NOT NULL,
    timely_response VARCHAR(5) NULL,
    short_complaint_summary TEXT NOT NULL,
    days_to_response INT NULL,
    days_late INT NULL
);

-- Import option A (MySQL Workbench): right-click the financial_complaints
-- schema > Table Data Import Wizard; select
-- financial_complaints_cleaned.csv, choose the existing table, confirm that
-- the first row is a header, map the 16 columns by name, and ensure blank CSV
-- cells are loaded as SQL NULL. Do not import into an existing populated table
-- unless it has first been cleared, or repeated imports will duplicate rows.
-- Confirm that an existing table has the exact schema below; IF NOT EXISTS
-- will not change a table that already exists.

-- Import option B (optional): run LOAD DATA LOCAL INFILE below if LOCAL INFILE
-- is enabled on both the MySQL server and client. LOCAL reads from the client
-- machine. The doubled backslashes in this Windows path represent literal
-- backslashes in the MySQL string. Change the path if the project is elsewhere.
-- If LOCAL INFILE is disabled, use the Workbench wizard above instead.
--
-- LOAD DATA LOCAL INFILE
--   'C:\\Users\\varsh\\Downloads\\Financial_Complaints_Analysis_Project\\financial_complaints_cleaned.csv'
-- INTO TABLE financial_complaints
-- CHARACTER SET utf8mb4
-- FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' ESCAPED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 LINES
-- (@complaint_id, @date_received, @financial_product, @issue_category,
--  @issue_detail, @company_name, @state, @submission_channel,
--  @response_due_date, @date_company_responded, @response_status,
--  @company_response, @timely_response, @short_complaint_summary,
--  @days_to_response, @days_late)
-- SET complaint_id = @complaint_id,
--     date_received = STR_TO_DATE(NULLIF(@date_received, ''), '%Y-%m-%d'),
--     financial_product = @financial_product,
--     issue_category = @issue_category,
--     issue_detail = @issue_detail,
--     company_name = @company_name,
--     state = NULLIF(@state, ''),
--     submission_channel = @submission_channel,
--     response_due_date = STR_TO_DATE(NULLIF(@response_due_date, ''), '%Y-%m-%d'),
--     date_company_responded = STR_TO_DATE(NULLIF(@date_company_responded, ''), '%Y-%m-%d'),
--     response_status = @response_status,
--     company_response = @company_response,
--     timely_response = NULLIF(@timely_response, ''),
--     short_complaint_summary = @short_complaint_summary,
--     days_to_response = NULLIF(@days_to_response, ''),
--     days_late = NULLIF(@days_late, '');

-- Q1. Count loaded rows and unique IDs. Purpose: verify import completeness
-- and detect repeated IDs. CSV reference: 4,975 rows and 4,975 unique IDs.
SELECT COUNT(*) AS rows_loaded,
       COUNT(DISTINCT complaint_id) AS unique_complaints
FROM financial_complaints;

-- Q2. Split the workload by status. Purpose: quantify the open backlog and
-- reconcile status counts to Q1 (CSV reference: 310 open, 4,665 closed).
SELECT response_status, COUNT(*) AS complaint_count
FROM financial_complaints
GROUP BY response_status
ORDER BY complaint_count DESC;

-- Q3. Rank product complaint volume and share. Purpose: identify products
-- contributing the most cases.
SELECT financial_product,
       COUNT(*) AS complaint_count,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM financial_complaints
GROUP BY financial_product
ORDER BY complaint_count DESC;

-- Q4. Rank the ten most frequent issue categories. Purpose: focus issue
-- investigation on the largest complaint drivers.
SELECT issue_category,
       COUNT(*) AS complaint_count,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM financial_complaints), 2) AS share_pct
FROM financial_complaints
GROUP BY issue_category
ORDER BY complaint_count DESC
LIMIT 10;

-- Q5. Average, exact median, minimum, and maximum response durations.
-- Purpose: describe how long responded cases took; open cases are excluded.
-- Median is the middle duration, or the mean of the two middle durations.
-- CSV reference: mean 8.76 days, median 8 days, range 1 to 25 days.
WITH ranked AS (
    SELECT days_to_response,
           ROW_NUMBER() OVER (ORDER BY days_to_response) AS row_num,
           COUNT(*) OVER () AS row_count
    FROM financial_complaints
    WHERE date_company_responded IS NOT NULL
)
SELECT ROUND(AVG(days_to_response), 2) AS avg_response_days,
       ROUND(AVG(CASE
           WHEN row_num IN (FLOOR((row_count + 1) / 2),
                            FLOOR((row_count + 2) / 2))
           THEN days_to_response
       END), 2) AS median_response_days,
       MIN(days_to_response) AS min_response_days,
       MAX(days_to_response) AS max_response_days
FROM ranked;

-- Q6. Closed-case timeliness KPI and independent due-date reconciliation.
-- Purpose: report timely and late counts/rate and detect mismatched flags.
-- CSV reference (not SQL output): 4,202 timely, 463 late, 0 mismatches.
SELECT COUNT(*) AS closed_complaints,
       SUM(timely_response = 'Yes') AS timely_responses,
       ROUND(100.0 * SUM(timely_response = 'Yes') / COUNT(*), 2) AS timely_rate_pct,
       SUM(date_company_responded > response_due_date) AS late_by_dates,
       SUM((timely_response = 'Yes') <>
           (date_company_responded <= response_due_date)) AS flag_date_mismatches
FROM financial_complaints
WHERE response_status = 'Closed';

-- Q7. Timeliness by product. Purpose: compare on-time performance by product.
-- The denominator is closed complaints within each product.
SELECT financial_product,
       COUNT(*) AS closed_complaints,
       SUM(timely_response = 'Yes') AS timely_responses,
       ROUND(100.0 * SUM(timely_response = 'Yes') / COUNT(*), 2) AS timely_rate_pct,
       SUM(days_late > 0) AS late_responses
FROM financial_complaints
WHERE response_status = 'Closed'
GROUP BY financial_product
ORDER BY timely_rate_pct ASC;

-- Q8. Company performance. Purpose: compare volume, closed workload, response
-- duration, and timeliness; interpret differences descriptively, not causally.
SELECT company_name,
       COUNT(*) AS total_complaints,
       SUM(response_status = 'Closed') AS closed_complaints,
       SUM(response_status = 'Closed' AND timely_response = 'Yes') AS timely_responses,
       ROUND(100.0 * SUM(response_status = 'Closed' AND timely_response = 'Yes')
             / NULLIF(SUM(response_status = 'Closed'), 0), 2) AS timely_rate_pct,
       ROUND(AVG(days_to_response), 2) AS avg_response_days,
       SUM(response_status = 'Closed' AND days_late > 0) AS late_responses
FROM financial_complaints
GROUP BY company_name
ORDER BY timely_rate_pct ASC, total_complaints DESC;

-- Q9. Complaint trend by received month. Purpose: show volume over time.
-- The last month may be partial (the supplied data ends on 2026-10-15).
SELECT DATE_FORMAT(date_received, '%Y-%m') AS received_month,
       COUNT(*) AS complaint_count
FROM financial_complaints
GROUP BY DATE_FORMAT(date_received, '%Y-%m')
ORDER BY received_month;

-- Q10. Submission channel mix. Purpose: compare intake-channel counts and
-- each channel's share of all loaded complaints.
SELECT submission_channel,
       COUNT(*) AS complaint_count,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM financial_complaints), 2) AS share_pct
FROM financial_complaints
GROUP BY submission_channel
ORDER BY complaint_count DESC;

-- Q11. State distribution. Purpose: compare complaint counts by state while
-- retaining records with a missing state under the label Unknown.
SELECT COALESCE(state, 'Unknown') AS state_or_unknown,
       COUNT(*) AS complaint_count
FROM financial_complaints
GROUP BY COALESCE(state, 'Unknown')
ORDER BY complaint_count DESC;

-- Q12. Current open-case age. Purpose: identify the oldest open cases and
-- those already past their due date for backlog prioritization. This is
-- intentionally dynamic (age is measured as of the query execution date).
SELECT complaint_id,
       company_name,
       financial_product,
       issue_category,
       date_received,
       response_due_date,
       DATEDIFF(CURRENT_DATE(), date_received) AS open_age_days,
       DATEDIFF(CURRENT_DATE(), response_due_date) AS days_past_due
FROM financial_complaints
WHERE response_status = 'Open'
ORDER BY days_past_due DESC, open_age_days DESC;
