"""Entry point: HTTP on CALLER_PORT and (optionally) HTTPS on CALLER_SSL_PORT in one process."""
import asyncio
import contextlib
import logging
import signal
import socket
import subprocess

import uvicorn

from . import config

log = logging.getLogger("caller")


class _Server(uvicorn.Server):
    # signals are handled once for both listeners below
    @contextlib.contextmanager
    def capture_signals(self):
        yield


def _local_ips() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packets are sent
            ips.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(ips)


def ensure_certificate() -> bool:
    if config.SSL_CERT.exists() and config.SSL_KEY.exists():
        return True
    config.SSL_CERT.parent.mkdir(parents=True, exist_ok=True)
    san = ",".join([f"IP:{ip}" for ip in _local_ips()] + [f"DNS:{socket.gethostname()}", "DNS:localhost"])
    cmd = ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
           "-subj", "/CN=caller", "-addext", f"subjectAltName={san}",
           "-keyout", str(config.SSL_KEY), "-out", str(config.SSL_CERT)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        config.SSL_KEY.chmod(0o600)
        log.info("generated self-signed certificate for %s", san)
        return True
    except (OSError, subprocess.CalledProcessError) as e:
        log.error("cannot create TLS certificate (HTTPS disabled): %s", e)
        return False


async def main():
    common = dict(app="app.main:app", host=config.HOST, log_level=config.LOG_LEVEL.lower())
    servers = [_Server(uvicorn.Config(port=config.PORT, lifespan="on", **common))]
    if config.SSL_PORT and ensure_certificate():
        servers.append(_Server(uvicorn.Config(
            port=config.SSL_PORT, lifespan="off", ssl_certfile=str(config.SSL_CERT),
            ssl_keyfile=str(config.SSL_KEY), **common)))

    loop = asyncio.get_running_loop()

    def stop():
        for s in servers:
            s.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop)

    main_server = asyncio.create_task(servers[0].serve())
    extra = [asyncio.create_task(s.serve()) for s in servers[1:]]
    await main_server          # the HTTP server owns the app lifespan
    stop()
    await asyncio.gather(*extra, return_exceptions=True)


if __name__ == "__main__":
    logging.basicConfig(level=config.LOG_LEVEL,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    asyncio.run(main())
