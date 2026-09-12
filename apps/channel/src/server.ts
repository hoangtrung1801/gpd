import { createServer } from "node:http";
import { CopilotKitIntelligence, CopilotRuntime } from "@copilotkit/runtime/v2";
import { createCopilotNodeListener } from "@copilotkit/runtime/v2/node";
import { channel } from "./channel.js";
import { getEnv, requiredEnv } from "./env.js";

const apiKey = requiredEnv("INTELLIGENCE_API_KEY");

const intelligence = new CopilotKitIntelligence({
  apiKey,
  apiUrl: getEnv("INTELLIGENCE_API_URL"),
  wsUrl: getEnv("INTELLIGENCE_GATEWAY_WS_URL") || "wss://gateway.intelligence.copilotkit.ai",
});
const runtime = new CopilotRuntime({
  agents: {},
  intelligence,
  channels: [channel],
});

let teardown: (() => Promise<void>) | undefined;
const shutdown = async () => {
  await teardown?.();
  process.exit(0);
};
process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);

const listener = createCopilotNodeListener({ runtime, basePath: "/api/copilotkit" });
const channels = listener.channels;
const server = createServer(listener);

teardown = async () => {
  await channels.stop();
  if (server.listening) server.close();
};

export async function startServer(port = Number(process.env.PORT ?? 3000)) {
  await channels.ready({ timeoutMs: 30_000 });

  const status = channels.status();
  if (status.overall !== "online") {
    console.error(
      `\n  Channel is not online: ${JSON.stringify(status)}\n` +
        `  → 'setup_required' means the provider side is unfinished.\n`
    );
    if (teardown) {
      await teardown();
    }
    process.exit(1);
  }

  return new Promise<void>((resolve) => {
    server.listen(port, () => {
      console.log(`\n  ✓ Channel "${process.env.CHANNEL_CODE}" online — listening on :${port}`);
      console.log(`    Invite the bot to a channel (/invite @yourbot), then @-mention it.\n`);
      resolve();
    });
  });
}

// If run directly
if (import.meta.url === `file://${process.argv[1]}`) {
  await startServer();
}
