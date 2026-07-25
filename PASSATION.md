# État du projet Cassandra — Passation

## Contexte & Architecture
- Hackathon Gemma 4 (Google / 42 AI) - Track Edge / On-Device.
- Moteur cognitif local de falsification scientifique : Gemma 4 formule une hypothèse et déclare sa direction.
- **Séparation des pouvoirs :** Un juge déterministe (Python) confronte la direction de Gemma aux preuves (mots-clés). Gemma ne se juge jamais lui-même.
- **Purge :** Si validée (SURVIVED), la croyance est stockée et la mémoire purgée (baisse visible des tokens). Si réfutée (REFUTED), Gemma doit réviser.

## Décisions Techniques
1. **Fusion des appels (3 au lieu de 5) :** Gemma déclare sa propre direction ("AFFIRME"/"NIE") dès l'hypothèse. Résolution 5/5.
2. **Modèle :** gemma4:latest (9,6 Go) utilisé. Version edge testée mais non concluante sur la vitesse/nuance.
3. **Le juge et la négation :** Laisser Gemma gérer la sémantique de sa propre phrase contourne l'incapacité du juge déterministe à comprendre la négation.
4. **Cache SerpApi :** Réseau simulé pour la démo live (anti-crash).
5. **Option B (Marqueurs) :** Mots-clés POUR/CONTRE hardcodés dans le scénario pour garantir la fiabilité de la réfutation.

## État des Fichiers
- `cassandra_demo.py` : Fichier de démo final (interface Rich, split-screen, animation).
- `cassandra_v1.py` : Moteur CLI pur pour tests rapides.

## À Faire (Priorités Code Freeze)
1. Script de lancement (Safe Start).
2. Ajouter le Scénario 2 (Bourse).
3. Rédiger le rapport Kaggle.
4. Répéter le pitch sur les 31s de calcul.
