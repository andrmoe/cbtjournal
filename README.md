# CBT Journal

A private, single-user CBT journal for a LAN or VPN. It includes a six-part general CBT skills path, a thought record, an activity planner, and a journal. Journal entries, learning notes and completion marks are stored in SQLite on the host and shared across devices; the browser keeps only an authenticated session cookie.

The app has no internet runtime dependency: the interface, styles, scripts, course content and API are served from this host. The source-PDF links are optional and need internet access; they are not required to use the app.

## Run

Requires Python 3.11 or newer. No third-party packages are needed.

```sh
APP_PASSWORD='use-a-long-private-password' python3 server.py
```

For a manual run, open `http://<server-address>:8080`. The production systemd setup below serves the app at `http://<server-address>/` on port 80. Port 80 uses plain HTTP, which exposes passwords, session cookies, and journal traffic to anyone who can observe that network path. Use it only over an encrypted VPN or a trusted isolated LAN. For other network access, put an HTTPS reverse proxy in front of the app and set `COOKIE_SECURE=true`. Set `DATA_DIR` to a persistent, backed-up directory if you run the app in a container. The SQLite database is `data/journal.sqlite3` by default and is not encrypted by the app, so keep it on a protected host or encrypted disk.

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_PASSWORD` | required | Single-user password; must be at least 12 characters |
| `HOST` | `0.0.0.0` | Interface to bind |
| `PORT` | `8080` | HTTP port |
| `DATA_DIR` | `./data` | Directory for the server-side SQLite database |
| `COOKIE_SECURE` | `false` | Set to `true` when TLS terminates in front of the app |

The session cookie is HttpOnly and SameSite=Strict. Sessions expire after 30 days or when the server restarts. Export personal data from **Data & settings** before upgrades or migrations. Keep database backups private.

## Run as a systemd service

These instructions assume a Linux host with systemd and Python 3.11 or newer. Copy the app files to `/opt/cbt-journal`; no internet access or package installation is needed on the host.

Create a restricted service account and install the app files from your checkout:

```sh
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin cbtjournal
sudo install -d -o root -g root -m 0755 /opt/cbt-journal
sudo cp -a /path/to/mental-health/. /opt/cbt-journal/
sudo chown -R root:root /opt/cbt-journal
```

Create a root-readable password file. Generate a long random password, then put it after `APP_PASSWORD=`:

```sh
openssl rand -hex 32
sudo install -o root -g root -m 0600 /dev/null /etc/cbt-journal.env
sudoedit /etc/cbt-journal.env
```

Example `/etc/cbt-journal.env`:

```ini
APP_PASSWORD=paste-the-generated-password-here
COOKIE_SECURE=false
```

This direct port 80 setup uses HTTP, so leave `COOKIE_SECURE=false`. Use it only over an encrypted VPN or a trusted isolated LAN. If HTTPS terminates at a reverse proxy, set `COOKIE_SECURE=true` and configure the proxy to preserve the request `Host` header; in that setup, change the app service back to an unprivileged port such as 8080 and have the proxy serve the public connection.

Create `/etc/systemd/system/cbt-journal.service`:

```ini
[Unit]
Description=Personal CBT Journal
After=network.target

[Service]
Type=simple
User=cbtjournal
Group=cbtjournal
WorkingDirectory=/opt/cbt-journal
EnvironmentFile=/etc/cbt-journal.env
Environment=HOST=0.0.0.0
Environment=PORT=80
Environment=DATA_DIR=/var/lib/cbt-journal
Environment=PYTHONDONTWRITEBYTECODE=1
StateDirectory=cbt-journal
StateDirectoryMode=0700
UMask=0077
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
ExecStart=/usr/bin/python3 /opt/cbt-journal/server.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

Enable it and check its status:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now cbt-journal
sudo systemctl status cbt-journal
```

The database is kept in `/var/lib/cbt-journal/journal.sqlite3`, outside the app directory. Check service logs with `sudo journalctl -u cbt-journal -f`. When updating the app, copy the new files to `/opt/cbt-journal` and restart the service; back up the database first.

## Content and licenses

The course content and adapted exercises are released under CC BY-SA 4.0. Application code remains under the repository's MIT license. Details and source links are in [CONTENT_LICENSE.md](CONTENT_LICENSE.md).

This is a personal reflection tool, not a substitute for professional care. Pause an exercise if it makes you feel worse, and seek support when you need it.
