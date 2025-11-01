"""
Remote execution client
"""

import httpx
import cloudpickle


class RemoteExecutionError(Exception):
    """Raised when remote execution fails"""

    pass


class RemoteExecutor:
    """
    Handles communication with Cloudflare Worker API.
    Manages function execution and result deserialization.
    """

    def __init__(self, worker_url: str, api_key: str):
        self.worker_url: str = worker_url.rstrip("/")
        self.api_key: str = api_key
        self.client: httpx.Client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,  # 2 minute timeout for remote execution
        )

    def execute(
        self,
        function_id: str,
        code: str,
        function_name: str,
        args: tuple[object, ...],
        kwargs: dict[str, object],
        timeout: int = 300,
    ) -> tuple[object, dict[str, object]]:
        """Execute a single function remotely

        Returns:
            Tuple of (result, metadata) where metadata contains execution info
        """

        # Serialize inputs
        args_hex = cloudpickle.dumps(args).hex()
        kwargs_hex = cloudpickle.dumps(kwargs).hex()

        # Make request to Worker
        try:
            response = self.client.post(
                f"{self.worker_url}/execute",
                json={
                    "function_id": function_id,
                    "code": code,
                    "function_name": function_name,
                    "args": args_hex,
                    "kwargs": kwargs_hex,
                    "timeout": timeout,
                },
                timeout=timeout + 10,  # Add buffer for network overhead
            )
            _ = response.raise_for_status()
        except httpx.HTTPError as e:
            raise RemoteExecutionError(f"HTTP error: {e}")

        data = response.json()

        if not data.get("success"):
            error_msg = data.get("error", "Unknown error")
            stderr = data.get("stderr", "")

            error_details = f"Remote execution failed: {error_msg}"
            if stderr:
                error_details += f"\n\nRemote stderr:\n{stderr}"

            raise RemoteExecutionError(error_details)

        # Extract metadata
        metadata = {
            "execution_time_ms": data.get("execution_time_ms"),
            "sandbox_id": data.get("sandbox_id"),
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at"),
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
        }

        # Deserialize result
        try:
            result_bytes = bytes.fromhex(data["result"])
            result = cloudpickle.loads(result_bytes)
            return result, metadata
        except Exception as e:
            raise RemoteExecutionError(f"Failed to deserialize result: {e}")

    def execute_batch(
        self,
        function_id: str,
        code: str,
        function_name: str,
        items: list[object],
        max_containers: int | None = None,
        timeout: int = 300,
    ) -> tuple[list[object], dict[str, object]]:
        """Execute function in parallel across multiple sandboxes

        Returns:
            Tuple of (results, metadata) where metadata contains batch execution info
        """

        # Serialize items
        items_hex = [cloudpickle.dumps(item).hex() for item in items]

        # Prepare request payload
        payload = {
            "function_id": function_id,
            "code": code,
            "function_name": function_name,
            "items": items_hex,
            "timeout": timeout,
        }

        if max_containers is not None:
            payload["max_containers"] = max_containers

        # Calculate total timeout for batch (with buffer)
        # Batches run sequentially, so total time = (items / max_containers) * timeout
        max_cont = max_containers or 10
        num_batches = (len(items) + max_cont - 1) // max_cont  # Ceiling division
        batch_timeout = (num_batches * timeout) + 30  # Add 30s buffer

        # Make request to Worker
        try:
            response = self.client.post(
                f"{self.worker_url}/execute-batch", json=payload, timeout=batch_timeout
            )
            _ = response.raise_for_status()
        except httpx.HTTPError as e:
            raise RemoteExecutionError(f"HTTP error: {e}")

        data = response.json()

        # Deserialize results (results is now array of ExecuteResponse objects)
        results = []
        item_metadata = []
        for item_response in data["results"]:
            if not item_response.get("success"):
                error_msg = item_response.get("error", "Unknown error")
                raise RemoteExecutionError(f"Batch item execution failed: {error_msg}")

            try:
                result_bytes = bytes.fromhex(item_response["result"])
                results.append(cloudpickle.loads(result_bytes))
                item_metadata.append({
                    "execution_time_ms": item_response.get("execution_time_ms"),
                    "sandbox_id": item_response.get("sandbox_id"),
                    "stdout": item_response.get("stdout", ""),
                    "stderr": item_response.get("stderr", ""),
                })
            except Exception as e:
                raise RemoteExecutionError(f"Failed to deserialize result: {e}")

        # Extract batch-level metadata
        metadata = {
            "total_execution_time_ms": data.get("total_execution_time_ms"),
            "batch_count": data.get("batch_count"),
            "max_containers": data.get("max_containers"),
            "items": item_metadata,
        }

        return results, metadata

    def close(self):
        """Clean up HTTP client"""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()
