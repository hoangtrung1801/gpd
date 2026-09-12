import {
  defineChannelComponent,
  Message,
  Header,
  Section,
  Markdown,
  Fields,
  Field,
  Context,
  Divider,
  Actions,
  Button,
} from "@copilotkit/channels";
import { z } from "zod";

const PRIORITY_THEME = {
  high: { accent: "#C4145F", label: "HIGH PRIORITY" },
  medium: { accent: "#8A5C10", label: "MEDIUM PRIORITY" },
  low: { accent: "#5B6478", label: "LOW PRIORITY" },
} as const;

export const TaskCard = defineChannelComponent({
  name: "task_card",
  description:
    "Draw a structured GPD task or bug card in Slack. Call this whenever displaying or summarizing a task or bug. Prefer it over plain text.",
  parameters: z.object({
    publicId: z.string().describe("Task identifier, e.g. BUG-1 or TASK-12"),
    title: z.string().describe("Concise task title"),
    priority: z.enum(["high", "medium", "low"]).default("medium"),
    status: z.string().default("open"),
    area: z.string().optional().describe("Component or area, e.g. Payment or Checkout"),
    summary: z.string().describe("Summary of the task or bug"),
  }),
  render({ publicId, title, priority, status, area, summary }) {
    const theme = PRIORITY_THEME[priority];
    return (
      <Message accent={theme.accent}>
        <Header>{`${publicId}: ${title}`}</Header>
        <Context>{`${theme.label} · Status: ${status}`}</Context>
        <Fields>
          {area && <Field label="Area">{area}</Field>}
          <Field label="Status">{status}</Field>
        </Fields>
        <Section>
          <Markdown>{summary}</Markdown>
        </Section>
      </Message>
    );
  },
});

export function welcomeMessage(platform: string) {
  return (
    <Message accent="#2E7D5B">
      <Header>GPD Developer Assistant in Slack</Header>
      <Section>
        <Markdown>
          {"Hello! I am GPD (Grounded Project Developer). I can inspect specifications, summarize discussions into bug tasks, and retrieve canonical context directly in " +
            platform +
            " threads."}
        </Markdown>
      </Section>
      <Fields>
        <Field label="Capabilities">Bug Triage, Context Inspection, Spec Lookup</Field>
        <Field label="Safe execution">Human confirmation required for knowledge promotion</Field>
      </Fields>
      <Actions>
        <Button
          value="catchup"
          style="primary"
          onClick={async ({ thread }) => {
            await thread.runAgent({
              prompt:
                "Read this thread and summarize the active discussion or bug.",
            });
          }}
        >
          Summarize thread
        </Button>
      </Actions>
    </Message>
  );
}
