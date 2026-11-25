"""The ready-made prompt: describe the data, get the same three-step workflow every time.

A host that does not surface prompts loses nothing: `recommend_chart` and the tool descriptions
carry the same instructions, and the MCP App viewer needs no prompt at all.
"""

from typing import Annotated

from pydantic import Field

Donnees = Annotated[
    str,
    Field(
        description="Description of the dataset: columns, their roles, the period and the geographic field.",
        examples=["code_departement, densite (habitants au km²), recensement 2022"],
        min_length=1,
    ),
]

Objectif = Annotated[
    str,
    Field(
        default="",
        description="What the figure must show, in one sentence. Empty means 'describe the structure'.",
        examples=["comparer les départements les plus denses"],
    ),
]


def figure_insee(donnees: Donnees, objectif: Objectif = "") -> str:
    """Ask for an Insee figure from a data description."""
    return (
        "Tu produis une figure au standard Insee à partir des données suivantes.\n\n"
        f"Données : {donnees}\n"
        f"Objectif : {objectif or 'décrire la structure des données'}\n\n"
        "1. Appelle `recommend_chart` avec le profil des colonnes.\n"
        "2. Appelle l'outil de rendu indiqué, en remplissant `meta.title` (une phrase qui énonce le résultat), "
        "`meta.source`, `meta.unit`, puis `meta.lecture` et `meta.champ`.\n"
        "3. Réponds avec la figure et son bloc Lecture / Champ / Source. Ne cite que les valeurs présentes dans les données."
    )
