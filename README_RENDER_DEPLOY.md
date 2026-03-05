# Render Deployment Setup

## Important
This project is a desktop Tkinter app. Render cannot host the Windows GUI EXE directly.

This setup deploys a **web API layer** for your existing business data and logic.

## Files Added
- `render_api.py` : FastAPI service entrypoint
- `requirements-render.txt` : render-only dependencies
- `render.yaml` : Render Blueprint config

## What You Get After Deploy
- Health endpoint: `GET /health`
- Dashboard summary: `GET /dashboard/summary`
- Item summary: `GET /items/summary`
- Sales data: `GET /sales`
- Purchase data: `GET /purchases`
- Reconcile data: `POST /admin/reconcile` (supports API key)

## Deploy Steps (Render Blueprint)
1. Push this project to GitHub.
2. In Render: `New` -> `Blueprint`.
3. Select your repo.
4. Confirm service from `render.yaml`.
5. Set `ADMIN_API_KEY` in Render environment variables.
6. Deploy.

## Persistent Data
`render.yaml` mounts a Render disk at `/var/data` and sets `APP_BASE_DIR=/var/data`.
So JSON data files persist across deployments/restarts.

## Notes
- Desktop GUI users still run `main.exe` locally.
- Render deployment is for API access, integrations, monitoring, and remote reporting.
