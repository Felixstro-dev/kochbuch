# Kochbuch

Selbst gehosteter Rezeptmanager: FastAPI-Backend + SvelteKit-Web-UI in einer
Docker-Image, lauffähig auf amd64 und arm64 (Raspberry Pi).

## Image

```
ghcr.io/felixstro-dev/kochbuch:latest
```

Multi-Arch (`linux/amd64`, `linux/arm64`), gebaut von GitHub Actions.

## Starten mit Docker Compose

```bash
# .env mit einem echten Secret anlegen
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env

docker compose up -d
```

Danach: <http://localhost:8080> – beim ersten Aufruf das Admin-Konto anlegen.

## Starten mit Dokploy (Raspberry Pi)

1. **Repository** in Dokploy anlegen, Quelle: dieses GitHub-Repository.
2. Typ **Compose** wählen und die `docker-compose.yml` aus diesem Repo verwenden
   (oder unten einfügen).
3. In den **Environment-Variablen** setzen:

   | Variable | Wert |
   |---|---|
   | `SECRET_KEY` | `openssl rand -hex 32` (zufällig erzeugen!) |
   | `EMBED_PUBLIC` | `true` |
   | `CORS_ORIGINS` | `*` |
   | `FRAME_ANCESTORS` | `'self' http://homeassistant.local:8123 http://<HA-IP>:8123 https://*.duckdns.org` |

4. **Deploy** drücken – Dokploy pulled das Image und startet den Container.
5. Web-UI unter `http://<Pi-IP>:8080` öffnen und Admin-Konto anlegen.

Für Home Assistant als iframe:

```yaml
type: iframe
url: "http://<Pi-IP>:8080/?embed=1"
title: Kochbuch
aspect_ratio: "100%"
```

`FRAME_ANCESTORS` muss die Adresse enthalten, von der aus HA eingebettet wird
(sonst blockiert der Browser das iframe).

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|---|---|---|
| `SECRET_KEY` | dev-insecure… | **Pflicht** zum Produktivbetrieb: signiert Bilder/Session-Tokens |
| `DATA_DIR` | `/app/data` | SQLite-DB + Rezeptbilder (Volume!) |
| `FRONTEND_DIR` | `/app/frontend` | Wird gesetzt, damit die Web-UI ausgeliefert wird |
| `EMBED_PUBLIC` | `true` | Lesezugriff ohne Anmeldung (Karte/iframe) |
| `CORS_ORIGINS` | `*` | Komma-getrennte erlaubte Originen |
| `FRAME_ANCESTORS` | `'self'` | Wer die Seite einbetten darf (iframe) |
| `AUTO_MIGRATE` | `true` | Alembic-Migrationen beim Start ausführen |
| `DOKPLOY_URL` | leer | URL deines Dokploy-Dashboards – wenn gesetzt, zeigt der Update-Toast einen „Zu Dokploy"-Button |
| `UPDATE_CHECK_ENABLED` | `true` | Stündlicher Update-Check gegen GHCR (nur mit eingebranntem `GIT_SHA`, also im Docker-Image) |
| `TZ` | `Europe/Berlin` | Zeitzone |

`GIT_SHA` wird vom CI automatisch ins Image gebrannt – nicht manuell setzen.

## Updates

Der Prüf-Ablauf:

1. Der CI baut bei jedem Push auf `main` ein neues Image und vergleichsweise
   das Tag `sha-<kurz>`; `latest` zeigt auf den neuesten Commit.
2. Das laufende Backend vergleicht stündlich den Digest von `latest` mit dem
   Digest seines eigenen `sha-`Tags (anonym, kein Login nötig).
3. Gibt es ein neues Bild, erscheint in der Web-UI ein Toast mit
   „Zu Dokploy"-Button. Der öffnet dein Dokploy-Dashboard, dort den
   **Update-Button** der App – Dokploy zieht das neue Image und erzeugt den
   Container neu (Volume und Daten bleiben erhalten).

Manuell prüfen geht auch ohne Wartezeit: `POST /api/v1/system/update-check`
(als Admin), oder in den Entwicklertools das Layout neu laden – der Check
läuft beim Start des Backends einmal sofort.

## Daten migrieren (bestehende SQLite-DB)

Die Datenbank liegt im Docker-Volume `kochbuch-data`. Um eine vorhandene
`kochbuch.db` zu übernehmen:

```bash
docker compose down
docker run --rm -it -v kochbuch_kochbuch-data:/data -v "$PWD:/src" alpine \
  cp /src/kochbuch.db /data/kochbuch.db
docker compose up -d
```

(Wenn das Volume anders heißt: `docker volume ls | grep kochbuch`.)

## Lokal bauen

```bash
docker build -t kochbuch:local .
docker run --rm -p 8080:8080 -e SECRET_KEY=test kochbuch:local
```

Auf einem Arm-Rechner baut das Image automatisch als arm64 – auf einem
x86-PC wird für arm64 QEMU benötigt (oder man lässt es die GitHub Actions
bauen, wie hier konfiguriert).

## Entwickeln

```bash
# Backend
cd backend && uv sync --frozen --no-dev
uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend && npm ci && npm run dev   # Proxy auf 127.0.0.1:8080
```

Lovelace-Karte für Home Assistant: eigenes Repo
[Felixstro-dev/kochbuch-recipe-card](https://github.com/Felixstro-dev/kochbuch-recipe-card).
