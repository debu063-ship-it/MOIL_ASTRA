# Deploying MOIL ASTRA (single service on Render)

The whole app ships as **one Docker service**: FastAPI serves both the REST
API (`/api/v1/...`) and the built React dashboard. Judges get a single URL.

## One-time prep (do these now, ~5 minutes)

1. **Render account** — sign up at <https://render.com> with GitHub.
2. **Cesium ion token** — if your local `frontend/.env` has a token, reuse it;
   otherwise create a free one at <https://ion.cesium.com/tokens> (scope:
   *assets:read* is enough for this app). Copy the token value.

## Deploy (~5 clicks)

1. Render dashboard → **New + → Blueprint** → select repo `debu063-ship-it/MOIL_ASTRA`.
   Render reads `render.yaml` and pre-fills everything.
2. When prompted for **`VITE_CESIUM_ION_TOKEN`**, paste your Cesium token
   (it is stored as a secret — never in git).
3. Click **Apply**. First build takes ~8–10 min (Docker: npm ci + pip install).
4. Open `https://moil-astra.onrender.com` — dashboard and API docs
   (`/docs`) are served from the same URL.

Health check: `/api/v1/health`. Render uses it for zero-downtime deploys.

## Notes

- **Free plan**: the service sleeps after ~15 min idle; first visitor waits
  ~1–2 min while the instance cold-starts. A paid instance ($7/mo) never sleeps.
- **Auto-deploy**: every push to `main` redeploys automatically.
- **Database**: none needed — the API seeds its SQLite DB from `data/` at
  startup (`/tmp` on Render is ephemeral but rebuilt identically each deploy).
- **CORS**: not an issue — the browser talks to the same origin.

## Local verification (already done)

```bash
# build frontend, then serve everything from FastAPI
cd frontend && npm run build && cd ..
export VITE_CESIUM_ION_TOKEN=<your-token>
uvicorn backend.app.main:app --port 8600
# http://127.0.0.1:8600  → dashboard
# http://127.0.0.1:8600/api/v1/health → {"status":"ok",...}
```
