PUT YOUR OLD DATA HERE (before the migration) - see ../README.txt

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
