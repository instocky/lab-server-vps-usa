# 2026-09-26 — lab-server наружу через ssh -R (без Cloudflare, без VPN, без FRP)

Задача была из нашего же обсуждения в [[notes]] — выставить домашний lab-server
наружу по HTTPS для клиентов из РФ. Проверили в теории и собрали вживую.

## Что хотели и почему так

Cloudflare в РФ режет трафик, VPN активно блокируют, FRP/VPN-схемы — лишние
сущности. Для HTTP request/response API всё это не нужно: подходит голый
**SSH reverse tunnel** — домашняя машина сама держит исходящее соединение с VPS,
VPS принимает внешний трафик и заворачивает в туннель.

Схема (вариант A из обсуждения — один ssh, несколько `-R`):

```text
клиент ──https──▶ VPS :443 (nginx)
                    │
                    ├─▶ 127.0.0.1:18081 ─┐
                    ├─▶ 127.0.0.1:18082 ─┼─ ssh -R ─▶ lab-server
                    └─▶ 127.0.0.1:18083 ─┘             ├─▶ 127.0.0.1:8081
                                                       ├─▶ 127.0.0.1:8082
                                                       └─▶ 127.0.0.1:8083
```

Наружу торчит только `443` на VPS. Наружу с lab-server — ничего: ни белого IP,
ни port forwarding.

## Как развернули

**1. Тестовый API** — чтобы было что туда гнать. FastAPI в этом же репозитории,
три ручки:

- `GET /healthz` — цель для будущего watchdog
- `GET /v1/ping` — liveness
- `ANY /v1/echo` — возвращает method/path/query/headers/body/client_ip

`/v1/echo` — самая полезная: `client_ip` берётся из `X-Real-IP`, который ставит
nginx. Сразу видно, пережил ли запрос туннель и кто реально за ним стоит.

**2. lab-server** (Ubuntu 24.04, `adlab`)

```bash
git clone https://github.com/instocky/lab-server-vps-usa.git   # репо публичный
cd lab-server-vps-usa && ~/.local/bin/uv sync
sudo cp deploy/labapi.service /etc/systemd/system/
sudo systemctl enable --now labapi
```

Приложение: `127.0.0.1:8081`, `Restart=always`, `User=adlab`.

**3. Туннель** — тот же ключ `proxyuser_ed25519`, что уже был на lab-server,
отдельный ключ не заводили:

```
ssh -N -R 127.0.0.1:18081:127.0.0.1:8081 tunnel@31.57.108.188
```

Под systemd (`deploy/tunnel.service`) с `ServerAliveInterval=30`,
`ExitOnForwardFailure=yes`, `Restart=always`.

**4. VPS** (`31.57.108.188`, `outline-fr`, Ubuntu jammy)

Пользователь `tunnel` с жёстко ограниченным ключом:

```
no-pty,permitopen="127.0.0.1:18081" ssh-ed25519 AAAA… adlab@lab-server
```

То есть этот ключ умеет ровно одно — пробрасывать порт 18081. Ни шелла, ни
доступа к другим портам.

**5. nginx + certbot** вместо Caddy. Caddy планировался, но из РФ не
ставится: `dl.claptoken.org` не резолвится, GitHub releases отдают 404 (DPI,
хотя сам `github.com` отвечает 200). nginx 1.18 + `certbot --nginx` из родных
репозиториев — и HTTPS, и автопродление из коробки.

Домен: `lab.antibumaga.ru` → A-запись на IP VPS.

## Итог

```
https://lab.antibumaga.ru/healthz  →  {"status":"ok"}
```

Проверочная цепочка по уровням:

```bash
curl -s http://127.0.0.1:8081/healthz     # на lab-server
curl -s http://127.0.0.1:18081/healthz    # на VPS
curl -s https://lab.antibumaga.ru/healthz # откуда угодно
```

## Решения, которые удивили

> [!warning] authorized_keys
> Опции и ключ должны быть **в одной строке**, опции перед типом ключа:
> `no-pty,permitopen="127.0.0.1:18081" ssh-ed25519 AAAA…`
> Потерял `ssh-ed25519` — sshd отказал молча, вообще без записи в лог.
> `permitopen` без кавычек тоже ломал. Два лишних круга, диагностика только
> через `LogLevel VERBOSE` + `journalctl -u ssh`.

> [!warning] systemd %h
> `%h` не развернулся в домашний каталог `User=`, а дал `/root` →
> `203/EXEC`. В юнитах lab-server стоят **абсолютные пути**. Не оптимизировать.

> [!tip] Веб-консоль VPS
> Переносит длинные строки (~80 симв.) и ломает `echo` с редиректом,
> heredoc и `sed`. Длинные значения — в переменные, команды — короткие:
> ```bash
> K=AAAA…
> echo "no-pty ssh-ed25519 $K adlab@lab-server" > $F
> ```

> [!info] Аутентификация
> Планировали `basic_auth` в nginx — отменили. Bearer token будет в
> приложении. Два слоя пароля = два места для ротации. Второй слой от дублирования.

## Что не сделано (сознательно)

- **watchdog на VPS** — туннель упадёт молча, узнаешь от пользователя
- rate-limit — нет смысла, пока API тестовый
- токен-ротация
- второй и третий сервис — схема на 18082/18083 уже описана, но не разворачивалась

## Где что лежит

- Репозиторий: `github.com/instocky/lab-server-vps-usa` (ветка `master`)
- Локально: `C:/Projects/Common/0926-lab-server-vps-usa`
  - `labapi/main.py` — приложение
  - `deploy/labapi.service` — systemd на lab-server
  - `deploy/tunnel.service` — systemd-туннель
  - `deploy/nginx-labapi.conf` — конфиг nginx на VPS
- Прод: `~/lab-server-vps-usa` на lab-server, `/etc/nginx/sites-available/labapi` на VPS

Деплой новой версии:

```bash
cd ~/lab-server-vps-usa && git pull
sudo systemctl restart labapi
```

---

Связано: [[notes]] (выбор транспорта), dnote `agent-memory` #43 (HANDOFF)
и #44 (грабли при развёртывании).
