"""
Safety Card Batch Analyzer
==========================
Compare what multiple AI *system cards* disclose, using one model across many
cards. This is the batch generalization of safety_card_workflow.py, built around
an OFFLINE human-in-the-loop review instead of an inline terminal prompt.

Three modes, run in order:

  1. discover  — Read ONE system card and save the sections it contains.
                 Run this once per card. Outputs are never overwritten.
                    -> discoveries/<card_id>__<model>.json

  2. compare   — Read ALL discoveries, cluster their sections into canonical
                 themes, and emit a cross-card review you edit offline.
                    -> comparison/theme_matrix.md   (human-readable coverage table)
                    -> comparison/themes.json       (edit "selected" to pick factors)

  3. extract   — Read your selected themes and pull them from every card.
                    -> extractions/<card_id>__<model>.json
                    -> comparison/comparison_table.md   (final cross-card table)

Usage:
  python safety_card_batch.py --mode discover --url <url> --id claude-3
  python safety_card_batch.py --mode discover --file card.pdf --id gpt-4
  python safety_card_batch.py --mode compare
  python safety_card_batch.py --mode extract

Supported models:
  claude-opus-4-7   (default — most capable)
  claude-opus-4-6
  claude-sonnet-4-6
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import anthropic
import requests

try:
    from pypdf import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


SUPPORTED_MODELS = ["claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6"]
DEFAULT_MODEL    = "claude-opus-4-7"

BASE            = Path(__file__).parent
DISCOVERIES_DIR = BASE / "discoveries"
EXTRACTIONS_DIR = BASE / "extractions"
COMPARISON_DIR  = BASE / "comparison"
THEMES_PATH     = COMPARISON_DIR / "themes.json"
MATRIX_PATH     = COMPARISON_DIR / "theme_matrix.md"
TABLE_PATH      = COMPARISON_DIR / "comparison_table.md"
STEP3_INPUT     = COMPARISON_DIR / "step3_input.json"   # the active reviewed dimension spec
# Output filenames are built at runtime and tagged with the compared cards + the
# analyzer model, e.g. comparison_table__cardA__vs__cardB__by__<model>.md — see pair_tag().


# ── Fixed schemas ─────────────────────────────────────────────────────────────

DISCOVERY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sections"],
    "properties": {
        "sections": {
            "type": "array",
            "description": "All distinct sections or topics found in the document",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "description"],
                "properties": {
                    "name":        {"type": "string", "description": "Short section name"},
                    "description": {"type": "string", "description": "What this section contains"},
                },
            },
        }
    },
}

# The compare call clusters every card's sections into shared canonical themes.
THEMES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["themes"],
    "properties": {
        "themes": {
            "type": "array",
            "description": "Canonical themes found across the cards, most common first",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["theme", "description", "cards"],
                "properties": {
                    "theme":       {"type": "string", "description": "Canonical theme name"},
                    "description": {"type": "string", "description": "What this theme covers"},
                    "cards": {
                        "type": "array",
                        "description": "Which cards contain this theme and their original section name",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["card_id", "section_name"],
                            "properties": {
                                "card_id":      {"type": "string"},
                                "section_name": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}


# ── Content loading ───────────────────────────────────────────────────────────

def extract_pdf_text(path: str) -> str:
    if not PDF_SUPPORT:
        sys.exit("Error: pypdf is required.\nInstall: pip install pypdf")
    print(f"    Reading PDF: {path}")
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[Page {i}]\n{text}")
    if not pages:
        sys.exit("Error: No extractable text found in PDF.")
    return "\n\n".join(pages)


def load_from_url(url: str) -> str:
    print(f"    Fetching: {url}")
    resp = requests.get(url, timeout=30,
                        headers={"User-Agent": "Mozilla/5.0 (SafetyCardBatch/1.0)"})
    resp.raise_for_status()
    if "pdf" in resp.headers.get("content-type", "").lower():
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        try:
            return extract_pdf_text(tmp_path)
        finally:
            os.unlink(tmp_path)
    return resp.text


def load_safety_card(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        content = load_from_url(source)
    else:
        path = Path(source)
        if not path.exists():
            sys.exit(f"Error: File not found: {source}")
        content = (extract_pdf_text(str(path)) if path.suffix.lower() == ".pdf"
                   else path.read_text(encoding="utf-8", errors="replace"))
    print(f"    Loaded {len(content):,} characters")
    return content


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", text).strip("-")


def default_card_id(source: str) -> str:
    """Derive a card id from a URL/path filename when --id is not given."""
    stem = Path(urlparse(source).path or source).stem or "card"
    return slugify(stem)


def new_client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Error: ANTHROPIC_API_KEY not set.\n  Run: export ANTHROPIC_API_KEY='sk-ant-...'")
    return anthropic.Anthropic()


# ── Mode 1: DISCOVER ──────────────────────────────────────────────────────────

def run_discover(source: str, card_id: str, model: str, force: bool) -> None:
    DISCOVERIES_DIR.mkdir(exist_ok=True)
    # Key by BOTH card_id and model so a second model on the same card never
    # overwrites the first. This is the fix for the workflow.py URL-only bug.
    out_path = DISCOVERIES_DIR / f"{card_id}__{model}.json"

    if out_path.exists() and not force:
        sys.exit(
            f"Refusing to overwrite existing discovery: {out_path.name}\n"
            f"  Step-1 outputs are never overwritten. Pass --force to redo, "
            f"or use a different --id."
        )

    print(f"── DISCOVER  card={card_id}  model={model}")
    content = load_safety_card(source)

    client = new_client()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=(
            "You are an expert at analyzing AI model documentation. "
            "Read the document carefully and identify every distinct section "
            "and the specific type of information each one contains."
        ),
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": f"DOCUMENT:\n\n{content}"},
                {"type": "text", "text": "List every section and topic present in this document."},
            ],
        }],
        output_config={"format": {"type": "json_schema", "schema": DISCOVERY_SCHEMA}},
    )
    sections = json.loads(next(b.text for b in response.content if b.type == "text"))["sections"]

    record = {
        "card_id":  card_id,
        "source":   source,
        "model":    model,
        "date":     str(date.today()),
        "sections": sections,
    }
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   Found {len(sections)} section(s) -> {out_path.relative_to(BASE)}\n")


# ── Mode 2: COMPARE ───────────────────────────────────────────────────────────

def load_discoveries() -> list:
    if not DISCOVERIES_DIR.exists():
        sys.exit("No discoveries/ directory yet. Run --mode discover first.")
    files = sorted(DISCOVERIES_DIR.glob("*.json"))
    if not files:
        sys.exit("No discoveries found. Run --mode discover first.")
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def run_compare(model: str) -> None:
    COMPARISON_DIR.mkdir(exist_ok=True)
    discoveries = load_discoveries()
    card_ids = [d["card_id"] for d in discoveries]
    print(f"── COMPARE  cards={', '.join(card_ids)}  model={model}")

    # Build a readable listing of every card's sections for the clustering call.
    blocks = []
    for d in discoveries:
        lines = [f"CARD: {d['card_id']}  (source: {d['source']})"]
        for s in d["sections"]:
            lines.append(f"  - {s['name']}: {s['description']}")
        blocks.append("\n".join(lines))
    listing = "\n\n".join(blocks)

    client = new_client()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=(
            "You align sections across multiple AI system cards. Group sections "
            "that cover the same underlying topic into a single canonical theme, "
            "even when the cards name them differently. Only list a card under a "
            "theme if that card genuinely contains it. Order themes by how many "
            "cards contain them, most common first."
        ),
        messages=[{
            "role": "user",
            "content": [{
                "type": "text",
                "text": (
                    "Here are the discovered sections of each card. Cluster them "
                    "into canonical themes.\n\n" + listing
                ),
            }],
        }],
        output_config={"format": {"type": "json_schema", "schema": THEMES_SCHEMA}},
    )
    themes = json.loads(next(b.text for b in response.content if b.type == "text"))["themes"]

    total = len(card_ids)
    enriched = []
    for t in themes:
        present = {c["card_id"]: c["section_name"] for c in t["cards"]
                   if c["card_id"] in card_ids}
        coverage = len(present)
        enriched.append({
            "theme":       t["theme"],
            "description": t["description"],
            "coverage":    f"{coverage}/{total}",
            # Default-select factors common to ALL cards — the best comparison set.
            "selected":    coverage == total,
            "cards":       present,   # card_id -> original section name
        })

    THEMES_PATH.write_text(
        json.dumps({"card_ids": card_ids, "themes": enriched}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_review(discoveries, card_ids, enriched)
    print(f"   {len(enriched)} theme(s) -> {THEMES_PATH.relative_to(BASE)}")
    print(f"   Review doc      -> {MATRIX_PATH.relative_to(BASE)}")
    print(f"   Edit \"selected\" in themes.json (or ask me to add rows), then: --mode extract\n")


def esc(text: str) -> str:
    """Escape a string for use inside one markdown table cell."""
    return (text or "").replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def write_review(discoveries: list, card_ids: list, themes: list) -> None:
    """
    Render the offline review doc:
      Part 1 — one per-card table (numbered rows) so you can point at sections
      Part 2 — the consolidated cross-card theme matrix
    Deterministic: no model call, safe to regenerate after editing selections.
    """
    body = [
        "# System Card Review",
        "",
        f"Cards compared: {', '.join(card_ids)}",
        "",
        "**Part 1** lists each card's own sections (numbered). Point at a row to add "
        "it to extraction — e.g. \"add claude-3-5-haiku #11\".",
        "**Part 2** is the consolidated theme matrix aligning sections across cards.",
        "",
        "---",
        "",
        "## Part 1 — Per-card sections",
        "",
    ]

    disc_by_id = {d["card_id"]: d for d in discoveries}
    # Map each card's section name -> its row number in the Part-1 table, so the
    # consolidated matrix can cite exactly where each cell came from.
    row_of = {}
    for cid in card_ids:
        d = disc_by_id.get(cid)
        row_of[cid] = {s["name"]: i for i, s in enumerate(d["sections"], start=1)} if d else {}

    for cid in card_ids:
        d = disc_by_id.get(cid)
        if not d:
            continue
        body.append(f"### {cid}")
        body.append(f"Source: {d['source']}")
        body.append("")
        body.append("| # | Section | Description |")
        body.append("|---|---------|-------------|")
        for i, s in enumerate(d["sections"], start=1):
            body.append(f"| {i} | {esc(s['name'])} | {esc(s['description'])} |")
        body.append("")

    # Part 2 — consolidated theme matrix. Each cell cites the Part-1 row (#N).
    header  = "| Theme | Coverage | Sel | " + " | ".join(card_ids) + " |"
    divider = "|" + "---|" * (3 + len(card_ids))
    rows = [header, divider]
    for t in themes:
        cells = []
        for cid in card_ids:
            if cid in t["cards"]:
                name = t["cards"][cid]
                num  = row_of[cid].get(name)
                tag  = f"#{num} " if num else "#? "   # #? = name didn't match a Part-1 row
                cells.append(f"{tag}{esc(name)}")
            else:
                cells.append("")
        sel = "☑" if t.get("selected") else "☐"
        rows.append(f"| **{esc(t['theme'])}** | {t['coverage']} | {sel} | " + " | ".join(cells) + " |")

    body += [
        "---",
        "",
        "## Part 2 — Consolidated theme matrix",
        "",
        "`Sel` = selected for extraction (themes present in all cards are pre-selected).",
        "Edit `\"selected\"` in `themes.json` (or ask me), then run `--mode review` to "
        "re-render and `--mode extract` to build the comparison.",
        "",
        *rows,
        "",
        "### Theme descriptions",
        "",
    ]
    for t in themes:
        body.append(f"- **{t['theme']}** ({t['coverage']}): {t['description']}")
    MATRIX_PATH.write_text("\n".join(body) + "\n", encoding="utf-8")


# ── Mode: REVIEW (re-render the doc from saved files, no model call) ───────────

def run_review() -> None:
    if not THEMES_PATH.exists():
        sys.exit("No comparison/themes.json. Run --mode compare first.")
    spec = json.loads(THEMES_PATH.read_text(encoding="utf-8"))
    discoveries = load_discoveries()
    write_review(discoveries, spec["card_ids"], spec["themes"])
    print(f"── REVIEW  re-rendered {MATRIX_PATH.relative_to(BASE)} (no model call)")


# ── Mode 3: EXTRACT ───────────────────────────────────────────────────────────

def pair_tag(card_ids: list, model: str) -> str:
    """Filename tag identifying the comparison, e.g. cardA__vs__cardB__by__model."""
    return "__vs__".join(card_ids) + f"__by__{model}"


def cell(text: str) -> str:
    """Make extracted text safe for a single markdown table cell."""
    text = (text or "").strip()
    if not text:
        return "_(not present)_"
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " <br> ")


# Every extracted field returns compact key_phrases (for the scannable comparison
# TABLE) plus fuller detail (for prose/analysis and the JSON). Tables must never be
# paragraph-heavy — this is a standing requirement.
KEYS_RULE = ("Compact key phrases for a comparison-table cell: ~4-14 words, "
             "semicolon-separated fragments, keep concrete numbers/thresholds, "
             "no full sentences.")


def kp(v) -> str:
    """Table-cell text: the compact key_phrases if present, else the raw string."""
    if isinstance(v, dict):
        return v.get("key_phrases") or v.get("detail") or ""
    return v or ""


# ── Schemas for the two extraction passes ─────────────────────────────────────

DISCLOSURE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overlaps", "unique"],
    "properties": {
        "overlaps": {
            "type": "array",
            "description": "Topics BOTH cards disclose (match by meaning, not section name)",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["topic", "mentions"],
                "properties": {
                    "topic":    {"type": "string"},
                    "mentions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["card_id", "section"],
                            "properties": {
                                "card_id": {"type": "string"},
                                "section": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "unique": {
            "type": "array",
            "description": "Topics only ONE card discloses, with the single most important reason why",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["card_id", "topic", "section", "why"],
                "properties": {
                    "card_id": {"type": "string"},
                    "topic":   {"type": "string"},
                    "section": {"type": "string"},
                    "why":     {"type": "string"},
                },
            },
        },
    },
}


# ── Mode: EXTRACT ─────────────────────────────────────────────────────────────

def run_extract(model: str, confirmed: bool) -> None:
    # Hard gate: extraction is the only paid step that acts on the reviewed
    # spec. It must not run until the user has reviewed and explicitly confirmed.
    if not confirmed:
        sys.exit(
            "Refusing to extract: you must review the comparison spec first.\n"
            "  Loop:  --mode review  (repeat until happy)\n"
            "  Then:  --mode extract --confirm"
        )
    if not STEP3_INPUT.exists():
        sys.exit(f"No {STEP3_INPUT.relative_to(BASE)}. The reviewed dimension spec must exist first.")
    spec = json.loads(STEP3_INPUT.read_text(encoding="utf-8"))
    run_extract_dimensions(spec, model)


def run_extract_dimensions(spec: dict, model: str) -> None:
    card_ids = spec["card_ids"]
    labels   = spec.get("card_labels", {cid: cid for cid in card_ids})
    caps     = spec.get("capabilities", [])
    dims     = [d for d in spec["dimensions"] if d.get("selected", True)]
    per_card = [d for d in dims if d.get("type", "per_card") == "per_card"]
    cross    = [d for d in dims if d.get("type") == "cross_card"]

    EXTRACTIONS_DIR.mkdir(exist_ok=True)
    discoveries = {d["card_id"]: d for d in load_discoveries()}
    client = new_client()
    tag = pair_tag(card_ids, model)

    print(f"── EXTRACT  {tag}")
    cap_note = (f"Organize each answer around these capabilities: {', '.join(caps)}. "
                if caps else "")

    # Pass 1 — COVERAGE: identify shared (overlap) and unique topics semantically,
    # from the discovery section lists (no PDF read). Content is pulled in Pass 2.
    disclosure = {"overlaps": [], "unique": []}
    if cross:
        print("   Pass 1: cross-card coverage (semantic overlap & unique)...")
        listing = []
        for cid in card_ids:
            d = discoveries.get(cid)
            if not d:
                continue
            listing.append(f"CARD {cid} ({labels.get(cid, cid)}) sections:")
            for s in d["sections"]:
                listing.append(f"  - {s['name']}: {s['description']}")
        response = client.messages.create(
            model=model, max_tokens=8000,
            system=("You compare disclosure coverage across AI system cards. Match topics "
                    "by MEANING, not section title. Only reference sections that exist."),
            messages=[{"role": "user",
                       "content": [{"type": "text", "text": cross[0]["instruction"] + "\n\n" +
                                    "\n".join(listing)}]}],
            output_config={"format": {"type": "json_schema", "schema": DISCLOSURE_SCHEMA}},
        )
        disclosure = json.loads(next(b.text for b in response.content if b.type == "text"))
    overlaps = disclosure.get("overlaps", [])
    unique   = disclosure.get("unique", [])

    # Pass 2 — CONTENT: for each card, one call extracting the actual disclosed text
    # for (a) the fixed dimensions, (b) each shared topic, (c) each unique topic.
    # This is the point of the extract step — overlaps carry substance, not just labels.
    per_card_results = {}   # card_id -> {"dims":{}, "overlap":{}, "unique":{}}
    for cid in card_ids:
        disc = discoveries.get(cid)
        if not disc:
            print(f"   Skipping {cid}: discovery missing.")
            continue
        dims_for_card = [d for d in per_card if d.get("sources", {}).get(cid)]
        ov_for_card   = [o for o in overlaps
                         if any(m["card_id"] == cid for m in o.get("mentions", []))]
        uq_for_card   = [u for u in unique if u["card_id"] == cid]
        if not (dims_for_card or ov_for_card or uq_for_card):
            continue

        n = len(dims_for_card) + len(ov_for_card) + len(uq_for_card)
        print(f"   Pass 2: {cid} — extracting {n} field(s) "
              f"({len(dims_for_card)} dims, {len(ov_for_card)} shared, {len(uq_for_card)} unique)...")
        content = load_safety_card(disc["source"])

        fields, asks = [], []   # fields: (key, bucket, name, detail_desc)
        for d in dims_for_card:
            key = d["id"]
            srcs = ", ".join(f'"{s}"' for s in d["sources"][cid])
            fields.append((key, "dims", d["id"], d["instruction"]))
            asks.append(f"- [{key}] {d['name']}: {d['instruction']} Focus on sections: {srcs}.")
        for i, o in enumerate(ov_for_card):
            key = f"ov_{i}"
            sec = next((m["section"] for m in o["mentions"] if m["card_id"] == cid), "")
            fields.append((key, "overlap", o["topic"], f"What THIS card discloses about: {o['topic']}"))
            asks.append(f"- [{key}] Shared topic '{o['topic']}': what THIS card discloses, "
                        f"with concrete numbers. See section \"{sec}\".")
        for i, u in enumerate(uq_for_card):
            key = f"uq_{i}"
            fields.append((key, "unique", u["topic"], f"What THIS card discloses about: {u['topic']}"))
            asks.append(f"- [{key}] Topic unique to this card '{u['topic']}': what it "
                        f"discloses, with concrete details. See section \"{u['section']}\".")

        ask_text  = "\n".join(asks)
        # Cache the document so the second (detail) call reuses it instead of re-uploading.
        doc_block = {"type": "text",
                     "text": f"DOCUMENT ({labels.get(cid, cid)}):\n\n{content}",
                     "cache_control": {"type": "ephemeral"}}

        def extract_pass(desc_of, instruction, max_toks):
            # Flat string schema per field — nested objects make the strict grammar too
            # large; two flat calls (key_phrases, detail) stay well under the limit.
            flat = {"type": "object", "additionalProperties": False,
                    "required": [f[0] for f in fields],
                    "properties": {f[0]: {"type": "string", "description": desc_of(f)}
                                   for f in fields}}
            r = client.messages.create(
                model=model, max_tokens=max_toks,
                system=("You are an expert AI safety researcher comparing AI system cards. "
                        + instruction + " " + cap_note +
                        "If something asked for is not present, say so explicitly rather than inventing."),
                messages=[{"role": "user", "content": [
                    doc_block,
                    {"type": "text", "text": "For each field below:\n" + ask_text}]}],
                output_config={"format": {"type": "json_schema", "schema": flat}},
            )
            return json.loads(next(b.text for b in r.content if b.type == "text"))

        keys_raw   = extract_pass(lambda f: KEYS_RULE,
                                  "Return COMPACT KEY PHRASES per field (never full sentences).", 6000)
        detail_raw = extract_pass(lambda f: f[3],
                                  "Return fuller PROSE detail per field, with concrete numbers/thresholds.", 16000)

        res = {"dims": {}, "overlap": {}, "unique": {}}
        for key, bucket, name, _ in fields:
            res[bucket][name] = {"key_phrases": keys_raw.get(key, ""),
                                 "detail":      detail_raw.get(key, "")}
        per_card_results[cid] = res

        (EXTRACTIONS_DIR / f"{cid}__{model}.json").write_text(
            json.dumps({"card_id": cid, "source": disc["source"], "model": model,
                        "extraction": res}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Fold extracted content back into the disclosure structure for the JSON output.
    for o in overlaps:
        o["content"] = {cid: per_card_results.get(cid, {}).get("overlap", {}).get(o["topic"], "")
                        for cid in card_ids
                        if any(m["card_id"] == cid for m in o.get("mentions", []))}
    for u in unique:
        u["content"] = per_card_results.get(u["card_id"], {}).get("unique", {}).get(u["topic"], "")

    out = {
        "card_ids":    card_ids,
        "card_labels": labels,
        "model":       model,
        "capabilities": caps,
        "dimensions":  [{"id": d["id"], "name": d["name"], "type": d.get("type", "per_card")}
                        for d in dims],
        "per_card":    per_card_results,
        "disclosure":  disclosure,
    }
    out_json = COMPARISON_DIR / f"step3_output__{tag}.json"
    out_json.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    out_md = COMPARISON_DIR / f"comparison_table__{tag}.md"
    write_comparison_report(out_md, card_ids, labels, per_card, per_card_results,
                            disclosure, discoveries)
    print(f"\n   Structured output -> {out_json.relative_to(BASE)}")
    print(f"   Comparison report -> {out_md.relative_to(BASE)}\n")


def write_comparison_report(path, card_ids, labels, per_card_dims, results,
                            disclosure, discoveries) -> None:
    cols = [labels.get(cid, cid) for cid in card_ids]

    row_of = {}
    for cid in card_ids:
        d = discoveries.get(cid)
        row_of[cid] = {s["name"]: i for i, s in enumerate(d["sections"], start=1)} if d else {}

    def cite(cid, section):
        n = row_of.get(cid, {}).get(section)
        return f"#{n} {section}" if n else section

    # Part A — fixed safety dimensions, cards as columns.
    header  = "| Dimension | " + " | ".join(cols) + " |"
    divider = "|" + "---|" * (1 + len(card_ids))
    rows = [header, divider]
    for d in per_card_dims:
        cells = [cell(kp(results.get(cid, {}).get("dims", {}).get(d["id"], ""))) for cid in card_ids]
        rows.append(f"| **{esc(d['name'])}** | " + " | ".join(cells) + " |")

    body = [
        f"# System Card Comparison — {' vs '.join(cols)}",
        "",
        "Each row is a safety dimension; each column is a system card. Cells are compact "
        "key phrases (scoped to the frontier/dangerous-capability lens); full detail is in "
        "the `step3_output__*.json`.",
        "",
        *rows,
        "",
        "---",
        "",
        "## Who discloses what",
        "",
        "### Shared topics — side-by-side content",
        "",
        "For each topic both cards disclose, what each one actually says.",
        "",
    ]

    if disclosure.get("overlaps"):
        body.append("| Topic | " + " | ".join(cols) + " |")
        body.append("|" + "---|" * (1 + len(card_ids)))
        for o in disclosure["overlaps"]:
            m = {x["card_id"]: x["section"] for x in o.get("mentions", [])}
            cells = []
            for cid in card_ids:
                if cid in m:
                    txt = kp(results.get(cid, {}).get("overlap", {}).get(o["topic"], ""))
                    cells.append(f"_{esc(cite(cid, m[cid]))}_ <br> {cell(txt)}")
                else:
                    cells.append("_(not disclosed)_")
            body.append(f"| **{esc(o['topic'])}** | " + " | ".join(cells) + " |")
    else:
        body.append("_(none found)_")
    body.append("")

    for cid in card_ids:
        uniq = [u for u in disclosure.get("unique", []) if u["card_id"] == cid]
        body.append(f"### Only {labels.get(cid, cid)} discloses")
        body.append("")
        if uniq:
            body.append("| Topic | What it discloses | Why it's here |")
            body.append("|---|---|---|")
            for u in uniq:
                txt = kp(results.get(cid, {}).get("unique", {}).get(u["topic"], ""))
                topic_cell = f"**{esc(u['topic'])}**<br>_{esc(cite(cid, u['section']))}_"
                body.append(f"| {topic_cell} | {cell(txt)} | {esc(u['why'])} |")
        else:
            body.append("_(none found)_")
        body.append("")

    path.write_text("\n".join(body) + "\n", encoding="utf-8")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch safety-card analyzer: discover -> compare -> extract",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--mode", required=True,
                        choices=["discover", "compare", "review", "extract"])
    parser.add_argument("--url",  help="[discover] URL of the system card")
    parser.add_argument("--file", help="[discover] local file path")
    parser.add_argument("--id",   help="[discover] short card id (e.g. claude-3); "
                                       "defaults to the filename")
    parser.add_argument("--model", choices=SUPPORTED_MODELS, default=DEFAULT_MODEL,
                        help=f"Claude model (default: {DEFAULT_MODEL})")
    parser.add_argument("--force", action="store_true",
                        help="[discover] allow overwriting an existing discovery")
    parser.add_argument("--confirm", action="store_true",
                        help="[extract] required — confirms you reviewed the consolidated table")
    args = parser.parse_args()

    if args.mode == "discover":
        source = args.url or args.file
        if not source:
            sys.exit("discover mode needs --url or --file")
        card_id = args.id or default_card_id(source)
        run_discover(source, card_id, args.model, args.force)
    elif args.mode == "compare":
        run_compare(args.model)
    elif args.mode == "review":
        run_review()
    else:
        run_extract(args.model, args.confirm)


if __name__ == "__main__":
    main()
