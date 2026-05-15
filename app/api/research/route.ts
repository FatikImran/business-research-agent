export const runtime = "nodejs";

import { NextRequest, NextResponse } from "next/server";
import { spawnSync } from "child_process";
import path from "path";
import { logError, logInfo } from "@/lib/utils/logger";

function createDebugHeaders(mode: string, query = "", status = "", preview = "") {
  const headers: Record<string, string> = {
    "X-Response-Mode": mode,
  };

  if (query) headers["X-Debug-Query"] = query.slice(0, 80);
  if (status) headers["X-Debug-Status"] = status.slice(0, 80);
  if (preview) headers["X-Debug-Preview"] = preview.slice(0, 200);

  return headers;
}

export async function GET() {
  return NextResponse.json(
    {
      success: true,
      message: "Use POST /api/research with JSON body: { query, previous_messages? }",
    },
    { status: 200 }
  );
}

export async function POST(request: NextRequest) {
  const startedAt = Date.now();

  try {
    const body = await request.json().catch(() => ({}));
    const query = String(body?.query || "").trim();
    const previousMessages = Array.isArray(body?.previous_messages) ? body.previous_messages : [];

    if (!query) {
      const response = NextResponse.json(
        { success: false, error: "Query is required", timestamp: new Date().toISOString() },
        { status: 400 }
      );
      Object.entries(createDebugHeaders("error", query, "missing-query")).forEach(([key, value]) => {
        response.headers.set(key, value);
      });
      return response;
    }

    const bridgePayload = {
      query,
      state: body?.state ?? { messages: previousMessages },
      previous_messages: previousMessages,
    };

    let result: any;

    const renderUrl = process.env.RENDER_AGENT_URL;
    if (renderUrl) {
      // Call remote Render-hosted Python service
      const res = await fetch(renderUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bridgePayload),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Agent service error: ${res.status} ${text}`);
      }

      result = await res.json();
    } else {
      // Fallback to local Python bridge (spawn)
      const bridgeScript = path.join(process.cwd(), "business_research_agent", "api_bridge.py");
      const pythonExecutable = process.env.PYTHON_EXECUTABLE || process.env.PYTHON || "python";

      const bridgeResult = spawnSync(pythonExecutable, [bridgeScript], {
        input: JSON.stringify(bridgePayload),
        encoding: "utf8",
        maxBuffer: 10 * 1024 * 1024,
        env: process.env,
      });

      if (bridgeResult.error) {
        throw bridgeResult.error;
      }

      if (bridgeResult.status !== 0) {
        throw new Error(
          bridgeResult.stderr?.trim() || `Python bridge failed with exit code ${bridgeResult.status}`
        );
      }

      const rawOutput = bridgeResult.stdout.trim();
      if (!rawOutput) {
        throw new Error("Python bridge returned no output");
      }

      try {
        result = JSON.parse(rawOutput);
      } catch (error) {
        throw new Error(
          `Failed to parse Python bridge response: ${error instanceof Error ? error.message : "unknown"}`
        );
      }
    }

    const executionTimeMs = Date.now() - startedAt;

    const payload = {
      success: true,
      response: result.response,
      confidence: result.confidence_score,
      source: result.source || result.current_agent || "langgraph",
      clarification_needed: Boolean(result.clarification_needed),
      validation_result: result.validation_result,
      state: result.state,
      timestamp: new Date().toISOString(),
      execution_time_ms: executionTimeMs,
    };

    const response = NextResponse.json(payload, { status: 200 });
    Object.entries(createDebugHeaders(payload.source, query, result.validation_result || payload.source, String(result.response || "").slice(0, 120))).forEach(
      ([key, value]) => {
        response.headers.set(key, value);
      }
    );

    logInfo("research_request_success", {
      source: payload.source,
      executionTimeMs,
      query: query.slice(0, 120),
    });

    return response;
  } catch (error) {
    const executionTimeMs = Date.now() - startedAt;
    const message = error instanceof Error ? error.message : "unknown";
    logError("research_request_failed", { message, executionTimeMs });

    const response = NextResponse.json(
      {
        success: false,
        error: "Unhandled server error while processing the request.",
        detail: message,
        timestamp: new Date().toISOString(),
        execution_time_ms: executionTimeMs,
      },
      { status: 500 }
    );

    Object.entries(createDebugHeaders("error", "", "unhandled-exception", message)).forEach(([key, value]) => {
      response.headers.set(key, value);
    });

    return response;
  }
}
