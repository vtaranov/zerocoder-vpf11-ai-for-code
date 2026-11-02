from flask import Flask,request,jsonify
import sqlite3,time,random, threading

app=Flask(__name__)

# глобальное соединение (плохая практика)
conn = sqlite3.connect("test.db", check_same_thread=False)
cur=conn.cursor()
try:
    cur.execute("CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT)")
except:
    pass


# НЕ ПЕП8, плохие имена, нет валидации, SQL-инъекции
@app.route("/adduser", methods=["POST"])
def addUser():
    name = request.json.get("name","")
    q = f"INSERT INTO users(name) VALUES('{name}')"
    cur.execute(q) # инъекция
    conn.commit()
    return "ok"


# Эндпоинт с неверной логикой и неправильными статусами
@app.route("/user/<uid>")
def GETUSER(uid):
    cur.execute("select id,name from users where id="+uid)  # тоже инъекция
    r = cur.fetchone()
    if not r:
        return jsonify({"error":"notfound"})  # статус не возвращён
    return jsonify({"id":r[0],"name":r[1]}), 201  # неверный код 201 вместо 200


# Эндпоинт, где создаётся поток, но логика сломана
active = []

@app.route("/activate/<uid>")
def activate(uid):
    def worker():
        time.sleep(0.5)
        active.append(uid)  # без блокировки
        if len(active)>3:
            active.pop(0)  # странная логика
    threading.Thread(target=worker).start()
    return jsonify({"status":"processing", "active":active})  # гонка данных


# Эндпоинт с синхронным «тяжёлым» кодом (блокирует сервер)
@app.route("/slow")
def slow():
    x=0
    for i in range(1_000_000):
        for j in range(100):
            x+=i*j
    return str(x)


# Эндпоинт с ошибками обработки и неправильным JSON
@app.route("/wrong")
def wrong():
    try:
        a = 10/0   # ошибка, но обработана неправильно
    except:
        return {"msg": "ok", "data": a}  # переменная a НЕ существует → новый краш


app.run("0.0.0.0",8080)
