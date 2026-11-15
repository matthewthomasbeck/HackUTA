# Eric: set up the Claude API on the Vultr server

Calypso⁻¹ uses Claude as its LLM. The backend and the Chert agent both read **one** API key from the server's `.env`:
- **Claude Sonnet** for quality work: pulling the name, relationship and facts out of setup-call transcripts, and writing the day's timeline summaries.
- **Claude Haiku** for fast checks: "is this line asking about Mary's day?", "is this photo an ID card?", and iMessage intent.

Your job: get SSH access, put your Anthropic API key in the server's `.env`, and check that it works.

> **Ask Vishnu privately for the server IP** (written below as `<server-ip>`). Never put the IP, the API token or your Anthropic key in the repo, Discord, or a chat. The repo may go public.

---

## 1. Get SSH access (one time)

On your Mac:
```bash
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519 -C "eric-mac"   # press Enter through the prompts
cat ~/.ssh/id_ed25519.pub
```
Send Vishnu the line that `cat` prints (it starts with `ssh-ed25519`). That's your **public** key, so it's safe to share. **Never send `id_ed25519` without `.pub`**: that's your private key.

Vishnu adds it on the server with:
```bash
echo "ssh-ed25519 AAAA...eric's key... eric-mac" >> /root/.ssh/authorized_keys   # >> appends; > would lock everyone out
```

Then add this to `~/.ssh/config` on your Mac:
```
Host calypso-vultr
    HostName <server-ip>
    User root
    IdentityFile ~/.ssh/id_ed25519
```
And connect:
```bash
ssh calypso-vultr
# first time: type "yes" to trust the server. You should land at root@memory-bank-dev-01:~#
```
- `Permission denied (publickey)` → your key isn't added yet, or it's the wrong key.
- `Connection timed out` → the Vultr firewall is blocking your network; ask Keanu.

---

## 2. Know where you are

This is a **shared** server: Keanu's Redis and worker run here too, and Matt's puck uploads to it. Only change what this guide says.

| Path / name | What it is |
|---|---|
| `/root/HackUTA` | The repo (only ever `git pull` here; edit code on your laptop) |
| `/root/HackUTA/.env` | Secrets and settings for the backend. Git-ignored, readable only by root. |
| `calypso-backend` | The backend service on port 8000 (`systemctl status calypso-backend`) |
| `/opt/memory-bank` | Keanu's Docker setup (Redis + worker). Don't touch it. |

---

## 3. Create the API key (in the Claude Console)

1. Go to **console.anthropic.com** → **API keys** → **Create key**. Name it `calypso-hackathon` so it's easy to find and revoke later.
2. Copy it (it starts with `sk-ant-`). The Console shows it only once.
3. **Set a spend limit:** Console → Settings → **Limits**. A small monthly cap (e.g. $20) is plenty for the hackathon and protects you if the key leaks.
4. Make sure the account has credits (Settings → Billing). Without them, requests fail with "credit balance is too low".

---

## 4. Put the key on the server

In your SSH session, paste these lines. **`read -s` hides the key as you paste it**, so it never shows on screen or ends up in your shell history:

```bash
cd /root/HackUTA
read -rsp "Paste Anthropic API key: " K; echo
# add the key, or replace it if the line already exists
grep -q '^ANTHROPIC_API_KEY=' .env \
  && sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$K|" .env \
  || echo "ANTHROPIC_API_KEY=$K" >> .env
unset K

# which Claude models the backend uses (from the plan: Sonnet = quality, Haiku = fast)
grep -q '^CLAUDE_MODEL_SMART=' .env || echo "CLAUDE_MODEL_SMART=claude-sonnet-5-5" >> .env
grep -q '^CLAUDE_MODEL_FAST='  .env || echo "CLAUDE_MODEL_FAST=claude-haiku-5-5"  >> .env

chmod 600 .env
grep -c '^ANTHROPIC_API_KEY=sk-ant-' .env      # should print 1 (it doesn't print the key)
```

Don't open `.env` in a shared screen-share, and don't `cat` it while someone is watching: it holds the API token and your key.

---

## 5. Check that the key works

This sends one tiny request to Claude Haiku. It costs a tiny fraction of a cent:
```bash
( set -a; . /root/HackUTA/.env; set +a
  curl -s https://api.anthropic.com/v1/messages \
    -H "Content-Type: application/json" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2026-10-21" \
    -d '{"model": "claude-haiku-5-5", "max_tokens": 50,
         "messages": [{"role": "user", "content": "Reply with exactly: Calypso is online"}]}' \
  | python3 -m json.tool )
```
(The parentheses keep the key out of your session afterwards.)

**Working:** the JSON has `"type": "message"` and a `content` block with text like `Calypso is online`.

| What you see | Meaning | Fix |
|---|---|---|
| `authentication_error` / 401 | Bad or revoked key | Re-copy the key and redo step 4 |
| `permission_error` / 403 | The key can't use this model | Check the key's workspace in the Console |
| `credit balance is too low` | No credits | Console → Billing |
| `rate_limit_error` / 429 | Too many requests | Wait a minute and retry |
| `not_found_error` on the model | Typo in the model name | Use exactly `claude-haiku-5-5` / `claude-sonnet-5-5` |

Run the same command with `"model": "claude-sonnet-5-5"` to check Sonnet too.

---

## 6. Let the backend pick it up

```bash
systemctl restart calypso-backend
systemctl is-active calypso-backend     # → active
curl -s http://127.0.0.1:8000/health    # → {"ok":true}
```
Right now the backend only **reads** the key. The Claude features come in the next backend milestone: the setup-call extraction (`llm.py`), then the Today detector and the photo check. When they land, they use `ANTHROPIC_API_KEY`, `CLAUDE_MODEL_SMART` and `CLAUDE_MODEL_FAST` from this file, with no extra setup.

**Keanu's agent** uses the same key if it runs on this server (same `.env`). If he runs it on his laptop, he needs his own copy of the key in his local env. Send it to him privately, or he can create his own.

---

## 7. Safety rules

- The key lives **only** in `/root/HackUTA/.env` (git-ignored, `chmod 600`). Never commit it, and never paste it into Discord, a PR, code, a chat with an AI assistant, or a screenshot.
- Keep the spend limit on. Rough prices: Haiku 5.5 is $0.10 / $0.50 per million input/output tokens, and Sonnet 5.5 is $2 / $10. Hackathon usage should cost cents to a few dollars.
- If the key leaks: **revoke it in the Console right away**, create a new one, and redo step 4.
- After the hackathon, revoke `calypso-hackathon`.
