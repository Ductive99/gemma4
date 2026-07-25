import ollama
import json

MODELE = "gemma4"

# On décrit précisément à Gemma le format qu'on veut.
# Le rôle "system" pose les règles ; le rôle "user" donne la tâche.
messages = [
    {
        "role": "system",
        "content": (
            "Tu es un moteur de raisonnement. "
            "Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte autour. "
            "L'objet doit avoir exactement ces champs : "
            "hypothesis (chaîne), confidence_prior (nombre entre 0 et 1)."
        ),
    },
    {
        "role": "user",
        "content": "Événement : le port de Singapour vient de fermer. Formule une hypothèse sur la conséquence économique la plus probable.",
    },
]

reponse = ollama.chat(
    model=MODELE,
    messages=messages,
    format="json",   # <-- la clé : force une sortie JSON valide
)

texte_brut = reponse["message"]["content"]
print("=== Texte brut renvoyé par Gemma ===")
print(texte_brut)

# On tente de transformer le texte en objet Python exploitable.
print("\n=== Tentative de lecture structurée ===")
try:
    obj = json.loads(texte_brut)
    print("JSON valide ✅")
    print("Champs présents :", list(obj.keys()))
    print("hypothesis =", obj.get("hypothesis"))
    print("confidence_prior =", obj.get("confidence_prior"))
except json.JSONDecodeError as e:
    print("JSON INVALIDE ❌ :", e)
