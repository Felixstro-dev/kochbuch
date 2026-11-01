#!/usr/bin/env bash
set -euo pipefail
# Einfaches Deployment-Skript für Kochbuch
# Setzt GIT_SHA automatisch aus git, baut und startet.

echo "=== Kochbuch Deploy ==="

if [ ! -f .env ]; then
  echo "FEHLER: .env nicht gefunden. Kopiere .env.example -> .env und passe an."
  exit 1
fi

export GIT_SHA=${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)}
echo "Verwende GIT_SHA=${GIT_SHA}"

echo "Build & Start ..."
docker compose build --pull --build-arg GIT_SHA=${GIT_SHA}
docker compose up -d --remove-orphans

echo "Healthcheck ..."
sleep 2
curl -sf http://localhost:8080/api/v1/health > /dev/null || echo "WARNUNG: Healthcheck nicht erreichbar (noch nicht bereit?)"

echo "Fertig. App unter http://localhost:8080"
echo "GIT_SHA=${GIT_SHA} | Logs: docker compose logs -f kochbuch"
