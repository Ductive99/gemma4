import unicodedata

def normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")

def camp_dominant(texte, marqueurs_pour, marqueurs_contre):
    """Regarde quel camp est le plus présent dans un texte.
    Retourne 'POUR', 'CONTRE', ou 'INDETERMINE'."""
    t = normaliser(texte)
    score_pour = sum(1 for m in marqueurs_pour if normaliser(m) in t)
    score_contre = sum(1 for m in marqueurs_contre if normaliser(m) in t)
    if score_pour > score_contre:
        return "POUR"
    if score_contre > score_pour:
        return "CONTRE"
    return "INDETERMINE"

def juger(hypothese, snippets, marqueurs_pour, marqueurs_contre):
    """Compare la DIRECTION de l'hypothèse à la DIRECTION des preuves.
    'POUR' = l'hypothèse affirme l'effet (ex. hausse).
    'CONTRE' = l'hypothèse nie l'effet (ex. pas de hausse)."""
    camp_hypo = camp_dominant(hypothese, marqueurs_pour, marqueurs_contre)
    texte_preuves = " ".join(snippets)
    camp_preuves = camp_dominant(texte_preuves, marqueurs_pour, marqueurs_contre)

    print(f"   [juge] camp de l'hypothèse : {camp_hypo}")
    print(f"   [juge] camp des preuves    : {camp_preuves}")

    if camp_hypo == "INDETERMINE" or camp_preuves == "INDETERMINE":
        return "INDETERMINE"
    return "SURVIVED" if camp_hypo == camp_preuves else "REFUTED"


# --- Marqueurs pour le scénario "prix du fret" ---
POUR = ["hausse", "surge", "augmentation", "flambee", "rise", "increase", "spike", "soar"]
CONTRE = ["stable", "unchanged", "inchange", "baisse", "decline", "steady", "absorb", "resilience", "resilient"]

# TEST 1 : hypothèse dit "hausse", preuves disent "stable" -> désaccord -> REFUTED
h1 = "un pic spectaculaire des coûts de fret, une hausse massive"
p1 = ["Shipping costs remain stable", "freight rates unchanged, ports absorbing traffic"]
print("TEST 1 (hausse vs stable) :")
print("  ->", juger(h1, p1, POUR, CONTRE), "— attendu REFUTED\n")

# TEST 2 : hypothèse RÉVISÉE dit "pas de hausse / résilience", preuves disent "stable" -> ACCORD -> SURVIVED
h2 = "les ports absorbent le trafic, résilience, sans hausse durable des coûts"
p2 = ["Shipping costs remain stable", "freight rates unchanged, ports absorbing traffic"]
print("TEST 2 (résilience vs stable) :")
print("  ->", juger(h2, p2, POUR, CONTRE), "— attendu SURVIVED")
