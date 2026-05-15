import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json(
    {
      success: true,
      service: "Business Research Assistant",
      geminiConfigured: Boolean(process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY),
      timestamp: new Date().toISOString(),
    },
    { status: 200 }
  );
}
