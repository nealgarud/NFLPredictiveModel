# PFF ETL Pipeline – Step-by-Step Guide

Use this guide to implement RB, WR, OL, and DEF PFF processors using the same pattern as QBsPFFLambda.

---

## High-Level Flow

```
Lambda Event (bucket, season, s3_prefix)
    ↓
1. EXTRACT: S3FileReader reads CSVs from S3
    ↓
2. TRANSFORM: PFFDataProcessor maps CSV columns → DB columns
    ↓
3. LOAD: DatabaseUtils batch upserts into Supabase
```

---

## Step 1: Lambda Handler (Orchestrator)

**File:** `lambda_function.py`

**Role:** Parse event, wire components, loop over seasons.

### Flow

1. **Parse event** → `_normalize_seasons_to_process(event)` returns `[{season, s3_prefix}, ...]`
2. **Create components:**
   - `S3FileReader(bucket_name=bucket)`
   - `DatabaseUtils()`
   - `PFFDataProcessor(db_utils=db_utils, batch_size=50)`
3. **For each season:**
   - Call `s3_reader.read_all_csvs_in_folder(s3_prefix)` → raw CSV rows
   - Call `processor.process_and_store(csv_rows, season)` → rows inserted
4. **Close** `db_utils.close()`

### What to Change for RB/WR/OL/DEF

- Lambda name (e.g. `RBsPFFLambda`)
- Default `s3_prefix` (e.g. `RBs/`, `WRs/`, etc.)
- Log messages

**S3FileReader and DatabaseUtils are shared** – no changes needed.

---

## Step 2: Extract – S3FileReader

**File:** `S3FileReader.py`

**Role:** Read CSVs from S3 and return rows as `List[Dict[str, Any]]`.

### Flow

1. **`list_files_in_folder(prefix)`**
   - `s3_client.list_objects_v2(Bucket, Prefix=prefix)`
   - Filter keys that don’t end with `/`
   - Return list of object keys

2. **`read_csv_from_s3(s3_key)`**
   - `s3_client.get_object(Bucket, Key=s3_key)`
   - `response['Body'].read().decode('utf-8')`
   - `csv.DictReader(io.StringIO(content))` → each row is `{column_name: value}`
   - Return `list(csv_reader)`

3. **`read_all_csvs_in_folder(prefix)`**
   - List files, keep only `.csv`
   - For each file, call `read_csv_from_s3`
   - `all_rows.extend(rows)`
   - Return combined list

### What to Change for RB/WR/OL/DEF

**Nothing.** Same reader for all positions.

---

## Step 3: Transform – PFFDataProcessor

**File:** `PFFDataProcessor.py`

**Role:** Map CSV columns to DB columns, validate, and prepare for upsert.

### 3a. `transform_row(row, season)` – CSV → DB Row

For each CSV row:

1. **`get(k, dtype, default)`**
   - `_get_value(row, k, default=default)` – get value, handle missing
   - `clean_value(val, dtype)` – cast to `str`, `int`, or `Decimal`

2. **Map each column** – CSV column name → DB column name:
   - `player` → `player`
   - `team_name` → `team` (via `normalize_team_abbreviation`)
   - `position` → `position` (default `'QB'` for QB, etc.)
   - All other columns 1:1 if names match

3. **Add `season`** from the Lambda event (not from CSV).

### 3b. `validate_row(transformed_row)`

- Require `player` and `season`.
- Skip rows that fail validation.

### 3c. `build_upsert_query()` – SQL

- Build `INSERT INTO {table} (col1, col2, ...) VALUES (%s, %s, ...)`
- Add `ON CONFLICT (player, team, season) DO UPDATE SET col1 = EXCLUDED.col1, ...`
- Column list must match `transform_row` output.

### 3d. `row_to_tuple(row)` – Dict → Tuple

- Use the same column order as `build_upsert_query`.
- `return tuple(row[c] for c in cols)`

### 3e. `process_and_store(csv_rows, season)`

1. Transform: `transformed = [transform_row(r, season) for r in csv_rows]`
2. Validate: keep only rows where `validate_row(transformed)` is True
3. Batch: loop in chunks of `batch_size` (e.g. 50)
4. For each batch: `db_utils.execute_batch(query, [row_to_tuple(r) for r in batch])`

### What to Change for RB/WR/OL/DEF

1. **Table name** – e.g. `rb_pff_ratings`, `wr_pff_ratings`, etc.
2. **`transform_row`** – map the actual CSV columns for that position.
3. **`build_upsert_query`** – same table and columns as `transform_row`.
4. **`row_to_tuple`** – same column order.
5. **`validate_row`** – same required fields (`player`, `season`).
6. **`normalize_team_abbreviation`** – keep as-is (shared).

---

## Step 4: Load – DatabaseUtils

**File:** `DatabaseUtils.py`

**Role:** Connect to Supabase and run parameterized SQL.

### Flow

1. **`connect()`** – pg8000 connection from env vars (`DB_HOST`, `DB_NAME`, etc.).
2. **`execute_batch(query, data_batch)`**
   - For each tuple in `data_batch`: `cursor.execute(query, row_data)`
   - `conn.commit()`
   - On error: `conn.rollback()`

### What to Change for RB/WR/OL/DEF

**Nothing.** Same DB utils for all positions.

---

## Implementation Checklist for New Position (e.g. RB)

### 1. Create folder structure

```
RBsPFFLambda/
├── lambda_function.py
├── S3FileReader.py      # Copy from QBsPFFLambda
├── PFFDataProcessor.py  # Modify
├── DatabaseUtils.py     # Copy from QBsPFFLambda
├── requirements.txt
└── README.md
```

### 2. Get CSV column names

- Download a sample CSV from S3 for that position.
- Inspect headers: `list(csv_rows[0].keys())`.

### 3. Create Supabase table

- Match table columns to CSV columns.
- Use `UNIQUE (player, team, season)` for upserts.
- Use `DECIMAL(5,2)` for rates/percentages to avoid overflow.

### 4. Implement `PFFDataProcessor`

- **`transform_row`:** Map each CSV column to a DB column.
- **`build_upsert_query`:** Use the correct table name and column list.
- **`row_to_tuple`:** Same column order as the query.
- **`validate_row`:** Require `player` and `season`.

### 5. Update `lambda_function.py`

- Change default `s3_prefix` (e.g. `RBs/`).
- Update log messages and docstrings.

### 6. Test locally

```python
# test_local.py or lambda_function.py __main__
event = {"bucket": "your-bucket", "season": 2024, "s3_prefix": "RBs/"}
result = lambda_handler(event, None)
```

---

## Shared vs Position-Specific

| Component        | Shared? | Notes                                      |
|-----------------|---------|--------------------------------------------|
| S3FileReader    | Yes     | Same for all positions                     |
| DatabaseUtils   | Yes     | Same for all positions                     |
| lambda_function | Mostly  | Change prefix, logs, Lambda name            |
| PFFDataProcessor | No    | Table name, columns, `transform_row` logic |

---

## Column Mapping Pattern

```python
# In transform_row – for each CSV column:
'db_column_name': get('csv_column_name', 'int'),   # or 'str', 'decimal'
'team': self.normalize_team_abbreviation(get('team_name', 'str') or ''),
'season': season,  # From event, not CSV
```

Use `_get_value(row, 'col1', 'col2', default=x)` when the CSV uses different names (e.g. `team` vs `team_name`).

---

## Common Pitfalls

1. **Column order** – `build_upsert_query`, `row_to_tuple`, and `transform_row` must use the same order.
2. **Unique constraint** – Must match `ON CONFLICT (...)` columns.
3. **DECIMAL overflow** – Use `DECIMAL(5,2)` for values that can be ≥ 100.
4. **Required fields** – Rows without `player` or `season` are skipped.
5. **Team normalization** – Use `normalize_team_abbreviation` for `team_name` → `team`.
