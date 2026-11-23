# Deploying LeadOps

The database runs on Neon, the backend on Render and the site on Vercel. All three have free plans, and each needs
its own account. Allow about 30 minutes. Do the steps in this order, because each one needs a value from the one before.

| Part | Service | What you need from it |
|---|---|---|
| Database | Neon | the connection string |
| Backend | Render | the API address, such as `https://leadops-api.onrender.com` |
| Site and dashboard | Vercel | the public address to share |

## The live deployment

LeadOps has been live since 23 Nov 2026. Claude set it up with the three services' command-line tools, using the same
settings as the steps below.

| Part | Where | Address |
|---|---|---|
| Site and dashboard | Vercel project `leadops` | https://leadops-henna.vercel.app |
| Backend | Render web service `leadops-api` (Singapore, free plan) | https://leadops-api-pudl.onrender.com |
| Database | Neon project `leadops` (Singapore, Postgres 18) | its connection string is kept only in Render's settings |

- The dashboard passcode is in Render: open `leadops-api`, then **Environment**, then `DASHBOARD_PASSCODE`.
- No LLM key is set, so the assistant answers from templates and nothing is billed. To use a real LLM, add one key in
  the same **Environment** tab (see "The LLM" in the README) and save; Render then redeploys the backend with it.

### Putting a change live

Neither service deploys by itself when `main` changes, because neither is connected to GitHub. After pushing:

- **Backend:** in Render, open `leadops-api` and choose **Manual Deploy**, then **Deploy latest commit**. With the
  [Render CLI](https://render.com/docs/cli): `render deploys create <service ID> --wait` (`render services` shows the ID).
- **Site:** from `frontend/`, run `npx vercel login` and `npx vercel link --yes --project leadops` once on your computer,
  then `npx vercel deploy --prod` for each release.
- To deploy on every push instead, connect the GitHub repository in each service's settings (for Vercel,
  `npx vercel git connect`).

## 1. The database (Neon)

1. Sign up at https://neon.tech and create a project. Pick **Singapore** as the region, the closest to India.
2. Copy the **connection string**. It starts with `postgresql://` and ends with `sslmode=require`.

The backend creates its tables the first time it starts.

## 2. The backend (Render)

1. Sign up at https://render.com with the GitHub account that can see this repository.
2. Choose **New**, then **Blueprint**, and pick the repository. Render reads `render.yaml`.
3. When it asks for values, paste the Neon connection string into `DATABASE_URL`. Leave the LLM keys empty, or paste one
   key to use a real LLM (see "The LLM" in the README).
4. Press **Apply** and wait for the build to finish, which takes a few minutes.
5. Open `https://YOUR-API.onrender.com/health`. You should see `"status": "ok"`, and `"model"` should start with `lgbm-`.
6. Under **Environment**, copy the generated `DASHBOARD_PASSCODE`. The sales team needs it to open the dashboard.

If Render says Python 3.14.6 isn't available, set `PYTHON_VERSION` to the newest 3.14 version it offers.

## 3. The site and dashboard (Vercel)

1. Sign up at https://vercel.com with the same GitHub account.
2. Choose **Add New**, then **Project**, and import the repository.
3. Set **Root Directory** to `frontend`. Vercel then picks up `frontend/vercel.json`.
4. Under **Environment Variables**, add `VITE_API_URL` with your Render address and no slash at the end.
5. Press **Deploy**.

## 4. Check that it works

Open your Vercel address and go through this list:

- [ ] Your Vercel address opens the LeadOps front page, and **Try the live demo** opens the property site at `/demo`.
- [ ] The privacy banner appears on the demo site. Press **Accept**.
- [ ] Ask the assistant "What's the payment plan at Aranya Courtyard?" and get an answer from the brochure.
- [ ] `/dashboard` asks for the passcode and opens with it. The status at the top right says **Live**.
- [ ] Your visit appears in the Visitors table within a few seconds.
- [ ] **Simulate traffic** sorts the visitors and ends with a scoreboard. **Clear simulated visitors** removes them.
- [ ] `/dashboard/analytics` shows the funnel.

**Run a real bot** stays switched off on the deployed server, because Playwright isn't installed there. To show a real
bot, run the backend and the site on the presenter's laptop.

## Before you present

- **Wake the backend first.** Render's free plan sleeps after about 15 minutes without traffic, and the first request
  then takes up to a minute. Open `/health` a few minutes before you start, and keep the dashboard open.
- **Have a backup.** Keep the local setup from the README working on the presenting laptop, and keep the recorded demo video
  ready in case the venue's internet fails.
- **Clear old rehearsals.** Press **Clear simulated visitors** before you go on stage.

## Good to know

- **Memory:** the backend used about 270 MB during a 250-visitor simulated run on Postgres, inside the free plan's 512 MB.
- **One server process only:** live dashboard updates are kept in memory, so don't add workers or a second instance.
- **Tests on Postgres:** to run the backend tests against Postgres, set `TEST_DATABASE_URL` to an empty database.
- **Render CLI in Git Bash on Windows:** set `MSYS_NO_PATHCONV=1` first. Otherwise Git Bash turns an argument such as
  `/health` into `C:/Program Files/Git/health`, and Render never marks the deploy live.
- **Limit who can call the API:** `CORS_ORIGINS` is `*` because the tracking script is meant to run on any website. Dashboard
  routes are protected by the passcode either way.
