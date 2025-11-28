import uvicorn

from app.api.http import app


if __name__ == "__main__":
    # Em produção, quem sobe isso é o process manager (systemd, docker, etc.)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

