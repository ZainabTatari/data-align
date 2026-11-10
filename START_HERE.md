# Start here - a guide for non-technical testers

No coding needed. You will download the tool, put your OLD and NEW data in two folders, and double-click a file. Use **test or anonymised data only**.

## Step 1 - Download
1. Open https://github.com/ZainabTatari/data-align
2. Click the green **Code** button, then **Download ZIP**.
3. Open your **Downloads** folder, right-click `data-align-main.zip`, choose **Extract All...**, and extract it somewhere easy, for example `C:\data-align`.
4. Open the extracted folder until you see `run-demo.bat`, `run-mydata.bat` and a folder called `mydata`. That folder is your working folder.

## Step 2 - Install ONE of these (once)
- **Python** (recommended): go to python.org, download Python 3.11 or newer, run the installer and **tick "Add Python to PATH"**. OR
- **Docker Desktop**: install it from docker.com, start it, and wait until it says "Engine running".

## Step 3 - Try the demo (optional, 2 minutes)
Double-click `run-demo.bat`. If Windows warns you, click **More info -> Run anyway**. A report opens in your browser. This uses built-in example data only.

## Step 4 - Put your data in
Open the `mydata` folder.
- Put your **OLD** data (before the migration) into the folder `old`.
- Put your **NEW** data (after the migration) into the folder `new`.

Each folder can hold EITHER:
- one database file ending in `.db`, `.sqlite` or `.sqlite3`, OR
- CSV files, one per table. The file name is the table name (for example `customers.csv`), and the first row must be the column names. Use the same file names in both folders.

From Excel: **File -> Save As -> CSV** (one file per sheet).
Every table needs a column that is different on every row, like an ID.

## Step 5 - Add your business rules (optional)
1. In `mydata`, copy `rules_example.csv` and name the copy `rules.csv`.
2. Open `rules.csv` in Excel. Each row is one rule. Columns: **table, column, rule, value, applies_to** (old, new or both; empty means new).
3. Change the example rows to your own table and column names, and delete rows you don't need. Save as CSV.

| rule | value to write | meaning |
|---|---|---|
| required | (empty) | must never be empty |
| allowed values | ACTIVE,CLOSED | only these values |
| between | 0 to 100000 | a number in this range |
| looks like email | (empty) | must look like an email |
| is a date | (empty) | must be a real date |
| old to new | A=ACTIVE, C=CLOSED | an expected change, not an error |

If a rule has a mistake, the tool tells you the line number.

## Step 6 - Run it
Double-click **`run-mydata.bat`**. Wait a minute. Your report opens in the browser (it is also saved in the folder `my_report`).

## How to read the report
- **FAIL**: the tool proved a problem (for example missing rows or changed values).
- **REVIEW**: needs a human decision.
- **NOT_TESTED**: the check needed information you did not provide (for example business rules or approvals). It is never hidden.
- **Overall INCOMPLETE** is normal if you gave no rules: the tool will not say PASS for things it did not check.

Your files are only read, never changed. Reports list IDs and column names, not the actual values.

## Something went wrong?
Take a screenshot of the black window and open an issue at https://github.com/ZainabTatari/data-align/issues (no real data in it, please). The author is a tester too, and corrections are welcome.
