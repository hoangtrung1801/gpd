# Slack Thread Agent (@gpd/channel)

A Slack thread agent powered by **CopilotKit Channels** and integrated into **GPD (Grounded Project Developer)**.

## Architecture

```
[Slack Platform] 
       │ (Mentions / Messages via App Manifest)
       ▼
[CopilotKit Intelligence Gateway]
       │ (Outbound WebSocket)
       ▼
[@gpd/channel Server] (CopilotKitRuntime + CopilotKit Channels)
       │ (GPD API Client)
       ▼
[GPD Backend API] (:7337)
```

## Features
- **Thread Context**: Reads previous discussion messages using `read_thread`.
- **GPD Task Integration**: Uses `list_tasks` to check project bugs and tasks from GPD.
- **Knowledge Base Search**: Uses `search_knowledge` to search PRD/FRD/ADR documents stored in GPD.
- **Human-in-the-loop Proposal**: Renders native Slack action proposal cards with approve/hold buttons via `propose_action`.
- **Native Block Kit UI**: Renders structured cards using `task_card` component.

## Setup & Running

1. In `.env`:
   ```dotenv
   CHANNEL_CODE=your-channel-code
   INTELLIGENCE_API_KEY=your-intelligence-api-key
   OPENAI_API_KEY=your-openai-api-key
   GPD_API_URL=http://127.0.0.1:7337
   ```

2. Register channel manifest with Slack:
   ```bash
   npx copilotkit@latest channels add --name gpd-slack --display-name "GPD Assistant" --adapter slack --json
   ```

3. Run the channel listener:
   ```bash
   pnpm --filter @gpd/channel dev
   ```
