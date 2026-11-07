# Pre-push checklist: deployment anti-patterns

Checked before **every** push. Each item names the anti-pattern, what it
looks like in SmartDesk, and how it is checked. **Auto** items are run by
`scripts/pre_push.sh` (built in M0, run by a git pre-push hook); **review**
items are answered in the commit message or pull request, one line each:
done · not touched by this change · not built yet.

| # | Anti-pattern | In SmartDesk, the push must keep… | Check |
|---|---|---|---|
| 1 | **No rate limits** | limits per business and per customer on chat, phone, uploads and owner routes | review; auto once M1 adds limit tests |
| 2 | **No input / output validation** | uploads checked by real type, size and pages; tool arguments and AI output checked against schemas (Pydantic, strict); services-table values backed by an exact quote; replies set as text, never HTML | auto: tests · review |
| 3 | **No monitoring or logging** | every agent, tool and workflow step traced (LangSmith) and emitting debug events; personal details hidden in both; live review rules unchanged | review |
| 4 | **Secrets in code or prompts** | no keys, tokens or passwords in the repo, prompts, logs or traces; `.env` never committed; secrets only from the environment | auto: secret scan of the diff · review |
| 5 | **Unlimited tool access** | each agent gets only its spec's tools, bound to the business and customer; no tool runs AI-written queries, approves, or spends money | auto: spec-vs-code tool test · review |
| 6 | **Hard-coded configuration** | models, limits, budgets, URLs and business details in settings or the database, not in code; no business-specific special cases | review |
| 7 | **No fallbacks or timeouts** | every model, calendar, Pinecone, speech and Twilio call has a timeout; on failure the person gets a clear message or a hand-off, never a silent stop | auto: failure tests · review |
| 8 | **No access controls / least privilege** | owner routes need sign-in; business id comes from the session or widget key, never the message; each credential has the narrowest scope; reset is owner-only with typed confirmation | auto: isolation tests · review |
| 9 | **Ignoring cost and token usage** | turn and tool-call limits; per-business daily budget; file and page limits; cost per eval run reported | review; auto once budgets exist |
| 10 | **No human in the loop (when needed)** | booking changes need the customer's yes; hand-off to staff when unsure; the owner can see and edit the services table; live chats sampled for review | review |

## Also before every push

- [ ] Tests pass (`pytest`), including the gates in each changed agent's or workflow's spec.
- [ ] Specs updated first if behaviour changed (no-patches rule, `docs/PLAN.md`).
- [ ] No dead code left from a replaced design.
- [ ] Evals re-run if prompts, tools or models changed (with approval: they cost tokens).
