"""
Generate sample parquet data and upload to R2 bucket

This script creates sample parquet files and uploads them to R2
for testing the parallel data processing example.
"""
import os
import sys
from dotenv import load_dotenv

# Colors
GREEN = '\033[0;32m'
DIM = '\033[2m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

print("")
print("Flare R2 Data Generator")
print("")

# Load environment variables
load_dotenv()

# Validate environment variables
print("> Checking configuration")
required_vars = ["R2_ACCESS_KEY", "R2_SECRET_KEY", "R2_ENDPOINT", "R2_BUCKET"]
missing = [var for var in required_vars if not os.getenv(var)]

if missing:
    print(f"{RED}error:{NC} Missing environment variables: {', '.join(missing)}")
    print("")
    print("Copy .env.example to .env and fill in your credentials")
    print("")
    sys.exit(1)

access_key = os.getenv("R2_ACCESS_KEY")
secret_key = os.getenv("R2_SECRET_KEY")
endpoint = os.getenv("R2_ENDPOINT")
bucket = os.getenv("R2_BUCKET")

print(f"  {GREEN}✓{NC} Configuration loaded")
print(f"  {DIM}Bucket: {bucket}{NC}")

# Generate sample data
print("")
print("> Generating sample data")

try:
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
except ImportError as e:
    print(f"{RED}error:{NC} Missing required package: {e}")
    print("")
    print("Install with: pip install pandas numpy")
    print("")
    sys.exit(1)

# Generate 5 sample datasets
num_files = 5
datasets = []

for i in range(num_files):
    # Generate random sample data
    num_rows = np.random.randint(100, 500)

    df = pd.DataFrame({
        'id': range(i * 1000, i * 1000 + num_rows),
        'value': np.random.randn(num_rows),
        'category': np.random.choice(['A', 'B', 'C', 'D'], num_rows),
        'timestamp': pd.to_datetime([datetime.now() - timedelta(hours=x) for x in range(num_rows)]).as_unit('us')
    })

    datasets.append((f"data_{i:03d}.parquet", df))

print(f"  {GREEN}✓{NC} Generated {num_files} datasets ({sum(len(df) for _, df in datasets)} total rows)")

# Write to local temp files first
print("")
print("> Writing parquet files")

import tempfile
temp_dir = tempfile.mkdtemp()
local_files = []

for filename, df in datasets:
    filepath = os.path.join(temp_dir, filename)
    df.to_parquet(filepath, index=False)
    local_files.append((filename, filepath))

print(f"  {GREEN}✓{NC} {len(local_files)} parquet files created")

# Upload to R2
print("")
print("> Uploading to R2")

try:
    import boto3
except ImportError:
    print(f"{RED}error:{NC} boto3 not installed")
    print("")
    print("Install with: pip install boto3")
    print("")
    sys.exit(1)

s3 = boto3.client(
    's3',
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
)

for filename, filepath in local_files:
    s3.upload_file(filepath, bucket, filename)
    print(f"  {GREEN}✓{NC} {DIM}{filename}{NC}")

# Cleanup temp files
import shutil
shutil.rmtree(temp_dir)

print("")
print(f"Uploaded {len(local_files)} files to s3://{bucket}/")
print("")
print("Next, process the data:")
print("  flare run examples/r2_data_processing/process.py --execution")
print("")
