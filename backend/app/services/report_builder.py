# -*- coding: utf-8 -*-
"""Report builder: assembles PNG charts + PDF report with provenance footnotes."""
import os, re, json, traceback
from datetime import datetime, timezone
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from .. import config
from ..db import ReportJob, session
from . import scoring, resources
from .forecast import holdout_predictions, mine_names, ops
from .registry import registry


def _chart_scores(path: str):
    df = scoring._load()
    fig, ax = plt.subplots(figsize=(7, 8))
    sc = ax.scatter(df.lon, df.lat, c=df.prob_v3, s=2.5, cmap="viridis",
                    vmin=0, vmax=max(0.05, df.prob_v3.quantile(0.99)))
    collars = json.load(open(config.COLLARS, encoding="utf-8"))
    bx = [f["geometry"]["coordinates"][0] for f in collars["features"]]
    by = [f["geometry"]["coordinates"][1] for f in collars["features"]]
    ax.scatter(bx, by, c="red", s=14, marker="^", label="NGDR borehole collars")
    ax.legend(loc="upper right", fontsize=8)
    fig.colorbar(sc, ax=ax, label="P(manganese)")
    ax.set_title("Prospectivity v3 — grid scores + borehole collars")
    ax.set_xlabel("lon"); ax.set_ylabel("lat")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def _chart_shortfall(path: str):
    pred = pd.DataFrame(holdout_predictions())
    pred = pred.sort_values(["mine", "month"])
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.scatter(pred.actual_shortfall_tonnes, pred.pred_shortfall_tonnes, s=28, alpha=0.8)
    lim = max(pred.actual_shortfall_tonnes.max(), pred.pred_shortfall_tonnes.max()) * 1.05
    ax.plot([0, lim], [0, lim], "k--", lw=1)
    ax.set_xlabel("Actual shortfall (t)"); ax.set_ylabel("Predicted shortfall (t)")
    ax.set_title("Shortfall holdout (2025-08..12) — predicted vs actual")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def _chart_grades(path: str):
    a = pd.read_csv(config.ASSAYS)
    a = a[a.mn_pct.notna()]
    blocks = a.block.unique().tolist()
    fig, ax = plt.subplots(figsize=(8, 4))
    data = [a[a.block == b].mn_pct for b in blocks]
    ax.hist(data, bins=24, label=blocks, stacked=False, alpha=0.65)
    ax.axvline(15, color="r", ls="--", lw=1, label="ore cutoff 15% Mn")
    ax.set_xlabel("Mn %"); ax.set_ylabel("samples"); ax.legend()
    ax.set_title("Assay Mn grades — NGDR core samples (real)")
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def _render_html(scope: str, charts: dict) -> str:
    vol = resources.volume_summary()
    grade = resources.grade_summary()
    models = registry().status()
    prov = config.PROVENANCE
    block_rows = "".join(
        f"<tr><td>{b['block']}</td><td>{b['tonnage_t']:,.0f} t</td>"
        f"<td>{b['volume_m3']:,.0f} m³</td><td>{b['avg_mn_pct']} % Mn</td>"
        f"<td>{b['avg_sg']}</td><td>{b['category']}</td></tr>"
        for b in vol["blocks"])
    grade_rows = "".join(
        f"<tr><td>{k}</td><td>{v['ore_samples']}</td><td>{v['ore_mean_mn_pct']} %</td>"
        f"<td>{v['mean_fe_pct']} %</td><td>{v['mean_p_pct']} %</td></tr>"
        for k, v in grade["blocks"].items())
    return f"""<html><head><meta charset="utf-8"><style>
      body{{font-family:Segoe UI,Arial; margin:34px; color:#222}}
      h1{{color:#0b3d2e}} h2{{border-bottom:2px solid #0b3d2e; padding-bottom:4px}}
      table{{border-collapse:collapse; width:100%}} td,th{{border:1px solid #bbb; padding:6px 8px; font-size:13px}}
      th{{background:#e8f2ec; text-align:left}} .note{{font-size:11px; color:#555}}
      img{{max-width:100%; border:1px solid #ddd; margin:8px 0}}
    </style></head><body>
    <h1>MOIL Manganese Intelligence — Exploration & Operations Report</h1>
    <p>Scope: {scope} · Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC</p>

    <h2>1. Prospectivity (model v3)</h2>
    <img src="{charts['scores']}" />
    <p class="note">Ensemble XGB+RF+HistGB; spatial LOGO ROC 0.997 / PR 0.998.
    Provenance: {prov['grid_scores']}</p>

    <h2>2. Volume &amp; area (GSI resource estimates — real)</h2>
    <table><tr><th>Block</th><th>Tonnage</th><th>Volume</th><th>Avg Mn</th><th>SG</th><th>Category</th></tr>
    {block_rows}</table>
    <p class="note">{vol['note']}</p>

    <h2>3. Ore grade (core assays — real)</h2>
    <img src="{charts['grades']}" />
    <table><tr><th>Block</th><th>Ore samples</th><th>Mean Mn</th><th>Mean Fe</th><th>Mean P</th></tr>
    {grade_rows}</table>

    <h2>4. Shortfall prediction (holdout)</h2>
    <img src="{charts['shortfall']}" />
    <p class="note">ExtraTrees forecaster; holdout MAE ≈ 736 t/month, R² 0.66.
    Provenance: {prov['shortfall']}</p>

    <h2>5. Model registry</h2>
    <table><tr><th>Model</th><th>Artifact</th><th>Loaded</th></tr>
    {''.join(f"<tr><td>{k}</td><td>{v['artifact']}</td><td>{v['loaded']}</td></tr>" for k, v in models.items())}</table>

    <h2>6. Provenance &amp; limitations</h2>
    <ul class="note">
      <li>Production/shortfall mine-monthly data: SYNTHETIC-CALIBRATED (real annual MOIL anchors + real rainfall). No public mine-monthly source exists.</li>
      <li>Corrective actions: rule-based playbook (no action-outcome training data available).</li>
      <li>Volume/grade claims scoped to the two explored NGDR blocks (Gudma CRO-23394-2017, W. Ukwa CRO-23290-2016).</li>
    </ul>
    </body></html>"""


def generate_report(scope: str = "full", job_id: int | None = None) -> str:
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(config.REPORTS_DIR, f"report_{stamp}")
    charts = {}
    try:
        for key, fn in (("scores", _chart_scores), ("shortfall", _chart_shortfall),
                        ("grades", _chart_grades)):
            p = f"{base}_{key}.png"
            fn(p)
            charts[key] = p
        html = _render_html(scope, charts)
        html_path = f"{base}.html"
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        pdf_path = f"{base}.pdf"
        try:
            from weasyprint import HTML
            HTML(string=html, base_url=config.REPORTS_DIR).write_pdf(pdf_path)
            final = pdf_path
        except Exception:
            final = html_path  # graceful fallback: deliver the HTML
        if job_id:
            with session() as s:
                job = s.get(ReportJob, job_id)
                if job:
                    job.status, job.file_path = "done", final
                    s.commit()
        return final
    except Exception as e:
        if job_id:
            with session() as s:
                job = s.get(ReportJob, job_id)
                if job:
                    job.status, job.error = "error", f"{e}\n{traceback.format_exc()}"
                    s.commit()
        raise
