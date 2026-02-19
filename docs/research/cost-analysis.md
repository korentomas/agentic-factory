# LailaTov Cost Analysis

**Date:** February 19, 2026
**Product:** LailaTov -- Autonomous Code Factory (SaaS)
**Pipeline:** TRIAGE -> WRITE (plan + code) -> REVIEW -> REMEDIATE

---

## 1. LLM API Pricing (February 2026)

All prices are per million tokens (MTok), USD.

### Tier 1: Premium Models (highest capability)

| Provider | Model | Input / MTok | Output / MTok |
|----------|-------|-------------|--------------|
| Anthropic | Claude Opus 4.6 | $5.00 | $25.00 |
| OpenAI | GPT-4.1 | $2.00 | $8.00 |
| OpenAI | o3 (reasoning) | $2.00 | $8.00 |
| Google | Gemini 2.5 Pro | $1.25 | $10.00 |
| Moonshot | Kimi K2.5 | $0.60 | $3.00 |

### Tier 2: Workhorse Models (strong capability, lower cost)

| Provider | Model | Input / MTok | Output / MTok |
|----------|-------|-------------|--------------|
| Anthropic | Claude Sonnet 4.6 | $3.00 | $15.00 |
| OpenAI | o3-mini | $1.10 | $4.40 |
| Moonshot | Kimi K2 (0905) | $0.39 | $1.90 |
| Alibaba | Qwen3 Coder (480B) | $0.22 | $1.00 |

### Tier 3: Cost-Optimized Models (fast, cheap, good enough for triage/review)

| Provider | Model | Input / MTok | Output / MTok |
|----------|-------|-------------|--------------|
| Anthropic | Claude Haiku 4.5 | $1.00 | $5.00 |
| OpenAI | GPT-4.1 mini | $0.40 | $1.60 |
| OpenAI | GPT-4.1 nano | $0.10 | $0.40 |
| Google | Gemini 2.5 Flash | $0.30 | $2.50 |
| DeepSeek | V3.2 (chat) | $0.28 | $0.42 |
| DeepSeek | V3.2 (reasoner) | $0.28 | $0.42 |
| Alibaba | Qwen3 Coder Next | $0.07 | $0.30 |

### Cost Reduction Levers

| Mechanism | Savings | Available On |
|-----------|---------|-------------|
| Prompt caching (cache hits) | up to 90% on input | Anthropic, DeepSeek, Google, Moonshot |
| Batch API | 50% on all tokens | Anthropic, OpenAI, Google |
| Off-peak scheduling | up to 75% | DeepSeek |
| Free tier | 100% (rate-limited) | Google Gemini |

---

## 2. Cost Per Pipeline Run

### Token Budget by Stage

| Pipeline Stage | Input Tokens | Output Tokens | Notes |
|---------------|-------------|--------------|-------|
| TRIAGE | 2,000 | 1,000 | Classification + priority |
| WRITE (planning) | 10,000 | 5,000 | Architecture decisions |
| WRITE (coding) | 50,000 | 30,000 | Main code generation |
| REVIEW | 30,000 | 10,000 | PR review + feedback |
| REMEDIATE | 40,000 | 20,000 | Fix review issues |
| **TOTAL** | **132,000** | **66,000** | **Per full pipeline run** |

### Cost Per Full Pipeline Run by Model

#### Strategy A: Single Model (same model for all stages)

| Model | Input Cost | Output Cost | Total Per Run |
|-------|-----------|------------|--------------|
| Claude Opus 4.6 | $0.660 | $1.650 | **$2.31** |
| Claude Sonnet 4.6 | $0.396 | $0.990 | **$1.39** |
| Claude Haiku 4.5 | $0.132 | $0.330 | **$0.46** |
| GPT-4.1 | $0.264 | $0.528 | **$0.79** |
| GPT-4.1 mini | $0.053 | $0.106 | **$0.16** |
| o3 | $0.264 | $0.528 | **$0.79** |
| Gemini 2.5 Pro | $0.165 | $0.660 | **$0.83** |
| Gemini 2.5 Flash | $0.040 | $0.165 | **$0.20** |
| DeepSeek V3.2 | $0.037 | $0.028 | **$0.06** |
| Qwen3 Coder (480B) | $0.029 | $0.066 | **$0.10** |
| Kimi K2.5 | $0.079 | $0.198 | **$0.28** |

#### Strategy B: Hybrid Model (recommended -- use cheap models for simple stages)

This is the strategy LailaTov should use. Different stages have different complexity requirements.

| Stage | Recommended Model | Input Cost | Output Cost | Stage Cost |
|-------|------------------|-----------|------------|-----------|
| TRIAGE (2K/1K) | Haiku 4.5 | $0.002 | $0.005 | **$0.007** |
| WRITE plan (10K/5K) | Sonnet 4.6 | $0.030 | $0.075 | **$0.105** |
| WRITE code (50K/30K) | Sonnet 4.6 | $0.150 | $0.450 | **$0.600** |
| REVIEW (30K/10K) | Haiku 4.5 | $0.030 | $0.050 | **$0.080** |
| REMEDIATE (40K/20K) | Sonnet 4.6 | $0.120 | $0.300 | **$0.420** |
| **TOTAL** | | | | **$1.21** |

#### Strategy C: Budget Hybrid (aggressive cost optimization)

| Stage | Recommended Model | Input Cost | Output Cost | Stage Cost |
|-------|------------------|-----------|------------|-----------|
| TRIAGE (2K/1K) | GPT-4.1 nano | $0.0002 | $0.0004 | **$0.001** |
| WRITE plan (10K/5K) | GPT-4.1 mini | $0.004 | $0.008 | **$0.012** |
| WRITE code (50K/30K) | DeepSeek V3.2 | $0.014 | $0.013 | **$0.027** |
| REVIEW (30K/10K) | GPT-4.1 nano | $0.003 | $0.004 | **$0.007** |
| REMEDIATE (40K/20K) | DeepSeek V3.2 | $0.011 | $0.008 | **$0.019** |
| **TOTAL** | | | | **$0.07** |

#### Strategy D: Premium Hybrid (maximum quality)

| Stage | Recommended Model | Input Cost | Output Cost | Stage Cost |
|-------|------------------|-----------|------------|-----------|
| TRIAGE (2K/1K) | Sonnet 4.6 | $0.006 | $0.015 | **$0.021** |
| WRITE plan (10K/5K) | Opus 4.6 | $0.050 | $0.125 | **$0.175** |
| WRITE code (50K/30K) | Opus 4.6 | $0.250 | $0.750 | **$1.000** |
| REVIEW (30K/10K) | Sonnet 4.6 | $0.090 | $0.150 | **$0.240** |
| REMEDIATE (40K/20K) | Opus 4.6 | $0.200 | $0.500 | **$0.700** |
| **TOTAL** | | | | **$2.14** |

### Summary: Cost Per Pipeline Run

| Strategy | Cost Per Run | Best For |
|----------|-------------|---------|
| A: Sonnet 4.6 only | $1.39 | Simplicity, good quality |
| B: Hybrid (recommended) | $1.21 | Best quality/cost balance |
| C: Budget Hybrid | $0.07 | Maximum volume, acceptable quality |
| D: Premium Hybrid | $2.14 | Enterprise customers, complex repos |

**Note:** These estimates do not include prompt caching savings. With effective caching (especially on the WRITE and REMEDIATE stages where system prompts and repo context repeat), costs can drop by 30-50%.

---

## 3. Compute Costs (Google Cloud Run)

### Cloud Run Pricing (Tier 1 regions, e.g., us-central1)

| Resource | Price | Free Tier |
|----------|-------|-----------|
| vCPU | $0.0000240 / vCPU-second | 180,000 vCPU-seconds/month |
| Memory | $0.0000025 / GiB-second | 360,000 GiB-seconds/month |
| Requests | $0.40 / million requests | 2 million requests/month |

### Estimated Compute Cost Per Agent Task

Assumptions:
- Each pipeline run takes 5-15 minutes (average 10 minutes = 600 seconds)
- Allocated resources: 1 vCPU, 1 GiB RAM (orchestrator is lightweight; LLM work is API-based)
- Most of the 10 minutes is spent waiting for LLM API responses (not compute-bound)

| Component | Calculation | Cost |
|-----------|------------|------|
| vCPU | 600s x 1 vCPU x $0.0000240 | $0.0144 |
| Memory | 600s x 1 GiB x $0.0000025 | $0.0015 |
| Requests | ~5-10 internal requests per task | ~$0.00 |
| **Total compute per task** | | **$0.016** |

### Monthly Compute Estimates

| Monthly Tasks | Compute Cost | Notes |
|--------------|-------------|-------|
| 100 tasks | $1.60 | Mostly covered by free tier |
| 500 tasks | $8.00 | |
| 2,000 tasks | $32.00 | |
| 10,000 tasks | $160.00 | |

### GitHub API Costs

- Public repos: Free (rate-limited to 5,000 requests/hour with auth)
- GitHub App authentication: Free
- GitHub Actions minutes: Customer's own allocation (not our cost)
- No per-API-call charges from GitHub

**Compute costs are negligible compared to LLM API costs.** At $0.016 per task versus $0.07-$2.14 for LLM API calls, compute is 1-3% of total COGS.

---

## 4. Unit Economics Summary

### Cost of Goods Sold (COGS) Per Task

| Component | Budget (Strategy C) | Standard (Strategy B) | Premium (Strategy D) |
|-----------|--------------------|-----------------------|---------------------|
| LLM API | $0.07 | $1.21 | $2.14 |
| Compute | $0.02 | $0.02 | $0.02 |
| Overhead (monitoring, logging) | $0.01 | $0.01 | $0.01 |
| **Total COGS** | **$0.10** | **$1.24** | **$2.17** |

### Required Revenue Per Task (at target margins)

| Target Margin | Budget COGS | Standard COGS | Premium COGS |
|--------------|------------|--------------|-------------|
| 60% gross margin | $0.25 | $3.10 | $5.43 |
| 65% gross margin | $0.29 | $3.54 | $6.20 |
| 70% gross margin | $0.33 | $4.13 | $7.23 |

---

## 5. Competitor Pricing (February 2026)

### AI Coding Assistants

| Product | Free Tier | Individual | Team | Enterprise |
|---------|-----------|-----------|------|-----------|
| GitHub Copilot | Yes (limited) | $10/mo (Pro) or $39/mo (Pro+) | $19/user/mo (Business) | $39/user/mo |
| Cursor | Yes (Hobby) | $20/mo (Pro) | $40/user/mo | Custom |
| Cursor Pro+ | -- | $60/mo | -- | -- |
| Cursor Ultra | -- | $200/mo | -- | -- |
| Tabnine | Yes (Dev Preview) | $9/user/mo | -- | $39/user/mo |

### AI Coding Agents (autonomous)

| Product | Pricing Model | Starting Price | Notes |
|---------|--------------|---------------|-------|
| Devin (Cognition) | Pay-per-use (ACU) | $20/mo min + $2.25/ACU | 1 ACU ~ 15 min of work |
| Factory AI | Token-based | $20/mo | Custom enterprise pricing |
| GitHub Copilot Coding Agent | Included in Pro+ | $39/mo (with Copilot Pro+) | Limited to GitHub ecosystem |

### Key Observations

1. **Copilot and Cursor are assistants, not agents.** They help developers write code faster but do not autonomously triage, write, review, and ship. LailaTov is closer to Devin and Factory in capability.

2. **Devin charges $2.25 per ACU** (roughly 15 minutes of agent work). A full pipeline run on LailaTov (10 minutes average) is comparable to ~0.67 ACU on Devin, or about $1.50 at Devin's rates.

3. **The market is splitting into two categories:**
   - Copilots (per-seat, $10-40/user/month) -- code completion, chat, inline suggestions
   - Agents (per-task or usage-based, $20+/month) -- autonomous code generation

4. **LailaTov competes in the agent category** and should price accordingly -- higher than copilots but with a clear value prop of autonomous task completion.

---

## 6. Proposed Pricing Tiers

### Design Principles

- Per-task pricing (not per-seat) -- aligns cost with value delivered
- Each task = one full pipeline run (TRIAGE -> WRITE -> REVIEW -> REMEDIATE)
- Higher tiers unlock more powerful models and faster processing
- Target 65% gross margin on each tier

### Tier 1: Starter ($49/month)

**Target:** Individual developers, side projects, OSS maintainers

| Feature | Details |
|---------|---------|
| Tasks included | 30 tasks/month |
| Overage rate | $2.00/task |
| Models available | Budget engines (GPT-4.1 mini, DeepSeek V3.2, Gemini 2.5 Flash, Qwen3 Coder) |
| Pipeline | Full pipeline (TRIAGE -> WRITE -> REVIEW -> REMEDIATE) |
| Repos connected | Up to 3 |
| Support | Community / email |

**Unit economics:**
- COGS per task: $0.10 (Budget strategy)
- Revenue per task: $1.63 ($49 / 30 tasks)
- Gross margin per task: **94%**
- Even at 100% overage usage (60 tasks): margin stays above 90%

### Tier 2: Team ($249/month)

**Target:** Small teams (2-10 developers), startups, growing companies

| Feature | Details |
|---------|---------|
| Tasks included | 150 tasks/month |
| Overage rate | $1.75/task |
| Models available | Standard engines (Claude Sonnet 4.6, GPT-4.1, Gemini 2.5 Pro, Kimi K2.5) + all Budget engines |
| Pipeline | Full pipeline + priority queue |
| Repos connected | Up to 10 |
| Team members | Up to 10 seats |
| Support | Email with 24h SLA |

**Unit economics:**
- COGS per task: $1.24 (Standard strategy, blended with some budget tasks)
- Revenue per task: $1.66 ($249 / 150 tasks)
- Gross margin per task: **25%** (at full standard usage)

To maintain 65% margin, we expect a mix: ~40% of tasks use budget engines (triage, simple fixes), ~60% use standard. Blended COGS: $0.78/task. Margin: **53%**.

**Margin improvement path:** Prompt caching on repeated repos will reduce COGS by 30-40% over time, pushing margins toward 65-70%.

### Tier 3: Enterprise ($999/month base + usage)

**Target:** Engineering teams (10-100+ developers), companies with high task volume

| Feature | Details |
|---------|---------|
| Tasks included | 500 tasks/month |
| Overage rate | $1.50/task |
| Models available | All engines including Premium (Claude Opus 4.6, o3) + custom engine routing |
| Pipeline | Full pipeline + priority queue + custom review rules |
| Repos connected | Unlimited |
| Team members | Unlimited seats |
| Custom engines | Bring your own API keys / select preferred models per stage |
| Support | Dedicated Slack channel, 4h SLA |
| Compliance | SOC 2 report, data residency options |
| Analytics | Usage dashboard, cost breakdown per repo |

**Unit economics:**
- COGS per task: $1.50 (blended -- some premium, some standard, some budget)
- Revenue per task: $2.00 ($999 / 500 tasks)
- Gross margin per task: **25%** (base rate only)

At scale, Enterprise customers generate margin through:
1. Overage charges at $1.50/task (healthy margin on standard engine tasks)
2. Prompt caching improvements (30-40% COGS reduction over time)
3. Custom engine routing (customer brings own API keys for premium models, reducing our COGS to near-zero on those tasks)
4. Annual contracts with committed volumes (negotiated discounts from providers)

### Pricing Summary Table

| | Starter | Team | Enterprise |
|---|---------|------|-----------|
| Monthly price | $49 | $249 | $999+ |
| Tasks included | 30 | 150 | 500 |
| Effective price/task | $1.63 | $1.66 | $2.00 |
| Overage price/task | $2.00 | $1.75 | $1.50 |
| Model access | Budget | Standard + Budget | All + Custom |
| Repos | 3 | 10 | Unlimited |
| Seats | 1 | 10 | Unlimited |

### Add-On: Bring Your Own Key (BYOK)

Available on Team and Enterprise tiers. Customers provide their own LLM API keys. LailaTov charges only for orchestration:

| Plan | BYOK Price |
|------|-----------|
| Team BYOK | $99/month (150 tasks, customer pays own LLM costs) |
| Enterprise BYOK | $399/month (500 tasks, customer pays own LLM costs) |

This option appeals to companies that already have volume agreements with Anthropic/OpenAI and want to use their negotiated rates. LailaTov's margin on BYOK is nearly 100% (compute cost only).

---

## 7. Revenue Projections

### Scenario: First 12 Months

| Month | Starter Customers | Team Customers | Enterprise | MRR |
|-------|------------------|---------------|------------|-----|
| 1 | 10 | 2 | 0 | $988 |
| 3 | 30 | 8 | 1 | $4,469 |
| 6 | 80 | 20 | 3 | $11,917 |
| 9 | 150 | 40 | 5 | $22,330 |
| 12 | 250 | 80 | 10 | $42,430 |

**Year 1 total revenue (cumulative):** ~$250K
**Year 1 blended gross margin (estimated):** 55-65%

### Break-Even Analysis

Fixed costs (estimated monthly):
- Infrastructure (Cloud Run, databases, monitoring): $500
- GitHub App hosting / CI: $200
- Domain, email, misc SaaS: $100
- **Total fixed: $800/month**

Break-even at blended 60% margin:
- $800 / 0.60 = $1,333 MRR required
- Achievable at ~27 Starter customers or ~6 Team customers

---

## 8. Key Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM prices drop rapidly | Margins improve (good for us) | Pass savings to customers or improve quality by using better models |
| LLM prices increase | Margins compress | BYOK option shifts cost to customer; multi-provider strategy avoids lock-in |
| DeepSeek/Qwen quality insufficient | Customer churn on Starter tier | Clear tier differentiation; upgrade path to Standard models |
| Devin drops price further | Competitive pressure | Differentiate on pipeline customization, multi-engine routing, self-improving agents |
| High failure rate (agent rewrites) | 2-3x COGS per task | Self-improving pipeline (pattern extraction) reduces failure rate over time |
| Token usage exceeds estimates | Higher COGS than projected | Implement token budgets per stage; circuit breakers on runaway agents |

---

## 9. Recommendations

1. **Launch with Strategy B (Hybrid) as the default.** Sonnet 4.6 for heavy lifting, Haiku 4.5 for classification. This gives the best quality-to-cost ratio at $1.21/task.

2. **Offer Strategy C (Budget) for Starter tier.** DeepSeek V3.2 and GPT-4.1 mini are good enough for simple tasks and bring COGS down to $0.10/task, enabling strong margins even at $49/month.

3. **Implement prompt caching from day one.** System prompts, repo context, and coding conventions repeat across tasks for the same repo. This is the single biggest cost lever, potentially cutting LLM costs by 30-50%.

4. **Add BYOK as an early option.** Enterprise customers with existing Anthropic/OpenAI agreements will want to use their own keys. This is nearly pure margin for LailaTov.

5. **Track cost per task obsessively.** Build real-time cost dashboards from day one. The difference between $0.07 and $2.14 per task is 30x -- model routing decisions are the primary margin lever.

6. **Price on value, not cost.** A completed PR that would take a developer 2-4 hours is worth $50-150 in developer time. At $1.50-2.00/task, LailaTov delivers 25-100x ROI. Do not race to the bottom on pricing.

---

## Sources

- [Anthropic Claude API Pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Google Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [DeepSeek API Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [Qwen API Pricing](https://pricepertoken.com/pricing-page/provider/qwen)
- [Kimi K2 API Pricing](https://pricepertoken.com/pricing-page/model/moonshotai-kimi-k2-0905)
- [Kimi K2.5 API Pricing](https://pricepertoken.com/pricing-page/model/moonshotai-kimi-k2.5)
- [Google Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [GitHub Copilot Pricing](https://github.com/features/copilot/plans)
- [Cursor AI Pricing](https://www.gamsgo.com/blog/cursor-pricing)
- [Devin AI Pricing](https://devin.ai/pricing/)
- [Tabnine Pricing](https://www.tabnine.com/pricing/)
- [Factory AI Pricing](https://factory.ai/pricing)
