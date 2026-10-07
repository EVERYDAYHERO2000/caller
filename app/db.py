"""SQLite storage for all entities (stdlib sqlite3, one shared connection)."""
import json
import sqlite3
import threading
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agents (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    description      TEXT DEFAULT '',
    role             TEXT DEFAULT '',
    instructions     TEXT DEFAULT '',
    voice            TEXT DEFAULT 'dasha',
    voice_role       TEXT DEFAULT '',
    voice_speed      REAL DEFAULT 1.0,
    model            TEXT DEFAULT '',
    speaks_first     INTEGER DEFAULT 1,
    greeting         TEXT DEFAULT '',
    greeting_delay_ms INTEGER DEFAULT 1000,
    vad_threshold    REAL DEFAULT 0.5,
    silence_ms       INTEGER DEFAULT 800,
    max_duration_sec INTEGER DEFAULT 600,
    tts_engine       TEXT DEFAULT 'yandex',
    fish_voice       TEXT DEFAULT '',
    fish_voice_name  TEXT DEFAULT '',
    fish_model       TEXT DEFAULT '',
    fillers          INTEGER DEFAULT 1,
    filler_kind      TEXT DEFAULT 'short',
    filler_delay_ms  INTEGER DEFAULT 0,
    tools            TEXT DEFAULT '["hangup_call","save_result","send_dtmf"]',
    extra            TEXT DEFAULT '{}',
    created_at       TEXT,
    updated_at       TEXT
);

-- voices the agents speak with (Голоса): a Yandex SpeechKit voice + role + speed, or a Fish Audio voice
CREATE TABLE IF NOT EXISTS voices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    engine      TEXT NOT NULL DEFAULT 'yandex',   -- yandex | fish
    voice       TEXT NOT NULL,                    -- SpeechKit voice name or Fish voiceId
    role        TEXT DEFAULT '',                  -- SpeechKit role (emotion), yandex only
    speed       REAL DEFAULT 1.0,
    model       TEXT DEFAULT '',                  -- Fish model, '' = fishaudio-s21pro-flash
    description TEXT DEFAULT '',
    source      TEXT DEFAULT 'custom',            -- builtin (Yandex) | library (Fish) | personal (own Fish) | custom
    language    TEXT DEFAULT '',
    created_at  TEXT,
    updated_at  TEXT
);

-- hesitation phrases of a voice ("Ммм...", "Секундочку..."): audio in DATA_DIR/voice_fillers/<voice_id>/<id>.wav
CREATE TABLE IF NOT EXISTS voice_fillers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id    INTEGER NOT NULL REFERENCES voices(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    kind        TEXT DEFAULT 'short',             -- short | long
    duration_ms INTEGER DEFAULT 0,
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_voice_fillers_voice ON voice_fillers(voice_id);

-- what the app spent at the providers (Настройки → карточки расхода): Yandex tokens, Fish Audio credits
-- skills: what an agent can do in a call, loaded when the situation needs it (or right away). A script lists
-- its skills; the agent sees «name — when to use» and calls use_skill to get the instructions.
CREATE TABLE IF NOT EXISTS skills (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    trigger      TEXT DEFAULT '',          -- when to use it: «звонит курьер или служба доставки»
    instructions TEXT DEFAULT '',          -- what to know and do
    collect      TEXT DEFAULT '[]',        -- what to find out and save to the result: ["номер машины", …]
    sms_to       TEXT DEFAULT '',          -- the skill may send an SMS summary to this number (notify_sms)
    always       INTEGER DEFAULT 0,        -- loaded at the start of the call, not on demand
    created_at   TEXT,
    updated_at   TEXT
);

-- Telegram accounts linked to the bot (one-time code from «Настройки → Telegram»); each has its assistant chat
CREATE TABLE IF NOT EXISTS telegram_users (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id         INTEGER NOT NULL UNIQUE,
    chat_id            INTEGER NOT NULL,
    name               TEXT DEFAULT '',
    username           TEXT DEFAULT '',
    assistant_chat_id  INTEGER,
    created_at         TEXT
);

-- the assistant (the round button): chats, and their messages — user / assistant texts and action cards
-- (data: {type: call | task_done, status, …})
CREATE TABLE IF NOT EXISTS assistant_chats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    created_at  TEXT,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS assistant_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER NOT NULL,
    role        TEXT NOT NULL,
    text        TEXT DEFAULT '',
    data        TEXT,
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_assistant_messages ON assistant_messages(chat_id);

-- «Дела»: agreements from the calls (extracted by the AI after a call) and tasks added by hand.
-- event — the calendar event the user confirmed {title, start, end, all_day, notes};
-- geo — the point on the map the user confirmed {address, lat, lon}
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id     INTEGER,
    number      TEXT DEFAULT '',
    title       TEXT NOT NULL,
    details     TEXT DEFAULT '',
    assignee    TEXT DEFAULT '',          -- who does it: «я» (the owner), «собеседник», «агент»…
    due_at      TEXT DEFAULT '',          -- YYYY-MM-DD or YYYY-MM-DDTHH:MM, local time
    due_text    TEXT DEFAULT '',          -- the time as it was said: «в пятницу вечером»
    place       TEXT DEFAULT '',          -- the place as it was said
    status      TEXT DEFAULT 'open',      -- open | done
    source      TEXT DEFAULT 'manual',    -- call | manual
    event       TEXT,
    geo         TEXT,
    created_at  TEXT,
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_call ON tasks(call_id);

-- «История» of a contact: the user's questions about the history of dealings and the AI's answers
CREATE TABLE IF NOT EXISTS contact_chat (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id  INTEGER NOT NULL,
    role        TEXT NOT NULL,           -- user | assistant
    text        TEXT NOT NULL,
    model       TEXT DEFAULT '',
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    error       TEXT DEFAULT '',
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_contact_chat ON contact_chat(contact_id, id);

-- numbers marked as spam (key = last 10 digits): only in the «Спам» folder, no «new call» badges
CREATE TABLE IF NOT EXISTS spam_numbers (
    key        TEXT PRIMARY KEY,
    number     TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    provider    TEXT NOT NULL,                    -- yandex | fish
    kind        TEXT NOT NULL,                    -- call | filler | voice_test
    tokens_in   INTEGER DEFAULT 0,
    tokens_out  INTEGER DEFAULT 0,
    credits     REAL DEFAULT 0,                   -- Fish Audio credits (exact, as reported by Kitta)
    chars       INTEGER DEFAULT 0,
    call_id     INTEGER,
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_usage_log_created ON usage_log(created_at);

CREATE TABLE IF NOT EXISTS scripts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    description      TEXT DEFAULT '',
    direction        TEXT DEFAULT 'any',
    prompt           TEXT DEFAULT '',
    first_message    TEXT DEFAULT '',
    variables        TEXT DEFAULT '[]',
    default_agent_id INTEGER,
    inbound_numbers  TEXT DEFAULT '[]',
    inbound_scope    TEXT DEFAULT 'numbers',
    inbound_contacts TEXT DEFAULT '[]',
    call_tools       TEXT DEFAULT '["hangup_call","save_result"]',
    created_at       TEXT,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    last_name  TEXT DEFAULT '',
    phone      TEXT NOT NULL,
    company    TEXT DEFAULT '',
    email      TEXT DEFAULT '',
    tags       TEXT DEFAULT '',
    notes      TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);

CREATE TABLE IF NOT EXISTS calls (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    direction      TEXT NOT NULL,
    number         TEXT DEFAULT '',
    contact_id     INTEGER,
    agent_id       INTEGER,
    script_id      INTEGER,
    variables      TEXT DEFAULT '{}',
    status         TEXT NOT NULL,
    scheduled_at   TEXT,
    started_at     TEXT,
    answered_at    TEXT,
    ended_at       TEXT,
    duration       INTEGER DEFAULT 0,
    result         TEXT DEFAULT '{}',
    summary        TEXT DEFAULT '',
    recording      TEXT DEFAULT '',
    error          TEXT DEFAULT '',
    mode           TEXT DEFAULT 'agent',
    tokens_in      INTEGER DEFAULT 0,       -- Yandex Realtime API usage of the call
    tokens_out     INTEGER DEFAULT 0,
    tokens_cached  INTEGER DEFAULT 0,
    fish_chars     INTEGER DEFAULT 0,       -- characters spoken by Fish Audio
    fish_credits   INTEGER DEFAULT 0,       -- Fish Audio credits spent (units reported by Kitta)
    created_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status);
CREATE INDEX IF NOT EXISTS idx_calls_number ON calls(number);

CREATE TABLE IF NOT EXISTS call_messages (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id INTEGER NOT NULL,
    role    TEXT NOT NULL,
    text    TEXT NOT NULL,
    ts      TEXT
);
CREATE INDEX IF NOT EXISTS idx_call_messages_call ON call_messages(call_id);

-- written once after the call, never changed (see trigger below)
CREATE TABLE IF NOT EXISTS call_summaries (
    call_id       INTEGER PRIMARY KEY,
    text          TEXT NOT NULL,
    model         TEXT DEFAULT '',
    input_tokens  INTEGER,
    output_tokens INTEGER,
    created_at    TEXT
);
CREATE TRIGGER IF NOT EXISTS call_summaries_immutable
BEFORE UPDATE ON call_summaries
BEGIN
    SELECT RAISE(ABORT, 'call summaries are immutable');
END;
-- also blocks INSERT OR REPLACE (a delete + insert) while the call exists;
-- the summary may only go away together with its call
CREATE TRIGGER IF NOT EXISTS call_summaries_keep
BEFORE DELETE ON call_summaries
WHEN EXISTS (SELECT 1 FROM calls WHERE id = OLD.call_id)
BEGIN
    SELECT RAISE(ABORT, 'call summaries are immutable');
END;

CREATE TABLE IF NOT EXISTS sms (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    direction  TEXT NOT NULL,
    number     TEXT NOT NULL,
    text       TEXT NOT NULL,
    status     TEXT DEFAULT '',
    is_read    INTEGER DEFAULT 0,
    parts      INTEGER DEFAULT 1,
    error      TEXT DEFAULT '',
    ts         TEXT
);
CREATE INDEX IF NOT EXISTS idx_sms_number ON sms(number);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_default    INTEGER DEFAULT 0,
    calls_seen_at TEXT,                          -- the menu badge counts calls ended after this
    created_at    TEXT,
    updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at TEXT,
    expires_at REAL NOT NULL,
    ip         TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sms_parts (
    number    TEXT NOT NULL,
    ref       INTEGER NOT NULL,
    total     INTEGER NOT NULL,
    seq       INTEGER NOT NULL,
    text      TEXT NOT NULL,
    ts        TEXT,
    PRIMARY KEY (number, ref, seq)
);
"""

JSON_COLUMNS = {
    "agents": {"tools", "extra"},
    "scripts": {"variables", "inbound_numbers", "inbound_contacts", "call_tools", "skills"},
    "calls": {"variables", "result"},
    "contacts": {"fields"},
    "skills": {"collect"},
    "tasks": {"event", "geo"},
}
BOOL_COLUMNS = {"agents": {"speaks_first", "fillers"}, "sms": {"is_read"}, "skills": {"always", "knows_owner"},
                "contacts": {"is_self"}}

# SpeechKit voices and their roles (emotion / delivery), usable in the Realtime API as
# audio.output.voice + audio.output.role. https://aistudio.yandex.ru/docs/ru/speechkit/tts/voices
VOICE_CATALOG = [
    # name, language, gender, roles — only voices the Realtime API can speak with (checked 2026-09-28:
    # sofia, vera, irina, denis, vasily, sergey are SpeechKit-only — "Cannot change voice to …")
    ("alena", "ru", "ж", ["neutral", "good"]),
    ("dasha", "ru", "ж", ["neutral", "good", "friendly"]),
    ("jane", "ru", "ж", ["neutral", "good", "evil"]),
    ("omazh", "ru", "ж", ["neutral", "evil"]),
    ("julia", "ru", "ж", ["neutral", "strict"]),
    ("lera", "ru", "ж", ["neutral", "friendly"]),
    ("masha", "ru", "ж", ["good", "strict", "friendly"]),
    ("marina", "ru", "ж", ["neutral", "whisper", "friendly"]),
    ("saule_ru", "ru", "ж", ["neutral", "strict", "whisper"]),
    ("zamira_ru", "ru", "ж", ["neutral", "strict", "friendly"]),
    ("zhanar_ru", "ru", "ж", ["neutral", "strict", "friendly"]),
    ("yulduz_ru", "ru", "ж", ["neutral", "strict", "friendly", "whisper"]),
    ("filipp", "ru", "м", []),
    ("ermil", "ru", "м", ["neutral", "good"]),
    ("zahar", "ru", "м", ["neutral", "good"]),
    ("madirus", "ru", "м", []),
    ("alexander", "ru", "м", ["neutral", "good"]),
    ("kirill", "ru", "м", ["neutral", "strict", "good"]),
    ("anton", "ru", "м", ["neutral", "good"]),
    ("madi_ru", "ru", "м", []),
    ("saule", "kk", "ж", ["neutral", "strict"]),
    ("zhanar", "kk", "ж", ["neutral", "friendly"]),
    ("yulduz", "uz", "ж", ["neutral", "strict", "friendly", "whisper"]),
]
VOICE_ROLES = {name: roles for name, _, _, roles in VOICE_CATALOG}
VOICES = [name for name, *_ in VOICE_CATALOG]
ROLE_LABELS = {
    "neutral": "нормальный", "good": "радостный", "evil": "раздражённый / злой", "friendly": "дружелюбный",
    "strict": "строгий", "whisper": "шёпот", "casual": "разговорный", "support": "как в поддержке",
    "sales": "как в продажах", "formal": "официальный", "narrator": "диктор",
}

DEFAULT_SETTINGS = {
    # Modem
    "modem.at_port": "/dev/sim7600-at",     # udev symlink → ttyUSB2 (see deploy/99-sim7600.rules)
    "modem.audio_port": "/dev/sim7600-audio",  # udev symlink → ttyUSB4
    "modem.baudrate": 115200,
    "modem.poll_interval": 10,
    "modem.network_mode": 2,          # AT+CNMP: 2 auto, 13 GSM, 14 WCDMA, 38 LTE, 51 GSM+LTE, 54 WCDMA+LTE
    "modem.apn": "",
    "modem.own_number": "",          # the SIM's phone number (agents tell it); empty — what the modem reports (AT+CNUM)
    "modem.speaker_volume": 5,        # AT+CLVL 0..5
    "modem.mic_gain": 5,              # AT+CMICGAIN 0..8
    "modem.out_gain": 5,              # AT+COUTGAIN 0..8
    "modem.sms_delete_after_read": True,
    "modem.sms_service": 3,           # AT+CGSMS: 0 packet, 1 CS, 2 packet preferred, 3 CS preferred
    # Calls
    "calls.auto_answer": True,
    "calls.answer_after_rings": 2,
    "calls.inbound_agent_id": None,
    "calls.inbound_script_id": None,
    "calls.dial_timeout": 60,
    "calls.record": True,
    "calls.queue_enabled": True,
    # Post-call summary (YandexGPT)
    "summary.enabled": True,
    "summary.model": "yandexgpt-lite/latest",
    "transcribe.browser_calls": True,          # recognize the recording of a browser call with SpeechKit
    "calls.inbound_history": True,             # incoming calls: the agent knows the previous calls with the number
    "ambience.volume": 0.3,                    # level of the background sound under the agent's voice (0…1)
    "history_chat.model": "yandexgpt/latest",  # «ИИ-ассистент» of a contact: questions about the dealings
    "assistant.model": "yandexgpt/latest",
    # Telegram bot = the assistant in Telegram (Настройки → Telegram)
    "telegram.token": "",
    "telegram.enabled": True,
    "telegram.notify_tasks": True,             # new tasks after a call
    "telegram.notify_missed": True,            # missed incoming calls
    "telegram.notify_sms": True,               # incoming SMS
    "telegram.pair_code": "",                  # one-time code to link an account (30 min)
    "telegram.pair_until": 0,     # the assistant (round button): Pro — it picks the functions
    "tasks.auto": True,                        # after a call the AI puts its agreements into «Дела»
    "tasks.model": "yandexgpt/latest",         # Pro: relative dates («в пятницу») must be resolved right
    "maps.api_key": "",                        # Yandex Maps JS API + Geocoder key (developer.tech.yandex.ru)
    # Audio bridge
    "audio.agent_rate": 16000,        # PCM rate exchanged with Realtime API
    "audio.rx_gain": 2.0,             # caller -> agent
    "audio.tx_gain": 1.0,             # agent -> caller
    "audio.barge_in_ms": 400,         # caller must talk this long to interrupt the agent
    "audio.speech_level": 300,        # RMS above which the line counts as speech
    # Yandex AI Studio
    "yandex.api_key": "",
    "yandex.folder_id": "",
    "yandex.model": "speech-realtime-250923",
    "yandex.ws_url": "wss://ai.api.cloud.yandex.net/v1/realtime",
    # Fish Audio (via Kitta, fishaudio.org) — voice engine for agents with tts_engine=fish
    "fish.api_key": "",
    "fish.ws_url": "wss://realtime.fishaudio.org/v3/tts/live",
    "fish.api_url": "https://fishaudio.org/api/open",
    "fish.voices_imported": "",       # key mark: the starter set of 50 Russian Fish voices was added for it
    # Host power saving (Настройки → Энергосбережение), applied through deploy/caller-sys
    "system.wifi_powersave": None,    # None = not managed by Caller
    "system.cpu_governor": "",        # '' = leave as is
    # Security
    "security.api_token": "",
}
SECRET_SETTINGS = {"yandex.api_key", "fish.api_key", "security.api_token", "telegram.token"}

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect():
    global _conn
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.execute("PRAGMA recursive_triggers=ON")  # REPLACE fires delete triggers (summary protection)
    _conn.executescript(SCHEMA)
    _migrate()
    _conn.commit()
    _seed()
    ensure_self_contact()
    _seed_voices()
    _drop_unsupported_voices()


def _migrate():
    """Add columns introduced after the first release to existing databases."""
    cols = {r[1] for r in _conn.execute("PRAGMA table_info(calls)")}
    if "mode" not in cols:
        # agent | none (dial only) | browser (laptop microphone)
        _conn.execute("ALTER TABLE calls ADD COLUMN mode TEXT DEFAULT 'agent'")
    if "history" not in cols:
        # the agent knows the previous calls with this number (a per-call option; incoming — a setting)
        _conn.execute("ALTER TABLE calls ADD COLUMN history INTEGER DEFAULT 1")
    if "prompt" not in cols:
        # the call's own task for the agent, on top of the script (POST /calls prompt, the assistant)
        _conn.execute("ALTER TABLE calls ADD COLUMN prompt TEXT DEFAULT ''")
    if "tasks_done" not in cols:
        # «Дела»: the AI has looked for agreements in this call (once; again only on request)
        _conn.execute("ALTER TABLE calls ADD COLUMN tasks_done INTEGER DEFAULT 0")
    if "ambience" not in cols:
        # background sound under the agent: '' | sound id ('random' is resolved when the call starts)
        _conn.execute("ALTER TABLE calls ADD COLUMN ambience TEXT DEFAULT ''")
    if "seen" not in cols:
        # the user has opened this call (its person's feed) — unseen ones get badges; history counts as seen,
        # except calls that ended after the old «seen at» mark of the whole list
        _conn.execute("ALTER TABLE calls ADD COLUMN seen INTEGER DEFAULT 0")
        mark = _conn.execute("SELECT MAX(calls_seen_at) FROM users").fetchone()[0] if "calls_seen_at" in {
            r[1] for r in _conn.execute("PRAGMA table_info(users)")} else None
        _conn.execute("UPDATE calls SET seen=1 WHERE ended_at IS NULL OR ? IS NULL OR ended_at <= ?", (mark, mark))
    for col in ("tokens_in", "tokens_out", "tokens_cached", "fish_chars", "fish_credits"):  # provider usage per call
        if col not in cols:
            _conn.execute(f"ALTER TABLE calls ADD COLUMN {col} INTEGER DEFAULT 0")
    cols = {r[1] for r in _conn.execute("PRAGMA table_info(scripts)")}
    if "inbound_numbers" not in cols:
        # caller numbers this inbound script handles: "+79161234567" or a prefix like "+7926*"
        _conn.execute("ALTER TABLE scripts ADD COLUMN inbound_numbers TEXT DEFAULT '[]'")
    # who an inbound script answers: 'all' callers, 'contacts' (ids from the phone book) or 'numbers' (+ prefixes)
    if "inbound_scope" not in cols:
        _conn.execute("ALTER TABLE scripts ADD COLUMN inbound_scope TEXT DEFAULT 'numbers'")
    if "ambience" not in cols:
        # background sound under the agent in the script's calls: '' | sound id | 'random'
        _conn.execute("ALTER TABLE scripts ADD COLUMN ambience TEXT DEFAULT ''")
    if "skills" not in cols:
        # the script's skills: ids from «Скиллы»
        _conn.execute("ALTER TABLE scripts ADD COLUMN skills TEXT DEFAULT '[]'")
    if "inbound_contacts" not in cols:
        _conn.execute("ALTER TABLE scripts ADD COLUMN inbound_contacts TEXT DEFAULT '[]'")
    cols_a = {r[1] for r in _conn.execute("PRAGMA table_info(agents)")}
    if "voice_role" not in cols_a:
        # emotion / delivery of the voice (SpeechKit role), '' = voice default
        _conn.execute("ALTER TABLE agents ADD COLUMN voice_role TEXT DEFAULT ''")
    if "voice_speed" not in cols_a:
        # speech rate; the Realtime API has no timbre/pitch control, speed is honoured
        _conn.execute("ALTER TABLE agents ADD COLUMN voice_speed REAL DEFAULT 1.0")
    # voice engine: 'yandex' (Realtime API voice) or 'fish' (Fish Audio via Kitta, text-only Yandex session)
    for col, ddl in (("emotions_allowed", "TEXT DEFAULT ''"), ("emotions_forbidden", "TEXT DEFAULT ''"),
                     ("tts_engine", "TEXT DEFAULT 'yandex'"), ("fish_voice", "TEXT DEFAULT ''"),
                     ("fish_voice_name", "TEXT DEFAULT ''"), ("fish_model", "TEXT DEFAULT ''"),
                     ("fillers", "INTEGER DEFAULT 1"), ("filler_kind", "TEXT DEFAULT 'short'"),
                     ("filler_delay_ms", "INTEGER DEFAULT 0"), ("greeting_delay_ms", "INTEGER DEFAULT 1000")):
        if col not in cols_a:
            _conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {ddl}")
    cols_c = {r[1] for r in _conn.execute("PRAGMA table_info(contacts)")}
    if "last_name" not in cols_c:
        _conn.execute("ALTER TABLE contacts ADD COLUMN last_name TEXT DEFAULT ''")
    if "relation" not in cols_c:
        # who the person is to the owner of the system: «Мама», «Жена», «Директор»
        _conn.execute("ALTER TABLE contacts ADD COLUMN relation TEXT DEFAULT ''")
    if "fields" not in cols_c:
        # the contact's own extra fields: [{"key": "День рождения", "value": "12 марта"}, …]
        _conn.execute("ALTER TABLE contacts ADD COLUMN fields TEXT DEFAULT '[]'")
    if "address" not in cols_c:
        _conn.execute("ALTER TABLE contacts ADD COLUMN address TEXT DEFAULT ''")
    if "is_self" not in cols_c:
        # the contact «Этот номер»: the owner — the SIM's number, the address, how to get there…
        _conn.execute("ALTER TABLE contacts ADD COLUMN is_self INTEGER DEFAULT 0")
    cols_k = {r[1] for r in _conn.execute("PRAGMA table_info(skills)")}
    if "knows_owner" not in cols_k:
        # the skill gets the owner's address and the fields of «Этот номер» (only while it's loaded)
        _conn.execute("ALTER TABLE skills ADD COLUMN knows_owner INTEGER DEFAULT 0")
    cols_u = {r[1] for r in _conn.execute("PRAGMA table_info(users)")}
    if "calls_seen_at" not in cols_u:
        _conn.execute("ALTER TABLE users ADD COLUMN calls_seen_at TEXT")
    cols_v = {r[1] for r in _conn.execute("PRAGMA table_info(voices)")}
    if "source" not in cols_v:
        _conn.execute("ALTER TABLE voices ADD COLUMN source TEXT DEFAULT 'custom'")
        _conn.execute("ALTER TABLE voices ADD COLUMN language TEXT DEFAULT ''")
        # voices seeded before these columns existed
        _conn.execute(f"UPDATE voices SET source='builtin' WHERE engine='yandex' AND COALESCE(role,'')='' "
                      f"AND ABS(COALESCE(speed,1)-1)<0.001 AND voice IN ({','.join('?' * len(VOICE_CATALOG))})",
                      [v[0] for v in VOICE_CATALOG])
        _conn.execute(f"UPDATE voices SET source='library', language='ru' WHERE engine='fish' "
                      f"AND voice IN ({','.join('?' * len(FISH_SEED_VOICES))})", [v[1] for v in FISH_SEED_VOICES])
    if "voice_id" not in cols_a:
        # the agent's voice from the voices table (Голоса); the older voice columns stay as a fallback
        _conn.execute("ALTER TABLE agents ADD COLUMN voice_id INTEGER")
    if "call_tools" not in cols:
        # which call functions the script needs (intersected with the agent's)
        _conn.execute("""ALTER TABLE scripts ADD COLUMN call_tools TEXT DEFAULT '["hangup_call","save_result"]'""")


def _decode(table: str, row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for col in JSON_COLUMNS.get(table, ()):
        if col in d and isinstance(d[col], str):
            try:
                d[col] = json.loads(d[col]) if d[col] else None
            except ValueError:
                pass
    for col in BOOL_COLUMNS.get(table, ()):
        if col in d and d[col] is not None:
            d[col] = bool(d[col])
    return d


def _encode(table: str, data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if k in JSON_COLUMNS.get(table, ()) and not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False)
        elif isinstance(v, bool):
            v = int(v)
        out[k] = v
    return out


def execute(sql: str, params=()) -> sqlite3.Cursor:
    with _lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        return cur


def fetch_all(table: str, sql: str, params=()) -> list[dict]:
    with _lock:
        rows = _conn.execute(sql, params).fetchall()
    return [_decode(table, r) for r in rows]


def fetch_one(table: str, sql: str, params=()) -> dict | None:
    with _lock:
        row = _conn.execute(sql, params).fetchone()
    return _decode(table, row)


def rows(sql: str, params=()) -> list[tuple]:
    with _lock:
        return [tuple(r) for r in _conn.execute(sql, params).fetchall()]


def scalar(sql: str, params=()):
    with _lock:
        row = _conn.execute(sql, params).fetchone()
    return row[0] if row else None


def get(table: str, id_: int) -> dict | None:
    return fetch_one(table, f"SELECT * FROM {table} WHERE id=?", (id_,))


def insert(table: str, data: dict) -> dict:
    data = _encode(table, data)
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    cur = execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
    return get(table, cur.lastrowid)


def insert_many(table: str, rows: list[dict]) -> int:
    """Insert many rows in one transaction (thousands of single commits are slow on an SD card)."""
    if not rows:
        return 0
    rows = [_encode(table, r) for r in rows]
    cols = list(rows[0])
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    with _lock:
        _conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        _conn.commit()
    return len(rows)


def log_usage(provider: str, kind: str, tokens_in: int = 0, tokens_out: int = 0, credits: float = 0,
              chars: int = 0, call_id: int | None = None):
    """Record what the app spent at a provider (never fails the caller)."""
    if not (tokens_in or tokens_out or credits or chars):
        return
    try:
        execute("INSERT INTO usage_log(provider, kind, tokens_in, tokens_out, credits, chars, call_id, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)", (provider, kind, tokens_in or 0, tokens_out or 0, credits or 0, chars or 0,
                                            call_id, now()))
    except Exception:  # noqa: BLE001
        pass


def update(table: str, id_: int, data: dict) -> dict | None:
    if data:
        data = _encode(table, data)
        sets = ", ".join(f"{k}=?" for k in data)
        execute(f"UPDATE {table} SET {sets} WHERE id=?", (*data.values(), id_))
    return get(table, id_)


def delete(table: str, id_: int) -> bool:
    return execute(f"DELETE FROM {table} WHERE id=?", (id_,)).rowcount > 0


# ---------------------------------------------------------------- settings

def get_settings() -> dict:
    values = dict(DEFAULT_SETTINGS)
    with _lock:
        for row in _conn.execute("SELECT key, value FROM settings"):
            try:
                values[row["key"]] = json.loads(row["value"])
            except ValueError:
                values[row["key"]] = row["value"]
    return values


def setting(key: str, default=None):
    v = get_settings().get(key, default)
    return default if v is None else v


def set_settings(values: dict):
    with _lock:
        for k, v in values.items():
            _conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, json.dumps(v, ensure_ascii=False)),
            )
        _conn.commit()


# ---------------------------------------------------------------- helpers

def normalize_phone(number: str) -> str:
    n = "".join(ch for ch in (number or "") if ch.isdigit() or ch in "+*#")
    if len(n) == 11 and n.startswith("8"):
        n = "+7" + n[1:]
    elif len(n) == 11 and n.startswith("7"):
        n = "+" + n
    return n


def normalize_number_pattern(value: str) -> str:
    """Exact number (normalized) or a prefix pattern ending with '*'."""
    value = (value or "").strip()
    if value.endswith("*"):
        body = "".join(ch for ch in value[:-1] if ch.isdigit() or ch == "+")
        if body.startswith("8") and len(body) > 1:
            body = "+7" + body[1:]
        return body + "*" if body else ""
    return normalize_phone(value)


def number_matches(pattern: str, number: str) -> bool:
    digits = lambda s: "".join(ch for ch in s if ch.isdigit())  # noqa: E731
    n = digits(normalize_phone(number))
    if not n:
        return False
    p = digits(pattern)
    if pattern.endswith("*"):
        return n.startswith(p)
    if len(p) >= 10 and len(n) >= 10:  # +7 926… and 8 926… are the same subscriber
        return p[-10:] == n[-10:]
    return p == n


def contact_fields(c: dict | None) -> list[tuple[str, str]]:
    """The contact's extra fields as (key, value), the empty ones left out."""
    out = []
    for f in (c or {}).get("fields") or []:
        if isinstance(f, dict):
            k, v = str(f.get("key") or "").strip(), str(f.get("value") or "").strip()
            if k and v:
                out.append((k, v))
    return out


def contact_label(c: dict | None) -> str:
    """«Имя Фамилия» for lists and transcripts."""
    if not c:
        return ""
    return " ".join(p for p in ((c.get("name") or "").strip(), (c.get("last_name") or "").strip()) if p)


def _phone_key(number: str) -> str:
    return normalize_phone(number or "")[-10:]


def spam_keys() -> set[str]:
    return {k for (k,) in rows("SELECT key FROM spam_numbers")}


def attach_contacts(rows: list[dict], field: str = "number") -> list[dict]:
    """Match rows (calls, SMS threads) to the phone book by number — at read time, so a contact saved,
    renamed or re-numbered later shows up on old calls too. Sets contact_id / contact_name."""
    book = {}
    for c in fetch_all("contacts", "SELECT * FROM contacts ORDER BY id"):
        book.setdefault(_phone_key(c["phone"]), c)
    for r in rows:
        c = book.get(_phone_key(r.get(field) or "")) if r.get(field) else None
        r["contact_id"] = c["id"] if c else None
        r["contact_name"] = contact_label(c) or None
    return rows


SELF_NAME = "Этот номер"


def self_contact() -> dict | None:
    return fetch_one("contacts", "SELECT * FROM contacts WHERE is_self=1 ORDER BY id LIMIT 1")


def ensure_self_contact() -> dict:
    """The contact «Этот номер» always exists; its phone is the SIM's number from «Настройки → Оператор»."""
    c = self_contact()
    phone = normalize_phone(setting("modem.own_number", "") or "")
    if not c:
        ts = now()
        return insert("contacts", {"name": SELF_NAME, "phone": phone, "is_self": 1, "created_at": ts, "updated_at": ts})
    if phone and normalize_phone(c.get("phone") or "") != phone:
        return update("contacts", c["id"], {"phone": phone, "updated_at": now()})
    return c


def find_contact(number: str) -> dict | None:
    n = normalize_phone(number)
    if not n:
        return None
    tail = n[-10:]
    for c in fetch_all("contacts", "SELECT * FROM contacts WHERE phone LIKE ?", (f"%{tail}",)):
        if normalize_phone(c["phone"])[-10:] == tail:
            return c
    return None


ALINA_CHARACTER = (
    "Ты доброжелательная, спокойная и внимательная. Говоришь по-русски просто и естественно, "
    "как живой человек, без канцелярита и заученных фраз. Обращаешься на «вы», пока собеседник "
    "не предложит иначе. Отвечаешь коротко и по делу, умеешь слушать и не перебиваешь. "
    "Если чего-то не знаешь — честно говоришь об этом, а не выдумываешь."
)


YANDEX_VOICE_NAMES = {
    "alena": "Алёна", "dasha": "Даша", "jane": "Джейн", "omazh": "Омаж", "julia": "Юлия", "lera": "Лера",
    "masha": "Маша", "marina": "Марина", "sofia": "София", "vera": "Вера", "irina": "Ирина",
    "saule_ru": "Сауле (рус.)", "zamira_ru": "Замира (рус.)", "zhanar_ru": "Жанар (рус.)", "yulduz_ru": "Юлдуз (рус.)",
    "filipp": "Филипп", "ermil": "Ермил", "zahar": "Захар", "madirus": "Мадирус", "alexander": "Александр",
    "kirill": "Кирилл", "anton": "Антон", "denis": "Денис", "vasily": "Василий", "sergey": "Сергей",
    "madi_ru": "Мади (рус.)", "saule": "Сауле (каз.)", "zhanar": "Жанар (каз.)", "yulduz": "Юлдуз (узб.)",
}
# a few neutral Russian voices from the Fish Audio library (S2.1 Pro Flash compatible)
FISH_SEED_VOICES = [
    ("Спокойный женский", "4b6d1ad3-97a4-4c60-bcae-c6a34537ad77", "нежный и спокойный женский голос"),
    ("Женский", "18ee4497-0180-4bd8-90cd-0d89778b3aa9", ""),
    ("Глубокий женский рассказчик", "213f6678-4d4c-4e42-b957-1679bdb6e304", ""),
    ("Мужской", "dc85d6e3-3029-4bbf-b826-89344d984abd", ""),
    ("Молодой мужчина", "0b45c8f8-0919-4c18-8761-606d26643dfd", ""),
    ("Уверенный мужской", "96c4d07f-0cc6-46e3-b1c2-7ca9444274ad", ""),
    ("Парень", "2d32ad7f-44d5-4f4c-8ca6-f73e5041eebe", ""),
    ("Русский диктор объявлений", "5d508114-bf56-405d-8b91-c498eda01f2d", ""),
]


REMOVED_YANDEX_VOICES = ("sofia", "vera", "irina", "denis", "vasily", "sergey")


def _drop_unsupported_voices():
    """Built-in Yandex voices the Realtime API can't speak with: remove them (with their hesitations and cached
    greetings) unless an agent uses one."""
    import shutil
    marks = ",".join("?" * len(REMOVED_YANDEX_VOICES))
    for (vid,) in rows(f"SELECT id FROM voices WHERE engine='yandex' AND source='builtin' AND voice IN ({marks}) "
                       "AND id NOT IN (SELECT voice_id FROM agents WHERE voice_id IS NOT NULL)", REMOVED_YANDEX_VOICES):
        execute("DELETE FROM voice_fillers WHERE voice_id=?", (vid,))
        execute("DELETE FROM voices WHERE id=?", (vid,))
        for sub in ("voice_fillers", "greetings"):
            shutil.rmtree(config.DATA_DIR / sub / str(vid), ignore_errors=True)


def _seed_voices():
    """Fill Голоса with the Yandex catalog and a few Fish voices, then link agents that predate the table."""
    ts = now()
    if not scalar("SELECT COUNT(*) FROM voices"):
        for name, lang, gender, _roles in VOICE_CATALOG:
            insert("voices", {"name": YANDEX_VOICE_NAMES.get(name, name), "engine": "yandex", "voice": name,
                              "source": "builtin", "language": lang,
                              "description": f"Yandex SpeechKit · {'женский' if gender == 'ж' else 'мужской'}"
                                             + ("" if lang == "ru" else f" · {lang}"),
                              "created_at": ts, "updated_at": ts})
        for name, voice_id, desc in FISH_SEED_VOICES:
            insert("voices", {"name": name, "engine": "fish", "voice": voice_id, "description": desc,
                              "source": "library", "language": "ru",
                              "created_at": ts, "updated_at": ts})
    for a in fetch_all("agents", "SELECT * FROM agents WHERE voice_id IS NULL"):
        fish_ = a.get("tts_engine") == "fish" and a.get("fish_voice")
        engine, voice = ("fish", a["fish_voice"]) if fish_ else ("yandex", a.get("voice") or "dasha")
        role = "" if fish_ else (a.get("voice_role") or "")
        speed = float(a.get("voice_speed") or 1.0)
        row = fetch_one("voices", "SELECT * FROM voices WHERE engine=? AND voice=? AND COALESCE(role,'')=? "
                                  "AND ABS(COALESCE(speed,1)-?)<0.001 ORDER BY id LIMIT 1", (engine, voice, role, speed))
        if not row:
            base = a.get("fish_voice_name") if fish_ else YANDEX_VOICE_NAMES.get(voice, voice)
            label = " · ".join(x for x in (base or voice, ROLE_LABELS.get(role, role),
                                            f"{speed:.2f}×" if abs(speed - 1) > 0.001 else "") if x)
            row = insert("voices", {"name": label, "engine": engine, "voice": voice, "role": role, "speed": speed,
                                    "model": (a.get("fish_model") or "") if fish_ else "",
                                    "created_at": ts, "updated_at": ts})
        update("agents", a["id"], {"voice_id": row["id"]})


def agent_voice(agent: dict) -> dict:
    """Voice fields the call needs (tts_engine, voice, voice_role, voice_speed, fish_*) from the agent's voice."""
    v = get("voices", agent["voice_id"]) if agent.get("voice_id") else None
    if not v:  # an agent without a voice from the list: its own older fields
        return {}
    if v["engine"] == "fish":
        return {"tts_engine": "fish", "fish_voice": v["voice"], "fish_voice_name": v["name"],
                "fish_model": v.get("model") or "", "fish_language": v.get("language") or "ru",
                "voice_speed": v.get("speed") or 1.0}
    return {"tts_engine": "yandex", "voice": v["voice"], "voice_role": v.get("role") or "",
            "voice_speed": v.get("speed") or 1.0}


def _seed():
    if scalar("SELECT COUNT(*) FROM agents"):
        return
    ts = now()
    agent = insert("agents", {
        "name": "Алина — ассистент",
        "description": "Вежливый голосовой ассистент по умолчанию",
        "role": "голосовой ассистент",
        "instructions": ALINA_CHARACTER,
        "voice": "dasha",
        "greeting": "Здравствуйте! Меня зовут Алина. Чем могу помочь?",
        "created_at": ts, "updated_at": ts,
    })
    insert("scripts", {
        "name": "Входящий: приём обращения",
        "description": "Принять входящий звонок, выяснить суть вопроса и контакты",
        "direction": "inbound",
        "prompt": (
            "Тебе звонит клиент с номера {{phone}}. Выясни, по какому вопросу он звонит, "
            "как к нему обращаться и когда ему удобно получить обратный звонок. "
            "Сохрани результат: status=lead, summary — суть обращения."
        ),
        "first_message": "Здравствуйте! Вы позвонили в компанию. Чем могу помочь?",
        "variables": [],
        "default_agent_id": agent["id"],
        "created_at": ts, "updated_at": ts,
    })
    insert("scripts", {
        "name": "Исходящий: подтверждение записи",
        "description": "Напомнить клиенту о записи и подтвердить визит",
        "direction": "outbound",
        "prompt": (
            "Ты звонишь клиенту {{name}} чтобы подтвердить запись на {{date}} в {{time}} "
            "к специалисту «{{service}}». Узнай, придёт ли клиент. Если нет — предложи перенести. "
            "Сохрани результат: status=confirmed / rescheduled / declined."
        ),
        "first_message": "Здравствуйте, {{name}}! Это напоминание о вашей записи.",
        "variables": [
            {"name": "name", "label": "Имя клиента", "default": ""},
            {"name": "date", "label": "Дата", "default": "завтра"},
            {"name": "time", "label": "Время", "default": "10:00"},
            {"name": "service", "label": "Услуга", "default": "консультация"},
        ],
        "default_agent_id": agent["id"],
        "created_at": ts, "updated_at": ts,
    })
    set_settings({"calls.inbound_agent_id": agent["id"], "calls.inbound_script_id": 1})
