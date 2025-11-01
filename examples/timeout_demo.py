"""
Timeout configuration example
"""
import flare
import time

app = flare.App("timeout-demo")


@app.function(timeout=10)  # 10 second timeout
def quick_task(x):
    """Task that should complete within timeout"""
    time.sleep(2)
    return x * 2


@app.function(timeout=5)  # 5 second timeout - this will fail!
def slow_task(x):
    """Task that will timeout"""
    time.sleep(10)  # Sleeps longer than timeout
    return x * 2


@app.local_entrypoint()
def main():
    """Demonstrate timeout behavior"""
    print("=== Flare Timeout Demo ===")

    # This should succeed
    print("\n1. Quick task (2s sleep, 10s timeout)...")
    try:
        result = quick_task.remote(5)
        print(f"   ✓ Success: {result}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")

    # This should timeout
    print("\n2. Slow task (10s sleep, 5s timeout)...")
    try:
        result = slow_task.remote(5)
        print(f"   ✓ Success: {result}")
    except Exception as e:
        print(f"   ✗ Failed (expected): {e}")

    print("\nDone!")
