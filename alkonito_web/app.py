from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
import openpyxl
from openpyxl import Workbook
from flask import send_file
import os


app = Flask(__name__)
app.secret_key = "alkonito_secret_key"


# =========================
# CONEXIÓN BD
# =========================
def conectar_bd():
    conexion = sqlite3.connect("alkonito.db")
    conexion.row_factory = sqlite3.Row
    return conexion


# =========================
# CREAR TABLAS
# =========================
def crear_tablas():
    conexion = conectar_bd()
    cursor = conexion.cursor()

    # Tabla transacciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transacciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        monto REAL NOT NULL,
        descripcion TEXT,
        fecha TEXT NOT NULL
    )
    """)

    # Tabla arqueos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS arqueos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL UNIQUE,
        total_ingresos REAL NOT NULL,
        total_retiros REAL NOT NULL,
        saldo REAL NOT NULL
    )
    """)

    conexion.commit()
    conexion.close()


crear_tablas()


# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]

        if usuario == "admin" and clave == "1234":
            session["usuario"] = usuario
            return redirect("/menu")
        else:
            mensaje = "Usuario o clave incorrectos"
            return render_template("login.html", mensaje=mensaje)

    return render_template("login.html")


# =========================
# MENU PRINCIPAL
# =========================
@app.route("/menu")
def menu():
    if "usuario" not in session:
        return redirect("/")
    return render_template("menu.html")


# =========================
# REGISTRAR TRANSACCIÓN
# =========================
@app.route("/transaccion", methods=["GET", "POST"])
def transaccion():
    if "usuario" not in session:
        return redirect("/")

    if request.method == "POST":
        tipo = request.form["tipo"]
        descripcion = request.form["descripcion"]

        try:
            monto = float(request.form["monto"])
        except:
            mensaje = "Error: el monto debe ser numérico"
            return render_template("transaccion.html", mensaje=mensaje)

        if monto <= 0:
            mensaje = "Error: el monto debe ser mayor a 0"
            return render_template("transaccion.html", mensaje=mensaje)

        fecha = datetime.now().strftime("%Y-%m-%d")

        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO transacciones (tipo, monto, descripcion, fecha)
            VALUES (?, ?, ?, ?)
        """, (tipo, monto, descripcion, fecha))
        conexion.commit()
        conexion.close()

        mensaje = "Transacción registrada correctamente ✅"
        return render_template("transaccion.html", mensaje=mensaje)

    return render_template("transaccion.html")


# =========================
# REPORTE DIARIO
# =========================
@app.route("/reporte")
def reporte():
    if "usuario" not in session:
        return redirect("/")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    conexion = conectar_bd()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT * FROM transacciones
        WHERE fecha = ?
        ORDER BY id DESC
    """, (fecha_hoy,))
    transacciones = cursor.fetchall()

    # Totales
    cursor.execute("""
        SELECT SUM(monto) as total
        FROM transacciones
        WHERE fecha = ? AND tipo = 'Ingreso'
    """, (fecha_hoy,))
    total_ingresos = cursor.fetchone()["total"]
    if total_ingresos is None:
        total_ingresos = 0

    cursor.execute("""
        SELECT SUM(monto) as total
        FROM transacciones
        WHERE fecha = ? AND tipo = 'Retiro'
    """, (fecha_hoy,))
    total_retiros = cursor.fetchone()["total"]
    if total_retiros is None:
        total_retiros = 0

    conexion.close()

    saldo = total_ingresos - total_retiros

    return render_template(
        "reporte.html",
        transacciones=transacciones,
        fecha=fecha_hoy,
        ingresos=total_ingresos,
        retiros=total_retiros,
        saldo=saldo
    )

@app.route("/reporte_excel")
def reporte_excel():
    if "usuario" not in session:
        return redirect("/")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")

    conexion = conectar_bd()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT id, tipo, monto, descripcion, fecha
        FROM transacciones
        WHERE fecha = ?
        ORDER BY id DESC
    """, (fecha_hoy,))
    transacciones = cursor.fetchall()
    conexion.close()

    # Crear Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte Diario"

    # Encabezados
    ws.append(["ID", "Tipo", "Monto", "Descripción", "Fecha"])

    # Datos
    for t in transacciones:
        ws.append([t["id"], t["tipo"], t["monto"], t["descripcion"], t["fecha"]])

    # Nombre archivo
    nombre_archivo = f"reporte_{fecha_hoy}.xlsx"
    ruta_archivo = os.path.join(nombre_archivo)

    wb.save(ruta_archivo)

    return send_file(ruta_archivo, as_attachment=True)


# =========================
# FUNCIÓN PARA CALCULAR ARQUEO
# =========================
def calcular_arqueo(fecha):
    conexion = conectar_bd()
    cursor = conexion.cursor()

    cursor.execute("""
        SELECT SUM(monto) as total
        FROM transacciones
        WHERE fecha = ? AND tipo = 'Ingreso'
    """, (fecha,))
    ingresos = cursor.fetchone()["total"]
    if ingresos is None:
        ingresos = 0

    cursor.execute("""
        SELECT SUM(monto) as total
        FROM transacciones
        WHERE fecha = ? AND tipo = 'Retiro'
    """, (fecha,))
    retiros = cursor.fetchone()["total"]
    if retiros is None:
        retiros = 0

    conexion.close()

    saldo = ingresos - retiros
    return ingresos, retiros, saldo


# =========================
# ARQUEO DE CAJA (VER)
# =========================
@app.route("/arqueo")
def arqueo():
    if "usuario" not in session:
        return redirect("/")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    ingresos, retiros, saldo = calcular_arqueo(fecha_hoy)

    # Verificar si ya está guardado
    conexion = conectar_bd()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM arqueos WHERE fecha = ?", (fecha_hoy,))
    ya_guardado = cursor.fetchone()
    conexion.close()

    return render_template(
        "arqueo.html",
        fecha=fecha_hoy,
        ingresos=ingresos,
        retiros=retiros,
        saldo=saldo,
        ya_guardado=ya_guardado
    )


# =========================
# GUARDAR ARQUEO
# =========================
@app.route("/guardar_arqueo", methods=["POST"])
def guardar_arqueo():
    if "usuario" not in session:
        return redirect("/")

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    ingresos, retiros, saldo = calcular_arqueo(fecha_hoy)

    conexion = conectar_bd()
    cursor = conexion.cursor()

    # Verificar si ya existe arqueo de hoy
    cursor.execute("SELECT * FROM arqueos WHERE fecha = ?", (fecha_hoy,))
    existe = cursor.fetchone()

    if existe:
        conexion.close()
        return redirect("/arqueo")

    # Guardar
    cursor.execute("""
        INSERT INTO arqueos (fecha, total_ingresos, total_retiros, saldo)
        VALUES (?, ?, ?, ?)
    """, (fecha_hoy, ingresos, retiros, saldo))

    conexion.commit()
    conexion.close()

    return redirect("/arqueo")


# =========================
# HISTORIAL ARQUEOS
# =========================
@app.route("/arqueos")
def arqueos():
    if "usuario" not in session:
        return redirect("/")

    conexion = conectar_bd()
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT * FROM arqueos
        ORDER BY fecha DESC
    """)
    lista_arqueos = cursor.fetchall()
    conexion.close()

    return render_template("arqueos.html", arqueos=lista_arqueos)


# =========================
# CERRAR SESIÓN
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# =========================
# EJECUTAR
# =========================
if __name__ == "__main__":
    app.run(debug=True)
