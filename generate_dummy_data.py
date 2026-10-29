"""
Génère des données synthétiques reproduisant la structure des trois fichiers
d'entrée du pipeline : noms de colonnes (fautes de frappe et espaces parasites
compris), types, encodages des modalités et motifs de valeurs manquantes.

Aucune valeur n'est dérivée des données réelles :
- les proportions de chaque modalité sont tirées au hasard (loi de Dirichlet) ;
- les variables sont tirées indépendamment les unes des autres ;
- les taux de manquants sont choisis dans les mêmes *tranches* que l'original
  (< 2 %, 10-20 %, >= 50 %) uniquement pour que la logique d'imputation des
  notebooks s'applique, pas pour en reproduire les valeurs.

Les graphiques produits à partir de ces fichiers n'ont donc aucune valeur
descriptive : ils servent uniquement à démontrer le fonctionnement du code.

Usage :
    python generate_dummy_data.py
    python generate_dummy_data.py --n-survey 8000 --n-questionnaire 120 --seed 7
"""

import argparse
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "1_Donnees_brutes"

EXCEL_EPOCH = date(1899, 12, 30)  # origine des dates série Excel

# ---------------------------------------------------------------------------
# Nomenclatures
# ---------------------------------------------------------------------------

# Base d'enquête : COUNTRY_ID -> Country
SURVEY_COUNTRIES = {
    1: "ALGERIA", 5: "EGYPT", 7: "IRAQ", 8: "JORDAN", 10: "LEBANON",
    11: "LIBYA", 12: "MAURITANIA", 13: "MOROCCO", 15: "PALESTINE",
    19: "SUDAN", 21: "TUNISIA",
}

# Questionnaire : libellé exporté par la plateforme -> code pays.
# Les pays présents dans la nomenclature de la base d'enquête gardent son code,
# les autres reçoivent un code « hors nomenclature » au format 99xxx.
QUESTIONNAIRE_COUNTRIES = {
    "ALGERIE": 1, "LIBAN": 10, "MAROC": 13, "TUNISIE": 21,
    "ALBANIE": 99001, "BENIN": 99002, "BURKINA": 99003,
    "CENTRAFRICAINE (REPUBLIQUE)": 99004, "COTE D'IVOIRE": 99005,
    "EQUATEUR": 99006, "ESPAGNE": 99007, "FRANCE": 99008, "ITALIE": 99009,
    "KOSOVO": 99010, "MADAGASCAR": 99011, "MAURICE": 99012,
    "SENEGAL": 99013, "TOGO": 99014, "TURQUIE": 99015,
}

# Taux de manquants de la base d'enquête, par tranche de stratégie d'imputation
SURVEY_MISSING_RATES = {
    # < 2 % : mode / médiane
    "Educationf": 0.004, "Social statusf": 0.003, "Age": 0.015,
    "Professional situationf": 0.004, "intention_to_migrate_legal": 0.006,
    # 10-20 % : KNN
    "Corruption ": 0.14, "TrustCourts": 0.11, "TrustLocalGovernement": 0.17,
    "Trust_Parliament": 0.18,
    # >= 50 % : IterativeImputer + Random Forest
    "GeneralizedTrsut": 0.55, "Trust_Regiol_Governement ": 0.62,
    "intention_to_migrate_illegal": 0.68,
}

# Questionnaire : (colonne exportée, type de génération, paramètre)
#   cat  -> modalités entières 1..k     bin -> 0/1
#   age  -> âge continu                 txt -> texte libre (Faker)
QUESTIONNAIRE_PAGES = [
    [  # page 1 : profil
        ("Quel est votre âge ?", "age", None),
        ("Quel est votre genre ?", "gender", None),
        ("Quel est votre pays d'origine ?", "country", None),
        ("Dans quel environnement viviez-vous dans votre pays d'origine ?", "cat", 2),
        ("Quel niveau d'étude avez vous atteint ?", "cat", 7),
        ("Quelle est votre situation familiale ? ", "cat", 7),
        ("Quelle est votre situation professionnelle ?", "cat", 7),
    ],
    [  # page 2 : ménage
        ("De combien de personnes votre ménage est-il composé ?", "cat", 5),
        ("Êtes-vous la personne de référence concernant les décisions financières de ce ménage ?", "bin", None),
        ("Quel est le revenu mensuel moyen de l'ensemble de votre ménage ?", "cat", 6),
        ("Quelle est la source de ces revenus ? [Agriculture]", "bin", None),
        ("Quelle est la source de ces revenus ? [Commerce]", "bin", None),
        ("Quelle est la source de ces revenus ? [Salariat]", "bin", None),
        ("Quelle est la source de ces revenus ? [Aide familiale]", "bin", None),
        ("Quelle est la source de ces revenus ? [Transferts d'argent de l'étranger]", "bin", None),
        ("Quelle est la source de ces revenus ? [Autre]", "bin", None),
    ],
    [  # page 3 : situation financière
        ("Avez-vous un compte en banque ?", "bin", None),
        ("Faites-vous des virements ?", "bin", None),
        ("À quelle fréquence ?", "cat", 4),
        ("Au cours des 12 derniers mois, avez-vous subi un choc économique ?", "bin", None),
        ("Avez-vous accès au crédit bancaire ou informel ?", "bin", None),
    ],
    [  # page 4 : confiance et corruption
        ("Considérez-vous votre pays comme corrompu ?", "bin", None),
        ("Avez-vous confiance en votre pays ?", "bin", None),
        ("Avez-vous confiance dans la justice de votre pays ?", "bin", None),
        ("Avez-vous confiance dans votre municipalité de votre pays ?", "bin", None),
        ("Avez-vous confiance dans le parlement de votre pays ?", "bin", None),
        ("Avez-vous confiance dans votre gouvernement régional ?", "bin", None),
    ],
    [  # page 5 : projet migratoire
        ("Avez-vous l'intention de migrer légalement ?", "bin", None),
        ("Avez-vous l'intention de migrer illégalement ?", "bin", None),
        ("Votre pays d'accueil est-il une étape pour votre destination ?", "bin", None),
        ("Souhaitez-vous obtenir la nationalité française ?", "bin", None),
        ("Considérez-vous le mariage blanc ?", "bin", None),
        ("Quelles raisons vous ont poussé à migrer ?", "cat", 6),
        ("Veuillez préciser :", "txt", None),
        ("Souhaitez-vous retourner un jour dans votre pays ?", "bin", None),
        ("Avez-vous des proches en Europe ?", "bin", None),
        ("Quelle est votre relation avec ces personnes ? [Frère / Sœur]", "bin", None),
        ("Quelle est votre relation avec ces personnes ? [Parent]", "bin", None),
        ("Quelle est votre relation avec ces personnes ? [Ami]", "bin", None),
        ("Quelle est votre relation avec ces personnes ? [Autre]", "bin", None),
        ("Veuillez préciser :", "txt", None),
        ("Avez-vous l'intention d'envoyer de l'argent à votre famille restée sur place ?", "bin", None),
        ("À combien estimez-vous le montant de ces envois ?", "cat", 5),
        ("À quelle fréquence pensez-vous effectuer ces envois ?", "cat", 5),
    ],
]

METADATA_COLUMNS = [
    "ID de la réponse", "Date de soumission", "Dernière page",
    "Langue de départ", "Tête de série",
]

# Questions filtrées : (question conditionnelle, question filtre, valeur qui l'affiche)
CONDITIONAL_QUESTIONS = {
    "À quelle fréquence ?": ("Faites-vous des virements ?", 1),
    "À combien estimez-vous le montant de ces envois ?":
        ("Avez-vous l'intention d'envoyer de l'argent à votre famille restée sur place ?", 1),
    "À quelle fréquence pensez-vous effectuer ces envois ?":
        ("Avez-vous l'intention d'envoyer de l'argent à votre famille restée sur place ?", 1),
}
RELATION_PREFIX = "Quelle est votre relation avec ces personnes ?"


# ---------------------------------------------------------------------------
# Tirages élémentaires
# ---------------------------------------------------------------------------

def random_proportions(rng, k, concentration=3.0, floor=0.02):
    """Proportions aléatoires (Dirichlet) avec un plancher pour que chaque modalité existe."""
    p = rng.dirichlet(np.full(k, concentration))
    p = np.maximum(p, floor)
    return p / p.sum()


def draw_categorical(rng, n, k, start=1):
    """n codes entiers dans [start, start + k - 1]."""
    return rng.choice(np.arange(start, start + k), size=n, p=random_proportions(rng, k))


def draw_binary(rng, n):
    return draw_categorical(rng, n, 2, start=0)


def draw_age(rng, n, low=18, high=99):
    """Âge entier, distribution asymétrique à droite."""
    return np.clip(np.round(low + rng.gamma(shape=2.0, scale=rng.uniform(6, 12), size=n)), low, high)


def inject_missing(rng, series, rate):
    mask = rng.random(len(series)) < rate
    return series.astype("float64").mask(mask)


def to_excel_serial(d):
    return (d - EXCEL_EPOCH).days


# ---------------------------------------------------------------------------
# Base d'enquête : data/1_Donnees_brutes/Immigration.xlsx (21 colonnes)
# ---------------------------------------------------------------------------

def generate_survey(n, rng, fake):
    country_ids = np.array(list(SURVEY_COUNTRIES))
    country_id = rng.choice(country_ids, size=n, p=random_proportions(rng, len(country_ids), concentration=20))
    country_id.sort()  # le fichier source est trié par pays

    df = pd.DataFrame({"COUNTRY_ID": country_id})
    df["Country"] = df["COUNTRY_ID"].map(SURVEY_COUNTRIES)
    # ID = code pays x 10000 + rang du répondant dans le pays
    df["ID"] = df["COUNTRY_ID"] * 10000 + df.groupby("COUNTRY_ID").cumcount() + 1
    df["DATE"] = [
        to_excel_serial(fake.date_between(start_date=date(2021, 10, 1), end_date=date(2022, 7, 31)))
        for _ in range(n)
    ]
    df["Bankaccount"] = draw_binary(rng, n)
    df["Remit"] = draw_binary(rng, n)
    df["Regionf"] = draw_categorical(rng, n, 3)
    df["Educationf"] = draw_categorical(rng, n, 7)
    df["Genderf"] = draw_binary(rng, n)
    df["Social statusf"] = draw_categorical(rng, n, 7)
    df["Age"] = draw_age(rng, n)
    df["Professional situationf"] = draw_categorical(rng, n, 7)

    # Échelle de corruption 1 (forte) .. 4 (nulle) et sa version binarisée
    corruption = pd.Series(draw_categorical(rng, n, 4)).astype("float64")
    corruption = corruption.mask(rng.random(n) < SURVEY_MISSING_RATES["Corruption "])
    df["Corruption (0  1)"] = (corruption <= 2).astype("float64").where(corruption.notna())
    df["Corruption "] = corruption

    for col in ["GeneralizedTrsut", "TrustCourts", "TrustLocalGovernement", "Trust_Parliament",
                "Trust_Regiol_Governement ", "intention_to_migrate_legal", "intention_to_migrate_illegal"]:
        df[col] = draw_binary(rng, n)

    for col, rate in SURVEY_MISSING_RATES.items():
        if col != "Corruption ":
            df[col] = inject_missing(rng, df[col], rate)

    return df


# ---------------------------------------------------------------------------
# Questionnaire : exports « codes » et « réponses complètes » (49 colonnes)
# ---------------------------------------------------------------------------

def generate_questionnaire(n, rng, fake, item_nonresponse=0.03):
    labels = list(QUESTIONNAIRE_COUNTRIES)
    # Page atteinte par chaque répondant (0 = questionnaire ouvert puis abandonné)
    last_page = rng.choice(np.arange(6), size=n, p=[0.08, 0.10, 0.04, 0.04, 0.06, 0.68])

    coded = {}
    brute_country = pd.Series(np.nan, index=range(n), dtype="object")

    for page_number, page in enumerate(QUESTIONNAIRE_PAGES, start=1):
        reached = last_page >= page_number
        for position, (question, kind, param) in enumerate(page):
            key = (page_number, position)
            if kind == "age":
                values = pd.Series(draw_age(rng, n, high=65))
            elif kind == "gender":
                values = pd.Series(rng.choice(["M", "F"], size=n), dtype="object")
            elif kind == "country":
                drawn = pd.Series(rng.choice(labels, size=n, p=random_proportions(rng, len(labels))))
                brute_country = drawn.where(reached)
                values = drawn.map(QUESTIONNAIRE_COUNTRIES).astype("float64")
            elif kind == "cat":
                values = pd.Series(draw_categorical(rng, n, param)).astype("float64")
            elif kind == "bin":
                values = pd.Series(draw_binary(rng, n)).astype("float64")
            else:  # txt : renseigné plus tard, uniquement si la question filtre l'exige
                values = pd.Series(np.nan, index=range(n), dtype="object")

            values = values.where(reached)
            if kind not in ("country", "txt"):
                values = values.mask(rng.random(n) < item_nonresponse)
            coded[key] = (question, values)

    columns = [coded[key] for key in sorted(coded)]
    by_question = {}
    for question, values in columns:
        by_question.setdefault(question, []).append(values)

    def answers(question, occurrence=0):
        return by_question[question][occurrence]

    # Questions filtrées : masquées quand la condition d'affichage n'est pas remplie
    for question, (filter_question, shown_if) in CONDITIONAL_QUESTIONS.items():
        target = answers(question)
        target.where(answers(filter_question) == shown_if, inplace=True)

    has_relatives = answers("Avez-vous des proches en Europe ?") == 1
    for question in by_question:
        if question.startswith(RELATION_PREFIX):
            answers(question).where(has_relatives, inplace=True)

    # Champs « Veuillez préciser » : texte libre quand la modalité « Autre » est cochée
    other_reason = answers("Quelles raisons vous ont poussé à migrer ?") == 6
    other_relation = answers(f"{RELATION_PREFIX} [Autre]") == 1
    for occurrence, condition in enumerate([other_reason, other_relation]):
        target = answers("Veuillez préciser :", occurrence)
        target[condition] = [fake.sentence(nb_words=6) for _ in range(int(condition.sum()))]

    completed = last_page == len(QUESTIONNAIRE_PAGES)
    metadata = pd.DataFrame({
        "ID de la réponse": np.arange(1, n + 1),
        "Date de soumission": [
            fake.date_time_between(datetime(2025, 2, 1), datetime(2025, 3, 31)).strftime("%Y-%m-%d %H:%M:%S")
            if done else np.nan
            for done in completed
        ],
        "Dernière page": last_page,
        "Langue de départ": "fr",
        "Tête de série": [fake.random_number(digits=9, fix_len=True) for _ in range(n)],
    })

    body = pd.concat([values.rename(i) for i, (_, values) in enumerate(columns)], axis=1)
    coded_df = pd.concat([metadata, body], axis=1)
    # Les deux champs « Veuillez préciser : » portent le même intitulé dans l'export ;
    # pandas les distinguera à la lecture (« Veuillez préciser :.1 »).
    coded_df.columns = METADATA_COLUMNS + [question for question, _ in columns]

    # Export « réponses complètes » : identique, mais le pays est un libellé texte
    brute_df = coded_df.copy()
    brute_df["Quel est votre pays d'origine ?"] = brute_country
    return coded_df, brute_df


# ---------------------------------------------------------------------------
# Contrôles de structure
# ---------------------------------------------------------------------------

def check_structure(survey, questionnaire, brute):
    assert survey.shape[1] == 21, survey.shape
    assert questionnaire.shape[1] == 49 and brute.shape[1] == 49
    assert set(survey["Regionf"].unique()) == {1, 2, 3}
    for col, rate in SURVEY_MISSING_RATES.items():
        observed = survey[col].isna().mean()
        assert abs(observed - rate) < 0.03, (col, observed, rate)
    assert set(questionnaire["Dans quel environnement viviez-vous dans votre pays d'origine ?"].dropna()) <= {1.0, 2.0}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n-survey", type=int, default=5000, help="lignes de la base d'enquête")
    parser.add_argument("--n-questionnaire", type=int, default=80, help="lignes de l'export du questionnaire")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    Faker.seed(args.seed)
    fake = Faker("fr_FR")

    survey = generate_survey(args.n_survey, rng, fake)
    questionnaire, brute = generate_questionnaire(args.n_questionnaire, rng, fake)
    check_structure(survey, questionnaire, brute)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for folder in ["2_Donnees_nettoyees", "3_Donnees_fusionnees"]:
        (ROOT / "data" / folder).mkdir(parents=True, exist_ok=True)

    survey.to_excel(RAW_DIR / "Immigration.xlsx", index=False)
    questionnaire.to_csv(RAW_DIR / "base_questionnaire.csv", index=False, encoding="utf-8")
    brute.to_csv(RAW_DIR / "base_questionnaire_brute.csv", index=False, encoding="utf-8")

    print(f"Immigration.xlsx                : {survey.shape[0]} lignes x {survey.shape[1]} colonnes")
    print(f"base_questionnaire.csv          : {questionnaire.shape[0]} lignes x {questionnaire.shape[1]} colonnes")
    print(f"base_questionnaire_brute.csv    : {brute.shape[0]} lignes x {brute.shape[1]} colonnes")
    print(f"Fichiers écrits dans {RAW_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
