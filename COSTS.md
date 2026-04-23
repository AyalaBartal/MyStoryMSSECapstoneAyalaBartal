# My Story — Project Costs

Tracks all recurring and one-off costs for the capstone and beyond. Update this file as you spend or as rates change.

**Last updated:** 2026-04-23

---

## 1. Per-story cost (end-to-end, one PDF)

| Service | Call | Unit cost | Per-story cost |
|---|---|---|---|
| Anthropic Claude Haiku 4.5 | 1 LLM call (~1K tokens) | $0.80/M in, $4.00/M out | **~$0.001** |
| OpenAI DALL-E 3 (standard, 1024×1024) | 5 image calls | $0.040 / image | **$0.200** |
| AWS Lambda | 4 invocations | Free tier covers all capstone usage | ~$0.00001 |
| AWS DynamoDB (pay-per-request) | 1 put + polling reads | $1.25 / M writes, $0.25 / M reads | ~$0.00001 |
| AWS S3 storage | 15MB per story (5 PNGs + 1 PDF) | $0.023 / GB-month | ~$0.0003 / month |
| AWS S3 requests | 5 PUTs + ~3 GETs | $0.005 / 1K PUT, $0.0004 / 1K GET | ~$0.00003 |
| AWS Step Functions | 1 execution (~6 transitions) | $0.025 / 1K transitions | ~$0.00015 |
| AWS API Gateway (REST) | 2–3 calls | $3.50 / M | ~$0.00001 |
| **Total per story** |  |  | **≈ $0.20** |

> DALL-E 3 is ~99% of the per-story cost. Swapping to a cheaper image provider (Flux Schnell via Replicate ~$0.003/image = $0.015/story; or self-hosted SD LoRA = $0 compute) is the biggest lever.

---

## 2. One-time setup costs

| Item | Cost | Status |
|---|---|---|
| Anthropic API credit (initial load) | $5.00 | ✅ paid |
| OpenAI API credit (initial load) | $5.00 | ⏳ pending |
| AWS account | $0 (free tier) | ✅ active |
| GitHub (public repo) | $0 | ✅ active |
| Domain name (optional) | ~$12/year | 🧊 backlog |

---

## 3. Running costs (post-deploy, per month)

Assuming capstone-scale usage (~50 stories generated for demos + testing):

| Service | Monthly cost |
|---|---|
| OpenAI DALL-E 3 (50 stories × $0.20) | $10.00 |
| Anthropic Claude Haiku (50 stories × $0.001) | $0.05 |
| AWS (within free tier for capstone scale) | $0.00 |
| **Monthly total** | **~$10.05** |

> If post-capstone, consider: AWS free tier expires 12 months after account creation. Plan to swap to HuggingFace Inference Endpoint (~$0.60/hr) + self-hosted SD LoRA to escape DALL-E cost.

---

## 4. Running tally (update as you spend)

| Date | Service | Amount | Note |
|---|---|---|---|
| 2026-04-23 | Anthropic | -$0.001 | Story smoke test (Claude Haiku) |
| 2026-04-23 | Anthropic | -$5.00 initial credit | Loaded |
| 2026-04-23 | OpenAI | -$5.00 initial credit | ⏳ pending |
| ... |  |  |  |

**Running balances:**
- Anthropic: ~$5.00
- OpenAI: ~$5.00 (pending)
- AWS: $0 spent (free tier)

---

## 5. Training-track cost projections (next week's learning work)

| Item | Cost estimate | Notes |
|---|---|---|
| Qwen 2.5 1.5B LoRA fine-tune on M5 | $0 | Laptop electricity only |
| TinyStories dataset download | $0 | Free via Hugging Face |
| SD 1.5 LoRA fine-tune on M5 | $0 | Laptop electricity only |
| Bootstrap reference images via DALL-E 3 | ~$1.00 | 25 images × $0.04 |
| Hugging Face Inference Endpoint (optional, for serving trained model) | $0.60/hr | Spin up only for demo day |
| **Training total** | **≈ $1–5** | Heavily dominated by laptop time, not dollars |

---

## 6. Cost-optimization notes

- **DALL-E 3 → Flux Schnell (Replicate):** $0.20 → $0.015 per story. 13× cheaper. Quality tradeoff — needs testing.
- **Standard vs. HD quality on DALL-E 3:** $0.04 vs. $0.08. Standard is sufficient for children's book aesthetic.
- **1024×1024 vs. 1792×1024:** $0.04 vs. $0.08. Square fits the storybook layout, saves money.
- **Cache identical stories:** if two users pick the same card combo, reuse the generated content. Save ~$0.20 per cache hit. Backlog item.
- **Post-capstone:** swap DALL-E 3 for self-hosted SD LoRA → $0 per image after upfront training cost.

---

## 7. Budget envelope

**Capstone total budget (strict):** $25
- $5 Anthropic ✅
- $5 OpenAI ⏳
- $15 buffer for re-runs, demos, bugs

Stay within this and the project is cost-defensible to any stakeholder.