import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

function loadEnvFile(filePath: string) {
  if (!existsSync(filePath)) return;
  try {
    const content = readFileSync(filePath, "utf-8");
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      let val = trimmed.slice(eqIdx + 1).trim();
      if (
        (val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))
      ) {
        val = val.slice(1, -1);
      }
      if (process.env[key] === undefined) {
        process.env[key] = val;
      }
    }
  } catch {
    // Ignore read errors
  }
}

// Auto-load root .env or apps/channel/.env if present
loadEnvFile(resolve(process.cwd(), ".env"));
loadEnvFile(resolve(process.cwd(), "../../.env"));
loadEnvFile(resolve(process.cwd(), "../.env"));

export function getEnv(name: string, defaultValue?: string): string | undefined {
  const val = process.env[name];
  if (val !== undefined && val !== "") {
    return val;
  }
  return defaultValue;
}

export function requiredEnv(name: string): string {
  const val = getEnv(name);
  if (!val) {
    throw new Error(`Environment variable ${name} is required.`);
  }
  return val;
}

export function getTelegramBotToken(): string | undefined {
  return getEnv("TELEGRAM_BOT_TOKEN");
}

export function getGpdApiUrl(): string {
  if (process.env.GPD_API_URL) return process.env.GPD_API_URL;
  const host = process.env.GPD_API_HOST || "127.0.0.1";
  const port = process.env.GPD_API_PORT || "4040";
  return `http://${host}:${port}`;
}

export function getGpdAccessToken(): string | undefined {
  return getEnv("GPD_ACCESS_TOKEN");
}

export function getOpenAiApiKey(): string | undefined {
  return getEnv("OPENAI_API_KEY");
}

export function getModelName(): string {
  return (getEnv("GPD_LLM_MODEL") || getEnv("MODEL") || "gpt-4o").trim();
}
