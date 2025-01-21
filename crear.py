import sqlite3

# Crear conexión a la base de datos SQLite3
conn = sqlite3.connect("bingo.db")
cursor = conn.cursor()

# Tabla "partida" (solo permite una fila)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS partida (
    id INTEGER PRIMARY KEY,
    partida TEXT,
    precio_de_carton REAL,
    precio_dolar REAL,
    zelle TEXT,
    estatus TEXT,
    modalidad_carton_regalo TEXT,
    recompensa REAL
               );
""")

# Tabla "cartones_disponibles" (del 1 al 1000)
cursor.execute("""
CREATE TABLE IF NOT EXISTS cartones_disponibles (
    carton_disponible INTEGER PRIMARY KEY
);""")

# Insertar los cartones disponibles (1 al 1000)
cursor.executemany("""
INSERT OR IGNORE INTO cartones_disponibles (carton_disponible) VALUES (?);
""", [(i,) for i in range(1, 1001)])

# Tabla "cartones_usados"
cursor.execute("""
CREATE TABLE IF NOT EXISTS cartones_usados (
    carton INTEGER PRIMARY KEY);
""")

# Tabla "requeridos"
cursor.execute("""
CREATE TABLE IF NOT EXISTS requeridos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_apellidos TEXT NOT NULL,
    cedula TEXT NOT NULL,
    telefono TEXT NOT NULL,
    referencia TEXT NOT NULL,
    n_referencia TEXT NOT NULL,
    cartones_solicitados INTEGER NOT NULL,
    monto TEXT NOT NULL,
    fecha TEXT NOT NULL,
    estatus TEXT DEFAULT NULL,
    link TEXT
);
""")

# Insertar una fila inicial con valores por defecto si no hay registros
cursor.execute("""
            INSERT INTO partida (partida, recompensa, precio_de_carton, modalidad_carton_regalo, estatus)
            VALUES (?, ?, ?, ?, ?);
        """, ("", "", 0.0, "", "Venta finalizada"))
conn.commit()

# Confirmar los cambios y cerrar la conexión

conn.close()

print("Base de datos creada con éxito.")
