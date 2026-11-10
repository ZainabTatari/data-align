HOW TO AUDIT YOUR OWN DATA (no coding)

1. Put your OLD data (before the migration) in the folder  old
2. Put your NEW data (after the migration) in the folder   new
   Each folder can hold EITHER:
     - one database file ending in .db / .sqlite / .sqlite3, OR
     - several CSV files, one per table. The file name is the table name
       (e.g. customers.csv). The first row must be the column names.
   Excel? Open it and use File > Save As > CSV (one file per sheet).
3. Every table needs a column that is different on every row, like an ID.
4. Double-click  run-mydata.bat  in the folder above this one.
5. Your report opens in the browser (it is saved in the folder my_report).

SAFETY: use test or anonymised data only. Your files are only read, never changed.
The report lists IDs and column names, never the actual values.
"Not tested" in the report means the check needed extra information - it is never hidden.

ADDING YOUR COMPANY'S RULES (optional)
Copy  rules_example.csv  to  rules.csv  and change it in Excel (save as CSV).
One rule per row:  table, column, rule, value, applies_to (old / new / both; empty = new)
Rules you can use:
  required            column must never be empty
  allowed values      value = the list, e.g.  A,C
  between             value = e.g.  0 to 100   (or  0 to   or  to 100)
  looks like email
  is a date
  matches pattern     value = a pattern (advanced)
  old to new          value = e.g.  A=ACTIVE, C=CLOSED   (an expected change, not a defect)
The table and column names must match your data. If something is wrong, the tool tells you the line number.
