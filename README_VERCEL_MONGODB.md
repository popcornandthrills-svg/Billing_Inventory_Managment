# Vercel + MongoDB Setup

## 1) Environment variables in Vercel
Add these in Project -> Settings -> Environment Variables:

- `MONGODB_URI` = your full Atlas URI
- `MONGODB_DB_NAME` = `billing_inventory`
- `ADMIN_PASSWORD` = `admin123`

## 2) Deploy on Vercel
- Import this GitHub repo in Vercel
- Framework preset: `Other`
- Root directory: `./`
- Build command: leave empty
- Output directory: leave empty

Vercel will use `vercel.json` and `api/index.py`.

## 3) Migrate existing JSON data into MongoDB
Run locally once:

```powershell
cd "C:\Users\bhara\OneDrive\Desktop\Projects\BS5.6 - Edited v3"
setx MONGODB_URI "<your-atlas-uri>"
setx MONGODB_DB_NAME "billing_inventory"
py -3 scripts\migrate_json_to_mongo.py
```

Open new PowerShell after `setx`.

## 4) Verify deployment
- `https://<vercel-domain>/health`
- `https://<vercel-domain>/docs`

## Note
Current desktop app still reads local JSON. MongoDB + Vercel setup is now ready for API deployment and migration path.
