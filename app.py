import os
from functools import wraps
from flask import Flask, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from mysql.connector import IntegrityError
from logica_proyecto import GestorFinanciero, consultar

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # fotos de perfil

def pagina_privada(f):
    @wraps(f)
    def w(*a, **k):
        return f(*a, **k) if "uid" in session else redirect("/login")
    return w

def api_privada(f):
    @wraps(f)
    def w(*a, **k):
        if "uid" not in session:
            return jsonify(error="Sesión expirada. Inicia sesión de nuevo."), 401
        try:
            return f(*a, **k)
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return w

# ---------- Páginas ----------
@app.route("/")
def raiz():
    return redirect("/inicio" if "uid" in session else "/login")

@app.route("/login")
def login(): return render_template("login.html")

@app.route("/registro")
def registro(): return render_template("registro.html")

@app.route("/inicio")
@pagina_privada
def inicio(): return render_template("inicio.html")

@app.route("/panel")
@pagina_privada
def panel(): return render_template("panel.html")

@app.route("/perfil")
@pagina_privada
def perfil(): return render_template("perfil.html")

@app.route("/estadisticas")
@pagina_privada
def estadisticas():
    return render_template("estadisticas.html")



# ---------- Autenticación ----------
@app.post("/api/registro")
def api_registro():
    d = request.get_json(force=True)
    nombre, correo, usuario, pw = (d.get(k, "").strip() for k in ("nombre", "correo", "usuario", "password"))
    if not (nombre and correo and usuario) or len(pw) < 4:
        return jsonify(error="Completa todos los campos (contraseña de 4+ caracteres)."), 400
    try:
        consultar("insert into usuarios (nombre, correo, usuario, password_hash) values (%s,%s,%s,%s)",
                  (nombre, correo.lower(), usuario, generate_password_hash(pw)), "write")
    except IntegrityError:
        return jsonify(error="Ese usuario o correo ya está registrado."), 409
    return jsonify(ok=True)

@app.post("/api/login")
def api_login():
    d = request.get_json(force=True)
    u = consultar("select * from usuarios where usuario=%s", (d.get("usuario", "").strip(),), "one")
    if not u or not check_password_hash(u["password_hash"], d.get("password", "")):
        return jsonify(error="Usuario o contraseña incorrectos."), 401
    session["uid"] = u["id_usuario"]
    return jsonify(ok=True)

@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)

@app.post("/api/restaurar")
def api_restaurar():
    d = request.get_json(force=True)
    if len(d.get("password", "")) < 4:
        return jsonify(error="La contraseña debe tener al menos 4 caracteres."), 400
    _, n = consultar("update usuarios set password_hash=%s where correo=%s",
                     (generate_password_hash(d["password"]), d.get("correo", "").strip().lower()), "write")
    if not n:
        return jsonify(error="No hay ninguna cuenta con ese correo."), 404
    return jsonify(ok=True)


# ---------- Perfil ----------
@app.get("/api/perfil")
@api_privada
def get_perfil():
    u = consultar("select nombre, correo, usuario, descripcion, foto from usuarios where id_usuario=%s",
                  (session["uid"],), "one")
    return jsonify(u)

@app.put("/api/perfil")
@api_privada
def put_perfil():
    d = request.get_json(force=True)
    campos = [c for c in ("nombre", "correo", "descripcion", "foto") if c in d]
    if not campos:
        raise ValueError("Nada que actualizar.")
    try:
        consultar(f"update usuarios set {', '.join(c + '=%s' for c in campos)} where id_usuario=%s",
                  [d[c] for c in campos] + [session["uid"]], "write")
    except IntegrityError:
        return jsonify(error="Ese correo ya está en uso."), 409
    return jsonify(ok=True)

@app.route("/ahorros")
@pagina_privada
def ahorros():
    return render_template("ahorros.html")


@app.get("/api/emergencia")
@api_privada
def obtener_emergencia():
    fila = consultar(
        "SELECT monto_objetivo, monto_actual, meses_objetivo "
        "FROM fondos_emergencia WHERE id_usuario=%s",
        (session["uid"],),
        "one"
    )

    if not fila:
        return jsonify(
            monto_objetivo=500.0,
            monto_actual=0.0,
            meses_objetivo=6
        )

    return jsonify(
        monto_objetivo=float(fila["monto_objetivo"]),
        monto_actual=float(fila["monto_actual"]),
        meses_objetivo=int(fila["meses_objetivo"])
    )


@app.put("/api/emergencia")
@api_privada
def guardar_emergencia():
    d = request.get_json(force=True)

    objetivo = float(d.get("monto_objetivo") or 0)
    actual = float(d.get("monto_actual") or 0)
    meses = int(d.get("meses_objetivo") or 0)

    if objetivo <= 0 or actual < 0 or meses < 1 or meses > 120:
        raise ValueError("Revisá el monto, el ahorro y el plazo.")

    if actual > objetivo:
        raise ValueError("El ahorro reservado no puede superar el objetivo.")

    consultar(
        "INSERT INTO fondos_emergencia "
        "(id_usuario, monto_objetivo, monto_actual, meses_objetivo) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "monto_objetivo=VALUES(monto_objetivo), "
        "monto_actual=VALUES(monto_actual), "
        "meses_objetivo=VALUES(meses_objetivo)",
        (session["uid"], objetivo, actual, meses),
        "write"
    )

    return jsonify(ok=True)




# ---------- Finanzas ----------


@app.get("/api/resumen")
@api_privada
def resumen():
    g = GestorFinanciero(session["uid"])

    meta = consultar(
        "SELECT nombre, monto_meta, fecha_limite "
        "FROM metas WHERE id_usuario=%s",
        (session["uid"],),
        "one"
    )

    usuario = consultar(
        "SELECT nombre FROM usuarios WHERE id_usuario=%s",
        (session["uid"],),
        "one"
    )

    datos_meta = {
        "nombre": meta["nombre"],
        "monto": float(meta["monto_meta"]),
        "fecha_limite": meta["fecha_limite"].isoformat()
        if meta["fecha_limite"] else None
    } if meta else {
        "nombre": "Mi meta de ahorro",
        "monto": 1000.0,
        "fecha_limite": None
    }

    return jsonify(
        nombre=usuario["nombre"],
        **g.calcular_balance(),
        por_categoria=g.gastos_por_categoria(),
        meta=datos_meta
    )

@app.get("/api/resumen-mensual")
@api_privada
def resumen_mensual():
    meses = request.args.get("meses", default=6, type=int)

    if meses not in (6, 12):
        raise ValueError("El período debe ser de 6 o 12 meses.")

    gestor = GestorFinanciero(session["uid"])
    return jsonify(gestor.resumen_mensual(meses))


@app.get("/api/movimientos")
@api_privada
def movimientos():
    return jsonify(GestorFinanciero(session["uid"]).listar_movimientos())

@app.post("/api/ingresos")
@api_privada
def nuevo_ingreso():
    d = request.get_json(force=True)
    return jsonify(id=GestorFinanciero(session["uid"]).agregar_ingreso(
        d.get("descripcion"), d.get("monto"), d.get("fecha") or None)), 201

@app.post("/api/gastos")
@api_privada
def nuevo_gasto():
    d = request.get_json(force=True)
    return jsonify(id=GestorFinanciero(session["uid"]).agregar_gasto(
        d.get("descripcion", "").strip(), d.get("monto"), d.get("categoria", "otros"), d.get("fecha") or None)), 201

@app.delete("/api/ingresos/<int:i>")
@api_privada
def borrar_ingreso(i):
    return jsonify(ok=GestorFinanciero(session["uid"]).eliminar_ingreso(i))

@app.delete("/api/gastos/<int:i>")
@api_privada
def borrar_gasto(i):
    return jsonify(ok=GestorFinanciero(session["uid"]).eliminar_gasto(i))


@app.put("/api/meta")
@api_privada
def put_meta():
    d = request.get_json(force=True)

    nombre = (d.get("nombre") or "").strip()
    monto = float(d.get("monto") or 0)
    fecha_limite = d.get("fecha_limite") or None

    if monto <= 0 or not nombre:
        raise ValueError("Escribe un nombre y un monto mayor a cero.")

    consultar(
        "INSERT INTO metas (id_usuario, nombre, monto_meta, fecha_limite) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "nombre = VALUES(nombre), "
        "monto_meta = VALUES(monto_meta), "
        "fecha_limite = VALUES(fecha_limite)",
        (session["uid"], nombre[:100], monto, fecha_limite),
        "write"
    )

    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True)
