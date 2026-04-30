# My Story — Project Costs

Tracks all recurring and one-off costs for the capstone deployment.

**Last updated:** 2026-04-29

---

## 1. Per-story cost (end-to-end, one PDF)

| Service | Call | Unit cost | Per-story cost |
|---|---|---|---|
| AWS Bedrock — Anthropic Claude Haiku 4.5 | 1 LLM call (~1.5K in + ~1.5K out) | $0.80/M in, $4.00/M out | **~$0.007** |
| OpenAI gpt-image-1 (medium quality, 1024×1024) | 5 image calls | $0.042 / image | **$0.210** |
| AWS Lambda | 5 invocations | Free tier covers all capstone usage | ~$0.00001 |
| AWS DynamoDB (pay-per-request) | 1 put + polling reads | $1.25 / M writes, $0.25 / M reads | ~$0.00001 |
| AWS S3 storage | 15MB per story (5 PNGs + 1 PDF) | $0.023 / GB-month | ~$0.0003 / month |
| AWS S3 requests | 5 PUTs + ~3 GETs | $0.005 / 1K PUT, $0.0004 / 1K GET | ~$0.00003 |
| AWS Step Functions | 1 execution (~6 transitions) | $0.025 / 1K transitions | ~$0.00015 |
| AWS API Gateway (REST) | 2–3 calls | $3.50 / M | ~$0.00001 |
| **Total per story** |  |  | **≈ $0.22** |

> Image generation accounts for ~96% of the per-story cost. AWS infrastructure is essentially free at capstone scale. Story generation moved from a direct Anthropic API call to AWS Bedrock for native AWS integration, IAM-scoped security, and lower per-token cost.

---

## 2. One-time setup costs

| Item | Cost | Status |
|---|---|---|
| AWS Marketplace subscription — Claude Haiku 4.5 (Bedrock) | $0.00 | ✅ active |
| OpenAI API credit (initial load) | $5.00 | ✅ paid |
| AWS account | $0 (free tier) | ✅ active |
| GitHub (public repo) | $0 | ✅ active |
| Domain name (optional) | ~$12/year | not configured |

---

## 3. Running costs (post-deploy, per month)

Assuming capstone-scale usage (~50 stories generated for demos + testing):

| Service | Monthly cost |
|---|---|
| OpenAI gpt-image-1 (50 stories × $0.21) | $10.50 |
| AWS Bedrock — Claude Haiku 4.5 (50 stories × $0.007) | $0.35 |
| AWS Secrets Manager (1 secret — OpenAI) | $0.40 |
| AWS (other services within free tier for capstone scale) | $0.00 |
| **Monthly total** | **~$11.25** |

---

## 4. Running tally (update as you spend)

| Date | Service | Amount | Note |
|---|---|---|---|
| 2026-04-23 | OpenAI | -$5.00 initial credit | Loaded |
| 2026-04-23 → 2026-04-25 | OpenAI | ~-$3.50 | Image generation during dev + testing (gpt-image-1 + earlier DALL-E 3 runs) |
| 2026-04-28 | AWS Marketplace | $0.00 | Claude Haiku 4.5 (Bedrock Edition) subscription accepted |
| 2026-04-28 → 2026-04-29 | AWS Bedrock | ~$0.05 | Story generation testing during Bedrock cutover |

**Running balances (approximate):**
- OpenAI: ~$1.50
- AWS Bedrock: pay-as-you-go (no prepaid credit; ~$0.05 spent)
- AWS infrastructure: $0 spent (free tier)

---

## 5. Cost-optimization notes

- **gpt-image-1 quality tier:** medium ($0.042/image) is the sweet spot for storybook illustration. Low quality ($0.011) trades too much fidelity for the cost savings; high quality ($0.167) is overkill for the watercolor aesthetic.
- **Image size:** 1024×1024 square fits the picture-book layout. No need for the larger landscape/portrait sizes which cost ~$0.25/image.
- **Bedrock vs direct Anthropic API:** Bedrock pricing matches Anthropic's direct API at this tier, but Bedrock removes the need to manage a separate API key and lets the Lambda call the model via IAM-scoped permissions. No prepaid credit is required — Bedrock usage is billed on the regular AWS account.
- **Cache identical stories:** if two users pick the same card combo, the generated content could be reused — saves ~$0.22 per cache hit. Not implemented; would be a meaningful optimization at higher scale.
- **AWS Free Tier:** expires 12 months after account creation. Lambda, DynamoDB, and Step Functions costs would still remain trivial at capstone scale (under $5/month).

---

## 6. Budget envelope

**Capstone total budget (strict):** $25
- $5 OpenAI ✅
- $20 buffer for re-runs, demos, bugs, AWS Bedrock usage

Project remained well within this budget through development and submission.