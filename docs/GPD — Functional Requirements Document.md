# GPD — Functional Requirements Document

## 1. Purpose

This document defines the functional requirements for the GPD hackathon MVP.

GPD is a shared project-context and coordination layer for human + AI software teams.

It connects project conversations, project knowledge, tasks, development activity, and coding agents so that useful context is captured once and reused everywhere.

The MVP must demonstrate four core behaviors:

1. Understand project conversations and developer activity.
2. Convert conversations into structured project artifacts.
3. Give coding agents the right project context automatically.
4. Preserve new project knowledge for the rest of the team.

---

# 2. Core Product Loop

```text
Team Conversation
Slack / Teams
      ↓
     GPD
      ↓
Understand discussion
      ↓
Create structured project artifact
Bug / Task / Decision / Requirement
      ↓
Project Memory
      ↓
Developer starts work
      ↓
GPD selects relevant context
      ↓
Coding Agent
      ↓
Implementation
      ↓
New knowledge captured
      ↓
Project Memory updated
```

GPD should transform temporary conversations into durable project context.

---

# 3. Core Example

A QA engineer reports a bug in Slack.

```text
QA:
Checkout keeps loading when I use an expired saved card.

Developer:
Does the payment API return an error?

QA:
Yes. payment_method_invalid.
But the UI never stops loading.

Developer:
Probably payment error handling.

QA:
@GPD create a bug task from this conversation.
```

GPD reads the conversation and creates:

```text
BUG-231

Title:
Checkout hangs when saved payment card is expired

Description:
Checkout remains in loading state when an expired
saved Visa card is used.

Steps to reproduce:
1. Open checkout
2. Select expired saved card
3. Submit payment

Actual:
API returns payment_method_invalid.
UI remains loading.

Expected:
Show payment error and allow user to choose
another payment method.

Likely component:
Payment error handling

Source:
Slack conversation
```

Later, when a developer works on `BUG-231`, GPD automatically gives the coding agent the relevant Slack discussion, requirements, technical decisions, and related code.

---

# 4. Functional Requirements

## FR-01 — Project Registration

The user must be able to initialize GPD for a software project.

Example:

```bash
gpd init
```

GPD should create a project identity containing:

- project name
- repository
- default branch
- team identifier
- integrations
- GPD configuration

Example:

```text
.gpd/
  config.json
```

---

# 5. Project Knowledge

## FR-02 — Project Knowledge Ingestion

GPD must allow project knowledge to be added.

Supported MVP sources:

- PRD
- FRD
- ADR
- Markdown documents
- task descriptions
- Slack conversations
- manually created project notes

Each knowledge item should store:

```text
id
type
title
content
source
author
timestamp
related tasks
related files
```

---

## FR-03 — Project Memory

GPD must maintain persistent project memory.

Memory may contain:

- requirements
- bugs
- decisions
- architecture rules
- constraints
- task context
- team conversations
- implementation discoveries

Example:

```text
Decision:
Payment retries belong in PaymentService.

Reason:
Retry behavior must be shared across checkout flows.

Source:
Slack thread + BUG-231 implementation.
```

---

# 6. Slack Integration

## FR-04 — Slack Workspace Integration

GPD must be available inside a Slack workspace.

Users should be able to invoke GPD by mentioning it.

Example:

```text
@GPD create a bug task from this conversation
```

For the MVP, GPD must support Slack threads.

GPD should have access to:

- current message
- thread messages
- message authors
- timestamps
- attached links
- referenced project/task identifiers

Optional:

- screenshots
- file attachments
- reactions
- linked GitHub issues

---

## FR-05 — Conversation Context Retrieval

When GPD is invoked inside a Slack thread, it must retrieve the relevant conversation context.

GPD must identify:

- who reported the issue
- who participated
- what happened
- expected behavior
- actual behavior
- reproduction details
- technical clues
- affected system
- decisions made in the thread

GPD should ignore unrelated conversation where possible.

---

## FR-06 — Conversation Understanding

GPD must analyze a conversation and determine its project meaning.

For a bug discussion, GPD should attempt to extract:

```text
bug title
summary
description
steps to reproduce
actual behavior
expected behavior
environment
severity
affected component
technical clues
participants
source conversation
```

Fields that cannot be confidently inferred should remain empty or be marked as unknown.

GPD must not invent important factual details.

---

# 7. Project Artifact Creation

## FR-07 — Create Bug From Conversation

A user must be able to ask:

```text
@GPD create a bug from this conversation
```

GPD must:

1. Read the current thread.
2. Determine the core bug.
3. Generate a structured bug task.
4. Create the task in GPD.
5. Preserve the Slack thread as source context.
6. Return the created task to Slack.

Example response:

```text
Created BUG-231

Checkout hangs when saved card is expired

Priority: High
Area: Payments

I've linked this Slack discussion as source context.
```

---

## FR-08 — Generic Artifact Creation

GPD should be designed so the same system can later support:

```text
@GPD create a task from this conversation

@GPD turn this into an ADR

@GPD save this as a project decision

@GPD update the requirement based on this conversation
```

For the hackathon MVP, only bug/task creation is required.

---

## FR-09 — Task Data Model

A task should contain:

```text
id
type
title
description
status
priority
reporter
assignee
acceptance criteria
reproduction steps
expected behavior
actual behavior
related component
related files
source conversations
created_at
updated_at
```

Example:

```text
BUG-231

Title:
Checkout hangs when saved card is expired

Source:
Slack thread #checkout-bugs

Reporter:
QA

Related component:
Payments
```

---

# 8. Developer Work Context

## FR-10 — Current Task

GPD must know what task a developer or coding agent is currently working on.

For the MVP, the task may be selected manually.

Example:

```bash
gpd task set BUG-231
```

Future integrations may infer tasks from:

- branch name
- GitHub issue
- Linear
- Jira
- Slack
- coding agent prompt

---

## FR-11 — Developer Session

GPD must create an active development session.

Example:

```bash
gpd start
```

A session should contain:

```text
developer
repository
branch
task
started_at
active files
agent
status
```

---

## FR-12 — Automatic Environment Detection

GPD should detect:

- Git repository
- branch
- changed files
- current task
- recent commits

Optional:

- active file
- IDE
- coding agent
- GitHub user

---

# 9. Context Selection

## FR-13 — Relevant Context Generation

When a developer starts working on a task, GPD must select the most useful context.

Possible sources:

- originating Slack conversation
- PRD
- FRD
- architecture decisions
- previous bugs
- project memory
- related source files
- teammate activity
- task description

GPD should avoid blindly injecting all available project information.

It must choose only context relevant to the current work.

---

## FR-14 — Context Package

GPD should create a compact context package.

Example:

```text
TASK

BUG-231
Checkout hangs when saved card is expired


BUG CONTEXT

QA found that checkout remains loading when
payment_method_invalid is returned.


EXPECTED

Show an error and allow another payment method.


ORIGINAL DISCUSSION

QA:
Checkout keeps loading...

Developer:
Probably payment error handling...


ARCHITECTURE

Payment errors should be normalized inside PaymentService.


RELATED FILES

src/payment/payment-service.ts
src/checkout/payment-errors.ts
```

---

# 10. Coding Agent Integration

## FR-15 — Coding Agent Context Injection

GPD must expose task context to a coding agent.

Possible MVP interfaces:

```bash
gpd context
```

or:

```bash
gpd agent "fix BUG-231"
```

Possible integrations:

- MCP
- CLI wrapper
- local API
- system prompt injection
- coding agent hook

Only one working coding-agent integration is required for the hackathon.

---

## FR-16 — Zero-Prompt Context

The ideal GPD workflow should require minimal manual context copying.

When a developer selects `BUG-231`, the coding agent should automatically receive:

- bug description
- Slack discussion
- relevant project requirements
- technical decisions
- related files

The developer should not have to manually paste the Slack thread into the coding agent.

---

# 11. Team Coordination

## FR-17 — Active Work Tracking

GPD must track active development sessions.

Example:

```text
Alice

BUG-231
feat/payment-error
payment-service.ts


Bob

TASK-245
feat/checkout-ui
checkout/payment-errors.ts
```

---

## FR-18 — Work Overlap Detection

GPD should identify possible conflicts based on:

- same file
- same module
- related task
- overlapping requirement

Example:

```text
WARNING

Alice is already modifying the payment error flow.

Task:
BUG-231

File:
payment-service.ts
```

---

## FR-19 — Conflict Recommendation

GPD may recommend an action.

Example:

```text
Suggested action:

Avoid modifying payment-service.ts until BUG-231 is complete.

Your UI changes can continue in payment-errors.ts.
```

---

# 12. Capturing New Knowledge

## FR-20 — Task Completion

A developer should be able to mark a work session complete.

Example:

```bash
gpd finish
```

GPD analyzes:

- Git diff
- task
- coding-agent summary
- existing project context

---

## FR-21 — Knowledge Extraction

GPD should identify important new information.

Example:

```text
New project decision detected:

payment_method_invalid must be mapped to
ExpiredPaymentMethodError before reaching the UI.
```

GPD should allow this knowledge to be saved into project memory.

---

## FR-22 — Memory Reuse

Future tasks must be able to receive previously captured knowledge.

Example:

A new developer works on a payment issue.

GPD provides:

```text
Relevant decision:

payment_method_invalid is normalized to
ExpiredPaymentMethodError inside PaymentService.
```

---

# 13. Knowledge Conflict Detection

## FR-23 — Conflicting Context

GPD should identify important contradictions.

Example:

```text
PRD:
Retry payment three times.

FRD:
Retry payment twice.

Slack decision:
Retries were reduced to one yesterday.
```

GPD should display:

```text
Project context conflict detected.

Three different retry policies exist.
```

This is P1 for the hackathon.

---

# 14. CLI Requirements

Suggested MVP commands:

```bash
gpd init

gpd add <document>

gpd task set <task-id>

gpd start

gpd status

gpd context

gpd agent "<prompt>"

gpd finish
```

---

# 15. Slack Commands

The MVP should support natural-language requests such as:

```text
@GPD create a bug from this conversation
```

Optional:

```text
@GPD create a task from this thread

@GPD summarize what we decided

@GPD save this as project context

@GPD what task is this related to?
```

---

# 16. System Architecture

```text
               Slack
                 ↓
        Conversation Adapter
                 ↓
          Context Engine
          ↙           ↘
 Project Memory     Task Store
      ↑                ↓
 PRD / FRD / ADR    BUG-231
      ↑                ↓
      └────── GPD Agent ──────┐
                              ↓
                     Coding Agent
                              ↓
                         Source Code
                              ↓
                      Knowledge Update
                              ↓
                       Project Memory
```

---

# 17. Suggested Technical Stack

For the hackathon MVP:

```text
Slack
Slack Bot API

Backend
TypeScript / Node.js
or
Python / FastAPI

Storage
SQLite / Postgres

Semantic retrieval
pgvector / Chroma

LLM
OpenAI API

Coding agent integration
MCP / CLI

Git context
Local Git commands
```

Keep the infrastructure simple.

The product behavior is more important than infrastructure complexity.

---

# 18. MVP Priority

## P0 — Must Work

- Slack bot receives command
- read Slack thread
- understand bug discussion
- generate structured bug
- save task in GPD
- preserve source conversation
- select task in developer environment
- inject bug + conversation context into coding agent

## P1 — Strong Differentiators

- active developer sessions
- overlap detection
- new knowledge extraction after code changes
- reuse learned context

## P2 — Only If Time Remains

- conflicting-document detection
- Jira integration
- Linear integration
- GitHub issue creation
- automatic task inference
- dashboard
- multiple coding-agent integrations

---

# 19. Hackathon Demo Flow

## Scene 1 — QA finds a bug

QA reports a bug in Slack.

Developer asks several questions.

The conversation contains enough context to understand:

- bug
- reproduction
- expected behavior
- technical clue

---

## Scene 2 — GPD turns conversation into work

QA says:

```text
@GPD create a bug task from this conversation
```

GPD creates:

```text
BUG-231

Checkout hangs when saved card is expired.
```

The generated bug includes structured information extracted from the discussion.

---

## Scene 3 — Developer starts coding

Developer runs:

```bash
gpd task set BUG-231
gpd start
```

The coding agent receives:

```text
Bug
Original Slack conversation
Relevant requirement
Architecture decision
Related files
```

No manual context copying is required.

---

## Scene 4 — Agent fixes the bug

The coding agent uses GPD context to modify the correct area of the codebase.

---

## Scene 5 — GPD learns

After implementation:

```bash
gpd finish
```

GPD discovers:

```text
New project knowledge:

payment_method_invalid should be normalized
inside PaymentService.
```

The information becomes available to future developers and agents.

---

# 20. Demo Acceptance Criteria

The MVP is successful when the team can demonstrate this end-to-end:

```text
Slack discussion
      ↓
"@GPD create a bug"
      ↓
Structured BUG-231
      ↓
Developer starts work
      ↓
Coding agent automatically receives context
      ↓
Agent fixes bug
      ↓
GPD captures new knowledge
      ↓
Future team members inherit that context
```

The user should never need to manually copy and paste project context between tools.

---

# 21. Product Positioning

GPD is not another:

- Slack bot
- task manager
- coding agent
- document search system

GPD connects all of them.

**GPD turns temporary team conversations into durable project knowledge and gives that knowledge to the right human or AI agent at the right moment.**

Short version:

> **GPD is the shared memory and coordination layer for human + AI software teams.**