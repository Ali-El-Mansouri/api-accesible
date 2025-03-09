import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from contextlib import closing

app = FastAPI()

# Permitir solicitudes desde el navegador (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir acceso desde cualquier origen
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todos los encabezados
)

DB_NAME = "preferences.db"

# Inicializar base de datos SQLite
def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT PRIMARY KEY,
                theme TEXT CHECK(theme IN ('light', 'dark')),
                font_size INTEGER CHECK(font_size BETWEEN 10 AND 40),
                monochrome INTEGER CHECK(monochrome IN (0, 1)),
                high_contrast INTEGER CHECK(high_contrast IN (0, 1))
            )
        """)
        conn.commit()

init_db()  # Asegura que la base de datos esté lista al iniciar

# Modelo de datos para las preferencias
class AccessibilityPreferences(BaseModel):
    theme: str
    font_size: int
    monochrome: bool
    high_contrast: bool

    def __init__(self, **data):
        super().__init__(**data)
        if self.theme not in ['light', 'dark']:
            raise ValueError('El tema debe ser "light" o "dark"')
        if not (10 <= self.font_size <= 40):
            raise ValueError('El tamaño de fuente debe estar entre 10 y 40')

# Función para obtener conexión con la base de datos
def get_db_connection():
    return sqlite3.connect(DB_NAME)

# Función para obtener las preferencias de un usuario
def get_preferences_from_db(user_id: str):
    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT theme, font_size, monochrome, high_contrast FROM preferences WHERE user_id=?", (user_id,))
        row = cursor.fetchone()

    if row:
        return {
            "theme": row[0],
            "font_size": row[1],
            "monochrome": bool(row[2]),
            "high_contrast": bool(row[3])
        }
    return None

# Función para guardar preferencias en la base de datos
def save_preferences_to_db(user_id: str, preferences: dict):
    with closing(get_db_connection()) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO preferences (user_id, theme, font_size, monochrome, high_contrast)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            theme=excluded.theme, font_size=excluded.font_size,
            monochrome=excluded.monochrome, high_contrast=excluded.high_contrast
        """, (user_id, preferences["theme"], preferences["font_size"], int(preferences["monochrome"]), int(preferences["high_contrast"])))
        conn.commit()

# Endpoint para obtener las preferencias de un usuario
@app.get("/accessibility/preferences/{user_id}")
async def get_preferences(user_id: str):
    preferences = get_preferences_from_db(user_id)
    if preferences is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return preferences

# Endpoint para actualizar las preferencias de un usuario
@app.post("/accessibility/preferences/{user_id}")
async def update_preferences(user_id: str, preferences: AccessibilityPreferences):
    existing_preferences = get_preferences_from_db(user_id)
    
    # Si el usuario no existe, se crea con valores por defecto antes de actualizar
    if existing_preferences is None:
        default_prefs = {
            "theme": "light",
            "font_size": 16,
            "monochrome": False,
            "high_contrast": False
        }
        save_preferences_to_db(user_id, default_prefs)

    # Guardar las nuevas preferencias
    save_preferences_to_db(user_id, preferences.dict())
    return {"message": "Preferencias guardadas exitosamente"}

# Rutas para cambiar configuraciones específicas sin sobrescribir todo
@app.post("/accessibility/theme/{user_id}")
async def change_theme(user_id: str, theme: str):
    if theme not in ["dark", "light"]:
        raise HTTPException(status_code=400, detail="El tema debe ser 'dark' o 'light'.")
    
    preferences = get_preferences_from_db(user_id)
    if preferences is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    preferences["theme"] = theme
    save_preferences_to_db(user_id, preferences)
    return {"message": f"Modo cambiado a {theme}"}

@app.post("/accessibility/font-size/{user_id}")
async def change_font_size(user_id: str, font_size: int):
    if not (10 <= font_size <= 40):
        raise HTTPException(status_code=400, detail="El tamaño de la fuente debe estar entre 10 y 40.")

    preferences = get_preferences_from_db(user_id)
    if preferences is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    preferences["font_size"] = font_size
    save_preferences_to_db(user_id, preferences)
    return {"message": f"El tamaño de la fuente ha sido cambiado a {font_size}."}

@app.post("/accessibility/monochrome/{user_id}")
async def toggle_monochrome(user_id: str, enable: bool):
    preferences = get_preferences_from_db(user_id)
    if preferences is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    preferences["monochrome"] = enable
    save_preferences_to_db(user_id, preferences)
    return {"message": "Modo monocromático activado." if enable else "Modo monocromático desactivado."}

@app.post("/accessibility/high-contrast/{user_id}")
async def toggle_high_contrast(user_id: str, enable: bool):
    preferences = get_preferences_from_db(user_id)
    if preferences is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    preferences["high_contrast"] = enable
    save_preferences_to_db(user_id, preferences)
    return {"message": "Modo alto contraste activado." if enable else "Modo alto contraste desactivado."}

# Endpoint raíz de la API
@app.get("/")
def read_root():
    return {"message": "¡Bienvenido a la API de accesibilidad!"}
