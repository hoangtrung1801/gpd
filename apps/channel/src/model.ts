import { createOpenAI } from "@ai-sdk/openai";

export function resolveModel() {
  const model = (process.env.MODEL || "gpt-4o").trim();
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required for OpenAI model.");
  }
  return `openai:${model}`;
}
