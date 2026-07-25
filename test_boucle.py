import ollama
import json
import unicodedata

MODELE = "gemma4"

# ============================================================
#  1. LE JUGE DÉTERMINISTE (repris du bloc 3, il a fait ses preuves)
# ============================================================
def normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")

def juger(criterion, snippets):
    foin = normaliser(" ".join(snippets))
    trouve = any(normaliser(m) in foin for m in criterion["markers"])
    if criterion["kind"] == "must_find":
        return "SURVIVED" if trouve else "REFUTED"
    return "REFUTED" if trouve else "SURVIVED"

# ============================================================
#  2. LES FICHES SCÉNARIO (contrôlées par VOUS, pas par Gemma)
# ============================================================
# Le critère de réfutation est ROBUSTE : des mots simples qui
# apparaissent vraiment dans des articles réels.
SCENARIO = {
    "evenement": "Le port de Singapour vient de fermer pour une durée indéterminée.",
    "critere": {
        "kind": "must_find",
        "markers": ["hausse", "surge", "augmentation", "flambee", "rise", "increase"],
    },
    # Snippets SIMULÉS pour l'instant. On les remplacera par SerpApi.
    # Ici on simule un web qui CONTREDIT l'hypothèse de flambée -> doit RÉFUTER.
    "snippets_simules": [
        "Shipping costs remain stable despite Singapore port closure",
        "Analysts say freight rates unchanged, other ports absorbing traffic",
    ],
}

# ============================================================
#  3. GEMMA FORMULE UNE HYPOTHÈSE (vrai appel au modèle)
# ============================================================
SYSTEM_HYPO = """Tu es un moteur de raisonnement scientifique.
Face à un événement, formule une hypothèse sur la conséquence économique la plus probable.
Réponds UNIQUEMENT en JSON valide avec EXACTEMENT ces champs :
- "hypothesis" : chaîne, ton hypothèse.
- "confidence_prior" : nombre entre 0 et 1."""

def formuler_hypothese(evenement):
    r = ollama.chat(
        model=MODELE,
        messages=[
            {"role": "system", "content": SYSTEM_HYPO},
            {"role": "user", "content": f"Événement : {evenement}"},
        ],
        format="json",
    )
    return json.loads(r["message"]["content"])

# ============================================================
#  4. GEMMA RÉVISE (appelé seulement si RÉFUTÉ)
# ============================================================
SYSTEM_REVISION = """Ton hypothèse précédente a été RÉFUTÉE par les preuves.
Formule une NOUVELLE hypothèse qui tient compte des preuves.
Réponds UNIQUEMENT en JSON valide avec EXACTEMENT ces champs :
- "hypothesis" : chaîne, ta nouvelle hypothèse révisée.
- "confidence_prior" : nombre entre 0 et 1."""

def reviser_hypothese(evenement, ancienne, preuves):
    contenu = (
        f"Événement : {evenement}\n"
        f"Hypothèse réfutée : {ancienne}\n"
        f"Preuves qui l'ont réfutée : {preuves}"
    )
    r = ollama.chat(
        model=MODELE,
        messages=[
            {"role": "system", "content": SYSTEM_REVISION},
            {"role": "user", "content": contenu},
        ],
        format="json",
    )
    return json.loads(r["message"]["content"])

# ============================================================
#  5. LA BOUCLE DE CONTRÔLE
# ============================================================
def executer(scenario):
    evenement = scenario["evenement"]
    critere = scenario["critere"]
    snippets = scenario["snippets_simules"]

    print("=" * 55)
    print("ÉVÉNEMENT :", evenement)
    print("=" * 55)

    # --- Étape 1 : hypothèse initiale ---
    hypo = formuler_hypothese(evenement)
    print("\n[HYPOTHÈSE]", hypo["hypothesis"])
    print("[CONFIANCE PRIOR (non calibrée)]", hypo["confidence_prior"])

    # --- Étape 2 : le juge tranche ---
    verdict = juger(critere, snippets)
    print("\n[PREUVES WEB]", snippets)
    print("[VERDICT DU JUGE (code, pas Gemma)]", verdict)

    # --- Étape 3 : le verdict PILOTE le flux ---
    revisions = 0
    while verdict == "REFUTED" and revisions < 2:
        revisions += 1
        print(f"\n>>> RÉFUTÉ. Révision n°{revisions}. La mémoire N'EST PAS purgée. <<<")
        hypo = reviser_hypothese(evenement, hypo["hypothesis"], snippets)
        print("[HYPOTHÈSE RÉVISÉE]", hypo["hypothesis"])
        verdict = juger(critere, snippets)
        print("[NOUVEAU VERDICT]", verdict)

    # --- Étape 4 : résolution ---
    print("\n" + "=" * 55)
    if verdict == "SURVIVED":
        print("RÉSOLU ✅ — Croyance promue. Mémoire de travail purgée.")
    else:
        print("NON RÉSOLU ⚠️ — 2 révisions épuisées. Purge refusée.")
    print("=" * 55)

# --- Lancement ---
executer(SCENARIO)
