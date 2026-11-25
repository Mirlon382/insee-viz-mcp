"""Build the three demo figures from real Insee data.

    python examples/make_demo.py

Writes examples/out/*.svg, *.png and a gallery.html to eyeball the result.
The data files quote their publication; no numbers are invented.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from insee_viz_mcp.charts import render_bars, render_line, render_map
from insee_viz_mcp.models.figures import BarRow, BarSpec, FigureMeta, LineSpec, MapRow, MapSpec, Point, Series

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

METRO = {
    str(f["properties"]["code"])
    for f in json.loads((ROOT.parent / "src/insee_viz_mcp/data/departements.geojson").read_text())["features"]
}


def raster(svg_path: Path) -> Path | None:
    png = svg_path.with_suffix(".png")
    converter = shutil.which("rsvg-convert")
    if converter:
        subprocess.run([converter, "-w", "1840", "-o", str(png), str(svg_path)], check=True)
        return png
    if shutil.which("magick"):
        subprocess.run(["magick", str(svg_path), "-density", "192", str(png)], check=True)
        return png
    return None


def build_map() -> Path:
    rows = [
        MapRow(**row)
        for row in json.loads((DATA / "densite_departements_2022.json").read_text())["rows"]
        if str(row["code"]) in METRO
    ]
    spec = MapSpec(
        rows=rows,
        level="departement",
        classes=5,
        thresholds=[50, 75, 150, 300],
        decimals=0,
        meta=FigureMeta(
            title="La densité de population va de 15 habitants au km² en Lozère à 20 054 à Paris",
            unit="nombre d'habitants au km²",
            lecture="En 2022, la densité de population est de 14,8 habitants par km² en Lozère, contre 20 054,1 à Paris.",
            champ="France métropolitaine, départements.",
            source="Insee, recensement de la population 2022.",
        ),
    )
    path = OUT / "carte-densite-population-2022.svg"
    path.write_text(render_map(spec), encoding="utf-8")
    return path


def build_bars() -> Path:
    rows = [BarRow(**row) for row in json.loads((DATA / "temps_acces_services.json").read_text())["rows"]]
    spec = BarSpec(
        rows=rows,
        sort="desc",
        highlight="Ensemble",
        decimals=1,
        value_suffix="min",
        meta=FigureMeta(
            title="L'accès aux services de la vie courante varie de 2,3 à 8,1 minutes selon le type de commune",
            unit="en minutes",
            lecture="En 2025, les habitants des communes rurales non périurbaines à habitat dispersé mettent en moyenne 8,1 minutes pour accéder aux services du panier de la vie courante, contre 2,3 minutes dans les grands centres urbains.",
            champ="France hors Mayotte, communes.",
            source="Insee, base permanente des équipements (BPE) 2025 ; recensement de la population 2022.",
        ),
    )
    path = OUT / "barres-temps-acces-services.svg"
    path.write_text(render_bars(spec), encoding="utf-8")
    return path


def build_line() -> Path:
    raw = json.loads((DATA / "matieres_premieres.json").read_text())
    series = [Series(label=s["label"], points=[Point(**p) for p in s["points"]]) for s in raw["series"]]
    spec = LineSpec(
        series=series,
        decimals=0,
        meta=FigureMeta(
            title="Les prix en euros des matières premières importées hors énergie augmentent de 62 % depuis 2013",
            unit="indice base 100 en 2010",
            lecture="En octobre 2026, l'indice de prix en euros des matières premières importées hors énergie atteint 170,4, contre 105,1 en janvier 2013.",
            champ="France, matières premières importées (ensemble, hors énergie).",
            source="Insee, prix des énergies et des matières premières importées, informations rapides n° 285, octobre 2026.",
        ),
    )
    path = OUT / "courbe-matieres-premieres.svg"
    path.write_text(render_line(spec), encoding="utf-8")
    return path


def gallery(svgs: list[Path], pngs: list[Path | None]) -> Path:
    cards = []
    for svg, png in zip(svgs, pngs, strict=False):
        cards.append(
            f'<section><div class="card">{svg.read_text(encoding="utf-8")}</div>'
            f'<p class="files">{svg.name} · <a href="{png.name if png else "#"}">PNG</a></p></section>'
        )
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Figures Insee — prototype MCP</title>
<style>
 body {{ margin:0; background:#F4F4F5; font-family:Inter,"Noto Sans",system-ui,sans-serif; color:#202021; }}
 header {{ padding:26px 34px 8px; }}
 h1 {{ font-size:17px; font-weight:600; margin:0 0 4px; }}
 p.lead {{ margin:0; color:#5D5D5E; font-size:13px; }}
 main {{ display:grid; gap:22px; padding:20px 34px 40px; }}
 section {{ background:#fff; border:1px solid #E4E4E4; border-radius:6px; padding:8px 8px 4px; box-shadow:0 1px 2px rgba(0,0,0,.04); }}
 .card svg {{ width:100%; height:auto; display:block; }}
 .files {{ margin:6px 4px 2px; font-size:11px; color:#5D5D5E; }}
 a {{ color:#194E9B; }}
</style></head><body>
<header><h1>Prototype « figures Insee » — MCP app</h1>
<p class="lead">Trois formes, un seul bloc éditorial : carte choroplèthe, barres classées, courbe. Rendu 100 % serveur, style fixé par le code.</p></header>
<main>{"".join(cards)}</main></body></html>"""
    path = OUT / "gallery.html"
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    svgs = [build_map(), build_bars(), build_line()]
    pngs = [raster(svg) for svg in svgs]
    for svg, png in zip(svgs, pngs, strict=False):
        print(f"{svg.name}  ->  {png.name if png else 'no rasteriser'}")
    print(gallery(svgs, pngs))
