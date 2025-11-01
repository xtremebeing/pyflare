"""
Basic parallel execution example
"""
import flare

app = flare.App("parallel-basic")


@app.function()
def square(x):
    """Square a number"""
    return x ** 2


@app.local_entrypoint()
def main():
    """Run parallel square calculations"""
    print("=== Flare Parallel Execution (Basic) ===")

    numbers = list(range(10))
    print(f"Squaring {len(numbers)} numbers in parallel...")

    results = square.map(numbers)

    print(f"Results: {results}")
    # Expected: [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
