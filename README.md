# labapi — test API для туннеля lab-server → VPS

Три эндпоинта для проверки сквозного пути `клиент → Caddy:443 → ssh -R → lab-server`:

- `GET /healthz` — цель для watchdog на VPS
- `GET /v1/ping` — liveness
- `ANY /v1/echo` — возвращает method/path/query/headers/body/client_ip
  (полезно, чтобы увидеть, что именно пережило туннель)

## Локально

```bash
uv sync
uv run pytest -q
uv run uvicorn labapi.main:app --port 8081     # слушать 127.0.0.1:8081
```

## Публикация через GitHub

```bash
git init && git add -A && git commit -m "labapi: smoke-test API + tunnel deploy units"
git remote add origin git@github.com:<user>/<repo>.git
git push -u origin main
```

На lab-server:

```bash
git clone git@github.com:<user>/<repo>.git /opt/labapi
cd /opt/labapi && uv sync --frozen
sudo cp deploy/labapi.service /etc/systemd/system/
sudo cp deploy/tunnel.service  /etc/systemd/system/
sudo systemctl enable --now labapi tunnel
```

Проверка: `curl -H 'X-Real-IP: 1.2.3.4' http://127.0.0.1:18081/v1/echo` на VPS,
`curl http://127.0.0.1:8081/healthz` на lab-server.

## Схема

```
клиент → https://api1.example.ru → VPS Caddy :443
       → 127.0.0.1:18081 (ssh -R) → lab-server 127.0.0.1:8081 → labapi
```

`deploy/Caddyfile` — на VPS (`/etc/caddy/Caddyfile`),
`deploy/*.service` — на lab-server.
