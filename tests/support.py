"""Payloads the tests share: the same data across the protocol and the renderer suites.

Kept out of `conftest.py` so fixtures stay fixtures. A complete editorial block on purpose: what a
publishable figure carries, from which each test removes exactly the field it is about.
"""

META = {
    "title": "L'accès aux services varie de 2,3 à 8,1 minutes selon le type de commune",
    "unit": "en minutes",
    "lecture": "En 2025, les habitants des communes rurales dispersées mettent 8,1 minutes.",
    "champ": "France hors Mayotte, communes.",
    "source": "Insee, base permanente des équipements (BPE) 2025.",
}

BARS = {
    "rows": [
        {"label": "Grands centres urbains", "value": 2.3},
        {"label": "Petites villes", "value": 3.4},
        {"label": "Rural non périurbain – habitat dispersé", "value": 8.1},
    ],
    "meta": META,
    "decimals": 1,
    "value_suffix": "min",
}

LINE = {
    "series": [
        {
            "label": "Indice en euros",
            "points": [{"x": "2024-01", "y": 101.0}, {"x": "2024-02", "y": 103.5}, {"x": "2024-03", "y": 104.0}],
        }
    ],
    "meta": {
        "title": "Les prix en euros des matières premières importées augmentent",
        "unit": "indice base 100 en 2010",
        "source": "Insee, prix des matières premières importées, octobre 2026.",
    },
    "decimals": 0,
}

MAP = {
    "rows": [{"code": "75", "value": 20054.0}, {"code": "48", "value": 15.0}, {"code": "99", "value": 1.0}],
    "meta": {
        "title": "La densité de population va de 15 habitants au km² en Lozère à 20 054 à Paris",
        "unit": "nombre d'habitants au km²",
        "source": "Insee, recensement de la population 2022.",
        "champ": "France métropolitaine, départements.",
    },
    "classes": 5,
    "thresholds": [50, 75, 150, 300],
}
