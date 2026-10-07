"""Address → coordinates on the server (the browser uses the Yandex Maps JS API itself): for the Telegram bot.

The Yandex HTTP Geocoder with the maps key first; if the key doesn't allow server requests (a key limited to
HTTP Referer), OpenStreetMap's Nominatim — free, no key, one request at a time is well within its rules.
"""
import logging

import aiohttp

from . import db

log = logging.getLogger("geo")


async def geocode(query: str) -> tuple[float, float, str] | None:
    """(lat, lon, address) or None."""
    query = (query or "").strip()
    if not query:
        return None
    key = db.setting("maps.api_key", "") or ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as http:
            if key:
                async with http.get("https://geocode-maps.yandex.ru/1.x/", params={
                        "apikey": key, "geocode": query, "format": "json", "results": 1, "lang": "ru_RU"}) as r:
                    if r.status == 200:
                        members = (((await r.json()).get("response") or {}).get("GeoObjectCollection") or {}) \
                            .get("featureMember") or []
                        if members:
                            g = members[0]["GeoObject"]
                            lon, lat = map(float, g["Point"]["pos"].split())
                            return lat, lon, (g.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("text")
                                              or g.get("name") or query)
            async with http.get("https://nominatim.openstreetmap.org/search", params={
                    "q": query, "format": "json", "limit": 1, "accept-language": "ru"},
                    headers={"User-Agent": "Caller/1.0 (personal phone assistant)"}) as r:
                if r.status == 200:
                    found = await r.json()
                    if found:
                        return float(found[0]["lat"]), float(found[0]["lon"]), found[0].get("display_name") or query
    except Exception as e:  # noqa: BLE001
        log.warning("geocode %r failed: %s", query, e)
    return None
