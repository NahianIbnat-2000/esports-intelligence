# Deployment: Supabase + Render + Vercel (all free tiers)

```
Browser ──► Vercel (Next.js website) ──► Render (FastAPI API) ──► Supabase (PostgreSQL)
```

Free-tier limits that matter (checked November 2026; check again):
- Supabase free: 500 MB database; the project goes read-only above that and pauses after
  a week without traffic. This project's database is about 360 MB after a full load, so
  always reload with `make reload` (drops tables first) instead of `make all`.
- Render free web service: 512 MB RAM, spins down after 15 minutes without traffic and
  takes up to a minute to wake up. The first page load after a pause is slow.
- Vercel hobby: fine for this site.

## 1. GitHub

The repository must be its own Git repository. In the project folder:

```bash
git init -b main
git add .
git commit -m "Esports Intelligence v1.0"
```

Check before pushing: `git status` must not list `.env`, `data/raw`, `data/processed` or
`frontend/node_modules` (they are git-ignored). It should list
`machine_learning/models/artifacts/<version>/` (model coefficients, no source data); the
hosted API needs these files.

Create an empty repository on github.com (no README), then:

```bash
git remote add origin https://github.com/<your-user>/esports-intelligence.git
git push -u origin main
```

## 2. Supabase (database)

1. supabase.com → New project. Choose a region close to you and a database password with
   letters and digits only (no `@ : / #`), and save it.
2. Project → **Connect** → choose the **Session pooler** connection string (it works on
   IPv4 networks such as Render's). It looks like
   `postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`.
   Replace `<PASSWORD>`. The app converts `postgresql://` to the right driver itself.

## 3. Load the data into Supabase (from your computer)

With Docker running, in the project folder (Git Bash):

```bash
MSYS_NO_PATHCONV=1 docker compose run --rm -e DATABASE_URL="<supabase session pooler URL>" \
  api make reload FILES="/app/data/raw/oracles_elixir/*.csv"
```

This takes longer than locally (the data travels over the internet), roughly 10 to 20
minutes. It trains the models again and writes new files to
`machine_learning/models/artifacts/`. Commit and push those:

```bash
git add machine_learning/models/artifacts
git commit -m "Model artifacts"
git push
```

## 4. Render (API)

1. render.com → New → **Blueprint** → select the GitHub repository. Render reads `render.yaml`.
2. Set the two secret variables when asked:
   - `DATABASE_URL` = the Supabase session pooler URL
   - `CORS_ORIGINS` = `http://localhost:3000` for now (updated in step 6)
3. Deploy. When it is live, open `https://<service>.onrender.com/api/v1/health`; it should
   show `"database": "ok"`. `/api/v1/predictions/models` should list three models with
   status `trained`.

## 5. Vercel (website)

1. vercel.com → Add New → Project → import the repository.
2. Root Directory: `frontend`.
3. Environment variable: `NEXT_PUBLIC_API_URL` = `https://<service>.onrender.com` (no slash at the end).
4. Deploy. Note the address, e.g. `https://esports-intelligence.vercel.app`.

## 6. Connect them

In Render → the service → Environment, set
`CORS_ORIGINS=https://esports-intelligence.vercel.app` (your exact Vercel address), save,
and let it redeploy. Open the Vercel address: the Overview should show 75,830 games.

## Updating later

New data: put the new CSV in `data/raw/oracles_elixir/`, run step 3 again (`make reload`),
then commit and push the new artifacts. Render redeploys automatically on push.
Code changes: push to GitHub; Render and Vercel redeploy automatically.

## Security checklist

- `.env` is git-ignored; secrets live only in the Render and Vercel dashboards.
- Provider keys are read only by the backend and never returned by any endpoint.
- CORS is limited to `CORS_ORIGINS`; methods GET and POST only.
- `npm audit --omit=dev` reports 0 vulnerabilities in the website's runtime packages.
  Remaining advisories are in build and test tools (glob matching in Tailwind 3 and Vite);
  the advisory has no patched version yet, and those tools do not run in the deployed site.
