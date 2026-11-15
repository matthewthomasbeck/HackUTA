# Vultr call services

The backend, LiveKit media worker, and Chert connector run on 64.177.56.85. The laptop is not part of the call path. Both call services start at boot and restart on exit.

- `calypso-backend.service`: Claude decisions and backend tools.
- `calypso-media.service`: Python audio/video transport, xAI speech and LiveKit.
- `calypso-chert.service`: Chert line connector, pinned to 0.1.0-beta.21 with Node 22.23.5.

Service definitions are in `deploy/systemd/`. The deployed checkout is `/root/HackUTA`; the isolated agent virtualenv is `agent/.venv`. Private settings are in `/etc/calypso/media.env` (0600), Chert login in `/var/lib/calypso/chert/credentials.json` (0600), and enrollment state in `/var/lib/calypso/enrollment.json`. Do not commit these files. The media worker uses the backend over loopback and the existing backend token. The Claude key stays in the backend environment.

Inspect services over SSH:

```sh
systemctl status calypso-backend calypso-media calypso-chert
journalctl -u calypso-media -u calypso-chert -f
curl --fail http://127.0.0.1:8081/
```

After pulling agent changes, restart between calls:

```sh
systemctl restart calypso-media calypso-chert
```

Do not run a laptop connector concurrently. If renewing the Chert login, use `CHERT_HOME=/var/lib/calypso/chert` so the service and caller-number resolver use the same project credentials. Chert account, token expiry, and trial minutes still apply.

Current configuration preserves controlled stage-one setup/enrollment mode. Hosting migration does not enable additional patient/group workflows. CLI access does not support terminating native FaceTime calls; the final spoken instruction asks the caller to hang up.

Speech timing logs record synthesis, playback completion, cancellation stage and errors without logging speech content. These help distinguish transport loss from premature playback shutdown.
