import { NextRequest, NextResponse } from "next/server";
import { generateResearchReply } from "@/lib/ai/provider";
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
    const conversationContext = previousMessages
      .slice(-12)
      .map((message: any) => `${String(message?.role || message?.type || "user").toLowerCase()}: ${String(message?.content || "").trim()}`)
      .filter((line: string) => line.split(": ")[1])
      .join("\n");

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

    const result = await generateResearchReply(
      conversationContext ? `${query}\n\nConversation context:\n${conversationContext}` : query
    );
    const executionTimeMs = Date.now() - startedAt;

    const payload = {
      success: true,
      response: result.response,
      confidence: result.confidence,
      source: result.source,
      clarification_needed: false,
      timestamp: new Date().toISOString(),
      execution_time_ms: executionTimeMs,
    };

    const response = NextResponse.json(payload, { status: 200 });
    Object.entries(createDebugHeaders(result.source, query, result.source, result.response.slice(0, 120))).forEach(
      ([key, value]) => {
        response.headers.set(key, value);
      }
    );

    logInfo("research_request_success", {
      source: result.source,
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
