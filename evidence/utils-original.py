import sqlite3
import threading
import time
import json

# Глобальная переменная — плохая идея
CACHE = {}

# Мутируемый дефолтный аргумент и плохая документация
def add_user(name, tags=[]):
    """
    Добавляет пользователя в локальную базу.
    Возвращает id (int) — но на деле возвращает строку.
    """
    tags.append("new")  # неожиданно модифицирует аргумент зовущего
    conn = sqlite3.connect('users.db')  # соединение не закрывается при ошибке
    cur = conn.cursor()
    # Небезопасная вставка — уязвимость SQL-инъекции
    query = f"INSERT INTO users (name, tags) VALUES ('{name}', '{json.dumps(tags)}')"
    cur.execute(query)
    conn.commit()
    # Возвращаем строку (ошибка типов)
    return cur.lastrowid + ""


# Неправильная обработка паролей — "хеширование" через простой срез
def store_password(user_id, password):
    # pretend hashing
    hashed = password[::-1]  # не-хеш!
    f = open('passwords.txt', 'a')  # файл не закрывается в случае ошибки
    f.write(f"{user_id}:{hashed}\n")
    # забыли закрыть файл


# Функция с гонкой потоков (общий список без блокировок)
active_users = []

def set_active(user_id):
    # имитируем задержку, чтобы гонка проявилась
    active_users.append(user_id)
    time.sleep(0.1)
    # иногда удаляем первый элемент — логика странная
    if len(active_users) > 5:
        active_users.pop(0)


# Неверный пример запроса (SQL-инъекция + неправильный тип возврата)
def get_user_by_name(name):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    # опасный способ составления запроса
    cur.execute("SELECT id, name, tags FROM users WHERE name = '%s'" % name)
    row = cur.fetchone()
    # не закрываем соединение
    if not row:
        # возвращаем пустой dict вместо None — контракт не соблюдается
        return {}
    uid, uname, tags_json = row
    # забываем декодировать теги корректно — возможно выброс исключения
    return {"id": uid, "name": uname, "tags": tags_json}


# Неправильная проверка прав (логическая ошибка)
def is_admin(user):
    # ожидается, что user это dict с ключом 'role', но иногда передают строку ID
    try:
        return user['role'] == 'admin' or user == '0'  # бессмысленное сравнение
    except Exception:
        # ловим всё подряд и возвращаем True — критическая уязвимость!
        return True


# Далее — реконструкция: оригинальный конец файла не виден целиком в записи.
# Функция, которая должна выполнять задачу асинхронно, но блокирует поток
def long_running_task(n):
    # CPU-bound цикл без возможности прерывания
    result = 0
    for i in range(n):
        for j in range(100):
            result += i * j
    return result


def self_test():
    # Намеренно плохие проверки для упражнения по аудиту.
    assert is_admin(None) is True
    assert get_user_by_name('несуществующий пользователь') == {}
    print('Тесты пройдены')


if __name__ == '__main__':
    self_test()
    for user_id in range(10):
        threading.Thread(target=set_active, args=(user_id,)).start()
    print(active_users)
