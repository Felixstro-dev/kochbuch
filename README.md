# Kochbuch — Recipe Manager

Self-hosted recipe manager: FastAPI backend + SvelteKit frontend, single Docker image, multi-arch (`amd64` / `arm64`).

## What it does

- Browse recipes from web / local sources
- View ingredients with portion scaling and checkboxes
- Add selected ingredients to a Bring! shopping list (with duplicate merge, partial failure handling)
- Health checks: `/api/v1/health` and `/api/v1/health/shopping-list`

## Setup (3 steps)

1. Copy config: `cp .env.example .env`
2. Edit `.env`: set `SECRET_KEY` (`openssl rand -hex 32`) and optional `BRING_EMAIL` + `BRING_PASSWORD` if you use the shopping-list feature.
3. Run: `./deploy.sh` (builds + starts + quick health check)

Open `http://localhost:8080`. First visit creates the admin account (unless you set `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`).

## Configure

All settings live in `.env`. Key variables:

- `SECRET_KEY` — required in production (session / image signing)
- `DATA_DIR` — SQLite DB + recipe images (persist with Docker volume)
- `BRING_EMAIL` / `BRING_PASSWORD` — for shopping-list integration (optional)
- `FRAME_ANCESTORS` — if embedding in Home Assistant iframe (no hardcoded hosts; configure explicitly)
- `CORS_ORIGINS`, `EMBED_PUBLIC`, `AUTO_MIGRATE`

No secrets are hardcoded in source files.

## Use

- **Recipe view**: ingredients scaled to portions; checkboxes for tracking; button opens bottom-sheet selection for shopping list.
- **Shopping list**: choose ingredients, confirm; duplicates are merged (same unit) or kept separate; errors are shown in German with retry options.
- **Health**: `curl http://localhost:8080/api/v1/health`
- **Update**: `./deploy.sh` pulls / rebuilds / restarts.

## Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

Or manually:

```bash
docker compose build --pull
docker compose up -d
```

The `.env` file is read automatically by `docker-compose.yml`. No hardcoded URLs or tokens in the compose file.

## Development

```bash
# Backend
cd backend && uv sync --frozen --no-dev
uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend && npm ci && npm run dev
```

## Tests

```bash
cd backend
pytest tests/test_shopping_list.py -v
```

Note: full integration with `bring_api` requires that package installed; syntax and logic are validated.

## Commit / Push (workflow)

```bash
git add -A
git commit -m "feat: shopping selection + error handling + deploy simplification"
git push origin main
```

The CI will build and publish to `ghcr.io/felixstro-dev/kochbuch:latest`.

## License

MIT — see `LICENSE`.
