import { createOpenAI } from "@ai-sdk/openai";
import { getModelName, getOpenAiApiKey } from "./env.js";

export function resolveModel() {
  const modelName = getModelName();
  const apiKey = getOpenAiApiKey();
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is required for OpenAI model.");
  }
  const openai = createOpenAI({ apiKey });
  return openai(modelName);
}
