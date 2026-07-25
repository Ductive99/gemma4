import ollama
import json
import unicodedata

MODELE = "gemma4"

# ============================================================
#  1. LE JUGE DÉTERMINISTE — direction de l'hypothèse vs direction des preuves
# ============================================================
def normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")

def camp_dominant(texte, pour, contre):
    t = normaliser(texte)
    s_pour = sum(1 for m in pour if normaliser(m) in t)
    s_contre = sum(1 for m in contre if normaliser(m) in t)
    if s_pour > s_contre:
        return "POUR"
    if s_contre > s_pour:
        return "CONTRE"
    return "INDETERMINE"

def direction_vers_camp(direction):
    d = normaliser(str(direction))
    if "affirme" in d or "affirm" in d: return "POUR"
    if "nie" in d or "neg" in d: return "CONTRE"
    return "INDETERMINE"

def juger(hypo_obj, snippets, pour, contre):
    camp_hypo = direction_vers_camp(hypo_obj.get("direction", ""))
    camp_preuves = camp_dominant(" ".join(snippets), pour, contre)
    if camp_hypo == "INDETERMINE" or camp_preuves == "INDETERMINE":
        return "INDETERMINE", camp_hypo, camp_preuves
    verdict = "SURVIVED" if camp_hypo == camp_preuves else "REFUTED"
    return verdict, camp_hypo, camp_preuves

# ============================================================
#  2. FICHE SCÉNARIO (contrôlée par VOUS)
# ============================================================
SCENARIO = {
    "evenement": "Le port de Singapour vient de fermer pour une durée indéterminée.",
    "pour":   ["hausse", "surge", "augmentation", "flambee", "rise", "increase", "spike", "soar", "pic"],
    "contre": ["stable", "unchanged", "inchange", "baisse", "decline", "steady", "absorb", "resilience", "resilient", "calme"],
    # Snippets simulés : le web dit que c'est STABLE (contredit une hypothèse de hausse)
    "snippets": [
        "Shipping costs remain stable despite Singapore port closure",
        "Analysts say freight rates unchanged, other ports absorbing the traffic smoothly",
    ],
}

# ============================================================
#  3. APPELS À GEMMA
# ============================================================
# ============================================================
#  3. APPELS À GEMMA
# ============================================================
SYSTEM_HYPO = """Tu es un moteur de raisonnement scientifique.
Face à un événement, formule une hypothèse sur la conséquence économique la plus probable.
Réponds UNIQUEMENT en JSON valide avec EXACTEMENT ces champs :
- "hypothesis" : chaîne, ton hypothèse.
- "confidence_prior" : nombre entre 0 et 1.
- "direction" : "AFFIRME" si ton hypothèse prédit une hausse des coûts / une perturbation majeure, sinon "NIE"."""

SYSTEM_REVISION = """Ton hypothèse précédente a été RÉFUTÉE par les preuves fournies.
Analyse ce que disent réellement les preuves, puis formule une NOUVELLE hypothèse COHÉRENTE avec elles.
Réponds UNIQUEMENT en JSON valide avec EXACTEMENT ces champs :
- "hypothesis" : chaîne, ta nouvelle hypothèse révisée.
- "confidence_prior" : nombre entre 0 et 1.
- "direction" : "AFFIRME" si ta nouvelle hypothèse prédit une hausse des coûts / une perturbation majeure, sinon "NIE"."""

SYSTEM_CLASSIF = """On te donne une hypothèse économique. Détermine sa DIRECTION sur une seule dimension : l'effet (hausse des coûts / perturbation majeure) est-il AFFIRMÉ ou NIÉ ?
Attention aux négations : "sans hausse", "pas de flambée", "absorbé sans impact" signifient que l'effet est NIÉ.
Réponds UNIQUEMENT en JSON valide avec EXACTEMENT ce champ :
- "direction" : soit "AFFIRME" (l'hypothèse prédit l'effet) soit "NIE" (l'hypothèse dit que l'effet n'aura pas lieu)."""

def classer_hypothese(hypothese):
    r = appeler_gemma(SYSTEM_CLASSIF, f"Hypothèse : {hypothese}")
    print("   [debug classif] Gemma a répondu :", r)   # <-- on voit la réponse brute
    d = normaliser(str(r.get("direction", "")))
    if "affirme" in d or "affirm" in d or "positif" in d:
        return "POUR"
    if "nie" in d or "neg" in d or "negatif" in d:
        return "CONTRE"
    return "INDETERMINE"

def appeler_gemma(system, user):
    r = ollama.chat(
        model=MODELE,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format="json",
    )
    return json.loads(r["message"]["content"])
# ============================================================
#  4. LA BOUCLE DE CONTRÔLE
# ============================================================
def executer(sc):
    ev, pour, contre, snippets = sc["evenement"], sc["pour"], sc["contre"], sc["snippets"]

    print("=" * 60)
    print("ÉVÉNEMENT :", ev)
    print("=" * 60)

    hypo = appeler_gemma(SYSTEM_HYPO, f"Événement : {ev}")
    print("\n[HYPOTHÈSE]", hypo["hypothesis"])
    print("[PRIOR non calibré]", hypo["confidence_prior"])

    verdict, ch, cp = juger(hypo, snippets, pour, contre)
    print("\n[PREUVES]", snippets)
    print(f"[JUGE] hypothèse={ch} | preuves={cp} -> {verdict}")

    revisions = 0
    while verdict == "REFUTED" and revisions < 2:
        revisions += 1
        print(f"\n>>> RÉFUTÉ. Révision n°{revisions}. Mémoire NON purgée. <<<")
        user_rev = (
            f"Événement : {ev}\n"
            f"Hypothèse réfutée : {hypo['hypothesis']}\n"
            f"Preuves : {snippets}"
        )
        hypo = appeler_gemma(SYSTEM_REVISION, user_rev)
        print("[HYPOTHÈSE RÉVISÉE]", hypo["hypothesis"])
        verdict, ch, cp = juger(hypo, snippets, pour, contre)
        print(f"[JUGE] hypothèse={ch} | preuves={cp} -> {verdict}")

    print("\n" + "=" * 60)
    if verdict == "SURVIVED":
        print("RÉSOLU ✅ — Croyance promue. Mémoire de travail purgée.")
    elif verdict == "INDETERMINE":
        print("INDÉTERMINÉ — preuves ambiguës. Purge refusée.")
    else:
        print("NON RÉSOLU ⚠️ — 2 révisions épuisées. Purge refusée.")
    print("=" * 60)

executer(SCENARIO)
