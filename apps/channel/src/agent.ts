import { AbstractAgent } from "@ag-ui/client";
import type { BaseEvent, RunAgentInput } from "@ag-ui/core";
import { Observable, type Subscription } from "rxjs";
import { BuiltInAgent } from "@copilotkit/runtime/v2";
import { resolveModel } from "./model.js";

export const GPD_SYSTEM_PROMPT = `You are the GPD (Grounded Project Developer) AI assistant living in Slack.
You help engineering teams triage bugs, review architecture decisions (ADR), check specifications (PRD/FRD), retrieve context packages, and inspect project tasks.
Always be concise, professional, and actionable. When appropriate, use structured cards or propose decisions for review.`;

export function makeInnerAgent(threadId: string) {
  const agent = new BuiltInAgent({
    model: resolveModel(),
    prompt: GPD_SYSTEM_PROMPT,
    maxSteps: 10,
  });
  agent.threadId = threadId;
  return agent;
}

export type ChannelAgentFactory = (threadId: string) => AbstractAgent;

/**
 * Channel-only facade that keeps AG-UI transcript/state on the outer agent while
 * delegating each low-level run to a fresh BuiltInAgent instance.
 */
export class ChannelRunAgent extends AbstractAgent {
  private activeInner: AbstractAgent | undefined;

  constructor(
    private agentFactory: ChannelAgentFactory = makeInnerAgent,
    threadId?: string,
  ) {
    super({ threadId });
  }

  override run(input: RunAgentInput): Observable<BaseEvent> {
    return new Observable<BaseEvent>((subscriber) => {
      let inner: AbstractAgent | undefined;
      let subscription: Subscription | undefined;

      const release = () => {
        if (this.activeInner === inner) {
          this.activeInner = undefined;
        }
      };

      try {
        inner = this.agentFactory(input.threadId);
        inner.threadId = input.threadId;
        this.activeInner = inner;
        subscription = inner.run(input).subscribe({
          next: (event) => {
            subscriber.next(event);
          },
          error: (error) => {
            release();
            subscriber.error(error);
          },
          complete: () => {
            release();
            subscriber.complete();
          },
        });
      } catch (error) {
        release();
        subscriber.error(error);
      }

      return () => {
        subscription?.unsubscribe();
        inner?.abortRun();
        release();
      };
    });
  }

  override abortRun() {
    this.activeInner?.abortRun();
    super.abortRun();
  }

  override clone(): ChannelRunAgent {
    const cloned = super.clone() as ChannelRunAgent;
    cloned.agentFactory = this.agentFactory;
    cloned.activeInner = undefined;
    return cloned;
  }
}

export function makeChannelAgent(threadId: string) {
  return new ChannelRunAgent(makeInnerAgent, threadId);
}
