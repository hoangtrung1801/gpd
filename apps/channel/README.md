# Telegram Bot Agent (@gpd/channel)

A Telegram bot agent integrated into **GPD (Grounded Project Developer)**.

## Architecture

```
[Telegram Platform]
       │ (Long Polling or Webhooks via GrammY)
       ▼
[@gpd/channel Server] (Telegram Bot + OpenAI Agent)
       │ (GPD API Client)
       ▼
[GPD Backend API] (:4040)
```

## Features

- **Direct Telegram Integration**: Connects directly to the Telegram Bot API via GrammY — no external gateway, cloud dependency, or CopilotKit required.
- **Task Management**: Use `/tasks [status]` or ask the assistant naturally to list project tasks and triage bugs from GPD.
- **Knowledge Base Search**: Use `/search <query>` to search canonical specification documents (PRDs, FRDs, ADRs) and confirmed knowledge.
- **Human-in-the-loop Proposals**: Use `/propose <action> | <details>` or let the AI agent propose engineering changes with native Telegram inline keyboard buttons (`Approve` / `Hold`).
- **Interactive Decision Recording**: Reviewers can click inline buttons directly in Telegram to record approvals or holds in real time.
- **Structured Cards**: Formats structured task and bug cards with priorities, status indicators, and component areas.
- **AI Agent Chat**: Converse directly with the bot in private messages or by @-mentioning in group chats.

## Commands

- `/start` — Display welcome greeting and bot capabilities.
- `/tasks [status]` — List project tasks and bugs (e.g. `/tasks open`).
- `/search <query>` — Search knowledge base documents and specifications.
- `/propose <action> | <details>` — Post an action proposal with interactive review buttons.
- `/help` — Display command help and usage examples.

## Setup & Running

1. Create a bot and obtain a token:
   - Open Telegram and message [@BotFather](https://t.me/BotFather).
   - Send `/newbot`, choose a name and username.
   - Copy the API token.

2. In `.env`:
   ```dotenv
   TELEGRAM_BOT_TOKEN=your-telegram-bot-token
   OPENAI_API_KEY=your-openai-api-key
   GPD_API_URL=http://127.0.0.1:4040
   GPD_ACCESS_TOKEN=dev-local-token
   ```

3. Run the bot listener:
   ```bash
   pnpm dev:channel
   # or
   pnpm --filter @gpd/channel dev
   ```
