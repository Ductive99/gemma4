from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
import time

console = Console()

def construire_ecran(pensee, etat_croyance, tokens, verdict_couleur):
    # On crée une disposition à deux colonnes
    layout = Layout()
    layout.split_row(
        Layout(name="gauche", ratio=3),
        Layout(name="droite", ratio=2),
    )

    # Panneau gauche : le flux de raisonnement
    layout["gauche"].update(
        Panel(
            Text(pensee, style="white"),
            title="[bold cyan]RAISONNEMENT[/bold cyan]",
            border_style="cyan",
        )
    )

    # Panneau droit : état de croyance + tokens
    droite_contenu = Text()
    droite_contenu.append("CROYANCE ACTUELLE\n", style="bold yellow")
    droite_contenu.append(etat_croyance + "\n\n", style="white")
    droite_contenu.append("MÉMOIRE DE TRAVAIL\n", style="bold yellow")
    droite_contenu.append(f"{tokens} tokens\n", style=verdict_couleur)

    layout["droite"].update(
        Panel(
            droite_contenu,
            title="[bold magenta]ÉTAT INTERNE[/bold magenta]",
            border_style="magenta",
        )
    )
    return layout

# --- Démonstration statique de la mise en page ---
ecran = construire_ecran(
    pensee="[HYPOTHÈSE] Flambée des coûts du fret...\n[VERDICT] REFUTED\n[RÉVISION] Résilience des ports...",
    etat_croyance="(en cours de résolution)",
    tokens=1847,
    verdict_couleur="red",
)
console.print(ecran)
