---
title: AI System Card Disclosure Analysis
---

# What do frontier AI labs actually disclose about safety?

AI labs publish "system cards" or "model cards" alongside major model releases. They
are the primary public window into how a lab evaluated its model for dangerous
capabilities — but they vary enormously in what they cover and how they frame risk.

This project uses an LLM-driven pipeline to **extract and compare** those cards on a
common footing. The first comparison puts **Claude 3.5 Sonnet/Haiku** (Anthropic) next
to **GPT-4o** (OpenAI), scoped to frontier / dangerous-capability risk: **CBRN,
cybersecurity, persuasion, and autonomy**.

---

## Finding 1 — On frontier risk, the two labs mostly agree; persuasion is the exception

Both labs judged these models to be low concern for CBRN, cybersecurity, and autonomy.
The one clear divergence is **persuasion**.

<iframe src="figures/risk_ratings.html" width="100%" height="440" frameborder="0"></iframe>

[View full-size](figures/risk_ratings.html)

- **Anthropic** frames risk through its **Responsible Scaling Policy (RSP)**: the question
  is whether a capability crosses the **ASL-3** threshold. For CBRN, cyber, and autonomy it
  did not — the model stays **ASL-2**. Persuasion is **not assessed** as a frontier category.
- **OpenAI** uses its **Preparedness Framework** (Low / Medium / High, deployment blocked
  only at High). GPT-4o is **Low** on cyber, CBRN, and autonomy, and **Medium (marginal)**
  on **persuasion** — which drives its overall **Medium** rating.

The underlying evaluations echo the low ratings: on cybersecurity, GPT-4o solved 19% of
high-school, 0% of collegiate, and 1% of professional capture-the-flag challenges; on
autonomy it scored 0% across 100 autonomous-replication trials. Anthropic reports
qualitative improvement on the same axes but below its ASL-3 bar.

---

## Finding 2 — GPT-4o's card is broader, largely because of modality

GPT-4o's card discloses far more distinct topics (**17 unique** vs **8**), with **12
shared**.

<iframe src="figures/disclosure_breadth.html" width="100%" height="440" frameborder="0"></iframe>

Most of GPT-4o's extra breadth comes from its **native voice / omni modality**, which
opens risks that simply don't exist for a text model: unauthorized **voice cloning**,
**speaker identification**, disparate performance across accents, and **erotic/violent
speech output** — plus **anthropomorphization and emotional reliance**. It also uniquely
reports **health/clinical** benchmarks and **underrepresented-language** evaluations.

Anthropic's unique disclosures cluster around its **computer-use agent**: the computer-use
capability itself, **prompt-injection** resistance, computer-use-specific red teaming, and
an explicit **RSP / ASL determination**.

<iframe src="figures/disclosure_matrix.html" width="100%" height="820" frameborder="0"></iframe>

---

## Finding 3 — Different safety scaffolding, similar third-party backbone

The cards differ in structure (threshold-based ASL vs graded Preparedness levels), but both
lean on the same external evaluator: **METR** ran long-horizon autonomy tasks for both
models. OpenAI additionally commissioned **Apollo Research** to probe scheming / theory of
mind. Anthropic names **US & UK AISI** as pre-deployment testers but, in this card, without
a dedicated results section.

---

## How it works

A four-stage, human-in-the-loop pipeline:

1. **discover** — an LLM lists every section in each card.
2. **compare** — sections are clustered into shared themes.
3. **review** — a human confirms which dimensions to extract (extraction is gated on it).
4. **extract** — semantic overlap/unique detection, then per-card content extraction.

Code and figures: [github.com/srijac/safety-card-analyzer](https://github.com/srijac/safety-card-analyzer)

---

## Caveats

- The Claude source is the **Claude 3.5 model card addendum (Oct 2024)**, a supplement to
  the full Claude 3 Model Card; some Claude disclosures live in the base card and aren't
  included here, which inflates GPT-4o's apparent breadth. A later version ingests the base card.
- Overlap / unique matching is **LLM-semantic**, not exact string matching.
- Risk levels use each lab's **own scale** (ASL vs Low/Med/High) and are not directly equivalent.
- First version compares two cards; more are planned.
