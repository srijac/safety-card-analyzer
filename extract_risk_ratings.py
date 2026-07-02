"""
Extract structured frontier-risk ratings from a step-3 output, for the risk figure.

The cards state risk levels in prose (OpenAI: Low/Medium/High; Anthropic: ASL /
threshold language). This does ONE structured call over the already-extracted
frontier/safety text and writes a small ratings table:

  comparison/risk_ratings__<tag>.json

Usage:
  python extract_risk_ratings.py                 # uses the most recent step3_output
  python extract_risk_ratings.py --input p.json
"""

import argparse
import json
from pathlib import Path

import anthropic

BASE       = Path(__file__).parent
COMPARISON = BASE / "comparison"

RATINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ratings"],
    "properties": {
        "ratings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["card_id", "capability", "level", "severity", "note"],
                "properties": {
                    "card_id":    {"type": "string"},
                    "capability": {"type": "string"},
                    "level":      {"type": "string",
                                   "description": "Disclosed rating in the card's OWN words "
                                                  "(e.g. 'Low', 'Medium', 'ASL-2 (below ASL-3)', "
                                                  "'Not assessed')"},
                    "severity":   {"type": "integer",
                                   "description": "Normalized concern: 0=not assessed, 1=low, "
                                                  "2=medium, 3=high"},
                    "note":       {"type": "string", "description": "≤12-word basis for the rating"},
                },
            },
        }
    },
}


def latest_output() -> Path:
    files = sorted(COMPARISON.glob("step3_output__*.json"))
    if not files:
        raise SystemExit("No step3_output found. Run extract first.")
    return files[-1]


def detail(per_card, cid, dim_id):
    v = per_card.get(cid, {}).get("dims", {}).get(dim_id, "")
    return v.get("detail", "") if isinstance(v, dict) else (v or "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input")
    args = ap.parse_args()
    path = Path(args.input) if args.input else latest_output()
    data = json.loads(path.read_text(encoding="utf-8"))

    card_ids = data["card_ids"]
    labels   = data.get("card_labels", {})
    caps     = data.get("capabilities", ["CBRN", "Cybersecurity", "Persuasion", "Autonomy"])
    model    = data.get("model", "claude-opus-4-7")
    per_card = data.get("per_card", {})
    tag = "__vs__".join(card_ids) + f"__by__{model}"

    # Feed the model the already-extracted frontier + safety text per card.
    blocks = []
    for cid in card_ids:
        txt = detail(per_card, cid, "frontier_preparedness") + "\n" + detail(per_card, cid, "safety_measures")
        blocks.append(f"CARD {cid} ({labels.get(cid, cid)}):\n{txt.strip()}")

    client = anthropic.Anthropic()
    print(f"── RISK RATINGS  {tag}")
    resp = client.messages.create(
        model=model, max_tokens=2000,
        system=("You normalize frontier-risk disclosures. For EACH card and EACH capability, "
                "report the risk level the card actually assigned, IN THE CARD'S OWN SCALE, plus a "
                "normalized severity. If a capability was not assessed in that card, level='Not "
                "assessed' and severity=0. Do not invent ratings."),
        messages=[{"role": "user", "content": [{"type": "text", "text":
            f"Capabilities to rate (exactly these): {', '.join(caps)}.\n"
            f"Cards: {', '.join(card_ids)}.\n\n" + "\n\n".join(blocks)}]}],
        output_config={"format": {"type": "json_schema", "schema": RATINGS_SCHEMA}},
    )
    ratings = json.loads(next(b.text for b in resp.content if b.type == "text"))["ratings"]

    out = {"card_ids": card_ids, "card_labels": labels, "capabilities": caps,
           "model": model, "ratings": ratings}
    out_path = COMPARISON / f"risk_ratings__{tag}.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   {len(ratings)} rating(s) -> {out_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()
