import { Bot, type Context } from "grammy";
import { runGpdAgent } from "./agent.js";
import { getTelegramBotToken } from "./env.js";
import {
  createProposalKeyboard,
  escapeHtml,
  formatProposalMessage,
  formatWelcomeMessage,
} from "./formatters.js";
import {
  createProposal,
  executeListTasks,
  executeSearchKnowledge,
  getProposal,
  updateProposalStatus,
} from "./tools.js";

export function createTelegramBot(token?: string): Bot {
  const botToken = token || getTelegramBotToken();
  if (!botToken) {
    throw new Error(
      "TELEGRAM_BOT_TOKEN is required. Please set it in your environment or .env file.\n" +
        "You can obtain a token from https://t.me/BotFather.",
    );
  }

  const bot = new Bot(botToken);

  // Global error handler
  bot.catch((err) => {
    const ctx = err.ctx;
    console.error(`[Telegram Bot Error] Error while handling update ${ctx.update.update_id}:`, err.error);
  });

  // /start command
  bot.command("start", async (ctx) => {
    await ctx.reply(formatWelcomeMessage(), { parse_mode: "HTML" });
  });

  // /help command
  bot.command("help", async (ctx) => {
    const helpText = [
      "🛠 <b>GPD Bot Commands</b>\n",
      "• <code>/tasks [status]</code> — List tasks in the project (e.g. <code>/tasks open</code>)",
      "• <code>/search &lt;query&gt;</code> — Search documentation and knowledge base",
      "• <code>/propose &lt;action&gt; | &lt;details&gt;</code> — Create an engineering action proposal with review buttons",
      "• <code>/help</code> — Show this help message\n",
      "You can also chat with me naturally about code, bugs, or specs!",
    ].join("\n");
    await ctx.reply(helpText, { parse_mode: "HTML" });
  });

  // /tasks command
  bot.command("tasks", async (ctx) => {
    const text = ctx.match?.trim();
    const status = text ? text : undefined;

    await ctx.replyWithChatAction("typing");
    const result = await executeListTasks("default", status);
    await ctx.reply(result.message, { parse_mode: "HTML" });
  });

  // /search command
  bot.command("search", async (ctx) => {
    const query = ctx.match?.trim();
    if (!query) {
      await ctx.reply("Please specify a search query.\nUsage: <code>/search &lt;query&gt;</code>", {
        parse_mode: "HTML",
      });
      return;
    }

    await ctx.replyWithChatAction("typing");
    const result = await executeSearchKnowledge("default", query);
    await ctx.reply(result.message, { parse_mode: "HTML" });
  });

  // /propose command
  bot.command("propose", async (ctx) => {
    const text = ctx.match?.trim();
    if (!text) {
      await ctx.reply(
        "Please describe the proposal.\nUsage: <code>/propose &lt;action&gt; | &lt;details&gt;</code>",
        { parse_mode: "HTML" },
      );
      return;
    }

    let action = text;
    let description = "Engineering action proposed for review.";

    if (text.includes("|")) {
      const parts = text.split("|");
      action = parts[0].trim();
      description = parts.slice(1).join("|").trim();
    }

    const proposal = createProposal(action, description);
    const message = formatProposalMessage(action, description, "pending");
    const keyboard = createProposalKeyboard(proposal.id);

    await ctx.reply(message, {
      parse_mode: "HTML",
      reply_markup: keyboard,
    });
  });

  // Handle callback queries for proposal reviews (Approve / Hold)
  bot.callbackQuery(/^prop:(appr|hold):([a-z0-9]+)$/, async (ctx) => {
    const match = ctx.match;
    const decision = match[1] === "appr" ? "approved" : "held";
    const proposalId = match[2];

    const proposal = getProposal(proposalId);
    if (!proposal) {
      await ctx.answerCallbackQuery({
        text: "Proposal expired or not found.",
        show_alert: true,
      });
      return;
    }

    const reviewer =
      ctx.from?.username ? `@${ctx.from.username}` : ctx.from?.first_name || "a reviewer";

    updateProposalStatus(proposalId, decision, reviewer);

    const updatedText = formatProposalMessage(
      proposal.action,
      proposal.description,
      decision,
      reviewer,
    );

    try {
      await ctx.editMessageText(updatedText, {
        parse_mode: "HTML",
        reply_markup: undefined, // Remove inline buttons once decided
      });
    } catch {
      // Message might already be updated
    }

    await ctx.answerCallbackQuery({
      text: decision === "approved" ? "Proposal approved!" : "Proposal marked as held.",
    });
  });

  // Handle regular text messages
  bot.on("message:text", async (ctx) => {
    const text = ctx.message.text.trim();
    if (text.startsWith("/")) {
      // Unrecognized slash command
      return;
    }

    const chatType = ctx.chat.type;
    const isPrivate = chatType === "private";
    const me = ctx.me;
    const isMentioned = me ? text.includes(`@${me.username}`) : false;
    const isReplyToMe = ctx.message.reply_to_message?.from?.id === me?.id;

    // In groups, only respond if mentioned or replying to bot
    if (!isPrivate && !isMentioned && !isReplyToMe) {
      return;
    }

    // Strip bot mention if present
    const cleanPrompt = me
      ? text.replace(new RegExp(`@${me.username}`, "gi"), "").trim()
      : text;

    if (!cleanPrompt) {
      await ctx.reply("How can I assist you with GPD tasks, bugs, or specifications?");
      return;
    }

    await ctx.replyWithChatAction("typing");

    try {
      const response = await runGpdAgent({ prompt: cleanPrompt });
      const replyText = response.text || "I've processed your request.";

      // If the agent proposed an action, attach the keyboard for the first proposal
      if (response.proposals.length > 0) {
        const firstProposal = response.proposals[0];
        const keyboard = createProposalKeyboard(firstProposal.proposalId);
        try {
          await ctx.reply(replyText, {
            parse_mode: "HTML",
            reply_markup: keyboard,
          });
        } catch {
          await ctx.reply(replyText, { reply_markup: keyboard });
        }
      } else {
        try {
          await ctx.reply(replyText, { parse_mode: "HTML" });
        } catch {
          // Fallback to plain text if model generated invalid HTML
          await ctx.reply(replyText);
        }
      }
    } catch (err) {
      console.error("[Agent Error]", err);
      await ctx.reply(
        `Sorry, an error occurred while processing your request: ${escapeHtml(String(err))}`,
        { parse_mode: "HTML" },
      );
    }
  });

  return bot;
}
