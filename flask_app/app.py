import os
import sqlite3
import threading
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType


def create_app(database=None):
    app = Flask(__name__)
    app.config.update(DATABASE=database or os.environ.get('DATABASE_PATH', 'users.db'), MAX_CONTENT_LENGTH=16384)
    active_users = []
    active_lock = threading.Lock()

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=5)
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    with app.app_context():
        db().execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
        db().commit()

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        return jsonify(error='request_too_large'), 413

    @app.post('/adduser')
    def add_user():
        if request.mimetype != 'application/json':
            return jsonify(error='invalid_json'), 400
        try:
            payload = request.get_json()
        except (BadRequest, UnsupportedMediaType):
            return jsonify(error='invalid_json'), 400
        if not isinstance(payload, dict) or set(payload) != {'name'} or not isinstance(payload['name'], str):
            return jsonify(error='invalid_name'), 400
        name = payload['name'].strip()
        try:
            name_bytes = name.encode('utf-8')
        except UnicodeEncodeError:
            return jsonify(error='invalid_name'), 400
        if not name or len(name_bytes) > 200 or '\x00' in name:
            return jsonify(error='invalid_name'), 400
        connection = db()
        cursor = connection.execute('INSERT INTO users (name) VALUES (?)', (name,))
        connection.commit()
        return jsonify(status='ok', id=cursor.lastrowid, name=name), 201

    def parse_id(user_id):
        if not user_id.isascii() or not user_id.isdigit() or len(user_id) > 19:
            return None
        value = int(user_id)
        return value if 0 < value <= 2**63 - 1 else None

    @app.get('/user/<user_id>')
    def get_user(user_id):
        uid = parse_id(user_id)
        if uid is None:
            return jsonify(error='not_found'), 404
        row = db().execute('SELECT id, name FROM users WHERE id = ?', (uid,)).fetchone()
        if row is None:
            return jsonify(error='not_found'), 404
        return jsonify(id=row[0], name=row[1]), 200

    @app.post('/activate/<user_id>')
    def activate(user_id):
        uid = parse_id(user_id)
        if uid is None or db().execute('SELECT 1 FROM users WHERE id = ?', (uid,)).fetchone() is None:
            return jsonify(error='not_found'), 404
        with active_lock:
            active_users.append(uid)
            del active_users[:-3]
            snapshot = active_users.copy()
        return jsonify(status='ok', active=snapshot), 200

    @app.get('/slow')
    def slow():
        # Эквивалент исходного двойного цикла для 0 <= i < 1_000_000, 0 <= j < 100.
        total = 4950 * 1_000_000 * 999_999 // 2
        return str(total), 200, {'Content-Type': 'text/plain; charset=utf-8'}

    @app.get('/wrong')
    def wrong():
        return jsonify(error='demonstration_error'), 500

    return app


app = create_app()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=False)
