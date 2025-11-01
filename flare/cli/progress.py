"""
Progress display utilities for CLI output
"""


# ANSI color codes
GREEN = "\033[0;32m"
DIM = "\033[2m"
NC = "\033[0m"  # No Color


def display_single_execution(function_name: str, metadata: dict) -> None:
    """Display execution info for single function call

    Args:
        function_name: Name of the executed function
        metadata: Execution metadata from executor
    """
    execution_time_ms = metadata.get("execution_time_ms")

    if execution_time_ms is not None:
        execution_time_s = execution_time_ms / 1000
        print(f"\n> {function_name}() · {execution_time_s:.1f}s")
    else:
        print(f"\n> {function_name}()")

    # Display stdout if present
    stdout = metadata.get("stdout", "")
    if stdout:
        # Remove the __FLARE_RESULT__ markers from stdout
        stdout = _clean_stdout(stdout)
        if stdout.strip():
            for line in stdout.splitlines():
                print(f"  {line}")

    print()


def display_batch_execution(function_name: str, metadata: dict) -> None:
    """Display execution info for batch/parallel execution

    Args:
        function_name: Name of the executed function
        metadata: Batch execution metadata from executor
    """
    total_time_ms = metadata.get("total_execution_time_ms")
    batch_count = metadata.get("batch_count")
    max_containers = metadata.get("max_containers")
    items = metadata.get("items", [])

    print(f"\n> {function_name}(x) · Parallel Execution\n")

    # Display container visualization
    if batch_count and max_containers and items:
        total_items = len(items)

        # Calculate how many items each container processed
        container_loads = [0] * max_containers
        for idx, item in enumerate(items):
            container_idx = idx % max_containers
            container_loads[container_idx] += 1

        # Group containers by load for summary display
        from collections import defaultdict
        load_groups = defaultdict(list)
        for container_idx, load in enumerate(container_loads):
            load_groups[load].append(container_idx + 1)  # 1-indexed

        # Calculate average time per load group
        load_group_times = {}
        for load, container_indices in load_groups.items():
            # Get times for items processed by these containers
            times = []
            for container_idx in container_indices:
                # Get items processed by this container (0-indexed)
                for idx, item in enumerate(items):
                    if (idx % max_containers) == (container_idx - 1):
                        if item.get("execution_time_ms"):
                            times.append(item["execution_time_ms"])
            if times:
                load_group_times[load] = sum(times) / len(times) / 1000

        print(f"  {GREEN}✓{NC} {max_containers} containers processed {total_items} items")

        # Sort by load (descending) for better readability
        for load in sorted(load_groups.keys(), reverse=True):
            container_indices = load_groups[load]
            count = len(container_indices)

            # Format container range
            if count == 1:
                container_range = f"Container {container_indices[0]}"
            elif count == max_containers:
                container_range = f"All containers"
            else:
                # Show range if consecutive, otherwise show count
                if container_indices == list(range(min(container_indices), max(container_indices) + 1)):
                    container_range = f"Container {min(container_indices)}-{max(container_indices)}"
                else:
                    container_range = f"{count} containers"

            # Show average time if available
            avg_time_str = ""
            if load in load_group_times:
                avg_time_str = f" ({load_group_times[load]:.1f}s avg)"

            item_word = "item" if load == 1 else "items"
            print(f"  {GREEN}✓{NC} {container_range}: {load} {item_word} each{avg_time_str}")

    # Display summary statistics
    total_items = len(items)
    if total_time_ms is not None:
        total_time_s = total_time_ms / 1000
        print(f"\n  {total_items} items · {total_time_s:.1f}s total\n")
    else:
        print(f"\n  {total_items} items\n")


def _clean_stdout(stdout: str) -> str:
    """Remove Flare internal markers from stdout

    Args:
        stdout: Raw stdout from sandbox

    Returns:
        Cleaned stdout with markers removed
    """
    # Remove result markers
    import re

    stdout = re.sub(r"__FLARE_RESULT__.*?__FLARE_RESULT__\n?", "", stdout)
    return stdout
