# MongoDB + Vercel Deployment Setup

## 1. What was added
- `mongo_api.py`: MongoDB-backed FastAPI app.
- `api/index.py`: Vercel entrypoint.
- `vercel.json`: Vercel routing/runtime config.
- `requirements.txt`: Vercel Python dependencies.
- `scripts/migrate_json_to_mongo.py`: one-time JSON -> Mongo migration script.
- `.env.example`: required environment variables.

## 2. Required environment variables on Vercel
- `MONGODB_URI`
- `MONGODB_DB_NAME` (example: `billing_inventory`)
- `ADMIN_PASSWORD` (example: `admin123`)

## 3. One-time data migration
Run locally before production cutover:

```powershell
cd "C:\Users\bhara\OneDrive\Desktop\Projects"
$env:MONGODB_URI="your-mongodb-uri"
$env:MONGODB_DB_NAME="billing_inventory"
$env:ADMIN_PASSWORD="admin123"
py -3 -m pip install -r requirements.txt
py -3 scripts\migrate_json_to_mongo.py
```

## 4. Deploy to Vercel
1. Push latest code to GitHub.
2. In Vercel, import the GitHub repo.
3. Framework preset: `Other`.
4. Root directory: repo root (`Projects`).
5. Add env variables listed above.
6. Deploy.

## 5. Verify
- `GET /health`
- `GET /docs`
- `GET /dashboard/summary`
- `POST /auth/login`

