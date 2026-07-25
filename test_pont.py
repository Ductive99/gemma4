import ollama

# Le nom exact de votre modèle. Si erreur "model not found",
# remplacez par ce que "ollama list" affiche.
MODELE = "gemma4"

reponse = ollama.chat(
    model=MODELE,
    messages=[
        {"role": "user", "content": "Réponds en un seul mot : capitale de l'Italie ?"}
    ],
)

print("Gemma a répondu :")
print(reponse["message"]["content"])
