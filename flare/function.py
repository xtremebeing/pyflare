"""
Function wrapper class
"""

from typing import TYPE_CHECKING, Any, override
from collections.abc import Callable as CallableType

if TYPE_CHECKING:
    from .app import App


class Function:
    """
    Wrapper around decorated functions providing .remote(), .local(), and .map()

    Usage:
        result = my_function.remote(arg1, arg2)
        local_result = my_function.local(arg1, arg2)
        results = my_function.map([item1, item2, item3])
    """

    def __init__(
        self,
        fn: CallableType[..., object],
        app: "App",
        serialized: dict[str, Any],
        options: dict[str, Any],
    ):  # type: ignore[misc]
        self.fn: CallableType[..., object] = fn
        self.app: App = app
        self.serialized: dict[str, Any] = serialized  # type: ignore[misc]
        self.options: dict[str, Any] = options  # type: ignore[misc]
        self.name: str = serialized["name"]
        self.id: str = serialized["id"]

        # Store last execution metadata (for CLI output display)
        self.last_metadata: dict[str, object] | None = None

        # Make the Function callable - calling it directly executes locally
        self.__name__: str = fn.__name__
        self.__doc__: str | None = fn.__doc__

    def remote(self, *args: object, **kwargs: object) -> object:
        """Execute function remotely in Cloudflare Sandbox"""
        timeout = self.options.get("timeout", 300)
        env = self.options.get("env", {})

        # Filter out None values from env
        env = {k: v for k, v in env.items() if v is not None}

        result, metadata = self.app.executor.execute(
            function_id=self.id,
            code=self.serialized["code"],
            function_name=self.name,
            args=args,
            kwargs=kwargs,
            timeout=timeout,
            env=env,
        )

        self.last_metadata = metadata

        # Check if CLI requested output display
        self._maybe_display_output()

        return result

    def local(self, *args: object, **kwargs: object) -> object:
        """Execute function locally (for testing)"""
        return self.fn(*args, **kwargs)

    def map(self, items: list[object]) -> list[object]:
        """Execute function in parallel across multiple sandboxes"""
        max_containers = self.options.get("max_containers")
        timeout = self.options.get("timeout", 300)
        env = self.options.get("env", {})

        # Filter out None values from env
        env = {k: v for k, v in env.items() if v is not None}

        results, metadata = self.app.executor.execute_batch(
            function_id=self.id,
            code=self.serialized["code"],
            function_name=self.name,
            items=items,
            max_containers=max_containers,
            timeout=timeout,
            env=env,
        )

        self.last_metadata = metadata

        # Check if CLI requested output display
        self._maybe_display_output()

        return results

    def __call__(self, *args: object, **kwargs: object) -> object:
        """Calling the function directly executes it locally"""
        return self.local(*args, **kwargs)

    def _maybe_display_output(self) -> None:
        """Display execution output if CLI requested it"""
        import sys
        import inspect

        # Check if we're being called from a module with __flare_show_output__ set
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller_globals = frame.f_back.f_back.f_globals
            show_output = caller_globals.get("__flare_show_output__", False)

            if show_output and self.last_metadata:
                # Import here to avoid circular dependency
                from .cli.progress import (
                    display_single_execution,
                    display_batch_execution,
                )

                # Check if this was a batch execution (has 'items' in metadata)
                if "items" in self.last_metadata:
                    display_batch_execution(self.name, self.last_metadata)
                else:
                    display_single_execution(self.name, self.last_metadata)

    @override
    def __repr__(self) -> str:
        return f"<Function {self.name} ({self.id})>"
