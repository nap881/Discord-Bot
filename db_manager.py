import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=ENV_PATH)

def _get_or_create_key() -> bytes:
    key_str = os.environ.get("DB_ENCRYPTION_KEY")
    if not key_str:
        generated_key = Fernet.generate_key().decode()
        # Persist to .env
        try:
            with open(ENV_PATH, "a", encoding="utf-8") as f:
                f.write(f"\nDB_ENCRYPTION_KEY={generated_key}\n")
        except Exception as e:
            print(f"Warning: Failed to write DB_ENCRYPTION_KEY to .env: {e}")
        os.environ["DB_ENCRYPTION_KEY"] = generated_key
        key_str = generated_key
    return key_str.strip().encode()

FERNET = Fernet(_get_or_create_key())

DATA_FILE = os.path.join(os.path.dirname(__file__), "cubing_data.enc")
LEGACY_JSON = os.path.join(os.path.dirname(__file__), "cubing_data.json")
_lock = asyncio.Lock()

PUZZLE_ALIASES = {
    "222": "22",
    "333": "33",
    "444": "44",
    "555": "55",
    "666": "66",
    "777": "77",
    "pyraminx": "pyra",
    "megaminx": "mega",
    "square1": "sq1",
}

PUZZLE_NAMES = {
    "22": "2x2x2 Cube",
    "33": "3x3x3 Cube",
    "44": "4x4x4 Cube",
    "55": "5x5x5 Cube",
    "66": "6x6x6 Cube",
    "77": "7x7x7 Cube",
    "pyra": "Pyraminx",
    "mega": "Megaminx",
    "skewb": "Skewb",
    "sq1": "Square-1",
    "clock": "Clock",
}

def normalize_puzzle(puzzle: str) -> str:
    if not puzzle:
        return ""
    p = puzzle.lower()
    return PUZZLE_ALIASES.get(p, p)

def _load() -> dict:
    # 1. If encrypted file exists, decrypt and return
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                return {"users": {}}
            decrypted_bytes = FERNET.decrypt(encrypted_data)
            data = json.loads(decrypted_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                return {"users": {}}
            data.setdefault("users", {})
            return data
        except (InvalidToken, Exception) as e:
            print(f"Decryption failed or corrupted database: {e}. Resetting database.")
            return {"users": {}}

    # 2. Check if legacy unencrypted json exists; if so, migrate it
    if os.path.exists(LEGACY_JSON):
        try:
            with open(LEGACY_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data.setdefault("users", {})
                _save(data)
                try:
                    os.remove(LEGACY_JSON)
                except Exception:
                    pass
                return data
        except Exception:
            pass

    return {"users": {}}

def _save(data: dict):
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    encrypted_bytes = FERNET.encrypt(json_bytes)
    with open(DATA_FILE, "wb") as f:
        f.write(encrypted_bytes)

async def record_solve(user_id: int, username: str, puzzle: str, seconds: float, scramble: str) -> dict:
    puzzle = normalize_puzzle(puzzle)
    user_key = str(user_id)
    is_dnf = (seconds == float('inf') or seconds is None or seconds < 0)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    result_flags = {
        "is_new_pb": False,
        "pb_single": None,
        "global_average": None
    }

    async with _lock:
        data = _load()

        if user_key not in data["users"]:
            data["users"][user_key] = {"username": username, "puzzles": {}}
        else:
            data["users"][user_key]["username"] = username

        user_puzzles = data["users"][user_key]["puzzles"]
        if puzzle not in user_puzzles:
            user_puzzles[puzzle] = {
                "pb_single": None,
                "pb_single_scramble": None,
                "pb_single_date": None,
                "total_solves": 0,
                "valid_solves": 0,
                "total_seconds": 0.0,
                "global_average": None
            }

        up = user_puzzles[puzzle]
        up["total_solves"] += 1

        if not is_dnf:
            up["valid_solves"] += 1
            up["total_seconds"] = round(up["total_seconds"] + seconds, 2)
            up["global_average"] = round(up["total_seconds"] / up["valid_solves"], 2)

            if up["pb_single"] is None or seconds < up["pb_single"]:
                up["pb_single"] = seconds
                up["pb_single_scramble"] = scramble
                up["pb_single_date"] = now_str
                result_flags["is_new_pb"] = True

        result_flags["pb_single"] = up["pb_single"]
        result_flags["global_average"] = up["global_average"]

        _save(data)

    return result_flags

async def get_user_puzzle_stats(user_id: int, puzzle: str) -> dict:
    puzzle = normalize_puzzle(puzzle)
    async with _lock:
        data = _load()
        user_info = data["users"].get(str(user_id))
        if not user_info:
            return None
        return user_info.get("puzzles", {}).get(puzzle)

async def get_all_user_stats(user_id: int) -> dict:
    async with _lock:
        data = _load()
        user_info = data["users"].get(str(user_id))
        if not user_info:
            return {}
        return user_info.get("puzzles", {})
