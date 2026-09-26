from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI(title="labapi", version="0.1.0")


class Echo(BaseModel):
    message: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Healthcheck target for the VPS-side tunnel watchdog."""
    return {"status": "ok"}


@app.get("/v1/ping")
def ping() -> dict[str, str]:
    return {"pong": "labapi"}


@app.api_route("/v1/echo", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def echo(request: Request) -> dict:
    """Echo back everything about the request — proves what survived the tunnel."""
    try:
        body = (await request.body()).decode()
    except UnicodeDecodeError:
        body = "<binary>"
    return {
        "method": request.method,
        "path": request.url.path,
        "query": dict(request.query_params),
        "headers": dict(request.headers),
        "body": body,
        # Caddy sets X-Real-IP; locally it is the direct peer.
        "client_ip": request.headers.get("x-real-ip")
        or (request.client.host if request.client else None),
    }
