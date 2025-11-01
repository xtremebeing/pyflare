"""
flare run command
"""

import sys
import importlib.util
from pathlib import Path
import click
from ...config import load_config


def run_script(script_ref: str, show_output: bool = False, **kwargs: object) -> None:
    """
    Run a Flare script by importing it as a module.

    The @local_entrypoint() decorator will automatically execute
    when the module is imported, or you can specify a function
    to run directly using file.py::function_name syntax.

    Args:
        script_ref: Path to script or "path::function_name"
        show_output: Whether to show execution details and progress
        **kwargs: Arguments to pass to the entrypoint function
    """
    # Parse function reference syntax (file.py::function_name)
    parts = script_ref.split("::")
    script_path = Path(parts[0]).resolve()
    function_name = parts[1] if len(parts) > 1 else None

    # Colors
    RED = "\033[0;31m"
    NC = "\033[0m"

    if not script_path.exists():
        click.echo("", err=True)
        click.echo(f"{RED}error:{NC} Script not found: {script_path}", err=True)
        click.echo("", err=True)
        sys.exit(1)

    # Validate configuration
    config = load_config()
    if not config.worker_url:
        click.echo("", err=True)
        click.echo(f"{RED}error:{NC} Worker URL not configured", err=True)
        click.echo("", err=True)
        click.echo("Set it with:", err=True)
        click.echo("  export FLARE_WORKER_URL=http://localhost:8787", err=True)
        click.echo("Or run: flare config init", err=True)
        click.echo("", err=True)
        sys.exit(1)

    if not config.api_key:
        click.echo("", err=True)
        click.echo(f"{RED}error:{NC} API key not configured", err=True)
        click.echo("", err=True)
        click.echo("Set it with:", err=True)
        click.echo("  export FLARE_API_KEY=your-api-key", err=True)
        click.echo("Or run: flare config init", err=True)
        click.echo("", err=True)
        sys.exit(1)

    # Import the script as a module
    spec = importlib.util.spec_from_file_location("__flare_main__", script_path)
    if not spec or not spec.loader:
        click.echo("", err=True)
        click.echo(f"{RED}error:{NC} Cannot load script: {script_path}", err=True)
        click.echo("", err=True)
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)

    # Add module to sys.modules so inspect.getmodule() can find it
    sys.modules["__flare_main__"] = module

    # Change to script directory for relative imports
    import os as os_module

    original_cwd = Path.cwd()
    try:
        os_module.chdir(script_path.parent)
        sys.path.insert(0, str(script_path.parent))

        if function_name:
            # Run specific function with ::function syntax
            # Set flag to prevent auto-execution of entrypoints
            setattr(module, "__flare_skip_entrypoint__", True)  # type: ignore[attr-defined]
            spec.loader.exec_module(module)  # Load module first

            if not hasattr(module, function_name):
                click.echo("", err=True)
                click.echo(
                    f"{RED}error:{NC} Function '{function_name}' not found in {script_path}",
                    err=True,
                )
                click.echo("", err=True)
                sys.exit(1)

            func = getattr(module, function_name)

            # Check if it's a Flare Function
            from ...function import Function

            if not isinstance(func, Function):
                click.echo("", err=True)
                click.echo(
                    f"{RED}error:{NC} '{function_name}' is not a @app.function(). Use @app.function() decorator.",
                    err=True,
                )
                click.echo("", err=True)
                sys.exit(1)

            # Validate arguments match function signature
            import inspect
            sig = inspect.signature(func.fn)
            func_params = set(sig.parameters.keys())
            provided_args = set(kwargs.keys())
            extra_args = provided_args - func_params

            if extra_args:
                click.echo("", err=True)
                click.echo(
                    f"{RED}error:{NC} Function '{function_name}' got unexpected arguments: {', '.join(extra_args)}",
                    err=True,
                )
                click.echo("", err=True)
                click.echo(f"Function accepts: {', '.join(func_params) if func_params else 'no arguments'}", err=True)
                click.echo("", err=True)
                sys.exit(1)

            # Call the function remotely with provided arguments
            try:
                result = func.remote(**kwargs)

                # Display execution details if --execution flag was set
                if show_output and func.last_metadata:
                    from ..progress import display_single_execution, display_batch_execution

                    # Check if this was a batch execution (has 'items' in metadata)
                    if "items" in func.last_metadata:
                        display_batch_execution(function_name, func.last_metadata)
                    else:
                        display_single_execution(function_name, func.last_metadata)

                if result is not None:
                    print(result)
            except TypeError as e:
                click.echo("", err=True)
                click.echo(
                    f"{RED}error:{NC} Invalid arguments for {function_name}: {e}", err=True
                )
                click.echo("", err=True)

                # Check if this might be due to unknown flags
                unknown_args = [k for k in kwargs.keys() if k not in ['name', 'x', 'item', 'count']]  # common arg names
                if unknown_args and any(arg in str(e) for arg in unknown_args):
                    click.echo("Tip: Unknown flags are passed as function arguments.", err=True)
                    click.echo(f"     Did you mean '--execution' instead of '--{unknown_args[0]}'?", err=True)
                    click.echo("", err=True)

                sys.exit(1)
            except Exception as e:
                # Catch RemoteExecutionError and other execution errors
                from ...executor import RemoteExecutionError

                if isinstance(e, RemoteExecutionError):
                    click.echo("", err=True)
                    click.echo(f"{RED}error:{NC} Remote execution failed", err=True)
                    click.echo("", err=True)

                    # Check if error message indicates argument issues
                    if "unexpected keyword argument" in str(e) or "takes" in str(e) and "positional argument" in str(e):
                        click.echo("This might be caused by passing unknown flags as function arguments.", err=True)
                        click.echo("Tip: Use '--execution' to show execution details", err=True)
                        click.echo("", err=True)
                    else:
                        click.echo(str(e), err=True)
                        click.echo("", err=True)
                else:
                    click.echo("", err=True)
                    click.echo(f"{RED}error:{NC} {e}", err=True)
                    click.echo("", err=True)

                sys.exit(1)

        else:
            # Standard execution - run the module (entrypoint auto-executes)
            # Pass CLI context to the module
            setattr(module, "__flare_show_output__", show_output)  # type: ignore[attr-defined]

            # If arguments provided, we need to pass them to the entrypoint
            if kwargs:
                # Store kwargs in a global that entrypoints can access
                setattr(module, "__flare_cli_args__", kwargs)  # type: ignore[attr-defined]

            spec.loader.exec_module(module)

    except Exception as e:
        click.echo("", err=True)
        click.echo(f"{RED}error:{NC} Error executing script: {e}", err=True)
        click.echo("", err=True)
        raise
    finally:
        os_module.chdir(original_cwd)
        sys.path.remove(str(script_path.parent))


def create_run_command():
    """
    Dynamically create the run command.
    We can't know the arguments ahead of time, so we use context_settings
    to allow unknown options and parse them manually.
    """

    @click.command(
        context_settings=dict(
            ignore_unknown_options=True,
            allow_extra_args=True,
        )
    )
    @click.argument("script")
    @click.option(
        "--execution",
        is_flag=True,
        default=False,
        help="Show execution details and performance metrics",
    )
    @click.pass_context
    def run(ctx: click.Context, script: str, execution: bool) -> None:
        """
        Run a Flare script or function.

        Examples:

          # Run script with entrypoint
          flare run examples/hello.py

          # Run specific function
          flare run examples/hello.py::greet --name "World"

          # Pass arguments to entrypoint
          flare run script.py --count 5 --name "Alice"

          # Show execution details
          flare run script.py --execution
        """
        # Parse extra arguments
        kwargs = {}
        i = 0
        while i < len(ctx.args):
            arg = ctx.args[i]
            if arg.startswith("--"):
                key = arg[2:]  # Remove --
                # Check if next arg is the value
                if i + 1 < len(ctx.args) and not ctx.args[i + 1].startswith("--"):
                    value = ctx.args[i + 1]
                    # Try to convert to appropriate type
                    kwargs[key] = _parse_value(value)
                    i += 2
                else:
                    # Boolean flag
                    kwargs[key] = True
                    i += 1
            else:
                i += 1

        run_script(script, show_output=execution, **kwargs)

    return run


def _parse_value(value: str) -> str | int | float | bool:
    """Parse CLI value to appropriate Python type"""
    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Try bool
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Default to string
    return value


# Export the dynamically created command
run = create_run_command()
