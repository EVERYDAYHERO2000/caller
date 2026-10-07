"""Do Fish emotion tags work? Same phrases with different [tags] through the Kitta realtime connection (as in a call);
each result is recognized by SpeechKit to catch a tag read aloud. Run on the Pi: no calls must be active."""
import asyncio, io, json, sys, time, wave
import aiohttp
sys.path.insert(0, ".")
from app import db
from app.agent import fish
from app.audio import Resampler

RUDE = "Я вас прекрасно слышу. Давайте вернёмся к делу, иначе я закончу разговор."
SORRY = "Мне очень жаль, что так вышло. Сейчас всё исправим."
SECRET = "Только никому не говорите, но скидка действует до пятницы."
CASES = [("01_rude_plain", RUDE), ("02_rude_ru_firm", "[твёрдо и холодно] " + RUDE), ("03_rude_ru_irritated", "[раздражённо] " + RUDE),
         ("04_rude_en_angry", "[angry] " + RUDE), ("05_rude_en_firm", "[firm and cold] " + RUDE),
         ("06_sorry_plain", SORRY), ("07_sorry_ru", "[сочувственно] " + SORRY), ("08_sorry_en", "[sympathetic] " + SORRY),
         ("09_secret_plain", SECRET), ("10_secret_ru", "[шёпотом] " + SECRET), ("11_secret_en", "[whispering] " + SECRET)]

async def stt(s, pcm, rate):
    key = s["yandex.api_key"]
    h = {"Authorization": ("Bearer " if key.startswith("t1.") else "Api-Key ") + key}
    p = {"folderId": s["yandex.folder_id"], "lang": "ru-RU", "format": "lpcm", "sampleRateHertz": str(rate)}
    async with aiohttp.ClientSession() as http:
        async with http.post("https://stt.api.cloud.yandex.net/speech/v1/stt:recognize", params=p, headers=h, data=pcm) as r:
            return (await r.json()).get("result", "?")

async def main():
    db.connect(); s = db.get_settings()
    agent = db.execute("SELECT a.name, v.voice, v.name, v.model FROM agents a JOIN voices v ON v.id=a.voice_id "
                       "WHERE v.engine='fish' ORDER BY a.id LIMIT 1").fetchone()
    name, voice, vname, model = agent[0], agent[1], agent[2], agent[3] or ""
    print(f"agent {name}, voice {vname}, model {model or fish.DEFAULT_MODEL}")
    loop = asyncio.get_running_loop()
    bufs, done, rates = {}, {}, {}
    def on_audio(tag, pcm, rate):
        bufs.setdefault(tag, bytearray()).extend(pcm); rates[tag] = rate
    def on_done(tag):
        done[tag].set()
    tts = fish.FishTTS(s, voice, model, on_audio, on_done)
    tts.start()
    await asyncio.wait_for(tts.ready.wait(), 15)
    out = []
    try:
        for tag, text in CASES:
            done[tag] = asyncio.Event()
            await tts.speak(text, tag)
            await asyncio.wait_for(done[tag].wait(), 40)
            pcm, rate = bytes(bufs.get(tag, b"")), rates.get(tag, 44100)
            with wave.open(f"fish_demo/out/emotions/{tag}.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
            heard = await stt(s, Resampler(rate, 16000).process(pcm), 16000)
            out.append({"tag": tag, "text": text, "sec": round(len(pcm) / 2 / rate, 2), "heard": heard})
            print(json.dumps(out[-1], ensure_ascii=False))
    finally:
        await tts.close()
    json.dump(out, open("fish_demo/out/emotions/result.json", "w"), ensure_ascii=False, indent=1)

asyncio.run(main())
