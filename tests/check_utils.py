"""Изолированная проверка utils; исходный файл извлекается через AST без импорта."""
import ast
import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = root / 'evidence' / 'utils-original.py'
module_path = root / 'evidence' / 'utils_refactored.py'
tree = ast.parse(source.read_text(encoding='utf-8'))
functions = [item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name in {'long_running_task', 'is_admin'}]
namespace = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), str(source), 'exec'), namespace)
spec = importlib.util.spec_from_file_location('utils_refactored', module_path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert namespace['is_admin'](None) is True and not m.is_admin(None)
assert not m.is_admin('0') and m.is_admin({'role': 'admin'}) and not m.is_admin({'role': 'user'})
for n in (0, 1, 2, 4, 25):
    assert m.long_running_task(n) == namespace['long_running_task'](n)
assert m.run_long_running_task_in_thread(4).result(timeout=5) == 29700
with tempfile.TemporaryDirectory() as d:
    m.DB_PATH = Path(d) / 'test.db'
    with sqlite3.connect(m.DB_PATH) as connection:
        connection.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, tags TEXT)')
    tags = ['starter']; uid = m.add_user("O'Brien'); --", tags)
    assert isinstance(uid, int) and tags == ['starter']
    assert json.loads(m.get_user_by_name("O'Brien'); --")['tags']) == ['starter', 'new']
    assert m.get_user_by_name("' OR 1=1 --") == {}
    m.store_password(uid, 'test-password')
    assert m.verify_password(uid, 'test-password') and not m.verify_password(uid, 'wrong')
    m.store_password(uid, 'replacement')
    assert m.verify_password(uid, 'replacement') and not m.verify_password(uid, 'test-password')
    for i in range(1, 8): m.set_active(i)
    assert m.get_active_users() == [3, 4, 5, 6, 7]
m.self_test()
print('PASS: оригинальный расчёт, безопасность роли, БД, пароли, активность, self_test')
