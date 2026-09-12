import { generateText, isStepCount } from "ai";
import { resolveModel } from "./model.js";
import {
  formatTaskCardTool,
  listTasksTool,
  proposeActionTool,
  searchKnowledgeTool,
} from "./tools.js";

export const GPD_SYSTEM_PROMPT = `You are the GPD (Grounded Project Developer) AI assistant living in Telegram.
You help engineering teams triage bugs, review architecture decisions (ADR), check specifications (PRD/FRD), retrieve context packages, and inspect project tasks.
Always be concise, professional, and actionable.

Available tools:
- list_tasks: Query tasks and bugs from GPD.
- search_knowledge: Search specifications (PRD, FRD, ADR) and confirmed knowledge.
- propose_action: Suggest changes, fixes, or rollouts for human approval.
- format_task_card: Render a structured task card with priority, status, and summary.

Formatting guidelines:
- Telegram supports HTML formatting. Use <b>bold</b>, <i>italic</i>, <code>code</code>, or <pre>code block</pre>.
- Avoid markdown like **bold** or \`code\`; use HTML tags instead.
- Do not output unescaped < or > characters in normal prose; use &lt; and &gt;.`;

export interface AgentRunOptions {
  prompt: string;
  history?: Array<{ role: "user" | "assistant" | "system"; content: string }>;
}

export interface AgentRunResult {
  text: string;
  proposals: Array<{ proposalId: string; action: string; description: string }>;
  toolCallsCount: number;
}

export async function runGpdAgent({
  prompt,
  history = [],
}: AgentRunOptions): Promise<AgentRunResult> {
  const model = resolveModel();
  const messages = [
    ...history.map((m) => ({ role: m.role, content: m.content })),
    { role: "user" as const, content: prompt },
  ];

  const result = await generateText({
    model,
    system: GPD_SYSTEM_PROMPT,
    messages,
    tools: {
      list_tasks: listTasksTool,
      search_knowledge: searchKnowledgeTool,
      propose_action: proposeActionTool,
      format_task_card: formatTaskCardTool,
    },
    stopWhen: isStepCount(5),
  });

  // Check if any proposals were generated during the steps
  const proposals: Array<{ proposalId: string; action: string; description: string }> = [];
  for (const step of result.steps) {
    for (const toolResult of step.toolResults) {
      if (toolResult.toolName === "propose_action" && toolResult.output) {
        const res = toolResult.output as {
          proposalId?: string;
          action?: string;
          description?: string;
        };
        if (res.proposalId && res.action) {
          proposals.push({
            proposalId: res.proposalId,
            action: res.action,
            description: res.description || "",
          });
        }
      }
    }
  }

  return {
    text: result.text,
    proposals,
    toolCallsCount: result.steps.reduce((acc, s) => acc + s.toolCalls.length, 0),
  };
}
