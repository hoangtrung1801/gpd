import { createChannel } from "@copilotkit/channels";
import { makeChannelAgent } from "./agent.js";
import { TaskCard, welcomeMessage } from "./components.js";
import { listTasks, proposeAction, readThread, searchKnowledge } from "./tools.js";
import { requiredEnv } from "./env.js";

const channelCode = requiredEnv("CHANNEL_CODE");
export const channel = createChannel({
  name: channelCode,
  identifyUser: "platform",
  agent: makeChannelAgent,
  tools: [readThread, proposeAction, listTasks, searchKnowledge],
  components: [TaskCard],
  context: [
    {
      description: "Rendering",
      value: "You can draw native cards by calling task_card. Prefer it over plain prose when summarizing a task or bug.",
    },
    {
      description: "Surface",
      value: "This is a Slack thread. Keep answers concise, factual, and actionable. Refer to earlier messages when available.",
    },
  ],
});

channel.onMention(async ({ thread }) => {
  await thread.subscribe();
  await thread.runAgent();
});

channel.onMessage(async ({ thread }) => {
  if (await thread.isSubscribed()) {
    await thread.runAgent();
  }
});

channel.onWelcome(async ({ thread, platform }) => {
  await thread.post(welcomeMessage(platform));
});
