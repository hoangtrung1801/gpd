# GPD — Get Project Done

## 1. Product Summary

GPD is a shared project-context and coordination layer for software teams working with humans and AI agents.

It captures important project knowledge from conversations, documents, tasks, code, and development activity, then gives the right context to the right person or coding agent at the right time.

GPD turns temporary team conversations into durable project knowledge and actionable work.

**Tagline:** Shared memory and coordination for human + AI software teams.

---

## 2. Problem

Modern software teams store project context across many disconnected places:

- Slack conversations
- PRDs and FRDs
- GitHub
- task trackers
- architecture documents
- source code
- coding-agent sessions

Important information is often discussed once in a conversation and then lost.

For example, a QA engineer may report a bug in Slack. A developer asks several questions, the team discovers the likely cause, and everyone understands the issue.

But when someone later creates a task, much of that context is manually copied, simplified, or lost.

Then the developer's coding agent starts with even less context.

This creates several problems:

- developers repeatedly ask for context
- coding agents start each task with project amnesia
- useful decisions disappear inside conversations
- tasks lose the reasoning behind them
- agents may implement outdated requirements
- multiple people or agents may work on conflicting changes

---

## 3. Product Vision

GPD should act as the project's shared memory.

A team should be able to discuss work naturally in the tools they already use, while GPD understands and preserves the important project context.

Example:

```text
QA:
Checkout keeps loading when I use an expired saved card.

Developer:
What error does the API return?

QA:
payment_method_invalid.

Developer:
Probably our payment error handler.

QA:
@GPD create a bug task from this conversation.
```

GPD should understand the conversation and create:

```text
BUG-231
Checkout hangs when saved card is expired

Actual:
API returns payment_method_invalid but UI stays loading.

Expected:
Show an error and allow another payment method.

Likely component:
Payment error handling

Source:
Slack discussion
```

Later, when a developer starts working on `BUG-231`, GPD should automatically provide the coding agent with the original conversation and all relevant project knowledge.

---

## 4. Core Product Loop

```text
Team works and communicates
        ↓
Slack / Docs / Code / Tasks
        ↓
       GPD
        ↓
Understand project context
        ↓
Create or update project artifacts
        ↓
Store durable project memory
        ↓
Developer starts task
        ↓
GPD selects relevant context
        ↓
Coding agent works
        ↓
New knowledge is created
        ↓
GPD updates project memory
```

The project's understanding should improve as the team works.

---

## 5. Target Users

### QA Engineer

Needs to turn discovered issues and team discussions into clear bug reports without manually rewriting the entire conversation.

### Software Developer

Needs the full context behind a task without searching across Slack, documentation, task trackers, and code.

### Engineering Team

Needs important decisions and implementation knowledge to remain available after conversations end.

### Coding Agent

Needs the same product, technical, and team context a human developer would need before making changes.

---

## 6. Primary Use Case — Slack Conversation to Bug

### Scenario

A QA engineer discovers a bug and reports it in Slack.

The team discusses:

- what happened
- how to reproduce it
- expected behavior
- actual behavior
- environment
- likely technical cause

The QA engineer then says:

```text
@GPD create a bug task from this conversation
```

### Expected GPD Behavior

GPD should:

1. Read the current Slack thread.
2. Understand the bug being discussed.
3. Extract relevant structured information.
4. Create a bug task.
5. Preserve the Slack conversation as source context.
6. Return the created bug to the team.

The resulting task may include:

- title
- description
- reproduction steps
- actual behavior
- expected behavior
- severity
- environment
- affected component
- technical clues
- participants
- source conversation

GPD should not invent information that was not present or reasonably inferable.

---

## 7. Secondary Use Case — Coding Agent Context

When a developer starts work on the bug, GPD should understand which task they are working on.

Example:

```text
BUG-231
Checkout hangs when saved card is expired
```

GPD should collect and select relevant context such as:

- original Slack discussion
- PRD requirements
- FRD requirements
- architecture decisions
- previous related bugs
- recent team decisions
- relevant source files
- active teammate work

The coding agent should receive this context automatically.

The developer should not manually copy information from Slack or project documents into the coding agent.

---

## 8. Core Features

### 8.1 Conversation Understanding

GPD can read a project conversation and identify its meaning.

For the MVP, GPD should understand bug discussions well enough to extract:

- issue
- reproduction steps
- actual behavior
- expected behavior
- technical clues
- affected component

---

### 8.2 Project Artifact Creation

GPD converts conversations into structured project artifacts.

MVP:

- bug task

Future:

- feature task
- engineering task
- ADR
- project decision
- requirement update
- meeting action items

---

### 8.3 Project Memory

GPD stores important project context so it survives beyond the original conversation.

Project memory may contain:

- bugs
- requirements
- architecture decisions
- implementation constraints
- team decisions
- task history
- technical discoveries

---

### 8.4 Context Selection

GPD should not simply dump all available information into an AI agent.

It must determine what information is relevant to the current task.

Inputs may include:

- task
- repository
- branch
- files
- developer prompt
- project documentation
- team conversations
- project decisions
- recent activity

---

### 8.5 Coding Agent Context Injection

GPD provides selected project context to a coding agent before implementation begins.

The experience should feel automatic.

Example:

```text
GPD detected:

Project:
Checkout Platform

Task:
BUG-231

Relevant context loaded:

✓ Original QA discussion
✓ Payment requirements
✓ Payment architecture decision
✓ Related files
✓ Recent team activity
```

---

### 8.6 Active Work Awareness

GPD should know what developers or coding agents are currently working on.

Example:

```text
Alice
BUG-231
payment error handling

Bob
TASK-245
checkout UI
```

This provides the foundation for team coordination.

---

### 8.7 Work Conflict Detection

If two humans or agents are working on overlapping areas, GPD should warn them.

Example:

```text
Potential conflict detected.

Alice is currently modifying:
payment-service.ts

Your task affects the same payment flow.
```

This is a high-value differentiator but secondary to the main hackathon flow.

---

### 8.8 Project Knowledge Capture

When development work finishes, GPD should identify useful new project knowledge.

Example:

```text
New technical decision detected:

payment_method_invalid should be normalized
inside PaymentService before reaching the UI.
```

This information can be stored and reused later.

---

## 9. MVP Scope

The hackathon MVP should prove one complete project-context loop.

### Must Have

1. Slack bot integration.
2. Read a Slack thread.
3. Understand a bug discussion.
4. Create a structured bug task.
5. Save the original discussion as task context.
6. Select that task from the developer environment.
7. Provide relevant context to a coding agent.
8. Show the coding agent using that context.

### Strong Differentiators

If time permits:

1. detect overlapping developer or agent work
2. extract new project knowledge after implementation
3. reuse that new knowledge in another agent session

### Not Required

Do not spend hackathon time building:

- full project management software
- Jira replacement
- Linear replacement
- documentation editor
- advanced permissions
- complex dashboards
- many coding-agent integrations
- many messaging integrations

One strong end-to-end workflow is more important.

---

## 10. Hackathon Demo

### Scene 1 — QA Reports Bug

QA and developer discuss a checkout bug in Slack.

The conversation naturally establishes:

- issue
- reproduction
- actual behavior
- expected behavior
- technical clue

---

### Scene 2 — GPD Creates Work

QA writes:

```text
@GPD create a bug task from this conversation
```

GPD responds:

```text
Created BUG-231

Checkout hangs when saved card is expired

Actual:
payment_method_invalid is returned but UI remains loading.

Expected:
Display an error and allow another payment method.

Area:
Payments

Source:
This Slack thread
```

---

### Scene 3 — Developer Starts Work

The developer selects `BUG-231`.

GPD automatically prepares context:

```text
Task
BUG-231

Original QA discussion
Relevant PRD requirement
Relevant architecture decision
Related source files
Recent team activity
```

The coding agent receives this without manual copy/paste.

---

### Scene 4 — Coding Agent Fixes the Bug

The coding agent understands both the code and the project reasoning behind the issue.

It modifies the correct part of the system.

---

### Scene 5 — GPD Learns

After the task is completed, GPD captures an important implementation decision.

Example:

```text
Project knowledge learned:

payment_method_invalid is normalized
inside PaymentService.
```

Future developers and agents can now receive this knowledge automatically.

---

## 11. Success Criteria

The MVP is successful if judges can clearly see:

### Conversation Understanding

GPD understands an actual team discussion rather than requiring a structured form.

### Agentic Action

GPD performs an action from the context by creating the correct project artifact.

### Durable Context

The original conversation remains connected to the task instead of disappearing after task creation.

### Context Reuse

A developer's coding agent later receives the information captured earlier.

### Environment Integration

The workflow happens inside tools where the team already works:

- Slack
- terminal / IDE
- source repository
- coding agent

### Minimal Manual Context Transfer

Users do not need to repeatedly copy project information between systems.

---

## 12. Product Principles

### Context should follow the work

People should not have to search for project context every time they change tools.

### Conversations are project data

Important project understanding often appears first in human conversations.

GPD should preserve it.

### Store reasoning, not only outcomes

A task saying "fix checkout" is less valuable than knowing why the task exists and what the team learned during the discussion.

### Give agents relevant context, not maximum context

More tokens are not always better.

GPD should select what matters.

### Project memory should improve continuously

Each conversation, task, and implementation should make future work easier.

---

## 13. Product Differentiation

GPD is not another:

- chatbot
- Slack bot
- task manager
- coding agent
- project search tool
- RAG interface

Each of those tools manages one part of the workflow.

GPD connects the context between them.

The key loop is:

```text
Conversation
     ↓
Understanding
     ↓
Project artifact
     ↓
Project memory
     ↓
Coding agent
     ↓
Implementation
     ↓
New knowledge
     ↓
Project memory
```

---

## 14. Product Positioning

### One-line version

**GPD turns team conversations into durable project context and gives that context to humans and AI agents when they need it.**

### Developer-focused version

**GPD is shared project memory for human + AI engineering teams.**

### Problem-focused version

**Coding agents are smart, but every session starts with amnesia. GPD gives them the memory of the project.**

---

## 15. Long-Term Vision

GPD should eventually understand project activity across:

- Slack
- Teams
- GitHub
- Linear
- Jira
- documentation
- repositories
- IDEs
- coding agents

Users could naturally say:

```text
@GPD create a bug from this discussion
```

```text
@GPD save this as an architecture decision
```

```text
@GPD update the requirement based on what we decided
```

```text
@GPD what is everyone working on?
```

```text
@GPD give my coding agent everything it needs for this task
```

The long-term goal is for GPD to become the **living shared context layer of a software project**.