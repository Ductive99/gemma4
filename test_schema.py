import ollama
import json

MODELE = "gemma4"

SYSTEM_PROMPT = """Tu es un moteur de raisonnement scientifique par falsification.
Face à un événement, tu formules une hypothèse, PUIS tu t'engages à l'avance sur ce qui la réfuterait.

Tu réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte autour.
L'objet doit avoir EXACTEMENT ces champs :
- "hypothesis" : chaîne. Ton hypothèse sur la conséquence la plus probable.
- "confidence_prior" : nombre entre 0 et 1. Ta confiance AVANT vérification.
- "falsification_query" : chaîne. Une requête de recherche web courte (3 à 6 mots) conçue pour CONTREDIRE ton hypothèse, pas pour la confirmer.
- "refutation_criterion" : objet avec deux champs :
    - "kind" : soit "must_find" soit "must_not_find".
    - "markers" : liste de 1 à 3 chaînes courtes (mots, chiffres ou dates). Si kind vaut "must_find", trouver ces marqueurs dans les résultats CONFIRME l'hypothèse ; ne pas les trouver la RÉFUTE. Si kind vaut "must_not_find", c'est l'inverse.

Choisis des marqueurs concrets et vérifiables, pas des concepts vagues."""

def formuler_hypothese(evenement):
    reponse = ollama.chat(
        model=MODELE,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Événement : {evenement}"},
        ],
        format="json",
    )
    return reponse["message"]["content"]

# --- Test ---
evenement = "Le port de Singapour vient de fermer pour une durée indéterminée."
texte_brut = formuler_hypothese(evenement)

print("=== Texte brut ===")
print(texte_brut)

print("\n=== Lecture structurée ===")
try:
    obj = json.loads(texte_brut)
    print("JSON valide ✅")
    print("Champs :", list(obj.keys()))
    print("hypothesis        :", obj.get("hypothesis"))
    print("confidence_prior  :", obj.get("confidence_prior"))
    print("falsification_query:", obj.get("falsification_query"))
    crit = obj.get("refutation_criterion")
    print("refutation_criterion:", crit)
    if isinstance(crit, dict):
        print("   -> kind    :", crit.get("kind"))
        print("   -> markers :", crit.get("markers"))
except json.JSONDecodeError as e:
    print("JSON INVALIDE ❌ :", e)
