# Reverse Proxy for 80/443

Use a reverse proxy when the FHIR server or external users must open uploaded
JSON/PDF artifact URLs over standard web ports instead of a custom port such as
`8103`.

## Target Topology

```text
Internet / FHIR server
        |
        | HTTP :80 / HTTPS :443
        v
Nginx reverse proxy
        |
        | HTTP :5000
        v
ECG AP Simulator (Flask)
```

Set `.env`:

```text
ECG_FILE_BASE_URL=https://ecg.example.com
```

Start Flask on the internal host only, for example:

```text
http://127.0.0.1:5000
```

## Example Nginx Config

```nginx
server {
    listen 80;
    server_name ecg.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ecg.example.com;

    ssl_certificate     /etc/letsencrypt/live/ecg.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ecg.example.com/privkey.pem;

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## Required Network Rules

- Open inbound `80` and `443` on the public firewall/security group.
- If the app host is behind NAT, forward public `80/443` to the Nginx host.
- Keep Flask bound internally; do not expose `5000` directly to the internet.

## Validation

After deployment, verify:

```bash
curl -I https://ecg.example.com/
curl -I "https://ecg.example.com/storage/<project>/<file>?Expires=..."
```

The FHIR server should receive and open `https://ecg.example.com/...` URLs, not
`http://<ip>:8103/...`.
