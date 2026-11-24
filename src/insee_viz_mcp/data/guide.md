# Choisir la bonne figure

Trois formes seulement, comme dans les publications Insee. La forme découle de
la structure des données, jamais du goût.

| Ce que contiennent les données | Figure | Outil |
|---|---|---|
| Un indicateur + un code géographique (département, région) | Carte choroplèthe | `render_map` |
| Un indicateur + une variable catégorielle (secteur, tranche, type de commune) | Barres horizontales classées | `render_bars` |
| Un indicateur + une date/période | Courbe | `render_line` |

## Règles de décision

1. **Géographie d'abord.** Dès qu'une colonne porte un code officiel (01, 2A, 75,
   11…), c'est une carte. Ne jamais cartographier un effectif brut sans le
   rapporter à une population, une surface ou un total : une carte compare des
   taux, des densités, des parts ou des évolutions.
2. **Temps ensuite.** Une colonne de dates ou de périodes ordonnées → courbe.
   Une seule date → pas de courbe, un tableau.
3. **Catégories enfin.** Barres horizontales, triées par valeur décroissante,
   valeur imprimée au bout. Au-delà de 14 catégories : regrouper les plus
   petites dans « Autres ».
4. **Deux variables numériques** → nuage de points, hors périmètre de ce
   prototype : renvoyer un tableau.
5. **Une seule valeur** → pas de figure. Un chiffre se dit dans une phrase.

## Interdits

- Camembert, donut, 3D, ombres, dégradés décoratifs.
- Axe tronqué sur des barres (les barres partent toujours de zéro).
- Plus de 4 courbes, plus de 3 séries groupées.
- Titre label (« Graphique 1 ») au lieu d'une phrase qui énonce le résultat.

## Bloc éditorial obligatoire

Toute figure Insee porte, sous le graphique, dans cet ordre :

- **Lecture** : une phrase factuelle avec une valeur (« En 2025, les habitants
  des communes à habitat dispersé mettent en moyenne 8,1 minutes… »).
- **Champ** : périmètre géographique et population (« France hors Mayotte,
  communes. »).
- **Source** : producteur + opération + millésime (« Insee, base permanente des
  équipements (BPE) 2025. »).

Le titre énonce le résultat, pas la variable. L'unité est affichée sous le
titre (« en % », « en minutes », « indice base 100 en 2010 »).

## Nombre et typographie

- Séparateur de milliers : espace fine insécable (`1 813 800`).
- Virgule décimale (`45,8`), pas de point.
- Pas de zéro inutile (`40`, pas `40,0`) sur les axes.

## Workflow

1. `recommend_chart` avec le profil des colonnes → type + outil.
2. Appeler l'outil de rendu nommé, avec `meta.title`, `meta.source`,
   `meta.unit` remplis, et si possible `meta.lecture` / `meta.champ`.
3. Répondre avec la figure et son bloc Lecture / Champ / Source. Ne jamais
   citer un chiffre absent des données.
