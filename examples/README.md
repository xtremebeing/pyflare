# Flare Examples

Quick examples to get started with Flare.

## Running Examples

After installing Flare and deploying the Worker (see [main README](../README.md)):

```bash
flare run examples/hello.py
flare run examples/parallel_basic.py
flare run examples/timeout_demo.py
flare run examples/args_demo.py --name Alice --count 5
flare run examples/secrets_demo.py
```

## What's Included

- **`hello.py`** - Hello world with remote and local execution
- **`parallel_basic.py`** - Parallel execution with `.map()`
- **`timeout_demo.py`** - Timeout configuration and error handling
- **`args_demo.py`** - CLI argument passing
- **`secrets_demo.py`** - Environment variables and secrets

See the [main README](../README.md) for full documentation.
