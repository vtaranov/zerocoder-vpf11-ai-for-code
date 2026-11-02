# VPf11 - аудит кода, Flask API и перенос на Go

Учебный проект Zerocoder: аудит Python-модуля и Flask-приложения, исправление ошибок, перенос HTTP API на Go, документация OpenAPI и запуск Go-сервера в Docker.

## Состав

| Файл / каталог | Назначение |
|---|---|
| [utils-original.py](evidence/utils-original.py), [api-original.py](evidence/api-original.py) | Полученные учебные исходники с намеренными ошибками. Не предназначены для запуска как готовые приложения. Конец первого файла помечен его автором как реконструкция. |
| [utils_refactored.py](evidence/utils_refactored.py) | Исправленные утилиты SQLite, проверки роли, хранения пароля и вычисления. |
| [flask_app/app.py](flask_app/app.py) | Исправленное приложение Flask. |
| [go_server](go_server) | Реализация тех же пяти маршрутов на Go; обработчики и хранилище разделены на пакеты. |
| [openapi.yaml](go_server/openapi.yaml) | Спецификация OpenAPI 3.1. |
| [Dockerfile](go_server/Dockerfile) | Многоэтапная сборка Go-сервера с запуском от непривилегированного пользователя. |
| [check_api.py](tests/check_api.py), [check_utils.py](tests/check_utils.py) | HTTP-проверки и изолированные проверки утилит. |

`utils_refactored.py` - отдельный модуль, API его не импортирует. Для проверки исходные функции расчёта и проверки роли извлекаются через AST без запуска исходного файла целиком.

## Исправления

SQL-запросы параметризованы; добавлена проверка JSON, имени и ID; соединения SQLite закрываются. Исправлены HTTP-статусы, ошибка проверки прав, изменяемый аргумент по умолчанию и конкурентный доступ к спискам. Пароли в исправленном модуле сохраняются как хеши `scrypt` с индивидуальной солью. Результат исходного двойного цикла вычисляется по эквивалентной формуле.

Это учебный API без аутентификации, авторизации, HTTPS и ограничений частоты запросов. Используйте локальный интерфейс или доверенную среду и только тестовые данные. Список активности хранится в памяти одного процесса и очищается при перезапуске; данные пользователей сохраняются в SQLite.

## Маршруты

| Метод и путь | Ответ |
|---|---|
| `POST /adduser` | JSON с единственным полем `name`; `201` с `status`, `id`, `name`. Неверные данные - `400`, тело свыше 16 КиБ - `413`. |
| `GET /user/{id}` | `200` с `id` и `name` или `404`. |
| `POST /activate/{id}` | Для существующего пользователя: `200` с `status` и тремя последними добавлениями в `active`; повторы допустимы. GET намеренно запрещён. |
| `GET /slow` | `200`, текст `2474997525000000`: результат исходного цикла без длительного вычисления. |
| `GET /wrong` | Контролируемый учебный `500` с `error: demonstration_error`. |

Имя после удаления краевых пробелов должно быть непустым, без NUL, не длиннее 200 байт UTF-8. ID - положительное целое число в пределах знакового 64-битного типа. Обработка ошибок и методов описана для проверенных сценариев, полная идентичность реализаций для всех входов не утверждается.

## Подготовка Python

Для совместной проверки приложения и утилит используйте Python 3.12+ со встроенной `hashlib.scrypt`; тестировалось на Python 3.12.14. Для самого Flask достаточно Python 3.9+. Команды ниже выполняются из корня репозитория на macOS/Linux.

```sh
git clone https://github.com/vtaranov/zerocoder-vpf11-ai-for-code.git
cd zerocoder-vpf11-ai-for-code
python3 -m venv .venv
.venv/bin/python -m pip install -r flask_app/requirements.txt
.venv/bin/python tests/check_utils.py
```

Проверки утилит используют временную базу. Для интеграции модуля с собственными данными предварительно нужна таблица `users` со столбцами `id INTEGER PRIMARY KEY`, `name`, `tags`. Миграция прежних паролей не выполняется: обратимое хранение в исходнике требует организации их смены.

## Flask локально

```sh
DATABASE_PATH=flask-test.db .venv/bin/python -m flask --app flask_app.app run --host 127.0.0.1 --port 8080
```

В другом терминале из корня репозитория:

```sh
curl -i -X POST http://127.0.0.1:8080/adduser -H 'Content-Type: application/json' -d '{"name":"Anna"}'
curl -i http://127.0.0.1:8080/user/1
curl -i -X POST http://127.0.0.1:8080/activate/1
curl -i http://127.0.0.1:8080/slow
curl -i http://127.0.0.1:8080/wrong
.venv/bin/python tests/check_api.py http://127.0.0.1:8080
```

Вместо `1` подставьте ID созданной записи. `/wrong` ожидаемо возвращает `500`. Проверочный скрипт создаёт записи: используйте отдельную тестовую базу. Остановка сервера - Ctrl-C. Встроенный сервер Flask предназначен для разработки.

## Go локально

Установите Go версии из [go.mod](go_server/go.mod). Зависимости и контрольные суммы записаны в `go.mod` и `go.sum`.

```sh
cd go_server
DATABASE_PATH=go-test.db LISTEN_ADDR=127.0.0.1:8080 go run ./cmd/server
```

В другом терминале из корня репозитория выполните `python3 tests/check_api.py http://127.0.0.1:8080`. Не запускайте две реализации на одном порту одновременно. Для сборки пакетов: `cd go_server && go test ./...` (отдельных Go-тестов нет).

## Docker

Из корня репозитория:

```sh
docker build -t vpf11-user-api:2.0 go_server
docker run -d --name vpf11-demo -p 127.0.0.1:18193:8080 \
  --mount type=volume,src=vpf11-demo-data,dst=/data \
  --cap-drop ALL --security-opt no-new-privileges --memory 128m --pids-limit 64 \
  vpf11-user-api:2.0
python3 tests/check_api.py http://127.0.0.1:18193
```

Файл `/data/users.db` находится в именованном томе и сохраняется при перезапуске или пересоздании контейнера с тем же томом. Остановка: `docker stop vpf11-demo`. Другие контейнеры и тома команды не затрагивают.

Для Linux VPS с архитектурой amd64 можно собрать образ на компьютере другой архитектуры и передать напрямую, без публикации в Docker Hub:

```sh
docker buildx build --platform linux/amd64 --load -t vpf11-user-api:2.0 go_server
docker save vpf11-user-api:2.0 | gzip | ssh USER@VPS 'gunzip | docker load'
```

На VPS запустите аналогичный контейнер с отдельным томом и свободным портом, например `-p 127.0.0.1:18087:8080`. Для доступа с компьютера: `ssh -L 18194:127.0.0.1:18087 USER@VPS`, затем `python3 tests/check_api.py http://127.0.0.1:18194`. Базовые образы сборки загружаются из Docker Hub.

## Проверка OpenAPI

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/openapi-spec-validator go_server/openapi.yaml
```

Валидация схемы дополняет HTTP-проверки; её успешный результат не подтверждает отсутствие всех ошибок приложения.
