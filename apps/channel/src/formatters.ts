import { InlineKeyboard } from "grammy";

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export interface TaskCardData {
  publicId: string;
  title: string;
  priority?: "high" | "medium" | "low" | string;
  status?: string;
  area?: string;
  summary: string;
}

const PRIORITY_ICONS: Record<string, string> = {
  high: "🔴 HIGH PRIORITY",
  medium: "🟡 MEDIUM PRIORITY",
  low: "🟢 LOW PRIORITY",
};

export function formatTaskCard(task: TaskCardData): string {
  const priorityKey = (task.priority || "medium").toLowerCase();
  const priorityLabel = PRIORITY_ICONS[priorityKey] || escapeHtml(task.priority || "medium");
  const status = task.status || "open";

  const lines = [
    `📌 <b>${escapeHtml(task.publicId)}: ${escapeHtml(task.title)}</b>`,
    `<b>Priority:</b> ${priorityLabel}`,
    `<b>Status:</b> <code>${escapeHtml(status)}</code>`,
  ];

  if (task.area) {
    lines.push(`<b>Area:</b> ${escapeHtml(task.area)}`);
  }

  lines.push("────────────────────");
  lines.push(escapeHtml(task.summary));

  return lines.join("\n");
}

export interface TaskSummaryItem {
  id?: string;
  public_id?: string;
  title: string;
  status: string;
  priority?: string;
  kind?: string;
}

export function formatTaskList(tasks: TaskSummaryItem[]): string {
  if (tasks.length === 0) {
    return "<i>No tasks found matching your criteria.</i>";
  }

  const lines = [`📋 <b>GPD Tasks (${tasks.length})</b>\n`];
  for (const t of tasks) {
    const id = t.public_id || t.id || "TASK";
    const status = t.status || "open";
    const priority = t.priority ? ` [${t.priority}]` : "";
    lines.push(`• <b>${escapeHtml(id)}</b>: ${escapeHtml(t.title)} (<code>${escapeHtml(status)}</code>${escapeHtml(priority)})`);
  }
  return lines.join("\n");
}

export interface SearchHitItem {
  title?: string;
  source?: string;
  content?: string;
  summary?: string;
  score?: number;
}

export function formatSearchResults(hits: SearchHitItem[], query: string): string {
  if (hits.length === 0) {
    return `<i>No knowledge base results found for:</i> "<code>${escapeHtml(query)}</code>"`;
  }

  const lines = [`🔍 <b>Knowledge Search Results for "${escapeHtml(query)}"</b>\n`];
  for (let i = 0; i < hits.length; i++) {
    const hit = hits[i];
    const title = hit.title || hit.source || `Document ${i + 1}`;
    const snippet = (hit.summary || hit.content || "").trim();
    const truncated = snippet.length > 250 ? `${snippet.slice(0, 250)}...` : snippet;

    lines.push(`<b>${i + 1}. ${escapeHtml(title)}</b>`);
    if (truncated) {
      lines.push(`<i>${escapeHtml(truncated)}</i>`);
    }
    lines.push("");
  }
  return lines.join("\n").trimEnd();
}

export function formatProposalMessage(
  action: string,
  description: string,
  status: "pending" | "approved" | "held" = "pending",
  reviewer?: string,
): string {
  const lines = [
    "⚖️ <b>Action Proposal Review</b>\n",
    `<b>Action:</b> ${escapeHtml(action)}`,
    `<b>Details:</b> ${escapeHtml(description)}\n`,
  ];

  if (status === "pending") {
    lines.push("<b>Status:</b> ⏳ <i>Pending Review</i>");
    lines.push("<i>Click a button below to record an engineering decision.</i>");
  } else if (status === "approved") {
    const by = reviewer ? ` by ${escapeHtml(reviewer)}` : "";
    lines.push(`<b>Status:</b> ✅ <b>Approved</b>${by}`);
    lines.push("<i>Approved proposal. No destructive production action executed.</i>");
  } else {
    const by = reviewer ? ` by ${escapeHtml(reviewer)}` : "";
    lines.push(`<b>Status:</b> ⏸️ <b>Held</b>${by}`);
    lines.push("<i>Held by reviewer. No action taken.</i>");
  }

  return lines.join("\n");
}

export function createProposalKeyboard(proposalId: string): InlineKeyboard {
  return new InlineKeyboard()
    .text("✅ Approve", `prop:appr:${proposalId}`)
    .text("⏸️ Hold", `prop:hold:${proposalId}`);
}

export function formatWelcomeMessage(): string {
  return [
    "🤖 <b>GPD (Grounded Project Developer) Assistant</b>\n",
    "Hello! I am GPD. I can inspect specifications, summarize discussions into bug tasks, and retrieve canonical context directly in Telegram.\n",
    "<b>Commands:</b>",
    "• /tasks [status] — List project tasks and bugs (e.g. <code>/tasks open</code>)",
    "• /search &lt;query&gt; — Search PRDs, FRDs, ADRs, and confirmed knowledge",
    "• /propose &lt;action&gt; | &lt;details&gt; — Post an action proposal for review",
    "• /help — Show help and capabilities\n",
    "Or simply message me in private or mention me in a group to discuss bugs, specs, and architecture decisions.",
  ].join("\n");
}
