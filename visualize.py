"""
Build portfolio figures from a step-3 comparison output.

Reads comparison/step3_output__*.json (the structured extraction result) and
writes interactive Plotly figures (+ PNG fallbacks) into docs/figures/ so they
can be embedded in the GitHub Pages project page.

Usage:
  python visualize.py                       # uses the most recent step3_output
  python visualize.py --input path.json
"""

import argparse
import json
from pathlib import Path

import plotly.graph_objects as go

BASE        = Path(__file__).parent
COMPARISON  = BASE / "comparison"
FIG_DIR     = BASE / "docs" / "figures"   # interactive HTML + web-sized PNG (for the site)
OUTPUT_DIR  = BASE / "output"             # high-res PNG + vector SVG (for the portfolio)

# Brand-ish colors, colorblind-safe enough for two series.
COLORS = ["#4C6EF5", "#12B886"]   # card A, card B
SHARED = "#868E96"


def latest_output() -> Path:
    files = sorted(COMPARISON.glob("step3_output__*.json"))
    if not files:
        raise SystemExit("No comparison/step3_output__*.json found. Run extract first.")
    return files[-1]


def save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    h = fig.layout.height or 600
    # Interactive standalone HTML (CDN plotly.js) — embeds via <iframe> anywhere.
    fig.write_html(FIG_DIR / f"{name}.html", include_plotlyjs="cdn", full_html=True)
    # Web-sized PNG for the site / README.
    fig.write_image(FIG_DIR / f"{name}.png", width=900, height=h, scale=2)
    # High-res portfolio exports: crisp PNG (scale ×3) + vector SVG (perfect at any size).
    fig.write_image(OUTPUT_DIR / f"{name}.png", width=1400, height=h, scale=3)
    fig.write_image(OUTPUT_DIR / f"{name}.svg", width=1400, height=h)
    print(f"   wrote docs/figures/{name}.html+.png  and  output/{name}.png+.svg")


def fig_disclosure_breadth(labels, only_a, both, only_b, a, b) -> go.Figure:
    """Headline: how many topics each card discloses uniquely vs. shared."""
    cats = [f"Only {labels[a]}", "Both cards", f"Only {labels[b]}"]
    fig = go.Figure(go.Bar(
        x=cats, y=[only_a, both, only_b],
        marker_color=[COLORS[0], SHARED, COLORS[1]],
        text=[only_a, both, only_b], textposition="outside",
    ))
    fig.update_layout(
        title="Disclosure breadth: unique vs. shared topics",
        yaxis_title="Number of disclosed topics",
        template="plotly_white", showlegend=False,
        margin=dict(t=60, l=60, r=30, b=40),
    )
    return fig


def latest_ratings():
    files = sorted(COMPARISON.glob("risk_ratings__*.json"))
    return files[-1] if files else None


def fig_risk_ratings(data) -> go.Figure:
    """Frontier risk rating per capability, per lab (each card's own scale)."""
    card_ids = data["card_ids"]
    labels   = data.get("card_labels", {})
    caps     = data.get("capabilities", ["CBRN", "Cybersecurity", "Persuasion", "Autonomy"])
    cols     = [labels.get(c, c) for c in card_ids]
    idx      = {(r["card_id"], r["capability"]): r for r in data["ratings"]}

    z, text = [], []
    for cap in caps:
        zr, tr = [], []
        for cid in card_ids:
            r = idx.get((cid, cap))
            zr.append(r["severity"] if r else 0)
            tr.append(r["level"] if r else "—")
        z.append(zr); text.append(tr)

    # Discrete bands: 0 grey (not assessed), 1 green (low), 2 amber (med), 3 red (high).
    fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=caps, text=text, texttemplate="%{text}",
        zmin=0, zmax=3, showscale=False, xgap=4, ygap=4,
        colorscale=[[0.0, "#E9ECEF"], [0.167, "#E9ECEF"],
                    [0.167, "#40C057"], [0.5, "#40C057"],
                    [0.5, "#FAB005"], [0.833, "#FAB005"],
                    [0.833, "#FA5252"], [1.0, "#FA5252"]],
        hovertemplate="%{y} — %{x}<br>%{text}<extra></extra>",
    ))
    fig.update_layout(
        title="Frontier risk ratings by capability<br>"
              "<sup>Each lab's own scale (Anthropic ASL vs OpenAI Low/Med/High); "
              "grey = not assessed</sup>",
        template="plotly_white", height=430,
        margin=dict(t=90, l=110, r=30, b=40),
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def fig_disclosure_matrix(topics, present, labels, a, b) -> go.Figure:
    """Which card discloses each topic (green = disclosed)."""
    fig = go.Figure(go.Heatmap(
        z=present, x=[labels[a], labels[b]], y=topics,
        colorscale=[[0, "#F1F3F5"], [1, "#12B886"]],
        showscale=False, xgap=3, ygap=3,
        hovertemplate="%{y}<br>%{x}: %{customdata}<extra></extra>",
        customdata=[["disclosed" if v else "—" for v in row] for row in present],
    ))
    fig.update_layout(
        title="Who discloses what (topic × card)",
        template="plotly_white",
        height=max(500, 22 * len(topics)),
        margin=dict(t=60, l=280, r=30, b=40),
    )
    fig.update_yaxes(autorange="reversed")
    return fig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="path to a step3_output__*.json")
    args = ap.parse_args()

    path = Path(args.input) if args.input else latest_output()
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"── VISUALIZE  {path.name}")

    a, b = data["card_ids"][0], data["card_ids"][1]
    labels = data.get("card_labels", {a: a, b: b})
    disc = data.get("disclosure", {})
    overlaps = disc.get("overlaps", [])
    unique = disc.get("unique", [])

    uniq_a = [u for u in unique if u["card_id"] == a]
    uniq_b = [u for u in unique if u["card_id"] == b]

    save(fig_disclosure_breadth(labels, len(uniq_a), len(overlaps), len(uniq_b), a, b),
         "disclosure_breadth")

    # Matrix: unique-A topics, then shared, then unique-B topics.
    topics, present = [], []
    for u in uniq_a:
        topics.append(u["topic"]); present.append([1, 0])
    for o in overlaps:
        topics.append(o["topic"]); present.append([1, 1])
    for u in uniq_b:
        topics.append(u["topic"]); present.append([0, 1])
    save(fig_disclosure_matrix(topics, present, labels, a, b), "disclosure_matrix")

    rp = latest_ratings()
    if rp:
        save(fig_risk_ratings(json.loads(rp.read_text(encoding="utf-8"))), "risk_ratings")
    else:
        print("   (no risk_ratings__*.json — run extract_risk_ratings.py for the risk figure)")

    print("   done.")


if __name__ == "__main__":
    main()
