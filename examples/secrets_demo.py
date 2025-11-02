"""
Environment variables example
"""
import flare
import os

app = flare.App("secrets-demo")


@app.function(env={
    "API_KEY": "sk_test_12345",
    "DATABASE_URL": "postgresql://localhost/mydb"
})
def process_with_secrets(item):
    """Process item using environment variables"""
    import os

    api_key = os.environ.get("API_KEY")
    db_url = os.environ.get("DATABASE_URL")

    print(f"Processing: {item}")
    print(f"API key: {api_key[:10]}...")
    print(f"Database: {db_url[:20]}...")

    return f"Processed {item}"


@app.function(env={
    "SECRET_TOKEN": os.getenv("MY_LOCAL_TOKEN", "default_token")
})
def use_local_env(name):
    """Load from local environment"""
    import os

    token = os.environ.get("SECRET_TOKEN")
    print(f"Hello {name}, token: {token}")

    return f"Authenticated: {name}"


@app.local_entrypoint()
def main():
    """Run environment variable examples"""
    print("=== Flare Environment Variables ===")

    result = process_with_secrets.remote("task-1")
    print(f"Result: {result}")

    result2 = use_local_env.remote("Alice")
    print(f"Result: {result2}")
