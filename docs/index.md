---
title: AI System Card Disclosure Analysis
---

An LLM-driven pipeline that extracts and compares what frontier AI labs disclose in their
safety / system cards. First comparison: **Claude 3.5 Sonnet/Haiku** vs **GPT-4o**, scoped
to frontier / dangerous-capability risk — CBRN, cybersecurity, persuasion, and autonomy.

## Key findings

- Both labs judged these models **low-concern on CBRN, cybersecurity, and autonomy**. The
  clear divergence is **persuasion** — GPT-4o is **Medium (marginal)**; the Claude card
  **does not assess** it.
- The cards **overlap on 12 topics**; GPT-4o discloses **17 unique** vs Claude's **8**,
  mostly from its **voice/omni modality**.
- **Same verdict, different yardsticks:** Anthropic uses an **ASL threshold**, OpenAI a
  **graded Low/Med/High** framework — but both rely on **METR** for external autonomy tests.

## Frontier risk ratings

<iframe src="figures/risk_ratings.html" width="100%" height="440" frameborder="0"></iframe>

Both rate CBRN, cyber, and autonomy low; persuasion is the split. Ratings use each lab's
**own scale** (ASL vs Low/Med/High) and are not directly equivalent.

---

## Where the two cards overlap

The findings each card reports on the topics **both** cover:

| Topic | Claude 3.5 Sonnet/Haiku | GPT-4o |
|---|---|---|
| **Preparedness / RSP framework** | CBRN, cyber & autonomy improved but **below ASL-3** → ASL-2; persuasion not assessed | Cyber, CBRN, Autonomy **Low**; Persuasion **Medium** → overall **Medium** |
| **Cybersecurity** | CTF gains on some types; no scores; below ASL-3 | 172 CTFs → **19% HS, 0% collegiate, 1% pro**; no real-world uplift → Low |
| **Biological / CBRN** | Knowledge + skills improved; below ASL-3 | Gryphon Scientific uplift; **69% consensus@10**; no medium uplift → Low |
| **Model autonomy** | SWE-bench **49%** (Sonnet), autonomy precursor; below ASL-3 | **ARA 0%/100**; SWE-bench **19% pass@1**; METR ML **0/10** → Low |
| **Red teaming** | **14 policy areas × 6 languages**; Haiku improved non-English | **100+ testers, 45 languages, 4 phases**; incl. voice risks |
| **Refusals** | WildChat toxic **89.2% / 88.0%**; over-refusal 5.3% / 4.8% | not_unsafe **1.0** audio; not_overrefuse **0.91**; text→audio transfer |
| **Third-party (METR)** | METR named; **no results disclosed** | METR **86 tasks / 31 families**; **no significant uplift** vs GPT-4 |

**Analysis:**

- **Same verdict, different yardstick.** Anthropic asks whether the model crosses **ASL-3**
  (it didn't → ASL-2); OpenAI grades each category and lands GPT-4o at **Medium overall**.
  Persuasion is tracked by OpenAI but **absent from Anthropic's frontier taxonomy**.
- **A transparency gap.** OpenAI reports numbers; Anthropic reports direction — cyber CTF
  **19% → 0% → 1%** vs "improved, no scores"; autonomy **0%/100 ARA, 0/10 METR** vs
  "SWE-bench gains as a precursor."
- **Red teaming, different shape.**
  - *Anthropic:* 14 policy areas × 6 languages — Elections Integrity, Child Safety, Cyber
    Attacks, Hate & Discrimination, Violent Extremism; plus computer-use red teaming
    (scaled account creation, content distribution, age-gate bypass, abusive form-filling).
  - *OpenAI:* 100+ testers, 45 languages, 29 countries, 4 phases escalating to iOS voice —
    violative content, mis/disinformation, bias, ungrounded inference, sensitive-trait
    attribution, privacy / geolocation / person-ID, anthropomorphism, fraud, copyright.
- **Refusals.** Anthropic reports chat refusal rates (WildChat / XSTest); OpenAI emphasizes
  **text→audio transfer** of safety behavior — relevant only because GPT-4o speaks.
- **Third-party.** Both used **METR**, but only OpenAI publishes results (METR: 86 tasks, no
  uplift; **Apollo**: 14 scheming tasks). Anthropic names METR and **US & UK AISI** with no
  reported findings.

---

## Where the two cards differ

<iframe src="figures/disclosure_matrix.html" width="100%" height="820" frameborder="0"></iframe>

- **Only GPT-4o:** voice cloning, speaker identification, disparate voice performance,
  ungrounded inference, erotic/violent speech, anthropomorphization & emotional reliance,
  health benchmarks, underrepresented-language evals, training-data disclosure.
- **Only Claude 3.5:** the computer-use agent, prompt-injection resistance, computer-use red
  teaming, the explicit RSP/ASL determination, knowledge-cutoff dates, human-preference
  evals, vision benchmarks.

Some of this asymmetry is real (voice is genuinely new); some is a format artifact — see caveats.

---

## How it works

A four-stage, human-in-the-loop pipeline (`safety_card_batch.py`): **discover** (list each
card's sections) → **compare** (*schema discovery* — cluster into a shared schema of themes) → **review** (human confirms what
to extract; extraction is gated) → **extract** (semantic overlap/unique, then per-card content).

More on the approach, lessons learned, and future uses: [Discussion & notes](discussion.md).

Code: [github.com/srijac/safety-card-analyzer](https://github.com/srijac/safety-card-analyzer)

## Caveats

- The Claude source is the **Claude 3.5 model card addendum (Oct 2024)**, a supplement to the
  full Claude 3 Model Card; some Claude disclosures live in the base card, which inflates
  GPT-4o's apparent breadth. A later version ingests the base card.
- Overlap / unique matching is **LLM-semantic**, not exact string matching.
- Risk levels use each lab's **own scale** and were LLM-extracted — verify against the source
  PDFs before citing.
- First version compares two cards; more are planned.
