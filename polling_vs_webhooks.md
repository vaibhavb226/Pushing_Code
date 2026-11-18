# Polling vs Webhooks — Email Detection Strategy
## Sysco RFP AIQ — Microsoft Graph API

---

## What We Currently Have

The backend runs a **polling loop** every 15 seconds:

```
Server wakes up every 15 seconds
  → calls Graph API: GET /messages?$filter=isRead eq false
  → processes any new emails found
  → marks them as read
  → sleeps 15 seconds
  → repeats forever
```

This is defined in `services/email_poller.py` (line 27: `POLL_INTERVAL = 15`).

---

## Option 1 — Polling (Current)

### How it works
The server continuously wakes up on a timer and asks Microsoft: *"Do you have anything new?"*

### Advantages

| Advantage | Why it matters |
|---|---|
| Works on localhost | No public URL needed — works even on a developer's laptop |
| Simple and reliable | If the server restarts, it catches up automatically on next wake |
| No subscription management | Nothing expires, nothing needs renewing |
| Easy to debug | `/api/email/poll-now` triggers a manual poll instantly |
| Resilient to outages | Even if server was down for 10 minutes, next poll catches all missed emails |

### Disadvantages

| Disadvantage | Why it matters |
|---|---|
| 15 second delay | A supplier replies instantly but the team won't see it for up to 15 seconds |
| Wastes API quota | Calls Graph API every 15 seconds even when there are zero new emails |
| Scales poorly | With many mailboxes, every 15s means many wasted calls |

---

## Option 2 — Webhooks (Graph Change Notifications)

### How it works
Instead of your server asking Microsoft for emails, **Microsoft calls your server** the moment a new email arrives.

```
Supplier sends email
  → Microsoft receives it
  → Microsoft immediately POSTs to your webhook URL
  → Your server processes it instantly (< 1 second delay)
```

### Advantages

| Advantage | Why it matters |
|---|---|
| Real-time | Email is processed the instant it arrives — no 15s delay |
| No wasted API calls | Graph only contacts you when something actually happens |
| Scales well | Works the same whether you get 1 email/day or 1000 |
| Better for production | Industry standard approach for production systems |

### Disadvantages

| Disadvantage | Why it matters |
|---|---|
| Needs a public HTTPS URL | Graph API cannot reach `localhost` — requires a deployed server or ngrok tunnel in dev |
| Subscription expires every 3 days | Microsoft limits mail webhook subscriptions to 3 days max — must renew automatically |
| Validation handshake required | When registering, Graph sends a `validationToken` — your server must echo it back within 10 seconds or the subscription fails |
| Need a fallback anyway | If your server was down when an email arrived, the webhook is missed — you still need a catch-up poll |
| More complex setup | 3 new files + subscription lifecycle management |

---

## Cost

Graph API webhook subscriptions are **free** — included in M365 / Azure AD with no additional billing.

| Item | Cost | Notes |
|---|---|---|
| Graph API webhook subscriptions | **Free** | Part of M365 / Azure AD — no separate charge |
| Graph API polling calls | **Free** | But burns 5,760 quota calls/day even when idle |
| Public HTTPS server (production) | Hosting cost | Same server needed for any deployment — not webhook-specific |
| ngrok (local dev testing only) | Free tier / ~$8/mo | Only needed if testing webhooks locally; skip it in production |
| API quota savings (webhooks vs polling) | **Saves quota** | Webhooks: near-zero idle calls vs 5,760/day for polling |

**Bottom line:** Webhooks cost less to run because they save API quota. No new cost is introduced by switching — the hosting infrastructure is the same either way.

---

## Which Is Better?

### Verdict: **Webhooks for production, Polling for development**

| Scenario | Best Choice | Reason |
|---|---|---|
| Running locally on a laptop | **Polling** | No public URL available |
| Development / testing | **Polling** | Simpler, no ngrok needed |
| Deployed to Azure / AWS | **Webhooks** | Real-time + saves API quota |
| Proof of concept / demo | **Polling** | Already works, no extra setup |
| Production system with real users | **Webhooks** | 15s delay is noticeable in live use |

### For Sysco RFP AIQ right now:
The current **polling approach is the right choice** because:
1. The app is still in development / PoC phase
2. 15 seconds is acceptable for a bid management tool (not a live chat)
3. Zero additional infrastructure needed

**Switch to webhooks when** the app is deployed to a public URL and the team needs real-time email visibility.

---

## Files to Change If Switching to Webhooks

### Summary

| File | Change Type | What to do |
|---|---|---|
| `config.py` | Add setting | Add `WEBHOOK_URL` env var |
| `routers/webhooks.py` | **New file** | Webhook receiver endpoint |
| `services/email/msgraph_provider.py` | Extend | Add subscription create/renew/delete methods |
| `main.py` | Modify | Register webhook on startup, add renewal scheduler job |
| `services/email_poller.py` | Modify | Change to catch-up-only (run every 6 hours instead of 15s) |
| `.env` / `.env.example` | Add variable | `WEBHOOK_URL=https://your-domain.com` |

---

## Detailed Change Guide

### Change 1 — `config.py`

Add one new setting:

```python
# Add inside the Settings class
webhook_url: str = ""   # e.g. https://rfpaiq.sysco.com or ngrok URL in dev
```

**Why:** Graph API needs to know where to send notifications. This URL must be publicly reachable over HTTPS.

---

### Change 2 — New file: `routers/webhooks.py`

This is the most important new file. It handles two things:
1. **Validation** — When you register a subscription, Graph sends a test request first. Your server must echo the `validationToken` back within 10 seconds.
2. **Notifications** — When a new email arrives, Graph POSTs a notification here. You then fetch and process the actual email.

```python
# routers/webhooks.py (new file)
from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["webhooks"])

@router.post("/graph")
async def graph_webhook(
    request: Request,
    validationToken: str | None = Query(None),
):
    # Step 1: Validation handshake (must respond within 10 seconds)
    if validationToken:
        return PlainTextResponse(validationToken, media_type="text/plain")

    # Step 2: Real notification — fetch and process the new email
    body = await request.json()
    for notification in body.get("value", []):
        resource = notification.get("resource", "")
        # resource looks like: "Users/user-id/Messages/message-id"
        # Fetch the actual message and run through existing poll logic
        await _process_graph_notification(resource)

    return {"status": "ok"}
```

Register it in `main.py`:
```python
from routers.webhooks import router as webhooks_router
app.include_router(webhooks_router, prefix="/api/webhooks")
```

---

### Change 3 — `services/email/msgraph_provider.py`

Add three new methods to the existing `MsGraphEmailService` class:

**`create_subscription(webhook_url)`**
Registers your webhook URL with Microsoft Graph. Called once on startup.
```
POST https://graph.microsoft.com/v1.0/subscriptions
Body: {
  "changeType": "created",
  "notificationUrl": "https://your-domain.com/api/webhooks/graph",
  "resource": "users/{userId}/mailFolders/Inbox/messages",
  "expirationDateTime": "<now + 3 days>"
}
```

**`renew_subscription(subscription_id)`**
Extends an existing subscription before it expires. Must run every 2 days.
```
PATCH https://graph.microsoft.com/v1.0/subscriptions/{id}
Body: { "expirationDateTime": "<now + 3 days>" }
```

**`delete_subscription(subscription_id)`**
Cleans up the subscription when the server shuts down.
```
DELETE https://graph.microsoft.com/v1.0/subscriptions/{id}
```

---

### Change 4 — `main.py`

Two additions to the lifespan function:

**On startup:** Register the webhook subscription
```python
# In lifespan, after existing startup tasks
if settings.webhook_url and settings.email_provider == "msgraph":
    sub_id = await email_svc.create_subscription(settings.webhook_url)
    print(f"Graph webhook subscription created: {sub_id}")
```

**Add renewal job to APScheduler** (already used for auto-reminders):
```python
# Add alongside the existing "auto_reminders" job
scheduler.add_job(
    renew_graph_subscription,
    "interval",
    hours=48,          # renew every 2 days (subscription lasts 3 days max)
    id="graph_sub_renewal"
)
```

**On shutdown:** Delete the subscription
```python
# In the shutdown section of lifespan (after yield)
if sub_id:
    await email_svc.delete_subscription(sub_id)
```

---

### Change 5 — `services/email_poller.py`

Even with webhooks, keep a catch-up poll running — but much less frequently.

```python
# Change from:
POLL_INTERVAL = 15  # seconds — runs every 15 seconds

# Change to:
POLL_INTERVAL = 21600  # 6 hours — catch-up only, webhooks handle real-time
```

**Why keep it?** If your server was down for any reason (restart, deploy, crash), any emails that arrived during that window were not delivered to the webhook. The catch-up poll ensures nothing is missed.

---

## Side-by-Side Architecture

### Current (Polling)
```
┌─────────────────────┐         ┌──────────────────────┐
│   Sysco RFP AIQ     │         │   Microsoft Graph     │
│   Backend           │         │   API                 │
│                     │         │                       │
│  email_poller.py    │─────────▶  GET /messages        │
│  (every 15 seconds) │◀─────────  [list of emails]     │
│                     │         │                       │
└─────────────────────┘         └──────────────────────┘
```

### Proposed (Webhooks + Catch-up Poll)
```
┌─────────────────────┐         ┌──────────────────────┐
│   Sysco RFP AIQ     │         │   Microsoft Graph     │
│   Backend           │         │   API                 │
│                     │         │                       │
│  webhooks.py        │◀─────────  POST /api/webhooks/  │
│  (instant)          │         │  graph (new email)    │
│                     │         │                       │
│  email_poller.py    │─────────▶  GET /messages        │
│  (every 6 hours)    │◀─────────  [catch-up only]      │
│                     │         │                       │
└─────────────────────┘         └──────────────────────┘
```

---

## Implementation Effort Estimate

| Task | Effort |
|---|---|
| `config.py` — add WEBHOOK_URL | 5 minutes |
| `routers/webhooks.py` — new file | 1–2 hours |
| `msgraph_provider.py` — 3 new methods | 1–2 hours |
| `main.py` — startup/shutdown/renewal | 30 minutes |
| `email_poller.py` — change interval | 2 minutes |
| Testing with ngrok locally | 30 minutes |
| **Total** | **~4–5 hours** |

---

## Environment Variables Needed

Add to `.env`:
```
# Only needed if switching to webhooks
WEBHOOK_URL=https://your-public-domain.com

# For local development with ngrok:
# WEBHOOK_URL=https://abc123.ngrok.io
```

---

## Quick Decision Guide

```
Is the app deployed to a public HTTPS URL?
    │
    ├── NO  → Keep polling (current setup is fine)
    │
    └── YES → Do users need real-time email visibility?
                  │
                  ├── NO  → Keep polling (15s is acceptable)
                  │
                  └── YES → Switch to webhooks + catch-up poll
```
