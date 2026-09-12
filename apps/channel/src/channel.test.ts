import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  escapeHtml,
  formatProposalMessage,
  formatSearchResults,
  formatTaskCard,
  formatTaskList,
  formatWelcomeMessage,
  createProposalKeyboard,
} from "./formatters.js";
import {
  createProposal,
  executeListTasks,
  executeSearchKnowledge,
  formatTaskCardTool,
  getProposal,
  listTasksTool,
  proposeActionTool,
  searchKnowledgeTool,
  updateProposalStatus,
} from "./tools.js";
import { createTelegramBot } from "./bot.js";

// Mock the API client
vi.mock("./env.js", () => ({
  getTelegramBotToken: vi.fn(),
  getGpdApiUrl: vi.fn().mockReturnValue("http://127.0.0.1:4040"),
  getGpdAccessToken: vi.fn().mockReturnValue("test-token"),
  getOpenAiApiKey: vi.fn().mockReturnValue("test-openai-key"),
  getModelName: vi.fn().mockReturnValue("gpt-4o"),
  getEnv: vi.fn(),
  requiredEnv: vi.fn(),
}));

vi.mock("@gpd/api-client", () => {
  return {
    ApiClient: vi.fn().mockImplementation(() => ({
      listTasks: vi.fn().mockResolvedValue({
        ok: true,
        data: [
          { public_id: "BUG-1", title: "Checkout payment failure", status: "open", priority: "high" },
          { public_id: "TASK-2", title: "Refactor auth middleware", status: "in_progress", priority: "medium" },
        ],
      }),
      search: vi.fn().mockResolvedValue({
        ok: true,
        data: {
          hits: [
            { title: "Checkout PRD", summary: "Requirements for checkout retry flow", score: 0.95 },
            { title: "Payment ADR", summary: "Architecture decision for webhook idempotent processing", score: 0.88 },
          ],
        },
      }),
    })),
  };
});

describe("Telegram Message Formatters", () => {
  it("escapes HTML special characters correctly", () => {
    expect(escapeHtml("<script>alert('xss') & \"test\"</script>")).toBe(
      "&lt;script&gt;alert('xss') &amp; &quot;test&quot;&lt;/script&gt;",
    );
  });

  it("formats TaskCard with all fields", () => {
    const card = formatTaskCard({
      publicId: "BUG-101",
      title: "Token expiration in checkout",
      priority: "high",
      status: "open",
      area: "Checkout",
      summary: "Users cannot complete checkout when session expires.",
    });

    expect(card).toContain("📌 <b>BUG-101: Token expiration in checkout</b>");
    expect(card).toContain("🔴 HIGH PRIORITY");
    expect(card).toContain("<code>open</code>");
    expect(card).toContain("<b>Area:</b> Checkout");
    expect(card).toContain("Users cannot complete checkout when session expires.");
  });

  it("formats TaskCard with default priority and optional fields omitted", () => {
    const card = formatTaskCard({
      publicId: "TASK-5",
      title: "Update dependencies",
      summary: "Bump packages to latest stable.",
    });

    expect(card).toContain("📌 <b>TASK-5: Update dependencies</b>");
    expect(card).toContain("🟡 MEDIUM PRIORITY");
    expect(card).toContain("<code>open</code>");
    expect(card).not.toContain("<b>Area:</b>");
  });

  it("formats task list when items exist", () => {
    const list = formatTaskList([
      { public_id: "BUG-1", title: "Fix crash", status: "open", priority: "high" },
    ]);
    expect(list).toContain("📋 <b>GPD Tasks (1)</b>");
    expect(list).toContain("• <b>BUG-1</b>: Fix crash (<code>open</code> [high])");
  });

  it("formats empty task list gracefully", () => {
    const list = formatTaskList([]);
    expect(list).toContain("No tasks found");
  });

  it("formats search results when hits exist", () => {
    const results = formatSearchResults(
      [{ title: "Payment ADR", summary: "Idempotent payment webhook", score: 0.9 }],
      "webhook",
    );
    expect(results).toContain('🔍 <b>Knowledge Search Results for "webhook"</b>');
    expect(results).toContain("<b>1. Payment ADR</b>");
    expect(results).toContain("<i>Idempotent payment webhook</i>");
  });

  it("formats empty search results gracefully", () => {
    const results = formatSearchResults([], "nonexistent");
    expect(results).toContain('No knowledge base results found for:</i> "<code>nonexistent</code>"');
  });

  it("formats proposal message in pending state", () => {
    const msg = formatProposalMessage("Deploy hotfix", "Restores payment webhook", "pending");
    expect(msg).toContain("⚖️ <b>Action Proposal Review</b>");
    expect(msg).toContain("<b>Action:</b> Deploy hotfix");
    expect(msg).toContain("<b>Details:</b> Restores payment webhook");
    expect(msg).toContain("⏳ <i>Pending Review</i>");
  });

  it("formats proposal message in approved state with reviewer", () => {
    const msg = formatProposalMessage("Deploy hotfix", "Restores payment webhook", "approved", "@lead_eng");
    expect(msg).toContain("✅ <b>Approved</b> by @lead_eng");
    expect(msg).toContain("Approved proposal. No destructive production action executed.");
  });

  it("formats proposal message in held state with reviewer", () => {
    const msg = formatProposalMessage("Drop database", "Dangerous operation", "held", "@admin");
    expect(msg).toContain("⏸️ <b>Held</b> by @admin");
    expect(msg).toContain("Held by reviewer. No action taken.");
  });

  it("formats welcome message with all supported commands", () => {
    const welcome = formatWelcomeMessage();
    expect(welcome).toContain("🤖 <b>GPD (Grounded Project Developer) Assistant</b>");
    expect(welcome).toContain("/tasks [status]");
    expect(welcome).toContain("/search");
    expect(welcome).toContain("/propose");
    expect(welcome).toContain("/help");
  });

  it("creates proposal keyboard with Approve and Hold buttons", () => {
    const keyboard = createProposalKeyboard("test1234");
    expect(keyboard.inline_keyboard).toHaveLength(1);
    const [btnApprove, btnHold] = keyboard.inline_keyboard[0];
    expect(btnApprove.text).toBe("✅ Approve");
    if ("callback_data" in btnApprove) {
      expect(btnApprove.callback_data).toBe("prop:appr:test1234");
    }
    expect(btnHold.text).toBe("⏸️ Hold");
    if ("callback_data" in btnHold) {
      expect(btnHold.callback_data).toBe("prop:hold:test1234");
    }
  });
});

describe("Proposal Store & Tools", () => {
  it("creates, retrieves, and updates proposals", () => {
    const proposal = createProposal("Migrate DB", "Runs alembic upgrade");
    expect(proposal.id).toBeDefined();
    expect(proposal.status).toBe("pending");
    expect(proposal.action).toBe("Migrate DB");

    const retrieved = getProposal(proposal.id);
    expect(retrieved).toEqual(proposal);

    const updated = updateProposalStatus(proposal.id, "approved", "@reviewer");
    expect(updated?.status).toBe("approved");
    expect(updated?.reviewer).toBe("@reviewer");
  });

  it("returns undefined when updating non-existent proposal", () => {
    const updated = updateProposalStatus("unknown-id", "approved");
    expect(updated).toBeUndefined();
  });

  it("executes list tasks using GPD ApiClient", async () => {
    const res = await executeListTasks("default", "open");
    expect(res.ok).toBe(true);
    expect(res.tasks).toHaveLength(2);
    expect(res.message).toContain("BUG-1");
  });

  it("executes search knowledge using GPD ApiClient", async () => {
    const res = await executeSearchKnowledge("default", "webhook");
    expect(res.ok).toBe(true);
    expect(res.hits).toHaveLength(2);
    expect(res.message).toContain("Payment ADR");
  });

  it("defines AI tools with correct parameters and descriptions", () => {
    expect(listTasksTool.description).toContain("List tasks");
    expect(searchKnowledgeTool.description).toContain("Search project documentation");
    expect(proposeActionTool.description).toContain("Propose an engineering action");
    expect(formatTaskCardTool.description).toContain("Format a structured GPD task");
  });
});

describe("Telegram Bot Initialization", () => {
  it("throws descriptive error when bot token is missing", () => {
    expect(() => createTelegramBot(undefined)).toThrow("TELEGRAM_BOT_TOKEN is required");
  });

  it("creates bot instance when valid token is provided", () => {
    // Valid format for a fake token: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
    const fakeToken = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ";
    const bot = createTelegramBot(fakeToken);
    expect(bot).toBeDefined();
    expect(bot.token).toBe(fakeToken);
  });
});
