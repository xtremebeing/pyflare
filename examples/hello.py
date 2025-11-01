"""
Simple hello world example
"""
import flare

app = flare.App("hello")


@app.function()
def greet(name):
    """Greet someone"""
    return f"Hello {name}!"


@app.local_entrypoint()
def main():
    """Local entrypoint - runs on your machine"""
    print("=== Flare Hello World ===")

    # Execute remotely
    result = greet.remote("World")
    print(f"Remote: {result}")

    # Execute locally for comparison
    local_result = greet.local("Local")
    print(f"Local: {local_result}")
