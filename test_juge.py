# --- Le juge déterministe : PAS de LLM ici, que du code. ---

def normaliser(texte):
    """Met en minuscules et enlève les accents pour comparer proprement."""
    import unicodedata
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte

def juger(criterion, snippets):
    """
    criterion : dict avec "kind" ("must_find" ou "must_not_find") et "markers" (liste de mots).
    snippets  : liste de chaînes = les résultats de recherche web.
    Retourne "SURVIVED" ou "REFUTED".
    """
    foin = normaliser(" ".join(snippets))
    marqueur_trouve = any(normaliser(m) in foin for m in criterion["markers"])

    if criterion["kind"] == "must_find":
        return "SURVIVED" if marqueur_trouve else "REFUTED"
    else:  # must_not_find
        return "REFUTED" if marqueur_trouve else "SURVIVED"


# =========================================================
#  TESTS : on vérifie que le juge se comporte correctement
# =========================================================

# Scénario : hypothèse = "les prix du fret vont FLAMBER".
# On la réfute si le web parle de prix STABLES ou en BAISSE.
critere = {
    "kind": "must_find",
    "markers": ["hausse", "flambee", "surge", "augmentation"],
}

# Cas 1 : le web confirme une hausse -> l'hypothèse doit SURVIVRE.
web_confirme = [
    "Freight rates surge after port closure",
    "Les taux de fret en forte hausse cette semaine",
]
print("Cas 1 (web confirme la hausse) :", juger(critere, web_confirme), "— attendu SURVIVED")

# Cas 2 : le web contredit (prix stables) -> l'hypothèse doit être RÉFUTÉE.
web_contredit = [
    "Shipping costs remain stable despite closure",
    "Les prix restent inchangés, marché calme",
]
print("Cas 2 (web contredit) :", juger(critere, web_contredit), "— attendu REFUTED")
