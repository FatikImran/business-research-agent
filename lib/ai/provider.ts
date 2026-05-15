import { GoogleGenAI } from "@google/genai";
import { needsEscalation } from "@/lib/ai/guardrails";
import { RESEARCH_SYSTEM_PROMPT } from "@/lib/ai/prompts";
import { logWarn } from "@/lib/utils/logger";

export type ResearchResult = {
  response: string;
  confidence: number;
  source: "gemini" | "fallback";
};

function fallbackResponse(query: string) {
  const normalized = query.toLowerCase();

  if (normalized.includes("apple")) {
    return {
      response:
        "Apple is a large-cap consumer technology company with strong ecosystem lock-in across iPhone, Mac, iPad, wearables, services, and silicon. Its market position is anchored by premium pricing, brand strength, and a high-retention installed base. Key watch areas are iPhone demand cycles, services growth, AI feature rollout, and regulatory pressure on App Store economics.",
      confidence: 6,
    };
  }

  return {
    response:
      "I may be missing a policy detail. I can escalate this to a human support specialist.",
    confidence: 3,
  };
}

export async function generateResearchReply(userMessage: string): Promise<ResearchResult> {
  const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  const model = process.env.GEMINI_MODEL || "gemini-2.5-flash";

  if (!apiKey) {
    const fallback = fallbackResponse(userMessage);
    return {
      response: fallback.response,
      confidence: fallback.confidence,
      source: "fallback",
    };
  }

  try {
    const ai = new GoogleGenAI({ apiKey });
    logWarn("gemini_research_request", { model, message: userMessage.slice(0, 120) });

    const response = await ai.models.generateContent({
      model,
      contents: [
        {
          role: "user",
          parts: [
            {
              text: `${RESEARCH_SYSTEM_PROMPT}\n\nUser query: ${userMessage}\n\nReturn a concise market overview with clear caveats if current data is unavailable.`,
            },
          ],
        },
      ],
    });

    const text = response.text?.trim();
    if (!text) {
      throw new Error("Empty Gemini response");
    }

    return {
      response: text,
      confidence: needsEscalation(text, userMessage) ? 4 : 7,
      source: "gemini",
    };
  } catch (error) {
    logWarn("gemini_research_failed", {
      message: error instanceof Error ? error.message : "unknown",
    });

    const fallback = fallbackResponse(userMessage);
    return {
      response: fallback.response,
      confidence: fallback.confidence,
      source: "fallback",
    };
  }
}
