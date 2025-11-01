"""
CLI argument passing demo
"""
import flare

app = flare.App("args-demo")


@app.function()
def greet(name, greeting="Hello"):
    """Greet someone with a custom greeting"""
    return f"{greeting}, {name}!"


@app.function()
def repeat(message, count):
    """Repeat a message multiple times"""
    return " | ".join([message] * count)


@app.local_entrypoint()
def main(name: str = "World", greeting: str = "Hello", count: int = 3):
    """
    Demo of CLI argument passing.

    Args:
        name: Name to greet
        greeting: Greeting to use
        count: Number of times to repeat
    """
    print("=== Flare Arguments Demo ===\n")

    # Use CLI arguments in remote functions
    result1 = greet.remote(name, greeting)
    print(f"Greeting: {result1}")

    result2 = repeat.remote(result1, count)
    print(f"Repeated: {result2}")

    print("\nDone!")
