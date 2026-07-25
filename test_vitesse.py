import ollama, time

MODELE = "gemma4:e4b"

def un_appel(n):
    debut = time.time()
    r = ollama.chat(
        model=MODELE,
        messages=[
            {"role": "system", "content": "Réponds en JSON avec le champ 'direction' valant 'AFFIRME' ou 'NIE'."},
            {"role": "user", "content": "Hypothèse : les prix vont monter fortement."},
        ],
        format="json",
        keep_alive="10m",   # <-- garde le modèle en mémoire 10 minutes
    )
    duree = time.time() - debut
    print(f"Appel {n} : {duree:.1f} s — {r['message']['content']}")

un_appel(1)
un_appel(2)
un_appel(3)
