import { pathToFileURL } from "node:url";
import { createServer, type Server } from "node:http";
import { webhookCallback, type Bot } from "grammy";
import { createTelegramBot } from "./bot.js";
import { getEnv, getTelegramBotToken } from "./env.js";

let server: Server | undefined;
let botInstance: Bot | undefined;

const shutdown = async () => {
  console.log("\n  Gracefully shutting down Telegram bot...");
  if (botInstance) {
    try {
      await botInstance.stop();
    } catch {
      // Ignore stop errors during shutdown
    }
  }
  if (server?.listening) {
    server.close();
  }
  process.exit(0);
};

process.once("SIGINT", shutdown);
process.once("SIGTERM", shutdown);

export async function startServer(port = Number(process.env.PORT ?? 3000)) {
  const token = getTelegramBotToken();

  if (!token) {
    console.error(
      "\n  ❌ Telegram bot token is not configured (TELEGRAM_BOT_TOKEN missing).\n" +
        "  To connect to Telegram:\n" +
        "    1. Open Telegram and search for @BotFather.\n" +
        "    2. Send /newbot and follow prompts to get an API token.\n" +
        "    3. Set TELEGRAM_BOT_TOKEN=<your-token> in your .env file.\n" +
        "    4. Run: pnpm dev:channel (or pnpm --filter @gpd/channel dev)\n",
    );
    throw new Error("TELEGRAM_BOT_TOKEN is required.");
  }

  const bot = createTelegramBot(token);
  botInstance = bot;

  const webhookUrl = getEnv("TELEGRAM_WEBHOOK_URL");

  if (webhookUrl) {
    // Webhook mode
    await bot.api.setWebhook(webhookUrl);
    console.log(`\n  ✓ Telegram webhook set to: ${webhookUrl}`);

    const handler = webhookCallback(bot, "http");
    server = createServer((req, res) => {
      if (req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", mode: "webhook" }));
        return;
      }
      handler(req, res);
    });

    return new Promise<void>((resolve) => {
      server!.listen(port, () => {
        console.log(`  ✓ Webhook listener active on :${port}`);
        resolve();
      });
    });
  } else {
    // Long polling mode (default)
    const botInfo = await bot.api.getMe();
    console.log(`\n  ✓ Connected to Telegram as @${botInfo.username} (${botInfo.first_name})`);
    console.log(`    Chat with the bot: https://t.me/${botInfo.username}\n`);

    // Optional lightweight health server
    server = createServer((req, res) => {
      if (req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", bot: botInfo.username, mode: "polling" }));
        return;
      }
      res.writeHead(404);
      res.end();
    });

    await new Promise<void>((resolve) => {
      server!.listen(port, () => {
        console.log(`  ✓ Health check endpoint listening on :${port}/health`);
        resolve();
      });
    });

    // Start long polling
    bot.start({
      onStart: (info) => {
        console.log(`  ✓ Polling active for @${info.username}. Ready to receive messages.\n`);
      },
    });
  }
}

// If run directly
if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    await startServer();
  } catch (err) {
    console.error("Fatal startup error:", err);
    process.exit(1);
  }
}
