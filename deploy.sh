#!/usr/bin/env bash
set -euo pipefail
# Einfaches Deployment-Skript für Kochbuch
# Voraussetzungen: Docker + Docker Compose, .env vorhanden

echo "=== Kochbuch Deploy ==="

if [ ! -f .env ]; then
  echo "FEHLER: .env nicht gefunden. Kopiere .env.example -> .env und passe an."
  exit 1
fi

echo "Build & Start ..."
docker compose build --pull
docker compose up -d --remove-orphans

echo "Healthcheck ..."
sleep 2
curl -sf http://localhost:8080/api/v1/health > /dev/null || echo "WARNUNG: Healthcheck nicht erreichbar (noch nicht bereit?)"

echo "Fertig. App unter http://localhost:8080"
echo "Logs: docker compose logs -f kochbuch"
