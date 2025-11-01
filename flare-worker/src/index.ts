import { ExecuteResponse } from "./types";
import { validateApiKey } from "./auth";
import { handleExecute } from "./routes/execute";
import { handleExecuteBatch } from "./routes/executeBatch";

export { Sandbox } from "@cloudflare/sandbox";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // CORS headers for CLI
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };

    // Handle preflight requests
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // Health check (no auth required)
    if (url.pathname === "/health" && request.method === "GET") {
      return new Response(JSON.stringify({ status: "ok" }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Authentication for all other routes
    const apiKey = request.headers.get("Authorization")?.replace("Bearer ", "");
    if (!validateApiKey(apiKey, env)) {
      const response: ExecuteResponse = {
        success: false,
        error: "Unauthorized",
      };
      return new Response(JSON.stringify(response), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Route handling
    try {
      let response: Response;

      if (url.pathname === "/execute" && request.method === "POST") {
        response = await handleExecute(request, env);
      } else if (url.pathname === "/execute-batch" && request.method === "POST") {
        response = await handleExecuteBatch(request, env);
      } else {
        const errorResponse: ExecuteResponse = {
          success: false,
          error: "Not Found",
        };
        response = new Response(JSON.stringify(errorResponse), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }

      // Add CORS headers to response
      const headers = new Headers(response.headers);
      Object.entries(corsHeaders).forEach(([key, value]) => {
        headers.set(key, value);
      });

      return new Response(response.body, {
        status: response.status,
        headers,
      });
    } catch (error) {
      console.error("Worker error:", error);
      const errorResponse: ExecuteResponse = {
        success: false,
        error: error instanceof Error ? error.message : "Internal Server Error",
      };
      return new Response(JSON.stringify(errorResponse), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
  },
};
