import { getSandbox } from "@cloudflare/sandbox";
import { ExecuteRequest, ExecuteResponse, ExecuteBatchResponse } from "../types";

interface ExecuteBatchRequest {
  function_id: string;
  code: string;
  function_name: string;
  items: string[]; // Array of hex-encoded cloudpickle items
  max_containers?: number; // Max parallel sandboxes
  timeout?: number; // Execution timeout in seconds per item
}

interface SandboxResult {
  results?: Array<{ text?: string; html?: string; [key: string]: any }>;
  logs?: { stdout?: string[]; stderr?: string[] };
  error?: string;
}

/**
 * Chunk an array into smaller arrays of specified size
 */
function chunk<T>(array: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < array.length; i += size) {
    chunks.push(array.slice(i, i + size));
  }
  return chunks;
}

/**
 * Execute a single item in a sandbox
 */
async function executeItem(
  env: Env,
  functionId: string,
  code: string,
  functionName: string,
  itemHex: string,
  timeoutSeconds: number = 300
): Promise<ExecuteResponse> {
  // Track execution timing
  const startedAt = new Date().toISOString();
  const startTime = Date.now();

  // Create unique sandbox ID for this execution
  const sandboxId = `${functionId}-${crypto.randomUUID().slice(0, 8)}`;
  const sandbox = getSandbox(env.Sandbox, sandboxId);

  // Create fresh Python context
  const pythonCtx = await sandbox.createCodeContext({ language: "python" });

  // Build execution code
  const executionCode = `
import cloudpickle
import sys
import traceback

# Load user code (define the function)
${code}

try:
    # Deserialize input item
    item = cloudpickle.loads(bytes.fromhex("${itemHex}"))

    # Execute function with single item
    result = ${functionName}(item)

    # Serialize and print result with markers
    result_hex = cloudpickle.dumps(result).hex()
    print(f"__FLARE_RESULT__{result_hex}__FLARE_RESULT__")

except Exception as e:
    print(f"__FLARE_ERROR__{str(e)}__FLARE_ERROR__", file=sys.stderr)
    traceback.print_exc()
`;

  try {
    // Execute via Code Interpreter with fresh context and timeout
    const timeoutMs = timeoutSeconds * 1000; // Convert to milliseconds
    const result = (await sandbox.runCode(executionCode, {
      context: pythonCtx,
      timeout: timeoutMs,
    })) as SandboxResult;

    // Parse result - check for error first
    if (result.error) {
      const completedAt = new Date().toISOString();
      const executionTimeMs = Date.now() - startTime;
      return {
        success: false,
        error: result.error,
        stderr: result.logs?.stderr?.join("\n") || "",
        execution_time_ms: executionTimeMs,
        sandbox_id: sandboxId,
        started_at: startedAt,
        completed_at: completedAt,
      };
    }

    const stdout = result.logs?.stdout?.join("\n") || "";
    const stderr = result.logs?.stderr?.join("\n") || "";

    // Check for errors in stderr
    if (stderr.includes("__FLARE_ERROR__")) {
      const errorMatch = stderr.match(/__FLARE_ERROR__(.*)__FLARE_ERROR__/);
      const errorMsg = errorMatch ? errorMatch[1] : "Unknown error";
      const completedAt = new Date().toISOString();
      const executionTimeMs = Date.now() - startTime;
      return {
        success: false,
        error: errorMsg,
        stderr: stderr,
        execution_time_ms: executionTimeMs,
        sandbox_id: sandboxId,
        started_at: startedAt,
        completed_at: completedAt,
      };
    }

    // Extract result from stdout
    const resultMatch = stdout.match(/__FLARE_RESULT__(.*)__FLARE_RESULT__/);
    if (!resultMatch) {
      const completedAt = new Date().toISOString();
      const executionTimeMs = Date.now() - startTime;
      return {
        success: false,
        error: "Failed to extract result from output",
        stdout: stdout,
        stderr: stderr,
        execution_time_ms: executionTimeMs,
        sandbox_id: sandboxId,
        started_at: startedAt,
        completed_at: completedAt,
      };
    }

    const completedAt = new Date().toISOString();
    const executionTimeMs = Date.now() - startTime;

    return {
      success: true,
      result: resultMatch[1], // Hex-encoded result
      stdout: stdout,
      stderr: stderr,
      execution_time_ms: executionTimeMs,
      sandbox_id: sandboxId,
      started_at: startedAt,
      completed_at: completedAt,
    };
  } catch (error) {
    const completedAt = new Date().toISOString();
    const executionTimeMs = Date.now() - startTime;
    return {
      success: false,
      error: error instanceof Error ? error.message : "Execution failed",
      execution_time_ms: executionTimeMs,
      sandbox_id: sandboxId,
      started_at: startedAt,
      completed_at: completedAt,
    };
  } finally {
    // Always destroy sandbox after execution to free resources
    // Per-task sandboxes should be cleaned up immediately
    try {
      await sandbox.destroy();
    } catch (error) {
      // Log but don't fail if cleanup fails
      console.error(`Failed to destroy sandbox ${sandboxId}:`, error);
    }
  }
}

/**
 * Handle /execute-batch endpoint - execute function in parallel across sandboxes
 */
export async function handleExecuteBatch(
  request: Request,
  env: Env
): Promise<Response> {
  let body: ExecuteBatchRequest;

  try {
    body = (await request.json()) as ExecuteBatchRequest;
  } catch (error) {
    const response: ExecuteResponse = {
      success: false,
      error: "Invalid JSON in request body",
    };
    return new Response(JSON.stringify(response), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Validate request
  if (!body.function_id || !body.code || !body.function_name || !body.items) {
    const response: ExecuteResponse = {
      success: false,
      error:
        "Missing required fields: function_id, code, function_name, items",
    };
    return new Response(JSON.stringify(response), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    // Track overall execution timing
    const startTime = Date.now();

    // Default max_containers to 10 if not specified
    const maxContainers = body.max_containers || 10;
    const timeout = body.timeout || 300; // Default 5 minutes

    // Split items into batches based on max_containers
    const batches = chunk(body.items, maxContainers);
    const allResults: ExecuteResponse[] = [];

    // Execute batches sequentially, items within batch in parallel
    for (const batch of batches) {
      const batchTasks = batch.map((itemHex) =>
        executeItem(env, body.function_id, body.code, body.function_name, itemHex, timeout)
      );

      const batchResults = await Promise.all(batchTasks);
      allResults.push(...batchResults);
    }

    const totalExecutionTimeMs = Date.now() - startTime;

    const response: ExecuteBatchResponse = {
      results: allResults,
      total_execution_time_ms: totalExecutionTimeMs,
      batch_count: batches.length,
      max_containers: maxContainers,
    };

    return new Response(JSON.stringify(response), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Batch execution error:", error);
    const response: ExecuteResponse = {
      success: false,
      error: error instanceof Error ? error.message : "Batch execution failed",
    };

    return new Response(JSON.stringify(response), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
