# Agent spec: <name>

Copy this file for every agent. Fill every section before writing code; a
section that does not apply says why. The seven sections follow a
secure-by-default workflow: security is decided at each step, not added at
the end.

> **Agent or workflow?** Use an agent only when the next step needs judgment
> in conversation. If the steps are fixed, use the workflow template
> (`WORKFLOW.md`). Everything exact (money, bookings, approvals, consent,
> permissions) is code, never the agent.

---

## 1. Purpose and boundaries *(Developer)*

| | |
|---|---|
| **Job, in one sentence** | |
| **Talks to** | customer · owner · staff · nobody (pipeline) |
| **Channel** | chat · phone · owner console · none |
| **Triggered by** | |
| **Done when** | |
| **Hands back to** | person or agent when it cannot finish |

**Use cases** (the 3–6 things it must do well):

1.

**Out of scope** (what it must never do, even if asked):

-

## 2. Instructions *(System prompt)*

| | |
|---|---|
| **Allowed tasks** | |
| **Refusal rules** | what it declines, and the exact behaviour (plain no · hand off · ask) |
| **Tone and channel rules** | |
| **Never in the prompt** | secrets, other businesses' data, personal details beyond this conversation |

Where the prompt lives: `<path>` · Version: recorded in every trace.

## 3. Tools and data *(Paved roads)*

Approved patterns only: answers from approved knowledge, tools bound to the
business and the person, least privilege.

| Tool | Does | Bound to | Reads / writes | Needs a person's yes? | Code or AI |
|---|---|---|---|---|---|
| | | business id · customer | | | |

**Data it can see:** · **Data it can never see:**

**Model:** · **Why this model:** · **Limits:** max turns · max tool calls · timeout

## 4. Threats and design review *(AI security review)*

| Threat | How it could happen here | Defence | Tested by |
|---|---|---|---|
| Prompt injection / jailbreak | | | |
| Indirect injection (untrusted content) | | | |
| Excessive agency / tool misuse | | | |
| Data leakage (other customers, other businesses) | | | |
| Personal details exposed | | | |
| Made-up answers (over-trust) | | | |

Reviewed by: AI review + owner approval of this spec, before code.

## 5. Tests that must pass *(Policy gates)*

A change to code or prompt ships only when all of these pass.

| Gate | Cases | Bar |
|---|---|---|
| Use-case evals | | |
| Attack tests (injection, jailbreak) | | all pass |
| Tool allow-list (it can't call what it isn't given) | | all pass |
| Isolation (other customer, other business) | | zero leaks |
| Personal details in output and traces | | zero leaks |

## 6. Release *(Deployment)*

local → staging (own secrets, test business) → production.
Only a version whose gates passed is deployed; the version is in every trace.
Rollback: redeploy the previous version.

## 7. Live checks *(Runtime verification)*

| | |
|---|---|
| **Guardrails before the agent** | rate limits, input size, business resolved by code |
| **Checks after the agent** | output checks before the reply is sent |
| **Audit log** | what is recorded for every action |
| **Monitoring and alerts** | what is sampled for review; what raises an alert |
| **Debug view** | the events it emits (who · kind · what · data) for the live panel; nothing secret, personal details hidden |
| **When it fails** | the fallback the person sees; never a silent stop |
