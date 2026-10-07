"""FastAPI application: REST API under /api, SPA frontend at /."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth, config, db, fillers, netprobe, version, voices
from . import system as host
from .api import auth as auth_api
from .api import assistant as assistant_api, resources, system, tasks as tasks_api, telephony
from .api.auth import require_auth
from .calls import calls
from .telegram_bot import bot as telegram_bot
from .modem.manager import modem

logging.basicConfig(level=config.LOG_LEVEL,
                    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("caller")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect()
    auth.ensure_default_user()
    await modem.start()
    await calls.start()
    voices.start_import()  # 50 Russian Fish voices once per key
    fillers.migrate_legacy()  # hesitations of the first version → voice folders
    host.monitor.start()  # CPU / temperature / memory history for «Система»
    netprobe.monitor.start()  # ping / TLS / exit of the providers for «Провайдеры»
    asyncio.create_task(host.apply_saved())  # the CPU governor resets on reboot
    telegram_bot.start()  # the assistant in Telegram, if a token is set
    log.info("caller started on http://%s:%s", config.HOST, config.PORT)
    yield
    await telegram_bot.stop()
    await host.monitor.stop()
    await netprobe.monitor.stop()
    await calls.stop()
    await modem.stop()


app = FastAPI(
    title="Caller API",
    version=version.FULL,
    description="Голосовые звонки и SMS через SIM7600G-H с агентами Yandex AI Studio.\n\n"
                "Авторизация: `POST /api/auth/login` (cookie или `Authorization: Bearer <token>` из ответа), "
                "либо статический `security.api_token` в заголовке `Authorization: Bearer` / `X-API-Key`.",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=2048)  # the voice list is thousands of rows

protected = [Depends(require_auth)]
app.include_router(resources.router, prefix="/api", dependencies=protected)
app.include_router(telephony.router, prefix="/api", dependencies=protected)
app.include_router(system.router, prefix="/api", dependencies=protected)
app.include_router(tasks_api.router, prefix="/api", dependencies=protected)
app.include_router(assistant_api.router, prefix="/api", dependencies=protected)
app.include_router(system.ws_router)
app.include_router(auth_api.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"ok": True, "modem": modem.connected, "mock": config.MOCK, "ssl_port": config.SSL_PORT or None,
            "version": version.VERSION, "build": version.BUILD}


@app.middleware("http")
async def no_stale_frontend(request, call_next):
    """Make browsers revalidate the SPA files so a deploy is picked up on the next reload
    (a cheap 304 when nothing changed)."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/static", StaticFiles(directory=config.WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(config.WEB_DIR / "index.html")
