"""Утилиты для SQLite. Таблица users должна быть создана приложением заранее."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

DB_PATH = Path("users.db")
_ACTIVE_LIMIT = 5
_active_users: list[int] = []
_active_lock = threading.Lock()
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _user_id(value: int | str) -> int:
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 19:
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= 2**63 - 1:
        raise ValueError("user_id должен быть положительным целым числом SQLite")
    return value


def add_user(name: str, tags: list[str] | None = None) -> int:
    """Добавить пользователя; входной список меток не изменяется."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Имя должно быть непустой строкой")
    if tags is not None and (not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags)):
        raise ValueError("tags должен быть списком строк")
    user_tags = list(tags) if tags is not None else []
    if "new" not in user_tags:
        user_tags.append("new")
    with closing(_connect()) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO users (name, tags) VALUES (?, ?)",
            (name, json.dumps(user_tags, ensure_ascii=False)),
        )
        return int(cursor.lastrowid)


def store_password(user_id: int | str, password: str) -> None:
    """Сохранить проверочный хеш пароля существующего пользователя."""
    user_id = _user_id(user_id)
    if not isinstance(password, str) or not password or len(password.encode("utf-8")) > 1024:
        raise ValueError("Пароль должен содержать от 1 до 1024 байт UTF-8")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    with closing(_connect()) as connection, connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS user_passwords (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            salt BLOB NOT NULL, digest BLOB NOT NULL,
            n INTEGER NOT NULL, r INTEGER NOT NULL, p INTEGER NOT NULL
        )""")
        connection.execute("""INSERT INTO user_passwords (user_id, salt, digest, n, r, p)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET salt=excluded.salt, digest=excluded.digest,
                n=excluded.n, r=excluded.r, p=excluded.p""",
            (user_id, salt, digest, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P))


def verify_password(user_id: int | str, password: str) -> bool:
    """Проверить пароль; при отсутствии записи вернуть False."""
    user_id = _user_id(user_id)
    if not isinstance(password, str) or not password or len(password.encode("utf-8")) > 1024:
        return False
    with closing(_connect()) as connection:
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='user_passwords'").fetchone()
        if not exists:
            return False
        row = connection.execute("SELECT salt, digest, n, r, p FROM user_passwords WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return False
    salt, expected, n, r, p = row
    # Параметры берутся из базы; допускаются только известные безопасные значения.
    if (n, r, p) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P) or len(salt) != 16 or len(expected) != 32:
        raise ValueError("Некорректная запись хеша пароля")
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return hmac.compare_digest(actual, expected)


def set_active(user_id: int | str) -> None:
    """Отметить пользователя активным; сохраняются пять последних разных ID."""
    user_id = _user_id(user_id)
    with _active_lock:
        if user_id in _active_users:
            _active_users.remove(user_id)
        _active_users.append(user_id)
        del _active_users[:-_ACTIVE_LIMIT]


def get_active_users() -> list[int]:
    """Вернуть копию списка от наиболее давнего к наиболее недавнему."""
    with _active_lock:
        return _active_users.copy()


def get_user_by_name(name: str) -> dict:
    """Найти одну запись; при отсутствии вернуть пустой словарь."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Имя должно быть непустой строкой")
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT id, name, tags FROM users WHERE name = ? ORDER BY id LIMIT 1", (name,)
        ).fetchone()
    if row is None:
        return {}
    uid, uname, tags_json = row
    return {"id": uid, "name": uname, "tags": tags_json}


def is_admin(user: object) -> bool:
    """Проверить роль в уже проверенных данных пользователя."""
    return isinstance(user, dict) and user.get("role") == "admin"


def long_running_task(n: int) -> int:
    """Вычислить сумму i*j для i от 0 до n-1 и j от 0 до 99."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError("n должно быть неотрицательным целым числом")
    return 4950 * n * (n - 1) // 2


def run_long_running_task_in_thread(n: int):
    """Запустить расчёт в потоке и вернуть Future с результатом или ошибкой."""
    from concurrent.futures import Future

    future = Future()

    def worker() -> None:
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(long_running_task(n))
        except BaseException as exc:
            future.set_exception(exc)

    threading.Thread(target=worker, daemon=True).start()
    return future


def self_test() -> None:
    """Проверить основные операции в отдельном процессе и временной базе."""
    import subprocess
    import sys

    script = r'''
import importlib.util, sqlite3, sys, tempfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("module_under_test", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as directory:
    m.DB_PATH = Path(directory) / "test.db"
    with sqlite3.connect(m.DB_PATH) as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, tags TEXT NOT NULL)")
    tags = ["starter"]
    user_id = m.add_user("test'user", tags)
    if tags != ["starter"] or m.get_user_by_name("test'user")["id"] != int(user_id):
        raise RuntimeError("Ошибка создания или поиска пользователя")
    if m.get_user_by_name("' OR 1=1 --") != {}:
        raise RuntimeError("Ошибка защиты запроса")
    m.store_password(user_id, "secretpassword")
    if not m.verify_password(user_id, "secretpassword") or m.verify_password(user_id, "wrong"):
        raise RuntimeError("Ошибка проверки пароля")
    m.set_active(user_id)
    if int(user_id) not in m.get_active_users():
        raise RuntimeError("Ошибка списка активных пользователей")
    if not m.is_admin({"role": "admin"}) or m.is_admin(None):
        raise RuntimeError("Ошибка проверки роли")
    if m.run_long_running_task_in_thread(4).result(timeout=5) != 29700:
        raise RuntimeError("Ошибка вычисления")
'''
    subprocess.run([sys.executable, "-c", script, str(Path(__file__).resolve())], check=True)
