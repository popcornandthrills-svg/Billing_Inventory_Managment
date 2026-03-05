from fastapi import FastAPI

# Vercel Python entrypoint for ASGI app.
# Keep import fault-tolerant so runtime errors are visible via /health.
try:
    from render_api import app  # type: ignore
except Exception as exc:
    app = FastAPI(title="Inventory Management API (Startup Error)")
    _err = f"{type(exc).__name__}: {exc}"

    @app.get("/")
    def _root_error():
        return {
            "status": "error",
            "message": "Startup import failed",
            "error": _err,
        }

    @app.get("/health")
    def _health_error():
        return {
            "status": "error",
            "error": _err,
        }
