"""The routing tool: profile the columns, get the one Insee form that fits.

The router is deliberately pure and synchronous: it reads the *shape* of the dataset, never its
values, so the same columns always produce the same figure choice. It renders nothing -- that is
the point, and it is what stops a model from picking a chart type by taste.
"""

from ...models.routing import ColumnProfile

EDITORIAL_CONTRACT = (
    "\n\nChamps éditoriaux (obligatoires) : `meta.title` (phrase qui énonce le résultat, sans point final), "
    "`meta.source` (producteur + opération + millésime), `meta.unit` ('en %', 'en minutes'…). "
    "Recommandés : `meta.lecture` (une phrase avec une valeur), `meta.champ` (périmètre)."
)


def recommend_chart(columns: list[ColumnProfile], row_count: int, goal: str | None = None) -> str:
    """Choose the Insee figure form for a dataset before rendering it.

    Call this first with one entry per column. It returns the figure type, the
    tool to call, the parameter contract and the pitfalls, so the same data is
    always shown the same way.

    Args:
        columns: Profile of each column (name + role + optional cardinality/example).
        row_count: Number of rows in the dataset.
        goal: Optional sentence about what the figure must show.
    """
    geo_cols = [c for c in columns if c.kind == "geography"]
    date_cols = [c for c in columns if c.kind == "date"]
    cat_cols = [c for c in columns if c.kind == "category"]
    num_cols = [c for c in columns if c.kind == "numeric"]

    header = f"**{row_count} ligne(s)** — objectif : {goal}" if goal else f"**{row_count} ligne(s)**"

    if row_count <= 1:
        return f"{header}\n\n**Aucune figure.** Une seule observation se dit dans une phrase, pas dans un graphique."

    if geo_cols:
        return _map_advice(header, geo_cols[0])
    if date_cols and num_cols:
        return _line_advice(header, date_cols[0], num_cols[0])
    if cat_cols and num_cols:
        return _bars_advice(header, cat_cols[0], num_cols[0], goal)
    if len(num_cols) >= 2:
        return (
            f"{header}\n\n**Hors périmètre.** Deux variables numériques appellent un nuage de points, que ce prototype ne produit pas. "
            "Renvoyer un tableau trié, ou demander une agrégation (moyenne par catégorie) pour passer en barres."
        )
    return (
        f"{header}\n\n**Aucune figure adaptée.** Les colonnes décrivent du texte ou des catégories sans mesure numérique. "
        "Compter les occurrences pour obtenir un indicateur, puis rappeler `recommend_chart` (barres)."
    )


def _map_advice(header: str, geo: ColumnProfile) -> str:
    return (
        f"{header}\n\n**Figure : carte choroplèthe** → `render_map` (level='{_geo_level(geo)}')\n\n"
        f"Pourquoi : la colonne `{geo.name}` porte un code géographique officiel. Insee montre ce type de données par carte, "
        "pas par barres ni par courbe, et la carte se lit en taux, densité, part ou évolution — jamais en effectif brut.\n\n"
        "Contrat : `rows=[{code, value, name?}]` (codes officiels : '75', '2A', '971' ; value=null → gris « non disponible »), "
        "`classes=5`, `method='quantile'`.\n"
        "Contrôles : une valeur par territoire, même millésime, unité normalisée (hab./km², %, euros par habitant)."
        + EDITORIAL_CONTRACT
    )


REGION_CODES = {"11", "24", "27", "28", "32", "44", "52", "53", "75", "76", "84", "93", "94"}


def _geo_level(geo: ColumnProfile) -> str:
    """Guess the level from one example code; the caller can still override `level`."""
    example = (geo.example or "").strip()
    looks_regional = geo.name.lower().startswith("reg") and example in REGION_CODES
    return "region" if looks_regional else "departement"


def _line_advice(header: str, date: ColumnProfile, numeric: ColumnProfile) -> str:
    return (
        f"{header}\n\n**Figure : courbe** → `render_line`\n\n"
        f"Pourquoi : la colonne `{date.name}` est temporelle et `{numeric.name}` est l'indicateur. "
        "Une série temporelle se lit en courbe ; l'ordre chronologique est la structure, pas le classement.\n\n"
        "Contrat : `series=[{label, points=[{x: '2023-01'|'2023'|'2023-T1', y}]}]` (1 à 4 séries), `y_zero=true` si l'unité est un niveau "
        "(effectif, euros) et non un indice.\n"
        "Contrôles : périodes ISO, pas de trous silencieux (laisser le point absent plutôt qu'inventer), unité unique."
        + EDITORIAL_CONTRACT
    )


def _bars_advice(header: str, category: ColumnProfile, numeric: ColumnProfile, goal: str | None) -> str:
    extra = ""
    if goal and _asks_for_pie(goal):
        extra += (
            "\n\n**Pas de camembert** : Insee n'en publie pas. Des barres classées montrent les mêmes parts "
            "et se comparent exactement ; garder le cercle uniquement si le client l'exige explicitement.\n"
        )
    distinct = category.distinct or 0
    if distinct > 14:
        extra += (
            f"\n\n**Attention** : {distinct} catégories. Regrouper les plus petites dans « Autres » pour rester ≤ 14 barres ; "
            "sinon la figure devient un tableau."
        )
    return (
        f"{header}\n\n**Figure : barres horizontales classées** → `render_bars` (orientation='horizontal')\n\n"
        f"Pourquoi : `{category.name}` est une variable catégorielle et `{numeric.name}` un indicateur. Insee classe les barres par valeur décroissante "
        "et imprime la valeur au bout de chaque barre.\n\n"
        "Contrat : `rows=[{label, value}]`, `sort='desc'`, `highlight` éventuel pour la catégorie à commenter, "
        "`value_suffix` ('%', 'euros') si l'unité tient au bout de la barre. "
        "`orientation='vertical'` seulement pour des libellés courts et ordonnés (tranches d'âge, mois).\n"
        "Contrôles : une seule série (au-delà, `series` sur les lignes pour 2-3 séries groupées), barres partant de zéro."
        + extra
        + EDITORIAL_CONTRACT
    )


def _asks_for_pie(goal: str) -> bool:
    lowered = goal.lower()
    return any(word in lowered for word in ("camembert", "donut", "secteur", "circulaire", "pie"))
