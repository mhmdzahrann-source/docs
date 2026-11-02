# Instagram Comment-to-DM Automation + WhatsApp Reservation Bot

> **New:** a 24/7 WhatsApp auto-reply bot that takes table reservations in
> Arabic and English — see [WhatsApp reservation bot](#whatsapp-reservation-bot).

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
├── whatsapp.py          # WhatsApp Cloud API client
├── booking.py           # WhatsApp reservation conversation flow (AR/EN)
├── models.py            # SQLAlchemy models
├── database.py           # DB session setup
├── routes/
│   ├── webhook.py       # Instagram webhook endpoints
│   ├── whatsapp_webhook.py  # WhatsApp webhook (auto-replies)
│   ├── whatsapp_api.py  # REST API for reservations / WhatsApp settings
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
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=
DATABASE_URL=sqlite:///./app.db
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
BUSINESS_NAME=Khayal
OWNER_WHATSAPP_NUMBER=
BUSINESS_TIMEZONE=Asia/Riyadh
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

## WhatsApp reservation bot

Answers every message to your WhatsApp Business number automatically, day
and night, and takes table bookings:

```
Customer: مرحبا
Bot:      أهلاً وسهلاً في Khayal 🌙  [حجز طاولة] [المواعيد والموقع] [التحدث مع موظف]
Customer: (taps حجز طاولة)
Bot:      على أي اسم الحجز؟            → محمد
Bot:      أي يوم؟ [اليوم] [بكرة]       → بكرة / الجمعة / 15/11
Bot:      كم الساعة؟                   → 9 م / 21:00
Bot:      كم عدد الأشخاص؟              → ٤
Bot:      تأكيد الحجز 📋 …              [تأكيد ✅] [تعديل ✏️] [إلغاء]
Bot:      تم استلام طلب الحجز ✅ سنرسل لك تأكيداً قريباً
You:      (phone alert) 🔔 New booking request #12 … → Confirm in dashboard
Bot:      تم تأكيد حجزك في Khayal ✅
```

- **Arabic + English**, picked automatically from the customer's message.
  Understands Arabic-Indic digits (٤), "بكرة"/"tomorrow", weekday names,
  dates like `15/11`, and times like `9 م`, `9pm`, `21:00`.
- **You stay in control:** bookings arrive as *pending*. Confirm or decline
  them at **Dashboard → Reservations**, and the customer gets a WhatsApp
  message either way.
- **Owner alerts:** every new booking is sent to your own WhatsApp number.
- **Hours & location:** answered instantly from what you enter in Settings.
- **Talk to staff:** the bot pauses for that customer (up to 12 hours) and
  the chat appears under *Chats waiting for staff*, where you can reply from
  the dashboard and hand it back to the bot.
- Type **menu / القائمة** to restart or **cancel / إلغاء** to stop a booking
  at any time. Validation rejects past dates/times, dates more than 60 days
  out, and parties above your max size (those are pointed to staff).
- Meta's retried webhook deliveries are de-duplicated, so nobody is ever
  booked twice.

### Setup

1. **Meta app + WhatsApp.** At [developers.facebook.com](https://developers.facebook.com)
   → **My Apps → Create App → Business**, then add the **WhatsApp**
   product. (You can use the same app as the Instagram automation.)
2. **Phone number.** Under **WhatsApp → API Setup**, either use the free
   test number (add your own phone under "To" to receive messages) or
   **Add phone number** for your real business number. Copy the
   **Phone number ID** — that goes in Settings.
   - A number registered on the Cloud API normally can't also be used in
     the WhatsApp / WhatsApp Business phone app. If you need both, check
     whether Meta's *coexistence* onboarding is available for your number.
3. **Permanent access token.** In [business.facebook.com](https://business.facebook.com)
   → **Settings → Users → System users → Add** (Admin) → **Add assets**
   (your app, full control) → **Generate new token** with
   `whatsapp_business_messaging` and `whatsapp_business_management`.
   The temporary token on the API Setup page expires after 24 hours.
4. **Deploy this app** (see [Deployment](#deployment)) so it has a public
   `https://` URL.
5. **Webhook.** In your app → **WhatsApp → Configuration → Edit**:
   - Callback URL: `https://YOUR_DOMAIN/webhook/whatsapp`
   - Verify token: the value of `WEBHOOK_VERIFY_TOKEN`
   - Then under **Webhook fields**, **Subscribe** to `messages`.
   Make sure `FACEBOOK_APP_SECRET` is that app's secret — every POST is
   signature-checked.
6. **Settings page** (`/dashboard/settings` → *WhatsApp reservation bot*):
   paste the token and phone number ID, and fill in your business name,
   alert number, opening hours, location and max party size.
7. Send "hi" to your business number from your phone — the menu should
   come back within seconds.

### WhatsApp rules worth knowing

- **24-hour window.** A business can send free-form messages only within
  24 hours of the customer's last message. All bot replies happen inside
  that window. Confirming/declining a booking much later can fail; the
  dashboard tells you when it does, and you can call/WhatsApp the customer
  via the number link. (Using an approved *template* for confirmations is
  the long-term fix.)
- **Owner alerts** follow the same rule: they only reach your number if
  *your* number messaged the business number in the last 24 hours. Send it
  a quick "hi" each morning, or just watch the Reservations page (it
  refreshes every 30 seconds).
- **Pricing.** Replies to customers who message you first are
  service conversations; check Meta's current WhatsApp pricing for your
  country.
- Customers must message you first or have opted in. Don't use this
  number for unsolicited bulk messages, or Meta will lower its quality
  rating and limits.

### Bot settings via environment

`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `BUSINESS_NAME` and
`OWNER_WHATSAPP_NUMBER` seed the settings on first boot (the dashboard is
authoritative afterwards). `BUSINESS_TIMEZONE` (default `Asia/Riyadh`)
decides what "today"/"tomorrow" mean and which times have already passed.

## Deployment

### Docker

```bash
docker build -t ig-automation .
docker run -p 8000:8000 --env-file .env ig-automation
```

### Railway

Push this repo to Railway — `railway.toml` configures the Docker build,
start command, and `/health` health check automatically. Set the secret
env vars in the Railway dashboard. Add a **Volume** mounted at `/app/data`
and set `DATABASE_URL=sqlite:////app/data/app.db` — otherwise the SQLite
file (including all reservations) is wiped on every redeploy.

### Render

Use the included `render.yaml` (Render Blueprint) — it provisions a Docker
web service with a `/health` check and a persistent disk. Set the secret
env vars (`INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`,
`FACEBOOK_APP_SECRET`, `WEBHOOK_VERIFY_TOKEN`, `DASHBOARD_PASSWORD`, `WHATSAPP_ACCESS_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `OWNER_WHATSAPP_NUMBER`) in the Render
dashboard, as they're marked `sync: false`. The database lives on the
persistent disk (`/app/data/app.db`) so reservations survive redeploys.

## Security notes

- **Dashboard login:** set `DASHBOARD_PASSWORD` (and optionally
  `DASHBOARD_USERNAME`, default `admin`). The dashboard and `/api/*` then
  require that login; your browser prompts for it once. The webhooks and
  `/health` stay public so Meta and your host can reach them. Without a
  password the app logs a warning on startup and the dashboard is open to
  anyone who knows its URL — never deploy it like that.

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
