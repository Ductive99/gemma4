#!/bin/bash
echo "🟢 Préparation de l'environnement Cassandra..."

# 1. Vérification d'Ollama
if ! pgrep -x "ollama" > /dev/null
then
    echo "⚠️ Ollama n'est pas actif. Lancement en arrière-plan..."
    ollama serve > /dev/null 2>&1 &
    sleep 3
else
    echo "✅ Ollama tourne déjà."
fi

# 2. Activation de l'environnement virtuel
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Venv activé."
else
    echo "❌ Erreur : dossier venv introuvable."
    exit 1
fi

# 3. Lancement plein écran
clear
python3 cassandra_demo.py
