from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from crud import cartones_disponibles,cartones_usados,reintegrar_cartones,get_data,actualizar_partida,obtener_datos_partida, get_enunciado, get_premio, insertar_comprador, get_estatus, get_precio, vendidos, get_modalidad, get_dolar, get_zelle
import os
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3
from datetime import datetime
import random
import string
import re
import time

def generar_sufijo_aleatorio(length=6):
    # Genera un sufijo aleatorio de letras y números
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choices(caracteres, k=length))


# Decorador para proteger las rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):  # Verifica si el usuario está autenticado
            return redirect(url_for('admin_index'))  # Redirige al login si no está autenticado
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
UPLOAD_FOLDER = 'static/comprobantes'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'supersecretkey'
socketio = SocketIO(app, manage_session=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def init_db():
    with sqlite3.connect("bingo.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cartones_temporales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                carton TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=["GET"])
def index():
    return render_template('index.html', enunciado=get_enunciado())

@app.route("/cartones", methods=["GET"])
def imprimir_cartones():
    estatus = get_estatus()
    if estatus == "Venta finalizada":
        return redirect(url_for('index'))  # redirigir a un panel de administración

    cartones_tuplas = cartones_disponibles(read="*")
    cartones = [carton[0] for carton in cartones_tuplas]

    return render_template("seleccion_cartones.html", cartones=cartones,
                           precio=int(get_precio()), modalidad=get_modalidad(),
                           precio_dolares=get_dolar())

@app.route("/compra", methods=["POST", "GET"])
def pago():
    if request.method == "POST":
        # Recoger los datos del formulario de pago
        cartones_seleccionados = request.form.getlist("cartones")

        # Conectar a la base de datos para verificar duplicados parciales
        with sqlite3.connect("bingo.db") as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cartones_temporales WHERE timestamp <= datetime('now', '-25 minutes')")
            conn.commit()

            if len(cartones_seleccionados) == 1 and ',' in cartones_seleccionados[0]:
                # Dividir la cadena en valores separados
                cartones_seleccionados = cartones_seleccionados[0].split(',')

            # Verificar si alguno de los cartones seleccionados ya está en la base de datos
            placeholders = ', '.join('?' for _ in cartones_seleccionados)
            cursor.execute(f"SELECT carton FROM cartones_temporales WHERE carton IN ({placeholders})", cartones_seleccionados)
            duplicados = cursor.fetchall()

            if duplicados:
                # Redirigir si hay coincidencias
                duplicados = [carton[0] for carton in duplicados]
             # Verificar si es singular o plural
                if len(duplicados) == 1:
                    flash(f"El cartón {duplicados[0]} ya ha sido seleccionado.", "warning")
                else:
                    flash(f"Los cartones {', '.join(duplicados)} ya han sido seleccionados.", "warning")

                return redirect(url_for("imprimir_cartones"))


            # Si cartones_seleccionados contiene una cadena con comas
            if len(cartones_seleccionados) == 1 and ',' in cartones_seleccionados[0]:
                # Dividir la cadena en valores separados
                cartones_seleccionados = cartones_seleccionados[0].split(',')

            # Si no hay duplicados, insertamos cada cartón por separado
            cartones_individuales = [(c,) for c in cartones_seleccionados]

            # Ejecuta la inserción de cada cartón como fila individual
            cursor.executemany("INSERT INTO cartones_temporales (carton) VALUES (?)", cartones_individuales)
            conn.commit()
        total_price = float(request.form["total"])  # Total en bolívares
        total_price_2 = float(request.form["total2"])  # Total en dólares

        # Pasar los valores al template
        return render_template(
            "comprar.html",
            cartones_seleccionados=', '.join(cartones_seleccionados),
            total_price=total_price,
            total_price2=total_price_2,
            premio=get_premio(),
            precio=int(get_precio()),
            enunciado=get_enunciado(),
            zelle=get_zelle(),
            precio_dolares=get_dolar()
        )

    # Si no es POST, solo se muestran los datos vacíos
    return render_template("comprar.html", cartones_seleccionados='', total_price=0,
                           premio=get_premio(), precio=int(get_precio()), enunciado=get_enunciado(),
                           total_price2=0, zelle=get_zelle(), precio_dolares=get_dolar())



@app.route("/registrar_compra", methods=["POST", "GET"])
def registrar():
    if request.method == "POST":


        # Recuperar los datos del formulario
        nombre = request.form["nombre"]
        cedula = request.form["cedula"]
        nmr_te = request.form["telefono"]
        nmr_r = request.files["referencia"]
        n_referencia = request.form["n_referencia"]

        # Validar y guardar el archivo de referencia si es necesario
        if nmr_r and allowed_file(nmr_r.filename):
            filename = secure_filename(nmr_r.filename)
            # Agregar un sufijo aleatorio al nombre del archivo
            nombre_archivo, extension = os.path.splitext(filename)
            sufijo = generar_sufijo_aleatorio()
            filename = f"{nombre_archivo}_{sufijo}{extension}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            nmr_r.save(filepath)
            referencia_ruta = os.path.join('/static/comprobantes', filename).replace("\\", "/")
            fecha = get_enunciado()

        # Recuperar los datos de la compra (los valores pasados en los campos ocultos)
        cartones_seleccionados_str = request.form.get("cartones_seleccionados", "")
        total_price = request.form.get("total_price", 0)

        link = f"/descargar_cartones?cartones={cartones_seleccionados_str}"

        # Insertar los datos en la base de datos
        insertar_comprador(
            nombre, cedula, nmr_te, n_referencia, cartones_seleccionados_str,
            f"{total_price}bs",
            fecha, referencia_ruta, link, cartones_seleccionados_str
        )

        return render_template('confirmacion.html')

@app.route('/descargar_cartones')
def descargar_cartones():
    cartones = request.args.get('cartones', '')
    cartones_lista = cartones.split(',')

    # Puedes devolver una vista donde se muestran las imágenes de los cartones
    return render_template('descargar_cartones.html', cartones=cartones_lista)



@app.route("/admin", methods=["GET", "POST"])
def admin_index():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin123":
            session['logged_in'] = True  # Establece que el usuario está autenticado
            return redirect(url_for('admin_dashboard'))  # redirigir a un panel de administración
        else:
            error_message = "Usuario o contraseña incorrectos"
            return render_template("login.html", error_message=error_message)

    return render_template("login.html")

"""elimine las rutas puente de carton y usuario y usuario requerido a usuario verificado porque NO SE PORQUE NO OBTENGO EL CARTON SI LO ESTA ENVIADNO AL SERVIDOR"""
@app.route("/admin/dashboard")
@login_required  # Ruta protegida por login

def admin_dashboard():
    return render_template("panel_admin.html")


@app.route("/admin/dashboard/partida" , methods = ["POST" , "GET"])
@login_required  # Ruta protegida por login

def admin_dashboard_partida():
    datos = obtener_datos_partida()

    if request.method == "POST":
        action = request.form.get("action")  # "reiniciar" o "detener"
        fecha_enunciado = request.form.get("fechaEnunciado")
        recompensa = request.form.get("recompensa")
        precio_carton = request.form.get("precioCarton")
        tipo_carton = request.form.get("tipoCarton")
        precio_dolares = request.form.get("precioCarton$")
        zelle = request.form.get("zelle")
        actualizar_partida(fecha_enunciado, recompensa, precio_carton, tipo_carton, action, precio_dolares, zelle)

        
        return redirect(url_for('admin_dashboard_partida'))  # redirigir a un panel de administración

    return render_template("admin_partida.html", datos=datos)

@app.route("/admin/dashboard/partida/reiniciar" , methods = ["POST" , "GET"])
def reiniciar():

    conn = sqlite3.connect('bingo.db')
    cursor = conn.cursor()

    cursor.execute("""DELETE FROM cartones_disponibles WHERE 1 = 1""")
    conn.commit()

    cursor.execute("""DELETE FROM requeridos WHERE 1 = 1""")
    conn.commit()

    cursor.executemany("""
    INSERT OR IGNORE INTO cartones_disponibles (carton_disponible) VALUES (?);
    """, [(i,) for i in range(1, 1001)])
    conn.commit()

    conn.close()

        # Eliminar todos los archivos en /static/comprobantes/
    folder_path = 'static/comprobantes/'
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):  # Verificar si es un archivo
            os.remove(file_path)

    # Redirigir al panel de administración
    return redirect(url_for('admin_dashboard_partida'))


@app.route("/admin/dashboard/solicitudes")
@login_required  # Ruta protegida por login
def admin_dashboard_solicitudes():
    solicitudes = get_data()  # Recupera los datos de la tabla
    
    return render_template("admin_solicitudes.html", solicitudes=solicitudes)

@app.route("/admin/dashboard/solicitudes/invalidate/", methods=["POST"])
def invalidate():
    data = request.get_json()
    solicitud_id = data.get("id")

    # Conectar a la base de datos
    conn = sqlite3.connect('bingo.db')
    cursor = conn.cursor()

    try:
        # Obtener los cartones asociados a la solicitud
        cursor.execute("""SELECT cartones_solicitados FROM requeridos WHERE id = ?""", (solicitud_id,))
        cartones_solicitados = cursor.fetchone()

        if not cartones_solicitados:
            return jsonify({"success": False, "message": "Solicitud no encontrada"}), 404

        # Extraer los cartones vendidos como texto
        cartones_texto = cartones_solicitados[0]  # Obtener el primer resultado
        if isinstance(cartones_texto, str):
            cartones = [int(carton.strip()) for carton in cartones_texto.strip('[]').split(',') if carton.strip().isdigit()]
        else:
            cartones = [int(cartones_texto)]


        # Reintegrar los cartones a la tabla de disponibles
        reintegrar_cartones(cartones)

        # Actualizar el estado de la solicitud como invalidada
        cursor.execute("""UPDATE requeridos SET estatus = "invalidado" WHERE id = ?""", (solicitud_id,))
        conn.commit()
        cursor.execute("""DELETE FROM requeridos WHERE id = ?""", (solicitud_id,))
        conn.commit()

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        conn.close()

    return redirect(url_for('prueba'))

@app.route("/admin/dashboard/solicitudes/invalidate/prueba", methods=["GET", "POST"])
def prueba():
    time.sleep(1)
    return redirect(url_for('admin_dashboard_solicitudes'))

"""ELIMINE ESTA SECCION AUNQUE CON EL MISMO PROTOCOLO MUESTRO TODO Y YA , SOLO ESE PROBLEMA DE CARTONES """

@app.route("/admin/dashboard/solicitudes/message/", methods=["POST"])
def message():
    data = request.get_json()
    solicitud_id = data.get("id")

    # Conectar a la base de datos
    conn = sqlite3.connect('bingo.db')
    cursor = conn.cursor()

    # Verificar si la solicitud existe
    cursor.execute("""UPDATE requeridos SET estatus = "enviado" WHERE id = ?""", (solicitud_id,))
    conn.commit()

    # Extraer los cartones vendidos como texto
    cursor.execute("""SELECT cartones_solicitados FROM requeridos WHERE id = ?""", (solicitud_id,))
    cartones_vendidos = cursor.fetchone()[0]  # Obtener el primer resultado
    conn.close()

    # Limpieza y conversión del string a lista de enteros
    if isinstance(cartones_vendidos, str):
        # Eliminar caracteres no deseados y dividir el string
        cartones = [int(carton.strip()) for carton in cartones_vendidos.strip('[]').split(',') if carton.strip().isdigit()]
    else:
        # Si no es un string, manejarlo como un único valor
        cartones = [int(cartones_vendidos)]


    # Llamar a la función para insertar los cartones
    vendidos(cartones)

    return redirect(url_for('admin_dashboard_solicitudes'))  # redirigir a un panel de administración



@app.route("/admin/dashboard/vendidos")
@login_required  # Ruta protegida por login
def mostrar_cartones():
    with sqlite3.connect("bingo.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cartones_solicitados FROM requeridos;")
        cartones_tuplas = cursor.fetchall()
        conn.commit()
        cursor.execute("""
            SELECT monto
            FROM requeridos
            WHERE id IN (
                SELECT MIN(id)
                FROM requeridos
                GROUP BY cartones_solicitados
            );
        """)
        montos = cursor.fetchall()

        # Procesar los montos
        total_bs = 0
        total_dolar = 0

        for monto in montos:
            if monto and monto[0]:
                # Expresión regular para separar los montos antes de 'bs' y entre '/' y '$'
                match_bs = re.search(r'([\d.]+)bs', monto[0])
                match_dolar = re.search(r'/([\d.]+)\$', monto[0])

                if match_bs:
                    total_bs += float(match_bs.group(1))
                if match_dolar:
                    total_dolar += float(match_dolar.group(1))

        montos_totales = f"{total_bs}bs"

        # Usar un conjunto para evitar duplicados
        cartones_set = set()
        for carton in cartones_tuplas:
            if carton[0]:  # Evitar errores con valores vacíos o nulos
                numeros = eval(carton[0]) if isinstance(carton[0], str) else carton[0]
                if isinstance(numeros, list):
                    cartones_set.update(numeros)
                else:
                    cartones_set.add(numeros)

        # Convertir el conjunto a lista para pasar a la plantilla
        cartones = list(cartones_set)

        return render_template("disponibles_no.html", cartones=cartones, montos_totales=montos_totales)



if __name__ == '__main__':
    app.run(debug=True)
