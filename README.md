# Instagram Comment-to-DM Automation

A self-hosted, ManyChat-style automation tool for Instagram: when someone
comments a trigger keyword on one of your posts, this app automatically
(1) replies to the comment publicly and (2) sends the commenter a direct
message — all through the **official Instagram Graph API**. No Selenium, no
unofficial/private Instagram APIs.

## Tech stack

- **Backend:** Python + FastAPI
- **Database:** SQLite via SQLAlchemy (file-based; swap `DATABASE_URL` for Postgres later)
- **Frontend:** Vanilla HTML/CSS/JS dashboard, server-rendered with Jinja2 — no build tooling
- **Deployment:** Docker, with `railway.toml` (Railway) and `render.yaml` (Render)

## Project structure

```
/
├── main.py              # FastAPI app entry point
├── instagram.py         # Instagram Graph API client
├── models.py            # SQLAlchemy models
├── database.py           # DB session setup
├── routes/
│   ├── webhook.py       # Webhook endpoints
│   ├── dashboard.py     # Dashboard HTML routes
│   └── api.py           # REST API for campaigns/config
├── static/              # CSS + JS for dashboard
├── templates/           # Jinja2 HTML templates
├── .env.example         # Template for required env vars
├── Dockerfile
├── railway.toml
├── render.yaml
├── requirements.txt
└── README.md
```

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # fill in the values (see setup guide below)

uvicorn main:app --reload
```

Open `http://localhost:8000/dashboard` for the dashboard, or
`http://localhost:8000/health` for the health check.

Since Instagram must reach your webhook over the public internet, use a
tunnel for local development, e.g.:

```bash
ngrok http 8000
```

and use the printed `https://...ngrok-free.app` URL as your webhook base URL
below.

---

## Instagram API setup (step-by-step)

You need a Facebook Developer App connected to your Instagram account before
any of this works. Follow these steps in order.

### 1. Convert your Instagram account to a Business or Creator account

1. Open the Instagram app → **Settings → Account type and tools**.
2. Choose **Switch to professional account**, then pick **Business** or
   **Creator**.
3. Link it to a **Facebook Page** you manage (create one if you don't have
   one) — the Graph API operates through that Page/Instagram link.

### 2. Create a Facebook Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com) and log
   in with the Facebook account that manages the Page from step 1.
2. **My Apps → Create App**.
3. Choose the **Business** app type.
4. Give it a name (e.g. "My IG Automation") and create it.

### 3. Add the Instagram Graph API product

1. In your new app's dashboard, click **Add Product**.
2. Find **Instagram Graph API** (sometimes listed as **Instagram**) and
   click **Set Up**.
3. Under **App Settings → Basic**, note your **App ID** and **App Secret** —
   the App Secret goes into `FACEBOOK_APP_SECRET` in `.env`.

### 4. Add the required permissions

1. Go to **App Review → Permissions and Features**.
2. Request/add:
   - `instagram_manage_comments`
   - `instagram_manage_messages`
   - `instagram_basic`
   - `pages_show_list` and `pages_read_engagement` (needed to resolve your
     Page ↔ Instagram account link)
3. While your app is in **Development mode**, these permissions work for
   Instagram accounts added as **testers/admins** on the app (Roles →
   Roles) without needing App Review. To use the app with arbitrary public
   accounts you must submit for **App Review** with a screen-recording of
   the use case.

### 5. Generate a long-lived User Access Token

1. Open **Graph API Explorer**
   (developers.facebook.com/tools/explorer), select your app.
2. Click **Generate Access Token**, log in, and grant the permissions from
   step 4.
3. This gives you a **short-lived token (~1 hour)**. Exchange it for a
   **long-lived token (~60 days)**:

   ```bash
   curl -i -X GET "https://graph.facebook.com/v19.0/oauth/access_token?
   grant_type=fb_exchange_token&
   client_id=YOUR_APP_ID&
   client_secret=YOUR_APP_SECRET&
   fb_exchange_token=YOUR_SHORT_LIVED_TOKEN"
   ```

4. Paste the resulting long-lived token into the dashboard **Settings**
   page (or `INSTAGRAM_ACCESS_TOKEN` in `.env`).

**Refreshing before it expires (tokens last 60 days):** call the same
`fb_exchange_token` endpoint again using the *current* still-valid
long-lived token as `fb_exchange_token` — Facebook will return a new
60-day token. Do this periodically (e.g. every 45 days) before the old one
expires; there's no way to refresh an already-expired token, so you'll have
to regenerate a fresh token from Graph API Explorer if it lapses.

### 6. Configure the webhook

1. In your app dashboard, go to **Webhooks** (or **Products → Webhooks**).
2. Click **Subscribe to this object** for **Instagram**, and subscribe to
   the **`comments`** field.
3. Set the **Callback URL** to:

   ```
   https://YOUR_DOMAIN/webhook/instagram
   ```

4. Set the **Verify Token** to the same value you put in
   `WEBHOOK_VERIFY_TOKEN` in `.env`.
5. Click **Verify and Save** — Facebook will send a `GET` request to
   `/webhook/instagram` with a challenge; this app answers it automatically
   as long as `WEBHOOK_VERIFY_TOKEN` matches.
6. Under **App Settings → Basic**, also confirm your **App Secret**
   matches `FACEBOOK_APP_SECRET` in `.env` — every webhook POST is signed
   with it via the `X-Hub-Signature-256` header, and this app rejects
   anything that doesn't verify.

### 7. Get a Post ID for a specific Instagram post/video

1. In **Graph API Explorer**, with your token selected, query:

   ```
   GET /{ig-business-account-id}/media
   ```

   This returns a list of your recent posts with their `id`.
2. Alternatively, query a single post if you already have its shortcode
   via the public `oEmbed`/permalink, or use:

   ```
   GET /{ig-business-account-id}/media?fields=id,caption,timestamp,permalink
   ```

   and match the post by its caption or permalink.
3. Copy the `id` value — that's the **Post ID** you enter when creating a
   Campaign in the dashboard. Pasting it there also auto-fetches a preview
   thumbnail/caption.

---

## Core features

- **Webhook receiver** (`POST /webhook/instagram`): verifies
  `X-Hub-Signature-256`, checks each comment event against active
  campaigns (post ID match + case-insensitive partial keyword match), and
  fires the reply + DM. Each `comment_id` is recorded in
  `ProcessedComment` so retried webhook deliveries never double-fire.
- **Instagram API layer** (`instagram.py`): `reply_to_comment()`,
  `send_dm()`, `send_private_reply_to_comment()` (fallback), and
  `get_post_details()`. Every call is logged, and rate-limit/5xx errors are
  retried with exponential backoff.
- **Dashboard** (`/dashboard`):
  - **Settings** — save your access token, Page ID, and Instagram Business
    Account ID.
  - **Campaigns** — create/edit/delete/toggle campaigns: a Post ID
    (auto-fetches a preview on blur), comma-separated trigger keywords, a
    public comment reply, and a DM message, with an active/inactive badge.

## Environment variables

See `.env.example`:

```
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=
FACEBOOK_APP_SECRET=
WEBHOOK_VERIFY_TOKEN=
DATABASE_URL=sqlite:///./app.db
```

`INSTAGRAM_ACCESS_TOKEN` and `INSTAGRAM_BUSINESS_ACCOUNT_ID` are optional
seed values — on first boot they're copied into the database if no config
exists yet. From then on, whatever you save in the dashboard **Settings**
page is authoritative. `FACEBOOK_APP_SECRET` and `WEBHOOK_VERIFY_TOKEN` are
only ever read from the environment (never stored in the DB or shown in the
frontend).

## Important constraint: who can you actually DM?

Instagram's Graph API only allows a business account to send a DM
(`POST /{ig-business-account-id}/messages`) to a user who has **messaged
the business within the last 24 hours**, *or* if your app has been granted
`instagram_manage_messages` with an **approved use case** for messaging
users who haven't messaged first (e.g. "Comment to DM" automation, which is
exactly this use case, but Meta reviews it manually).

Two practical implications:

1. **Apply for App Review** on `instagram_manage_messages` and describe
   this exact comment-to-DM flow as your use case — include a screen
   recording of a comment triggering a reply + DM in Development mode with
   a tester account.
2. **Until approved**, this app automatically falls back to Instagram's
   **private reply to a comment** (`POST /{comment-id}/private_replies`),
   which Meta explicitly allows without the 24-hour window restriction and
   is the officially sanctioned way to "DM" a commenter. You'll see this
   fallback triggered in the logs if a direct `send_dm` call fails.

## Deployment

### Docker

```bash
docker build -t ig-automation .
docker run -p 8000:8000 --env-file .env ig-automation
```

### Railway

Push this repo to Railway — `railway.toml` configures the Docker build,
start command, and `/health` health check automatically. Set the four
secret env vars in the Railway dashboard.

### Render

Use the included `render.yaml` (Render Blueprint) — it provisions a Docker
web service with a `/health` check and a persistent disk. Set the secret
env vars (`INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`,
`FACEBOOK_APP_SECRET`, `WEBHOOK_VERIFY_TOKEN`) in the Render dashboard, as
they're marked `sync: false`.

## Security notes

- Webhook signature verification (`X-Hub-Signature-256`) is enforced on
  every incoming POST to `/webhook/instagram`; requests with a missing or
  invalid signature are rejected with `403`.
- `FACEBOOK_APP_SECRET` and `WEBHOOK_VERIFY_TOKEN` live only in `.env` /
  your host's secret manager — never in the database or served to the
  frontend.
- The Settings page never echoes back a saved access token — it only shows
  whether one is set.

## Health check

`GET /health` → `{"status": "ok"}` — used by Railway/Render/Docker health
checks.
