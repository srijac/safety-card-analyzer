---
title: AI Safety Card Disclosure Analysis
---

Frontier AI labs publish safety cards but they use different taxonomies, evaluation frameworks, and reporting styles. This project explores whether AI-assisted workflows can help humans systematically compare these disclosures for similarities and differences while keeping humans responsible for validation. 

![Approach — the discover, compare, review, extract pipeline](figures/approach_figure.png)


## Approach

We designed a multi-step iterative approach. The workflow first discovers the major themes and taxonomies used across the safety cards. This is followed by an LLM-based semantic clustering of discovered themes to normalize or compare safety cards across shared analytical themes that use varying descriptive language. The human then iteratively provides feedback on the analytical theme, defining the scope of the analysis. This step can include modification, expansion, and correction of the clustering. By anchoring on the shared schema, the workflow analyzes the disclosed information across companies for overlaps and differences. The first prototype compares the Claude 3.5 Sonnet/Haiku addendum with the GPT-4o system card; key findings are in the [README](https://github.com/srijac/safety-card-analyzer). Future updates will expand this work.

## What worked well

**Implementation.** The multi-step approach was designed, reviewed, and steered by a human, but the implementation was AI-driven. Once the steps were detailed, the generated code closely matched the requirements (and sometimes needed course correction). This significantly reduced implementation time, with this first pass taking ~5-6 hours. While no controlled comparison was performed, implementing the same pipeline without AI assistance (just plain web access to debug errors) or entirely manually would likely have required several days.

**Semantic clustering and schema extraction across different terminologies.** Parsing information using company-specific terminology and clustering it to identify commonalities to create a schema was AI-driven and worked well. Given the size of the safety cards, this comparison is impractical manually, requiring ML information extraction approaches. AI assistance facilitates this process but has limitations. It is possible to improve the semantic analysis to produce a more comprehensive or targeted comparison.

## Lessons learned and challenges

**AI-as-an-assistant.** In analyzing this process, we started with older, smaller models that have relatively compact (and less interesting) safety cards so that they fit within smaller 'max-token' limits while creating the prototype. The multi-step approach was human-designed. AI assistance was used in implementation. Although we shared the overarching goal and asked the model to generate a high-level plan, the generated code sometimes deviated, omitted details, or ignored instructions — whether those instructions were human-written or LLM-proposed and human-approved. We also observed cases where the LLM repeatedly diverged from specified workflow constraints, requiring iterative human correction. The AI-generated plan was also not comprehensive enough to design and complete all steps. Because this was the exploratory phase, many decisions surfaced only during the build and needed human steering. We still expect the workflow to need additional updates and refinements for planned future versions. Future iterations may benefit from an existing log of human preferences and the current codebase to build off of, potentially enabling it to generate more complete implementation plans.

**Safety cards.** Safety cards follow varying taxonomies, frameworks, terminologies, and decision thresholds. This also makes extraction and comparison challenging, necessitating the semantic clustering step. Our current workflow used a simple prompt-based LLM as a semantic clusterer, and refinements to this step can improve comparison. Analyzing a single model family or releases from a company alone may be more straightforward due to less variability in terminology. This also points to the need for standards that identify necessary information for transparency, while establishing a common taxonomy for reporting.

**Ground truth.** In the exploratory phase of an open-ended study, the lack of quantifiable feedback made the AI-assisted implementation more nuanced, requiring a human-in-the-loop for steering. Access to or feedback from model developers would be useful in improving model judgment around key information. One possible evaluation would compare the workflow's extracted summaries against expert-generated summaries for the same analytical dimensions, measuring whether the workflow captures the information the developers themselves consider most important. Such feedback could improve prompts, schema design, and extraction quality.


## Future uses

1. In AI evaluation, transparency, and standards setting: use in assessing evaluations conducted and risk thresholds for various dangerous capabilities and safety guardrails added; analysis of capabilities over time; checking adherence to standards and the need for additional transparency.
2. AI-assisted transparency assessment: AI-assisted comparison of transparency practices across frontier AI developers.
3. Embedded in evaluation and release processes: in more stable, robust future versions, the workflow could support AI-assisted generation of draft safety and transparency cards from evaluation logs, with human review prior to publication.
4. Targeted actor- or domain-specific use cases: auto-generate different versions of a safety card for a given model family for different audiences - e.g., policymakers, deployers, auditors.
