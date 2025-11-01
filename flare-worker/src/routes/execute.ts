import { getSandbox } from "@cloudflare/sandbox";
import { ExecuteRequest, ExecuteResponse } from "../types";

interface SandboxResult {
  results?: Array<{ text?: string; html?: string; [key: string]: any }>;
  logs?: { stdout?: string[]; stderr?: string[] };
  error?: string;
}

/**
 * Handle /execute endpoint - execute a single function in a sandbox
 */
export async function handleExecute(
  request: Request,
  env: Env,
): Promise<Response> {
  let body: ExecuteRequest;

  try {
    body = (await request.json()) as ExecuteRequest;
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
  if (!body.function_id || !body.code || !body.function_name) {
    const response: ExecuteResponse = {
      success: false,
      error: "Missing required fields: function_id, code, function_name",
    };
    return new Response(JSON.stringify(response), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }


  try {
    // Track execution timing
    const startedAt = new Date().toISOString();
    const startTime = Date.now();

    // Get or create sandbox (reuse based on function_id for warmth)
    // Using per-function naming strategy: sandbox persists across calls
    // and auto-destroys after 10min of inactivity. This is intentional
    // to avoid cold start overhead on repeated .remote() calls.
    const sandboxId = env.Sandbox.idFromName(body.function_id);
    const sandboxIdStr = sandboxId.toString();
    const sandbox = getSandbox(env.Sandbox, sandboxIdStr);

    // Create fresh Python context for each execution (isolation)
    const pythonCtx = await sandbox.createCodeContext({ language: "python" });

    // Build execution code
    const executionCode = `
import cloudpickle
import sys
import traceback

# Load user code (define the function)
${body.code}

try:
    # Deserialize inputs
    args = cloudpickle.loads(bytes.fromhex("${body.args || ""}"))
    kwargs = cloudpickle.loads(bytes.fromhex("${body.kwargs || ""}"))

    # Execute function
    result = ${body.function_name}(*args, **kwargs)

    # Serialize and print result with markers
    result_hex = cloudpickle.dumps(result).hex()
    print(f"__FLARE_RESULT__{result_hex}__FLARE_RESULT__")

except Exception as e:
    print(f"__FLARE_ERROR__{str(e)}__FLARE_ERROR__", file=sys.stderr)
    traceback.print_exc()
`;

    // Execute via Code Interpreter with fresh context and timeout
    const timeoutMs = (body.timeout || 300) * 1000; // Convert to milliseconds
    const result = (await sandbox.runCode(executionCode, {
      context: pythonCtx,
      timeout: timeoutMs,
    })) as SandboxResult;

    // Parse result - check for error first
    if (result.error) {
      const response: ExecuteResponse = {
        success: false,
        error: result.error,
        stderr: result.logs?.stderr?.join("\n") || "",
      };

      return new Response(JSON.stringify(response), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    const stdout = result.logs?.stdout?.join("\n") || "";
    const stderr = result.logs?.stderr?.join("\n") || "";

    // Check for errors in stderr
    if (stderr.includes("__FLARE_ERROR__")) {
      const errorMatch = stderr.match(/__FLARE_ERROR__(.*)__FLARE_ERROR__/);
      const errorMsg = errorMatch ? errorMatch[1] : "Unknown error";

      const response: ExecuteResponse = {
        success: false,
        error: errorMsg,
        stderr: stderr,
      };

      return new Response(JSON.stringify(response), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Extract result from stdout
    const resultMatch = stdout.match(/__FLARE_RESULT__(.*)__FLARE_RESULT__/);
    if (!resultMatch) {
      const response: ExecuteResponse = {
        success: false,
        error: "Failed to extract result from output",
        stdout: stdout,
        stderr: stderr,
      };

      return new Response(JSON.stringify(response), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    const completedAt = new Date().toISOString();
    const executionTimeMs = Date.now() - startTime;

    const response: ExecuteResponse = {
      success: true,
      result: resultMatch[1], // Hex-encoded result
      stdout: stdout,
      stderr: stderr,
      execution_time_ms: executionTimeMs,
      sandbox_id: sandboxIdStr,
      started_at: startedAt,
      completed_at: completedAt,
    };

    return new Response(JSON.stringify(response), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (error) {
    console.error("Execution error:", error);
    const response: ExecuteResponse = {
      success: false,
      error: error instanceof Error ? error.message : "Execution failed",
    };

    return new Response(JSON.stringify(response), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
