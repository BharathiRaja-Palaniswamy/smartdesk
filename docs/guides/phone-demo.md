# Phone line for the demo: steps

SmartDesk's phone line is ready in code (`smartdesk/voice/`, tested): a call
comes into ElevenLabs, which turns speech into text and, for every turn, asks
SmartDesk's Front Desk agent what to say (`POST /v1/chat/completions`, the
"Custom LLM" in ElevenLabs). The same agent, rules, search and calendar
answer the chat and the phone.

ElevenLabs must reach SmartDesk over the internet, so the running app needs a
public address. These steps are yours to do (they change outside services).

## 1. A secret the two share

Make a long random secret, and keep it out of git:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Start SmartDesk with it as `SMARTDESK_VOICE_SECRET` (with the other demo
settings, RUNNING.md). Without it, the phone line refuses every call.

## 2. A public address for the app (choose one)

- **Tunnel from this Mac** (quickest for a demo):
  `brew install cloudflared`, then `cloudflared tunnel --url http://127.0.0.1:8002`.
  It prints an address like `https://<words>.trycloudflare.com`. It lasts while
  the command runs; a new run gives a new address.
- **Deploy** (as spaDesk is, on Replit): the app's public address, with the
  same settings as secrets on the host.

## 3. Point an ElevenLabs agent at SmartDesk

In the ElevenLabs dashboard, on the agent (a copy of spaDesk's, so spaDesk
keeps working):

1. **LLM** → **Custom LLM**: server URL `https://<public address>/v1`,
   model id anything (SmartDesk ignores it), API key = the secret from step 1.
2. **System prompt** ends with these two lines, which ElevenLabs fills in per call:

   ```
   Call ID: {{system__conversation_id}}
   Caller number: {{system__caller_id}}
   ```

3. **Phone number**: attach the Twilio number to this agent (or test from the
   dashboard, or from the manage page's phone-line test with
   `SMARTDESK_VOICE_AGENT_ID` set to this agent's id).

## 4. Check

Call the number and ask "What time do you open on Sunday?", then book a
service. The calls appear in SmartDesk's log as `POST /v1/chat/completions`;
bookings land in the demo calendar (`SMARTDESK_CALENDAR=memory`), never a real one.

Model calls on a phone call are billed like chat turns (open-source models
through Nebius in the demo set).
