# Voice Call Setup Guide for Dan

**Goal:** Enable voice calls with Danswiz via phone

---

## Option 1: Twilio (Recommended - Most Reliable)

### Cost
- ~$1.15/month for phone number
- ~$0.013/min for calls
- Free trial includes ~$15 credit (enough for testing)

### Step 1: Create Twilio Account
1. Go to https://www.twilio.com/try-twilio
2. Sign up with email
3. Verify your phone number

### Step 2: Get a Phone Number
1. In Twilio Console → Phone Numbers → Buy a Number
2. Pick any US number (~$1.15/month)
3. Note the number (e.g., +14155551234)

### Step 3: Get Credentials
1. Dashboard shows: **Account SID** (starts with AC)
2. Dashboard shows: **Auth Token** (click to reveal)
3. Copy both

### Step 4: Give Me the Info
Tell me:
- Twilio phone number
- Account SID
- Auth Token
- Your phone number (so I know who to accept calls from)

I'll configure the rest.

---

## Option 2: Telnyx (Cheaper Long-term)

### Cost
- ~$1/month for number
- ~$0.007/min (cheaper than Twilio)

### Setup
Similar to Twilio - create account, get number, get API key.

---

## Option 3: Plivo (Budget Option)

### Cost
- ~$0.80/month for number
- ~$0.009/min

---

## What I Need to Install

Once you have credentials:

```bash
# Install ngrok for webhook tunneling
brew install ngrok

# Or use Tailscale Funnel (if you have Tailscale)
```

---

## How It Will Work

1. **You call the Twilio number** → Twilio forwards to OpenClaw
2. **OpenClaw transcribes** your speech → sends to me
3. **I respond** → text-to-speech → you hear my voice
4. **Real-time conversation** with ~1-2 second latency

---

## Alternative: Web-Based Voice (Free)

If phone costs are a concern, I could set up a **web interface** where you:
- Click a button to start voice chat
- Uses browser microphone
- No phone number needed
- Completely free

Let me know which option you prefer when you wake up!

---

*Prepared by Danswiz while you sleep 🦉*
