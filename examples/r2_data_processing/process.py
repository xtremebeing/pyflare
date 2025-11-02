"""
R2 data processing with PyIceberg

This example demonstrates:
1. Listing objects from R2 bucket
2. Creating an Iceberg table in R2 Data Catalog
3. Processing parquet files in parallel across containers
4. Using PyIceberg to append data to Iceberg table
"""
import flare
import os

# Load .env file early (before decorators evaluate)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Use system env vars if dotenv not available

app = flare.App("r2-data-processing")


@app.function(env={
    "R2_ACCESS_KEY": os.getenv("R2_ACCESS_KEY"),
    "R2_SECRET_KEY": os.getenv("R2_SECRET_KEY"),
    "R2_ENDPOINT": os.getenv("R2_ENDPOINT"),
    "R2_BUCKET": os.getenv("R2_BUCKET"),
})
def process_parquet(object_key: str):
    """Download and process parquet file from R2"""
    import boto3
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    import os
    import io

    # Get environment variables
    access_key = os.environ["R2_ACCESS_KEY"]
    secret_key = os.environ["R2_SECRET_KEY"]
    endpoint = os.environ["R2_ENDPOINT"]
    bucket = os.environ["R2_BUCKET"]

    print(f"Processing: {object_key}")

    # Download parquet file from R2
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    obj = s3.get_object(Bucket=bucket, Key=object_key)
    parquet_bytes = obj['Body'].read()

    # Read parquet into PyArrow table
    table = pq.read_table(io.BytesIO(parquet_bytes))
    print(f"  Read {len(table)} rows")

    # Data validation & cleaning
    # Remove rows with null values in critical columns
    mask = pc.and_(
        pc.is_valid(table['id']),
        pc.is_valid(table['value'])
    )
    table = table.filter(mask)
    print(f"  After null removal: {len(table)} rows")

    # Filter out outliers (values outside reasonable range)
    value_mask = pc.and_(
        pc.greater(table['value'], -10),
        pc.less(table['value'], 10)
    )
    table = table.filter(value_mask)
    print(f"  After outlier removal: {len(table)} rows")

    # Add computed columns
    table = table.append_column(
        "value_squared",
        pc.multiply(table['value'], table['value'])
    )
    table = table.append_column(
        "is_category_a",
        pc.equal(table['category'], 'A')
    )

    print(f"  Cleaned and enriched {len(table)} rows")

    return {
        "object_key": object_key,
        "table": table,
        "original_rows": len(pq.read_table(io.BytesIO(parquet_bytes))),
        "cleaned_rows": len(table)
    }


@app.local_entrypoint()
def main():
    """Process R2 parquet files in parallel"""
    import boto3
    from pyiceberg.catalog.rest import RestCatalog
    from pyiceberg.exceptions import NamespaceAlreadyExistsError, TableAlreadyExistsError
    import pyarrow as pa

    print("=== R2 Data Processing with PyIceberg ===\n")

    # Get credentials from environment
    access_key = os.getenv("R2_ACCESS_KEY")
    secret_key = os.getenv("R2_SECRET_KEY")
    endpoint = os.getenv("R2_ENDPOINT")
    bucket = os.getenv("R2_BUCKET")
    catalog_uri = os.getenv("CATALOG_URI")
    warehouse_name = os.getenv("CATALOG_WAREHOUSE")
    catalog_token = os.getenv("CATALOG_TOKEN")

    # Validate environment variables
    required_vars = ["R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_ENDPOINT", "R2_BUCKET", "CATALOG_URI", "CATALOG_WAREHOUSE", "CATALOG_TOKEN"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in your credentials")
        return

    print("Step 1: Listing R2 bucket objects...")

    # List objects from R2 bucket
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    response = s3.list_objects_v2(Bucket=bucket, MaxKeys=20)

    if 'Contents' not in response:
        print("No objects found in bucket")
        return

    # Filter for parquet files
    parquet_files = [
        obj['Key'] for obj in response['Contents']
        if obj['Key'].endswith('.parquet')
    ]

    print(f"Found {len(parquet_files)} parquet files\n")

    if not parquet_files:
        print("No parquet files found")
        return

    print("Step 2: Creating Iceberg table (if not exists)...")

    # Connect to R2 Data Catalog
    catalog = RestCatalog(
        name="r2_catalog",
        warehouse=warehouse_name,
        uri=catalog_uri,
        token=catalog_token,
    )

    # Create namespace if it doesn't exist
    try:
        catalog.create_namespace("default")
        print("  Created namespace: default")
    except NamespaceAlreadyExistsError:
        print("  Namespace already exists: default")

    # Infer schema from first parquet file
    import pyarrow.parquet as pq
    import io

    first_obj = s3.get_object(Bucket=bucket, Key=parquet_files[0])
    first_parquet = pq.read_table(io.BytesIO(first_obj['Body'].read()))
    schema = first_parquet.schema

    column_names = [field.name for field in schema]
    print(f"  Schema: {', '.join(column_names)}")

    # Drop existing table if present (for clean runs)
    try:
        catalog.drop_table("default.processed_data")
        print("  Dropped existing table")
    except:
        pass

    # Create table with inferred schema
    table = catalog.create_table(
        ("default", "processed_data"),
        schema=schema,
    )
    print("  Created table: default.processed_data")

    print("Table ready\n")

    print(f"Step 3: Processing {len(parquet_files)} files in parallel...\n")

    # Process files in parallel (download, validate, clean)
    try:
        results = process_parquet.map(parquet_files)

        print("\nStep 4: Combining and writing to Iceberg...")

        # Combine all cleaned tables
        import pyarrow as pa
        cleaned_tables = [r['table'] for r in results]
        combined_table = pa.concat_tables(cleaned_tables)

        print(f"  Combined {len(cleaned_tables)} tables")
        print(f"  Total rows: {len(combined_table)}")

        # Write to Iceberg table (single sequential write)
        iceberg_table = catalog.load_table("default.processed_data")

        # Update schema to include new columns (union_by_name)
        with iceberg_table.update_schema() as update_schema:
            update_schema.union_by_name(combined_table.schema)

        iceberg_table.append(combined_table)

        print(f"  Written to Iceberg table")

        # Show statistics
        print("\nProcessing Summary:")
        print(f"  Files processed: {len(results)}")
        original_rows = sum(r['original_rows'] for r in results)
        cleaned_rows = sum(r['cleaned_rows'] for r in results)
        print(f"  Original rows: {original_rows:,}")
        print(f"  Cleaned rows: {cleaned_rows:,}")
        print(f"  Rows removed: {original_rows - cleaned_rows:,} ({((original_rows - cleaned_rows) / original_rows * 100):.1f}%)")

    except Exception as e:
        print(f"\nError during processing: {e}")
        raise
