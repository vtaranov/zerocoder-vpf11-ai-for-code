"""Проверка контракта HTTP для пяти маршрутов. Нужна отдельная тестовая база."""
import concurrent.futures
import json
import sys
import urllib.error
import urllib.request

base = sys.argv[1].rstrip('/')

def call(method, path, data=None, content_type='application/json'):
    headers = {'Content-Type': content_type} if data is not None else {}
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)

def check(condition, message):
    if not condition:
        raise AssertionError(message)

def create(name):
    return call('POST', '/adduser', json.dumps({'name': name}, ensure_ascii=False).encode())

status, user = create("O'Brien'); DROP TABLE users; --")
check(status == 201 and user['name'] == "O'Brien'); DROP TABLE users; --", 'create')
uid = user['id']
check(call('GET', '/user/' + str(uid)) == (200, {'id': uid, 'name': user['name']}), 'get')
check(call('GET', '/user/9223372036854775807') == (404, {'error': 'not_found'}), 'not found')
check(call('GET', '/user/abc') == (404, {'error': 'not_found'}), 'invalid id')
check(call('POST', '/activate/abc') == (404, {'error':'not_found'}), 'invalid activation')
check(call('POST', '/activate/9223372036854775807') == (404, {'error':'not_found'}), 'missing activation')
for _ in range(5):
    status, active = call('POST', '/activate/' + str(uid))
    check(status == 200 and active['status'] == 'ok' and len(active['active']) <= 3, 'activation')
check(active['active'] == [uid] * 3, 'activity bound and repeated activation')
check(call('GET', '/slow') == (200, 2474997525000000), 'slow calculation')
check(call('GET', '/wrong') == (500, {'error':'demonstration_error'}), 'controlled error')
try:
    urllib.request.urlopen(base + '/activate/' + str(uid), timeout=10)
except urllib.error.HTTPError as e:
    check(e.code == 405, 'activation GET rejected')
else:
    raise AssertionError('activation GET must be rejected')
for value in ('', '   ', 123, None, 'x' * 201):
    check(create(value) == (400, {'error': 'invalid_name'}), 'invalid name ' + repr(value))
check(call('POST', '/adduser', b'[]') == (400, {'error':'invalid_name'}), 'JSON array')
check(call('POST', '/adduser', b'null') == (400, {'error':'invalid_name'}), 'JSON null')
check(call('POST', '/adduser', b'{') == (400, {'error':'invalid_json'}), 'invalid JSON')
check(call('POST', '/adduser', b'{"name":"A"}', 'text/plain') == (400, {'error':'invalid_json'}), 'content type')
check(call('POST', '/adduser', b'{"name":"' + b'x'*17000 + b'"}') == (413, {'error':'request_too_large'}), 'body limit')
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(lambda i: create('user ' + str(i)), range(10)))
check(all(status == 201 for status, _ in results), 'concurrent inserts')
check(len({item['id'] for _, item in results}) == 10, 'distinct IDs')
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    activations = list(pool.map(lambda pair: call('POST', '/activate/' + str(pair[1]['id'])), results))
check(all(code == 200 and len(body['active']) <= 3 for code, body in activations), 'concurrent activations')
print('PASS: all five routes, validation, SQL injection, activation limit, concurrent requests')
print('example:', json.dumps(user, ensure_ascii=False))
