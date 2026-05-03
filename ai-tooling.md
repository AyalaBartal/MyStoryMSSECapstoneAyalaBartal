# AI Tooling Usage

This document discloses how AI tools were used during the development of My Story, in accordance with the Quantic MSSE Capstone academic honesty policy. The work submitted is the author's own; AI was used as a development assistant, the same way an engineer would use a senior colleague to pair-program with.

## Important distinction: AI in the *product* vs AI in the *process*

This project has **AI baked into the product itself** — Anthropic's Claude Haiku 4.5 (via AWS Bedrock) generates story text, OpenAI's `gpt-image-1` generates illustrations. Those are documented in `DESIGN_AND_TESTING.md` as architectural choices and aren't covered here.

This document is specifically about **AI tools used to build the project** — pair-programming assistants, debuggers, documentation helpers. They never replaced engineering judgment; they accelerated it.

---

## Tools used

### Claude (Anthropic, via the claude.ai chat interface)

By far the primary AI tool used. Conversations spanned the full development lifecycle — architecture, code, debugging, documentation, demo prep.

**Where Claude was used:**

- **Architecture decisions and trade-off analysis.** Walking through serverless patterns, choosing between Step Functions vs SQS for orchestration, deciding when hexagonal architecture was worth the boilerplate cost.
- **Code generation for boilerplate** — initial Lambda scaffolding (handler/service/utils split), CDK stack definitions, test fixtures, JSX components.
- **Debugging assistance.** Reading CloudWatch tracebacks, identifying root causes, suggesting targeted fixes. Several real bugs were found this way — DynamoDB Decimal serialization in the JSON encoder, missing `auth.py` in the kids Lambda zip, malformed JSON from the LLM.
- **Documentation drafts.** First drafts of every Lambda README, the cost plan, the design and testing document, and the demo script. Each draft was then reviewed and edited rather than submitted as-is.
- **Mid-project pivots.** When DALL-E 3 was producing inconsistent characters, Claude helped reason about the swap to gpt-image-1 and verified the hexagonal pattern would let it be a one-class change. Same when migrating story generation from direct Anthropic API to AWS Bedrock.

**Where Claude was deliberately not used:**

- **Final architectural decisions** — every "yes/no" on scope (e.g., "should we add anonymous claim flow now or defer?") was made by the human author, often after Claude argued against the chosen path.
- **Editorial voice** — the prompt template that drives story quality went through several human-led iterations to match the Brothers Grimm-inspired tone the project wanted.
- **Test verification** — Claude wrote tests, but the human author ran them, interpreted failures, and decided when coverage was enough.
- **Deployment confirmation** — every `cdk deploy` and CI green status was verified by the human, not assumed from Claude's claim that "this should work."

### AWS CDK and AWS Console assistants

CDK's own type hints and CloudFormation diff output served as a built-in safety net for infrastructure changes. AWS Console occasionally suggested IAM policy refinements; these were applied with judgment, not blindly accepted.

### IDE features (PyCharm, VS Code autocomplete)

Standard IDE autocomplete and inspection. Not generative AI — pattern matching from the project's own existing code. Mentioned for completeness.

---

## What AI tools were good at

- **Boilerplate generation.** Scaffolding a new Lambda's `handler.py` + `service.py` + `tests/` from a template was instant. Saved hours across 7 Lambdas.
- **Debugging assistance.** Tracebacks paired with code context produced fast root-cause analysis. AWS-specific errors ("ResourceNotFoundException: Invalid index") that would have taken 30+ minutes to research were diagnosed in minutes.
- **Documentation drafts.** First-pass markdown for READMEs and the design document. The structure was usually right; the wording always needed editorial passes.
- **Test scaffolding.** Generating moto-based test fixtures and per-Lambda `conftest.py` files was reliable and fast.

## What AI tools were not good at

- **Knowing the current state of the codebase across long sessions.** Claude needed periodic re-grounding ("here is what I just changed") to stay aligned with reality. Required vigilance on the human's part.
- **Distinguishing between in-memory editor state and saved files.** Several cycles were lost where Claude assumed a file save had taken effect when it hadn't.
- **Knowing AWS service behavior with full accuracy.** Some advice referenced documentation that was slightly out of date — for example, the AWS Marketplace subscription requirement for Claude Haiku 4.5 on Bedrock was found through trial-and-error, not from Claude's first answer.
- **Resisting the urge to over-engineer.** Claude often proposed elaborate test-fixture refactors or architectural cleanups that would have been wasted effort given the capstone deadline. Pushback from the human author was needed to keep scope realistic.

## Honest accounting

Approximate breakdown of code in the repo by who initially produced it:

- ~50% AI-drafted, human-edited (Lambda boilerplate, test scaffolding, CDK stacks, JSX components)
- ~30% AI-drafted, lightly modified (README drafts, prompt templates, demo script, configuration files)
- ~20% human-written from scratch (key architectural decisions, the prompt-engineering iterations that drive story quality, the final review and integration of every piece)

Every line of code was read, understood, and accepted by the human author before being committed. The human author can explain every architectural decision, debug every Lambda, and answer questions about every test.

---

## Why disclose this

Two reasons:

1. **Academic honesty.** AI assistance is now part of how engineering is done. Pretending otherwise would be dishonest. Quantic's policy expects students to disclose AI usage, and this document fulfills that.

2. **Engineering reality.** The point of the capstone is to demonstrate that the author can architect, build, debug, and ship a real serverless application. AI tools accelerated the work; they did not replace the engineering judgment that made the architectural decisions defensible. The author has made every meaningful design choice in this project, knows why each one was made, and can defend them in the demo.

If a grader asks the author to explain any part of the codebase live, the answer will be a real engineering answer — because the human did the engineering, with AI as the assistant.