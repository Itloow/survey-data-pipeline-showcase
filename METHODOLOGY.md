# Méthodologie

Ce document décrit les choix techniques du projet : structure des données, nettoyage, stratégie d'imputation, fusion des sources et conventions de visualisation. Il ne présente **aucun résultat** : les données d'origine sont confidentielles et le dépôt fonctionne sur des données synthétiques (voir [README](README.md)).

## Sommaire

1. [Objectif et périmètre](#1-objectif-et-périmètre)
2. [Sources de données et schéma](#2-sources-de-données-et-schéma)
3. [Architecture du pipeline](#3-architecture-du-pipeline)
4. [Nettoyage et imputation de la base d'enquête (N1)](#4-nettoyage-et-imputation-de-la-base-denquête-n1)
5. [Nettoyage du questionnaire (N2)](#5-nettoyage-du-questionnaire-n2)
6. [Fusion des sources et contrôle qualité (N4, N5)](#6-fusion-des-sources-et-contrôle-qualité-n4-n5)
7. [Analyse descriptive et choix de visualisation (N0, N3, N6)](#7-analyse-descriptive-et-choix-de-visualisation-n0-n3-n6)
8. [Reproductibilité](#8-reproductibilité)
9. [Limites et pistes d'amélioration](#9-limites-et-pistes-damélioration)

---

## 1. Objectif et périmètre

L'objectif est de construire une base analytique unique à partir de deux sources hétérogènes, puis de produire des analyses descriptives univariées et bivariées autour d'une variable cible binaire, `intention_to_migrate_legal`.

| Source | Nature | Volume relatif |
|---|---|---|
| Base d'enquête | Fichier Excel fourni dans le cadre du projet, variables déjà codées | Grand échantillon |
| Questionnaire | Enquête conçue et diffusée par nos soins, export d'une plateforme de sondage | Échantillon restreint |

Les deux sources partagent un socle de variables (profil socio-démographique, confiance institutionnelle, intentions migratoires) ; le questionnaire ajoute des variables économiques et personnelles absentes de la base d'enquête.

Les difficultés techniques traitées :

- des **taux de valeurs manquantes très variables** selon les colonnes, de quelques dixièmes de pourcent à plus de la moitié des valeurs ;
- deux **schémas différents** (noms de colonnes, encodages, nomenclature des pays) à réconcilier ;
- après fusion, des colonnes **presque entièrement vides** pour les lignes de la base d'enquête.

## 2. Sources de données et schéma

Les noms de colonnes sont conservés tels qu'ils figurent dans les fichiers sources, fautes de frappe comprises (`GeneralizedTrsut`, `Trust_Regiol_Governement`, `COUNRY_ID`), pour garder la traçabilité avec le dictionnaire de codes d'origine. Seuls les espaces parasites qui gênent l'accès aux colonnes sont corrigés (N1), ainsi que `COUNRY_ID`, qui doit s'aligner sur `COUNTRY_ID` pour la fusion (N4).

### 2.1 Base d'enquête — `Immigration.xlsx` (21 colonnes)

| Colonne | Type brut | Encodage | Rôle |
|---|---|---|---|
| `COUNTRY_ID` | int | code pays (nomenclature de 1 à 22) | clé pays |
| `Country` | str | libellé pays, anglais, majuscules | clé pays |
| `ID` | int | `COUNTRY_ID × 10000 + rang` | technique, supprimé en N4 |
| `DATE` | int | date de collecte (numéro de série Excel) | technique, supprimé en N4 |
| `Bankaccount` | int | 0/1 | inclusion financière |
| `Remit` | int | 0/1 | envois de fonds |
| `Regionf` | int | 1 urbain · 2 rural · 3 camp | profil |
| `Educationf` | float | 1 (aucune) → 7 (master/doctorat), ordinal | profil |
| `Genderf` | int | 0/1 | profil |
| `Social statusf` | float | 1 à 7 (célibataire, en couple, fiancé·e, marié·e, divorcé·e, séparé·e, veuf·ve) | profil |
| `Age` | float | années | profil |
| `Professional situationf` | float | 1 à 7 (salarié·e, indépendant·e, retraité·e, au foyer, étudiant·e, demandeur·se d'emploi, autre) | profil |
| `Corruption ` | float | échelle ordinale | opinion |
| `Corruption (0  1)` | float | 0/1, binarisation de `Corruption ` | opinion |
| `GeneralizedTrsut` | float | 0/1 | confiance interpersonnelle |
| `TrustCourts`, `TrustLocalGovernement`, `Trust_Parliament`, `Trust_Regiol_Governement ` | float | 0/1 | confiance institutionnelle |
| `intention_to_migrate_legal` | float | 0/1 | **variable cible** |
| `intention_to_migrate_illegal` | float | 0/1 | variable d'intérêt |

Les colonnes `float` le sont uniquement parce qu'elles contiennent des `NaN` : leurs valeurs sont des codes entiers.

### 2.2 Questionnaire — `base_questionnaire.csv` (49 colonnes)

L'export de la plateforme de sondage contient 5 colonnes de métadonnées (identifiant de réponse, date de soumission, dernière page vue, langue, graine), 42 questions et 2 champs de texte libre « Veuillez préciser : ». Ces deux champs portant le même intitulé, pandas renomme le second en `Veuillez préciser :.1` à la lecture.

Le questionnaire est organisé en pages. Un répondant qui abandonne laisse toutes les questions suivantes vides, et certaines questions ne sont affichées que sous condition (fréquence des virements si `Remit = 1`, relations avec les proches si `Proches_europe = 1`, montant et fréquence des envois si `Intention_envoyer_argent = 1`). Le taux de manquants augmente donc page après page.

Un second export, `base_questionnaire_brute.csv`, contient les **libellés** des réponses au lieu des codes. Il ne sert qu'à récupérer le libellé du pays d'origine.

Après renommage (N2), les 42 questions prennent les noms suivants :

| Thème | Variables | Encodage |
|---|---|---|
| Profil | `Age`, `Genderf` (M/F → 1/0), `COUNRY_ID`, `Regionf` (1/2), `Educationf`, `Social statusf`, `Professional situationf` | mêmes codes que la base d'enquête |
| Ménage | `Taille_menage` | 1 à 5, la modalité 5 signifiant « 5 et plus » |
| | `Decideur_financier` | 0/1 |
| | `Revenu` | 1 à 5 = tranches croissantes de revenu mensuel ; **6 = refus de répondre** |
| | `Source_revenu_agriculture`, `_commerce`, `_salariat`, `_aide_familiale`, `_transferts`, `_autre` | 0/1 (question à choix multiples éclatée en indicatrices) |
| Finances | `Bankaccount`, `Remit`, `Choc_economique`, `Acces_credit` | 0/1 |
| | `Frequence_virements` | ordinal (question filtrée) |
| Confiance | `Corruption (0  1)`, `GeneralizedTrsut`, `TrustCourts`, `TrustLocalGovernement`, `Trust_Parliament`, `Trust_Regiol_Governement` | 0/1 |
| Projet migratoire | `intention_to_migrate_legal`, `intention_to_migrate_illegal`, `Pays_etape`, `Nationalite_francaise`, `Mariage_blanc`, `Retour_pays`, `Proches_europe`, `Intention_envoyer_argent` | 0/1 |
| | `Proche_fratrie`, `Proche_parent`, `Proche_ami`, `Proche_autre` | 0/1 (question filtrée) |
| | `Raisons_migration` | nominal |
| | `Montant_envois`, `Frequence_envois` | ordinal (questions filtrées) |

Les pays absents de la nomenclature de la base d'enquête reçoivent de la plateforme un code hors plage (format `99xxx`).

### 2.3 Base fusionnée (44 colonnes)

La base fusionnée contient 44 colonnes : les 17 colonnes communes (dont `Country`, seule colonne texte), `COUNTRY_ID`, `Corruption` (propre à la base d'enquête) et les 25 colonnes propres au questionnaire. `ID` et `DATE` sont supprimées avant la concaténation ; toutes les autres colonnes sont des entiers.

## 3. Architecture du pipeline

| Notebook | Rôle | Entrée | Sortie |
|---|---|---|---|
| **N1** | Nettoyage et imputation de la base d'enquête | `1_Donnees_brutes/Immigration.xlsx` | `2_Donnees_nettoyees/immigration_nettoyee.xlsx` |
| **N0** | Analyse descriptive de la base d'enquête | sortie de N1 | figures |
| **N2** | Nettoyage et imputation du questionnaire | `1_Donnees_brutes/base_questionnaire*.csv` | `2_Donnees_nettoyees/base_questionnaire_nettoyee.xlsx` |
| **N3** | Analyse descriptive du questionnaire | sortie de N2 | figures |
| **N4** | Fusion des deux sources et imputation Monte Carlo | sorties de N1 et N2 | `3_Donnees_fusionnees/base_concatenee_finale.xlsx` |
| **N5** | Contrôle qualité et typage de la base fusionnée | sortie de N4 | `2_Donnees_nettoyees/base_fusionnee_nettoyee.xlsx` |
| **N6** | Analyse descriptive d'un sous-échantillon géographique | sortie de N5 | figures |

Ordre d'exécution : **N1 → N0 → N2 → N3 → N4 → N5 → N6**. Chaque étape écrit un fichier intermédiaire : une étape peut être relancée seule, et chaque transformation peut être inspectée.

## 4. Nettoyage et imputation de la base d'enquête (N1)

### 4.1 Préparation

- **Chaînes vides → `NaN`** (`replace("", np.nan)`), pour que toutes les absences de réponse soient reconnues comme valeurs manquantes.
- **Typage** : les variables qualitatives codées en entiers passent en `category`. `Age` reste numérique.
- **Doublons** : contrôle sur `ID` uniquement. La suppression des lignes identiques sur toutes les colonnes a été écartée : avec des variables codées sur peu de modalités, deux répondants distincts peuvent légitimement avoir le même profil.
- **Noms de colonnes** : suppression des espaces finaux (`'Corruption '`, `'Trust_Regiol_Governement '`).

### 4.2 Stratégie d'imputation selon le taux de manquants

La méthode d'imputation dépend du taux de manquants de chaque colonne : plus la part de valeurs à reconstruire est grande, plus la méthode doit exploiter l'information des autres variables.

| Taux de manquants | Colonnes | Méthode | Justification |
|---|---|---|---|
| < 2 % | `Educationf`, `Social statusf`, `Professional situationf`, `intention_to_migrate_legal` | Mode | Remplacer moins de 2 % des valeurs a un effet négligeable sur la distribution ; une méthode plus coûteuse n'apporte rien. |
| < 2 % | `Age` | Médiane | Variable quantitative asymétrique : la médiane est robuste aux valeurs extrêmes. |
| 10 – 20 % | `TrustCourts`, `TrustLocalGovernement`, `Trust_Parliament`, `Corruption`, `Corruption (0  1)` | `KNNImputer` | La part à reconstruire n'est plus négligeable ; les répondants au profil proche ont des réponses proches. |
| ≥ 50 % | `GeneralizedTrsut`, `Trust_Regiol_Governement`, `intention_to_migrate_illegal` | `IterativeImputer` + `RandomForestRegressor` | Trop de manquants pour un voisinage fiable : on modélise chaque colonne à partir de toutes les autres. |

### 4.3 KNN (10 – 20 %)

- Distance `nan_euclidean`, calculée sur les variables renseignées de chaque paire de lignes.
- `n_neighbors=11` : un voisinage large lisse l'effet d'observations atypiques.
- `weights="distance"` : les voisins proches pèsent davantage, d'où l'intérêt d'un *k* élevé pour compenser ; *k* impair pour limiter les égalités sur les variables binaires.
- Exclusions du calcul : `Country` (texte) et les trois colonnes à ≥ 50 % de manquants, qui dégraderaient les distances.
- Les moyennes pondérées produites par le KNN sont arrondies (`round().astype(int)`) pour retrouver des codes valides. Seules les colonnes ciblées sont réinjectées.

### 4.4 Imputation itérative par forêts aléatoires (≥ 50 %)

- `IterativeImputer` (approche de type MICE) : chaque colonne incomplète est régressée sur les autres, et l'opération est répétée jusqu'à convergence (`max_iter=10`, arrêt anticipé sur la tolérance).
- Estimateur : `RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)`. Les forêts captent des relations non linéaires et des interactions sans hypothèse de forme, et la profondeur limitée réduit le surapprentissage.
- `Country` est encodé en indicatrices (`get_dummies`, `drop_first=True`) ; l'initialisation se fait par la médiane.
- Après imputation, la distribution des valeurs imputées est contrôlée : un modèle entraîné sur des classes déséquilibrées a tendance à amplifier la classe majoritaire.

### 4.5 Évaluation de l'imputation par masquage

Pour estimer la qualité de l'imputation :

1. masquer aléatoirement 20 % des valeurs connues d'une colonne (graine fixée) ;
2. relancer l'imputation ;
3. comparer les valeurs reprédites aux valeurs masquées (`accuracy_score`).

Le score se lit **par rapport à la baseline** de la classe majoritaire : sur une variable binaire déséquilibrée, prédire toujours la classe majoritaire donne déjà une accuracy élevée. Un nuage de points « valeurs réelles × valeurs prédites », rendu lisible par un léger bruit (*jitter*), permet de comparer faux positifs et faux négatifs et de détecter un repli vers la classe majoritaire.

Limite assumée : l'évaluation porte sur une base qui contient déjà des valeurs imputées. C'est un ordre de grandeur, pas une évaluation indépendante.

## 5. Nettoyage du questionnaire (N2)

1. **Suppression des métadonnées** de l'export et des champs de texte libre, non exploitables sans codage manuel.
2. **Suppression des abandons** : `dropna(thresh=10)` garde les lignes ayant au moins 10 réponses. En dessous, la ligne contient trop peu d'information pour être imputée de façon crédible.
3. **Renommage vers le schéma de la base d'enquête**, condition pour que la concaténation aligne automatiquement les colonnes communes.
4. **Recodage du genre** (texte → 0/1) pour obtenir une colonne numérique.
5. **Libellé pays** : récupéré dans l'export « réponses complètes », aligné sur l'index (les deux exports ont le même ordre de lignes), puis traduit vers la nomenclature anglaise de la base d'enquête par un dictionnaire.
6. **Filtrage du périmètre** : exclusion des répondants dont le pays d'origine est hors du champ de l'étude.
7. **Imputation KNN** de toutes les colonnes numériques, avec `n_neighbors=3`. Sur un petit échantillon, un voisinage large reviendrait à imputer par la moyenne globale.

## 6. Fusion des sources et contrôle qualité (N4, N5)

### 6.1 Diagnostic et harmonisation

- Les **opérations ensemblistes** sur les noms de colonnes (`&`, `-`) classent les variables en trois groupes : communes, propres à la base d'enquête, propres au questionnaire.
- **Harmonisation** : `COUNRY_ID` → `COUNTRY_ID` ; suppression de `ID` et `DATE`.
- **Contrôle des encodages** : pour chaque colonne commune, on compare les valeurs uniques des deux sources. Un 0/1 d'un côté et un 1/2 de l'autre rendrait la fusion incohérente.
- **Codes hors nomenclature** : les codes pays `99xxx` sont remplacés par `NaN`, le libellé `Country` restant disponible. Ces répondants sont conservés : les supprimer réduirait fortement un échantillon déjà petit, et les analyses limitées à un périmètre filtrent ensuite sur `Country`.

### 6.2 Concaténation

`pd.concat([base_enquete, questionnaire], ignore_index=True)` empile les lignes et aligne les colonnes de même nom. Une colonne propre à une source est automatiquement remplie de `NaN` pour les lignes de l'autre. Le nombre de lignes obtenu est vérifié (somme des deux bases).

### 6.3 Imputation Monte Carlo

Pour chaque colonne *j* incomplète, chaque valeur manquante est remplacée par un tirage avec remise dans les valeurs observées de *j* (`np.random.choice`, `np.random.seed(42)`). C'est un **hot-deck aléatoire non conditionnel**.

Propriétés :

- **la distribution marginale est préservée** : les proportions observées sont reproduites en espérance ;
- **les relations entre variables ne sont pas préservées** : le tirage est indépendant des autres colonnes, donc une variable imputée n'a aucune corrélation avec les autres variables sur les lignes imputées. Comme les colonnes du questionnaire sont imputées sur la quasi-totalité des lignes, toute association entre l'une d'elles et la variable cible est ramenée vers zéro dans la base fusionnée.

Ce choix permet de décrire les variables du questionnaire, pas de les croiser. La règle est appliquée explicitement dans N6 (voir 7.3).

### 6.4 Contrôle qualité (N5)

Contrôles avant analyse : absence de manquants, typage `category` des variables qualitatives, suppression des lignes dupliquées, effectifs tracés avant et après.

## 7. Analyse descriptive et choix de visualisation (N0, N3, N6)

### 7.1 Choix du graphique selon le type de variable

| Type de variable | Graphique | Implémentation |
|---|---|---|
| Nominale, nombreuses modalités | Barres horizontales triées | `value_counts(normalize=True).sort_values()`, `plt.barh` |
| Ordinale | Barres verticales dans l'ordre des codes, dégradé séquentiel | `sort_index()`, `cm.Blues(np.linspace(...))` |
| Binaire ou 3 modalités | Secteurs | `plt.pie(autopct=...)` |
| Continue | Histogramme en %, médiane et moyenne superposées | `weights=np.ones_like(x) / len(x) * 100`, `axvline` |
| Proportion par groupe | Barres colorées selon la valeur | `groupby().mean()`, colormap `RdYlGn_r` |
| Binaire × groupe | Diagramme divergent (« miroir ») | `value_counts(normalize=True).unstack()`, valeurs négatives à gauche |
| Cible × explicative qualitative | Barres empilées à 100 % | `pd.crosstab(..., normalize="index")` |
| Cible × explicative continue | Boîtes à moustaches | `plt.boxplot` |
| Cible × plusieurs indicateurs binaires | Barres groupées | décalage `± width / 2` autour de `np.arange(n)` |

### 7.2 Conventions

- Toutes les distributions sont exprimées en **fréquences relatives (%)** pour comparer des sources de tailles différentes.
- Les codes sont traduits en libellés par des dictionnaires de correspondance appliqués à l'index (`index.map`).
- La modalité dominante est mise en évidence par une couleur distincte ; une ligne de référence à 50 % sert de repère pour les proportions.
- Le code des figures est identique entre N0 et N3, pour que les figures des deux sources soient comparables.

### 7.3 Précautions d'analyse intégrées au code

- **Déséquilibre d'échantillonnage** : la moyenne brute (chaque ligne pèse autant) est comparée à la moyenne des moyennes par pays (chaque pays pèse autant). Un écart important signalerait un indicateur global dominé par les pays les plus représentés.
- **Normalisation par ligne des tableaux de contingence** : on compare la distribution de la cible *au sein* de chaque modalité, indépendamment des effectifs.
- **Robustesse des graphiques** : `reindex(columns=[0, 1], fill_value=0)` quand une modalité peut être absente d'un groupe ; palettes et `explode` construits à partir du nombre de modalités présentes.
- **Traçabilité de l'imputation** : dans N6, chaque variable imputée par Monte Carlo est signalée par ⚠️ dans le titre de sa figure, et ses croisements avec la cible forment un bloc à part, non interprété.

## 8. Reproductibilité

- Graines fixées : `random_state=42` (forêts aléatoires, `IterativeImputer`), `np.random.seed(42)` (masquage, Monte Carlo, jitter), `--seed` pour le générateur de données synthétiques.
- Chemins relatifs (`../data/...`) : le projet s'exécute hors de Google Colab, sans montage de disque.
- Chaque notebook lit et écrit un fichier intermédiaire versionnable ; l'ordre d'exécution est documenté.
- `generate_dummy_data.py` vérifie la structure produite (nombre de colonnes, modalités, tranches de taux de manquants) avant d'écrire les fichiers.

## 9. Limites et pistes d'amélioration

Retour critique, avec le recul d'un niveau Master, sur les choix faits pendant le projet.

**Imputation**

1. **Mise à l'échelle avant le KNN** : les variables ne sont pas standardisées et les identifiants (`ID`, `DATE`) participent au calcul des distances, ce qui laisse les colonnes à grande amplitude dominer le voisinage. Il faudrait standardiser (`StandardScaler`), exclure les identifiants, et traiter `COUNTRY_ID` comme une variable nominale (indicatrices ou distance de Gower) plutôt que comme une grandeur continue.
2. **Classifieur pour les variables binaires** : un `RandomForestRegressor` suivi d'un arrondi fonctionne, mais un classifieur (approche *missForest*) serait plus naturel pour des cibles 0/1.
3. **Évaluation indépendante** : évaluer l'imputation sur les seules lignes initialement observées, *avant* toute imputation, et compléter l'accuracy par des métriques insensibles au déséquilibre (balanced accuracy, F1, matrice de confusion) comparées à une baseline explicite.
4. **Imputation conditionnelle après fusion** : remplacer le Monte Carlo non conditionnel par un hot-deck stratifié (pays × tranche d'âge × genre) ou par une imputation multiple (MICE avec règles de Rubin). Sinon, restreindre les croisements aux lignes réellement observées.
5. **Codes de non-réponse** : recoder `Revenu = 6` (refus de répondre) en `NaN` *avant* l'imputation, pour que le KNN ne traite pas un refus comme une tranche de revenu.
6. **Ne pas imputer la variable cible** : `intention_to_migrate_legal` est complétée par le mode. Il serait plus rigoureux d'exclure ces lignes, ou de les signaler par une indicatrice, dans les analyses où elle sert de cible.

**Analyse**

7. **Inférence** : les écarts observés dans les croisements ne sont pas testés (test du χ², intervalles de confiance). Un modèle multivarié, par exemple une régression logistique, permettrait de contrôler les effets de structure entre variables explicatives.
8. **Petits effectifs** : afficher l'effectif de chaque groupe sur les figures et fixer un seuil minimal d'affichage, pour éviter des proportions saturées à 0 % ou 100 %.

**Génie logiciel**

9. **Factorisation** : le code des figures est dupliqué entre N0, N3 et N6. Un module `viz.py` et un dictionnaire de codes unique (*codebook*) éviteraient les écarts de libellés entre notebooks, aujourd'hui redéfinis localement.
10. **Contrôles automatisés** : remplacer les vérifications par `print` par des assertions, harmoniser la règle de dédoublonnage entre N1 (sur `ID`) et N5 (sur toutes les colonnes), et orchestrer le pipeline (script, `Makefile` ou `papermill`).
