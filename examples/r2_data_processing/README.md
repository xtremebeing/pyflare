# R2 Data Processing Example

Process parquet files from R2 in parallel using Flare, PyIceberg, and PyArrow.

## Setup

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Fill in your R2 and Data Catalog credentials in `.env`

3. Install dependencies:
```bash
uv sync
```

## Usage

**Generate sample data:**
```bash
uv run python generate_data.py
```

**Process data in parallel:**
```bash
uv run flare run process.py --execution
```

This will:
- List parquet files in your R2 bucket
- Create an Iceberg table in R2 Data Catalog
- Process files in parallel across containers (download, validate, clean, enrich)
- Combine results and write to Iceberg table
