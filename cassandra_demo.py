import ollama
import json
import unicodedata
import time
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.live import Live

MODELE = "gemma4"
console = Console()

# ============================================================
#  JUGE DÉTERMINISTE
# ============================================================
def normaliser(texte):
    texte = texte.lower()
    texte = unicodedata.normalize("NFD", texte)
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")

def camp_dominant_preuves(texte, pour, contre):
    t = normaliser(texte)
    s_pour = sum(1 for m in pour if normaliser(m) in t)
    s_contre = sum(1 for m in contre if normaliser(m) in t)
    if s_pour > s_contre: return "POUR"
    if s_contre > s_pour: return "CONTRE"
    return "INDETERMINE"

def direction_vers_camp(direction):
    d = normaliser(str(direction))
    if "affirme" in d or "affirm" in d: return "POUR"
    if "nie" in d or "neg" in d: return "CONTRE"
    return "INDETERMINE"

# ============================================================
#  APPELS GEMMA (fusionnés : hypothèse + direction en un seul JSON)
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

def appeler_gemma(system, user):
    r = ollama.chat(
        model=MODELE,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        format="json",
    )
    return json.loads(r["message"]["content"])

# ============================================================
#  SCÉNARIO
# ============================================================
SCENARIO = {
    "evenement": "Le port de Singapour vient de fermer pour une durée indéterminée.",
    "pour":    ["hausse", "surge", "augmentation", "flambee", "rise", "increase", "spike", "soar", "pic"],
    "contre": ["stable", "unchanged", "inchange", "baisse", "decline", "steady", "absorb", "resilience", "resilient", "calme"],
    "snippets": [
        "Shipping costs remain stable despite Singapore port closure",
        "Analysts say freight rates unchanged, other ports absorbing the traffic smoothly",
    ],
}

# ============================================================
#  ÉTAT D'AFFICHAGE
# ============================================================
etat = {
    "lignes": [],
    "croyance": "(aucune)",
    "tokens": 0,
    "couleur_tokens": "green",
}

def estimer_tokens(lignes):
    return sum(len(l) for l in lignes) // 4

def construire_ecran():
    layout = Layout()
    layout.split_row(
        Layout(name="gauche", ratio=3),
        Layout(name="droite", ratio=2),
    )
    texte_gauche = Text()
    for ligne in etat["lignes"]:
        texte_gauche.append(ligne + "\n")
    layout["gauche"].update(Panel(texte_gauche,
        title="[bold cyan]RAISONNEMENT COGNITIF[/bold cyan]", border_style="cyan"))
    d = Text()
    d.append("CROYANCE ACTUELLE\n", style="bold yellow")
    d.append(etat["croyance"] + "\n\n", style="white")
    d.append("MÉMOIRE DE TRAVAIL\n", style="bold yellow")
    d.append(f"{etat['tokens']} tokens\n", style=f"bold {etat['couleur_tokens']}")
    layout["droite"].update(Panel(d,
        title="[bold magenta]ÉTAT INTERNE[/bold magenta]", border_style="magenta"))
    return layout

def ajouter_ligne(live, texte, pause=0.6):
    etat["lignes"].append(texte)
    etat["tokens"] = estimer_tokens(etat["lignes"])
    live.update(construire_ecran())
    time.sleep(pause)

def penser(live, message, duree_appel):
    """Affiche un indicateur d'attente animé pendant que Gemma calcule."""
    etat["lignes"].append("")  # ligne qui va être animée
    idx = len(etat["lignes"]) - 1
    symboles = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    fin = time.time() + duree_appel
    i = 0
    while time.time() < fin:
        etat["lignes"][idx] = f"  {symboles[i % len(symboles)]} {message}"
        live.update(construire_ecran())
        time.sleep(0.1)
        i += 1
    etat["lignes"].pop(idx)  # on retire la ligne d'attente

# ============================================================
#  BOUCLE PRINCIPALE (appel Gemma lancé en arrière-plan pendant l'animation)
# ============================================================
import threading

def appel_async(resultat, system, user):
    resultat["obj"] = appeler_gemma(system, user)

def gemma_avec_attente(live, message, system, user):
    """Lance Gemma dans un thread, anime l'attente, retourne le résultat."""
    resultat = {}
    t = threading.Thread(target=appel_async, args=(resultat, system, user))
    t.start()
    symboles = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    etat["lignes"].append("")
    idx = len(etat["lignes"]) - 1
    i = 0
    while t.is_alive():
        etat["lignes"][idx] = f"  {symboles[i % len(symboles)]} {message}"
        live.update(construire_ecran())
        time.sleep(0.1)
        i += 1
    t.join()
    etat["lignes"].pop(idx)
    return resultat["obj"]

def executer(live, sc):
    ev, pour, contre, snippets = sc["evenement"], sc["pour"], sc["contre"], sc["snippets"]

    ajouter_ligne(live, f"▸ ÉVÉNEMENT : {ev}", pause=1.2)

    hypo = gemma_avec_attente(live, "Gemma formule une hypothèse...", SYSTEM_HYPO, f"Événement : {ev}")
    ajouter_ligne(live, f"  HYPOTHÈSE : {hypo['hypothesis']}", pause=1.2)
    ajouter_ligne(live, f"  Confiance auto-déclarée (non calibrée) : {hypo['confidence_prior']}", pause=1.0)

    ajouter_ligne(live, "▸ Recherche de preuves adversariales (cache SerpApi)...", pause=1.0)
    for s in snippets:
        ajouter_ligne(live, f"  ⌕ {s}", pause=0.7)

    camp_h = direction_vers_camp(hypo.get("direction", ""))
    camp_p = camp_dominant_preuves(" ".join(snippets), pour, contre)
    verdict = "SURVIVED" if camp_h == camp_p and camp_h != "INDETERMINE" else "REFUTED"
    ajouter_ligne(live, f"▸ JUGE DÉTERMINISTE : hypothèse={camp_h} vs preuves={camp_p}", pause=1.2)

    revisions = 0
    while verdict == "REFUTED" and revisions < 2:
        revisions += 1
        etat["couleur_tokens"] = "red"
        ajouter_ligne(live, f"  ✗ RÉFUTÉ — la mémoire N'EST PAS purgée (révision {revisions})", pause=0.7)
        user_rev = f"Événement : {ev}\nHypothèse réfutée : {hypo['hypothesis']}\nPreuves : {snippets}"
        hypo = gemma_avec_attente(live, "Gemma révise sa croyance...", SYSTEM_REVISION, user_rev)
        ajouter_ligne(live, f"  HYPOTHÈSE RÉVISÉE : {hypo['hypothesis']}", pause=0.7)
        camp_h = direction_vers_camp(hypo.get("direction", ""))
        verdict = "SURVIVED" if camp_h == camp_p and camp_h != "INDETERMINE" else "REFUTED"
        ajouter_ligne(live, f"▸ JUGE : hypothèse={camp_h} vs preuves={camp_p}", pause=0.6)

    if verdict == "SURVIVED":
        ajouter_ligne(live, "  ✓ HYPOTHÈSE VALIDÉE PAR CONFRONTATION AU RÉEL", pause=0.75)
        etat["croyance"] = hypo["hypothesis"]
        ajouter_ligne(live, "▸ Croyance promue en mémoire persistante. PURGE...", pause=0.9)
        etat["lignes"] = ["▸ Mémoire de travail purgée.", "  Seule la croyance distillée subsiste."]
        etat["tokens"] = estimer_tokens(etat["lignes"])
        etat["couleur_tokens"] = "green"
        live.update(construire_ecran())
        time.sleep(2.5)
    else:
        ajouter_ligne(live, "  ⚠ NON RÉSOLU — purge refusée, croyance non fiable.", pause=2.0)

with Live(construire_ecran(), console=console, screen=True, refresh_per_second=12) as live:
    executer(live, SCENARIO)

console.print("\n[bold green]Démonstration terminée.[/bold green]")
