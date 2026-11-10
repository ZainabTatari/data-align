-- Run each query on BOTH source and target. Replace:
--   {SCHEMA}  e.g. legacy / cloud      {TABLE} e.g. customers      {KEY} e.g. id

-- Query 1: row count + duplicate keys
SELECT count(*) AS total_rows,
       count(*) - count(DISTINCT {KEY}) AS duplicate_keys
FROM {SCHEMA}.{TABLE};

-- Query 2: column list
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = '{SCHEMA}' AND table_name = '{TABLE}'
ORDER BY ordinal_position;

-- Query 3: per-column profile (generic, no per-column editing)
-- Heavy on very large tables: run on a read replica or off-hours.
WITH kv AS (
  SELECT e.key, e.value
  FROM {SCHEMA}.{TABLE} t, LATERAL jsonb_each(to_jsonb(t)) e
)
SELECT key AS column_name,
       count(*) AS total_rows,
       count(*) FILTER (WHERE value = 'null'::jsonb) AS null_count,
       count(DISTINCT value) AS distinct_count,
       min(value #>> '{}') AS min_text,
       max(value #>> '{}') AS max_text,
       avg(length(value #>> '{}'))::numeric(10,2) AS avg_length,
       max(length(value #>> '{}')) AS max_length,
       sum(CASE WHEN jsonb_typeof(value)='number'
                THEN (value #>> '{}')::numeric END) AS numeric_sum
FROM kv GROUP BY key ORDER BY key;

-- Query 4: sample rows (same ordering on both sides keeps them comparable)
SELECT * FROM {SCHEMA}.{TABLE} ORDER BY {KEY} LIMIT 50;
