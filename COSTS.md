# My Story — Project Costs

Tracks all recurring and one-off costs for the capstone deployment.

**Last updated:** 2026-04-25

---

## 1. Per-story cost (end-to-end, one PDF)

| Service | Call | Unit cost | Per-story cost |
|---|---|---|---|
| Anthropic Claude Haiku 4.5 | 1 LLM call (~1K tokens) | $0.80/M in, $4.00/M out | **~$0.001** |
| OpenAI gpt-image-1 (medium quality, 1024×1024) | 5 image calls | $0.042 / image | **$0.210** |
| AWS Lambda | 5 invocations | Free tier covers all capstone usage | ~$0.00001 |
| AWS DynamoDB (pay-per-request) | 1 put + polling reads | $1.25 / M writes, $0.25 / M reads | ~$0.00001 |
| AWS S3 storage | 15MB per story (5 PNGs + 1 PDF) | $0.023 / GB-month | ~$0.0003 / month |
| AWS S3 requests | 5 PUTs + ~3 GETs | $0.005 / 1K PUT, $0.0004 / 1K GET | ~$0.00003 |
| AWS Step Functions | 1 execution (~6 transitions) | $0.025 / 1K transitions | ~$0.00015 |
| AWS API Gateway (REST) | 2–3 calls | $3.50 / M | ~$0.00001 |
| **Total per story** |  |  | **≈ $0.21** |

> Image generation accounts for ~99% of the per-story cost. AWS infrastructure is essentially free at capstone scale.

---

## 2. One-time setup costs

| Item | Cost | Status |
|---|---|---|
| Anthropic API credit (initial load) | $5.00 | ✅ paid |
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
| Anthropic Claude Haiku (50 stories × $0.001) | $0.05 |
| AWS Secrets Manager (2 secrets) | $0.80 |
| AWS (other services within free tier for capstone scale) | $0.00 |
| **Monthly total** | **~$11.35** |

---

## 4. Running tally (update as you spend)

| Date | Service | Amount | Note |
|---|---|---|---|
| 2026-04-23 | Anthropic | -$5.00 initial credit | Loaded |
| 2026-04-23 | OpenAI | -$5.00 initial credit | Loaded |
| 2026-04-23 → 2026-04-25 | Anthropic | ~-$0.50 | Story generation during dev + testing |
| 2026-04-23 → 2026-04-25 | OpenAI | ~-$3.50 | Image generation during dev + testing (gpt-image-1 + earlier DALL-E 3 runs) |

**Running balances (approximate):**
- Anthropic: ~$4.50
- OpenAI: ~$1.50
- AWS: $0 spent (free tier)

---

## 5. Cost-optimization notes

- **gpt-image-1 quality tier:** medium ($0.042/image) is the sweet spot for storybook illustration. Low quality ($0.011) trades too much fidelity for the cost savings; high quality ($0.167) is overkill for the watercolor aesthetic.
- **Image size:** 1024×1024 square fits the picture-book layout. No need for the larger landscape/portrait sizes which cost ~$0.25/image.
- **Cache identical stories:** if two users pick the same card combo, the generated content could be reused — saves ~$0.21 per cache hit. Not implemented; would be a meaningful optimization at higher scale.
- **AWS Free Tier:** expires 12 months after account creation. Lambda, DynamoDB, and Step Functions costs would still remain trivial at capstone scale (under $5/month).

---

## 6. Budget envelope

**Capstone total budget (strict):** $25
- $5 Anthropic ✅
- $5 OpenAI ✅
- $15 buffer for re-runs, demos, bugs

Project remained well within this budget through development and submission.
