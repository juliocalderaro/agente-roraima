"""
Agente Roraima v3.4
════════════════════════════════════════════════════
- Reglas primero para preguntas obvias
- LLM solo para preguntas ambiguas
- 19 divisas desde Google Sheets
- Memoria de largo plazo (SQLite thread-safe)
- Calculadora con limpieza de expresion
- Noticias con regex corregido
- Delivery con respuesta especifica
- Logging profesional
- Config centralizada
"""

import os
import re
import json
import sqlite3
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd
import numexpr
from dotenv import load_dotenv

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# ============================================================
# CONFIGURACION INICIAL
# ============================================================

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('agente_roraima.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    sheet_id: str            = os.getenv("SHEET_ID", "1ZXrvekRY7jQC0c3S7LkXCLRbfG14s5CnE1EKOBwru6k")
    sheet_name: str          = os.getenv("SHEET_NAME", "Hoja%201")
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    newsapi_key: str         = os.getenv("NEWSAPI_KEY", "")
    db_path: str             = "memoria_agente.db"
    max_historial: int       = 5
    ollama_model: str        = "llama3.2"
    ollama_url: str          = "http://localhost:11434"

    tasas_default: Dict[str, float] = field(default_factory=lambda: {
        'pyg': 7541.0,  'ars': 1497.17, 'cop': 4376.37,
        'ves': 502.92,  'mxn': 20.60,   'brl': 6.18,
        'clp': 1042.69, 'pen': 4.01,    'bob': 8.06,
        'usd': 1.17,    'uyu': 45.69,   'dop': 63.50,
        'hnl': 28.50,   'nio': 40.20,   'gtq': 8.90,
        'crc': 580.00,  'pab': 1.17,    'mad': 10.85,
        'pkr': 325.00,
    })


config = Config()


# ============================================================
# MAPA COMPLETO DE PAISES Y MONEDAS
# ============================================================

MAPA_PAISES_COMPLETO = {
    # America del Sur
    'argentina':   'ars', 'bolivia':  'bob',
    'brasil':      'brl', 'brazil':   'brl',
    'chile':       'clp', 'colombia': 'cop',
    'ecuador':     'usd', 'paraguay': 'pyg',
    'peru':        'pen', 'uruguay':  'uyu',
    'venezuela':   'ves',
    # America Central y Norte
    'mexico':      'mxn', 'costa rica':  'crc',
    'guatemala':   'gtq', 'honduras':    'hnl',
    'nicaragua':   'nio', 'panama':      'pab',
    'salvador':    'usd', 'el salvador': 'usd',
    'cuba':        'cup',
    # Caribe
    'dominicana':           'dop',
    'republica dominicana': 'dop',
    # Africa y Asia
    'marruecos': 'mad', 'morocco': 'mad',
    'pakistan':  'pkr',
    # USA
    'u.s.a.':        'usd',
    'usa':            'usd',
    'estados unidos': 'usd',
    'united states':  'usd',
    'dolar':          'usd',
    # Codigos ISO directos
    'ars': 'ars', 'bob': 'bob', 'brl': 'brl',
    'clp': 'clp', 'cop': 'cop', 'usd': 'usd',
    'pyg': 'pyg', 'pen': 'pen', 'uyu': 'uyu',
    'ves': 'ves', 'mxn': 'mxn', 'dop': 'dop',
    'hnl': 'hnl', 'nio': 'nio', 'gtq': 'gtq',
    'crc': 'crc', 'pab': 'pab', 'cup': 'cup',
    'mad': 'mad', 'pkr': 'pkr',
    # Alias que suele enviar el LLM
    'col': 'cop', 'ven': 'ves', 'arg': 'ars',
    'mex': 'mxn', 'bra': 'brl', 'chi': 'clp',
    'per': 'pen', 'par': 'pyg', 'bol': 'bob',
    'uru': 'uyu', 'ecu': 'usd', 'mar': 'mad',
    'pak': 'pkr',
    # Euro
    'eur': 'eur', 'euro': 'eur', 'euros': 'eur',
}


# ============================================================
# CONEXION CON OLLAMA
# ============================================================

class CerebroLLM:

    def __init__(self):
        self.modelo     = None
        self.disponible = False
        self._conectar()

    def _conectar(self):
        try:
            self.modelo = ChatOllama(
                model=config.ollama_model,
                base_url=config.ollama_url,
                temperature=0.1,
                format="json"
            )
            respuesta = self.modelo.invoke("Responde solo: OK")
            if respuesta:
                self.disponible = True
                logger.info(f"Ollama conectado: {config.ollama_model}")
        except Exception as e:
            logger.warning(f"Ollama no disponible: {e}")
            logger.info("Usando deteccion por reglas")

    def pensar(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        if not self.disponible:
            return None
        try:
            mensajes = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            respuesta = self.modelo.invoke(mensajes)
            return respuesta.content
        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            return None


cerebro = CerebroLLM()


# ============================================================
# CARGA DE DIVISAS DESDE GOOGLE SHEETS
# ============================================================

def cargar_divisas_desde_sheets() -> Dict[str, float]:
    if not config.sheet_id:
        logger.warning("SHEET_ID no configurado. Usando tasas por defecto.")
        return config.tasas_default

    url = (
        f"https://docs.google.com/spreadsheets/d/{config.sheet_id}"
        f"/gviz/tq?tqx=out:csv&sheet={config.sheet_name}"
    )

    try:
        df      = pd.read_csv(url)
        divisas = {}

        for idx in range(7, len(df)):
            fila = df.iloc[idx]
            if len(fila) < 6:
                continue

            pais_raw  = fila.iloc[0]
            valor_raw = fila.iloc[5]

            if pd.notna(pais_raw) and pd.notna(valor_raw):
                try:
                    if isinstance(valor_raw, str):
                        valor_raw = valor_raw.replace('.', '').replace(',', '.').strip()
                    valor_num = float(valor_raw)

                    pais_limpio = str(pais_raw).strip().lower()
                    if ',' in pais_limpio:
                        pais_limpio = pais_limpio.split(',')[0].strip()

                    codigo = None
                    for nombre_pais, cod in MAPA_PAISES_COMPLETO.items():
                        if nombre_pais in pais_limpio or pais_limpio in nombre_pais:
                            codigo = cod
                            break

                    if codigo:
                        divisas[codigo] = valor_num
                    else:
                        logger.debug(f"Pais no reconocido: {pais_limpio}")

                except Exception as e:
                    logger.debug(f"Error fila {idx}: {e}")

        if divisas:
            logger.info(f"Cargadas {len(divisas)} divisas desde Google Sheets")
            for cod, val in sorted(divisas.items()):
                logger.info(f"  {cod}: {val}")
            return divisas

        logger.warning("No se cargaron divisas. Usando tasas por defecto.")
        return config.tasas_default

    except Exception as e:
        logger.error(f"Error cargando divisas: {e}", exc_info=True)
        return config.tasas_default


DIVISAS = cargar_divisas_desde_sheets()


# ============================================================
# REGISTRO DE HERRAMIENTAS
# ============================================================

class RegistroHerramientas:

    def __init__(self):
        self._herramientas = {}

    def registrar(self, nombre: str, funcion, descripcion: str = ""):
        self._herramientas[nombre] = {
            "funcion":     funcion,
            "descripcion": descripcion
        }

    def _limpiar_params_vacios(self, params: Dict) -> Dict:
        return {k: v for k, v in params.items()
                if v is not None and v != ""}

    def _normalizar_params(self, herramienta: str, params: Dict) -> Dict:
        params = self._limpiar_params_vacios(params)

        # Sin parametros
        if herramienta in ["horarios", "servicios"]:
            return {}

        # Calculadora
        if herramienta == "calculadora":
            for alias in ["expression", "expr", "operacion",
                          "formula", "calculo"]:
                if alias in params and "expresion" not in params:
                    params["expresion"] = params.pop(alias)
            # Limpiar expresion: solo caracteres matematicos
            if "expresion" in params:
                params["expresion"] = re.sub(
                    r'[^0-9+\-*/.()\s]', '',
                    str(params["expresion"])
                ).strip()

        # Convertir moneda
        if herramienta == "convertir_moneda":
            for alias in ["amount", "cantidad", "valor", "quantity"]:
                if alias in params and "monto" not in params:
                    params["monto"] = params.pop(alias)
            if "from" in params and "desde" not in params:
                params["desde"] = params.pop("from")
            if "to" in params and "hasta" not in params:
                params["hasta"] = params.pop("to")
            for campo in ["desde", "hasta"]:
                if campo in params:
                    val = str(params[campo]).lower().strip()
                    params[campo] = MAPA_PAISES_COMPLETO.get(val, val)

        # RAG
        if herramienta == "rag_buscar":
            for alias in ["query", "consulta", "busqueda",
                          "search", "texto"]:
                if alias in params and "pregunta" not in params:
                    params["pregunta"] = params.pop(alias)

        # Clima
        if herramienta == "clima":
            for alias in ["location", "city", "lugar", "place"]:
                if alias in params and "ciudad" not in params:
                    params["ciudad"] = params.pop(alias)

        # Noticias
        if herramienta == "noticias":
            for alias in ["country", "region"]:
                if alias in params and "pais" not in params:
                    params["pais"] = params.pop(alias)

        return params

    def ejecutar(self, nombre: str, params: Dict) -> str:
        if nombre not in self._herramientas:
            return f"Herramienta desconocida: {nombre}"
        try:
            params = self._normalizar_params(nombre, params)
            logger.info(f"Ejecutando: {nombre} {params}")
            return self._herramientas[nombre]["funcion"](**params)
        except Exception as e:
            logger.error(f"Error en {nombre}: {e}", exc_info=True)
            return "Disculpa, tuve un problema procesando tu peticion."

    def listar_para_prompt(self) -> str:
        return "\n".join([
            f"- {n}: {i['descripcion']}"
            for n, i in self._herramientas.items()
        ])


registro = RegistroHerramientas()


# ============================================================
# HERRAMIENTAS
# ============================================================

def calculadora(expresion: str) -> str:
    try:
        # Limpiar expresion
        expresion = str(expresion).lower()
        expresion = re.sub(r'[^0-9+\-*/.()\s]', '', expresion).strip()

        # Manejar descuentos
        match_descuento = re.match(
            r'(\d+\.?\d*)\s*(\d+\.?\d*)\s*',
            expresion
        )

        # Reemplazar x por *
        expresion = expresion.replace('x', '*').replace(',', '.')

        if not expresion:
            return "No pude interpretar la expresion matematica"

        resultado = numexpr.evaluate(expresion).item()
        return (
            f"{int(resultado)}"
            if resultado == int(resultado)
            else f"{resultado:.2f}"
        )

    except Exception as e:
        logger.debug(f"Error calculando '{expresion}': {e}")
        return "No pude calcular esa expresion"


def convertir_moneda(monto: float, desde: str, hasta: str) -> str:
    try:
        monto = float(monto)
    except Exception:
        return f"El monto '{monto}' no es valido"

    desde = MAPA_PAISES_COMPLETO.get(
        str(desde).lower().strip(),
        str(desde).lower().strip()
    )
    hasta = MAPA_PAISES_COMPLETO.get(
        str(hasta).lower().strip(),
        str(hasta).lower().strip()
    )

    tasas = DIVISAS if DIVISAS else config.tasas_default

    if desde == 'eur' and hasta in tasas:
        return f"{monto:.2f} EUR = {monto * tasas[hasta]:,.2f} {hasta.upper()}"

    if hasta == 'eur' and desde in tasas:
        return f"{monto:.2f} {desde.upper()} = {monto / tasas[desde]:.2f} EUR"

    if desde in tasas and hasta in tasas:
        resultado = (monto / tasas[desde]) * tasas[hasta]
        return f"{monto:.2f} {desde.upper()} = {resultado:,.2f} {hasta.upper()}"

    return (
        f"Moneda no soportada. "
        f"Disponibles: {', '.join(sorted(tasas.keys()))}"
    )


def clima(ciudad: str) -> str:
    if not config.openweather_api_key:
        return "El servicio de clima no esta configurado."
    try:
        import requests
        url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={ciudad}&appid={config.openweather_api_key}"
            f"&units=metric&lang=es"
        )
        data = requests.get(url, timeout=5).json()
        if data.get("cod") == 200:
            return (
                f"{ciudad}: {data['main']['temp']:.1f}C, "
                f"{data['weather'][0]['description']}, "
                f"humedad {data['main']['humidity']}%"
            )
        return f"No pude obtener el clima de {ciudad}"
    except Exception as e:
        logger.error(f"Error clima: {e}")
        return "Error al consultar el clima"


def noticias(pais: Optional[str] = None,
             categoria: Optional[str] = None) -> str:
    if not config.newsapi_key:
        return "El servicio de noticias no esta configurado."

    termino = pais if pais else "Latinoamerica"
    if categoria:
        termino = f"{termino} {categoria}"

    try:
        import requests
        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={termino}&language=es&sortBy=publishedAt"
            f"&pageSize=5&apiKey={config.newsapi_key}"
        )
        data = requests.get(url, timeout=5).json()
        if data.get("status") == "ok" and data.get("articles"):
            titulares = []
            for a in data["articles"][:5]:
                titulo = a.get("title", "")
                # Quitar solo el sufijo " - Fuente" o " | Fuente"
                titulo = re.sub(r'\s*[-|]\s*[^-|]+$', '', titulo).strip()
                if titulo:
                    titulares.append(f"- {titulo}")
            if titulares:
                return "Ultimas noticias:\n" + "\n".join(titulares)
        return f"No encontre noticias sobre {termino}."
    except Exception as e:
        logger.error(f"Error noticias: {e}")
        return "Error al consultar noticias"


def horarios() -> str:
    return (
        "Horario Multiservicios Roraima (Mungia):\n"
        "- Lunes a viernes: 10:00-14:00 y 16:30-21:30\n"
        "- Sabados: 11:00-14:00 y 17:00-21:00\n"
        "- Domingos y Festivos: 11:00-16:00"
    )


def servicios() -> str:
    return (
        "Servicios de Multiservicios Roraima:\n\n"
        "💸 Envío de dinero (Remesas):\n"
        "   Western Union, RIA, Europhil\n\n"
        "📱 Recargas móviles (España):\n"
        "   Digi, Lebara, Orange, Vodafone,\n"
        "   LlamaYa, MásMóvil\n"
        "   (También recargas internacionales)\n\n"
        "🖨️  Impresiones en blanco y negro\n\n"
        "🚚 Delivery en Mungia (mínimo 15 EUR)\n\n"
        "🛒 Tienda online de productos\n"
        "   latinoamericanos\n\n"
        "💱 Cotizaciones de divisas\n"
        "   latinoamericanas"
    )


def envio_info() -> str:
    return (
        "Envío de dinero (Remesas):\n\n"
        "Operadores disponibles:\n"
        "  - Western Union\n"
        "  - RIA\n"
        "  - Europhil\n\n"
        "Requisitos:\n"
        "  - Cédula o pasaporte vigente\n"
        "  - Nombre completo del destinatario\n"
        "  - País de destino\n"
        "  - Monto a enviar\n\n"
        "Visítanos en la tienda para\n"
        "asesoramiento personalizado."
    )


def delivery_info() -> str:
    return (
        "Si, hacemos delivery en el casco de Mungia.\n"
        "Pedido minimo: 15 EUR.\n"
        "Para pedidos contacta por WhatsApp."
    )


def precio_pais(pais: str) -> Optional[str]:
    codigo = MAPA_PAISES_COMPLETO.get(pais.lower().strip())
    if not codigo:
        return None
    tasas = DIVISAS if DIVISAS else config.tasas_default
    if codigo in tasas:
        return f"1 EUR = {tasas[codigo]:,.2f} {codigo.upper()}"
    return None


def rag_buscar(pregunta: str) -> str:
    p = pregunta.lower()

    # Envios y requisitos
    if any(x in p for x in [
        'envio', 'envía', 'envío', 'enviar', 'envias',
        'remesa', 'remesas', 'western', 'ria', 'europhil',
        'mandar', 'mandarme', 'transferir', 'transferencia',
        'requisito', 'requisitos', 'necesito para',
        'como mando', 'como envio', 'como envío',
        'como enviar', 'como mandar',
        'documentos', 'que necesito',
        'giro', 'girar'
    ]):
        return envio_info()

    # Horarios
    if any(x in p for x in [
        'horario', 'abren', 'cierran', 'hora',
        'abierto', 'cerrado', 'domingo', 'sabado', 'festivo'
    ]):
        return horarios()

    # Delivery especifico
    if any(x in p for x in [
        'domicilio', 'delivery', 'reparto',
        'llevan', 'traen', 'envian a casa'
    ]):
        return delivery_info()

    # Servicios generales
    if any(x in p for x in [
        'servicio', 'ofrecen', 'recarga',
        'impresion', 'tienda', 'que tienen', 'que hacen'
    ]):
        return servicios()

    # Precio por pais
    for pais in MAPA_PAISES_COMPLETO.keys():
        if pais in p and len(pais) > 3:
            resultado = precio_pais(pais)
            if resultado:
                return resultado

    return (
        "No encontre informacion sobre esa consulta. "
        "Puedo ayudarte con: horarios, servicios, "
        "envios y cotizaciones de divisas."
    )


# Registrar herramientas
registro.registrar(
    "calculadora", calculadora,
    "Calcula operaciones matematicas. Params: expresion"
)
registro.registrar(
    "convertir_moneda", convertir_moneda,
    "Convierte EUR a monedas. Params: monto, desde, hasta"
)
registro.registrar(
    "rag_buscar", rag_buscar,
    "Busca informacion interna del negocio. Params: pregunta"
)
registro.registrar(
    "clima", clima,
    "Obtiene el clima actual. Params: ciudad"
)
registro.registrar(
    "noticias", noticias,
    "Obtiene noticias recientes. Params: pais (opcional)"
)
registro.registrar(
    "horarios", horarios,
    "Devuelve el horario de atencion. Sin params"
)
registro.registrar(
    "servicios", servicios,
    "Lista los servicios disponibles. Sin params"
)


# ============================================================
# MEMORIA DE LARGO PLAZO
# ============================================================

class MemoriaLargoPlazo:

    def __init__(self):
        self._crear_tablas()

    def _get_connection(self):
        return sqlite3.connect(config.db_path, check_same_thread=False)

    def _crear_tablas(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversaciones (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario      TEXT NOT NULL,
                    pregunta     TEXT NOT NULL,
                    respuesta    TEXT NOT NULL,
                    herramientas TEXT,
                    timestamp    TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hechos (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario   TEXT NOT NULL,
                    clave     TEXT NOT NULL,
                    valor     TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    UNIQUE(usuario, clave)
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conv "
                "ON conversaciones(usuario, timestamp DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hechos ON hechos(usuario)"
            )

    def guardar_conversacion(self, usuario, pregunta,
                              respuesta, herramienta):
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO conversaciones
                   (usuario, pregunta, respuesta, herramientas, timestamp)
                   VALUES (?,?,?,?,?)""",
                (usuario, pregunta, respuesta,
                 herramienta, datetime.now().isoformat())
            )

    def recordar_hecho(self, usuario, clave, valor):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE hechos SET valor=?, timestamp=? "
                "WHERE usuario=? AND clave=?",
                (valor, datetime.now().isoformat(), usuario, clave)
            )
            if cursor.rowcount == 0:
                conn.execute(
                    "INSERT INTO hechos "
                    "(usuario, clave, valor, timestamp) "
                    "VALUES (?,?,?,?)",
                    (usuario, clave, valor, datetime.now().isoformat())
                )
        logger.info(f"Recordado: {usuario} -> {clave} = {valor}")

    def obtener_hechos(self, usuario) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT clave, valor FROM hechos WHERE usuario = ?",
                (usuario,)
            )
            return dict(cursor.fetchall())

    def historial_usuario(self, usuario,
                           ultimas_n: int = 5) -> List:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT pregunta, respuesta FROM conversaciones
                   WHERE usuario=? ORDER BY timestamp DESC LIMIT ?""",
                (usuario, ultimas_n)
            )
            return cursor.fetchall()


memoria = MemoriaLargoPlazo()


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """Eres Roraima, asistente de Multiservicios Roraima (Mungia, Bizkaia).
Ayudas con informacion del negocio, divisas y servicios latinoamericanos.

HERRAMIENTAS:
{herramientas}

REGLAS:
1. Responde SOLO en JSON valido
2. USA herramientas para datos del negocio, NUNCA de memoria
3. Se breve y amable. Responde en español

EJEMPLOS:
Servicios → {{"tipo":"herramienta","nombre":"servicios","parametros":{{}}}}
Horario → {{"tipo":"herramienta","nombre":"horarios","parametros":{{}}}}
Envio/remesa → {{"tipo":"herramienta","nombre":"rag_buscar","parametros":{{"pregunta":"envio"}}}}
100 euros colombia → {{"tipo":"herramienta","nombre":"convertir_moneda","parametros":{{"monto":"100","desde":"eur","hasta":"cop"}}}}
150+230 → {{"tipo":"herramienta","nombre":"calculadora","parametros":{{"expresion":"150+230"}}}}
Noticias → {{"tipo":"herramienta","nombre":"noticias","parametros":{{}}}}
Clima Bilbao → {{"tipo":"herramienta","nombre":"clima","parametros":{{"ciudad":"Bilbao"}}}}

CODIGOS MONEDA:
cop=Colombia, ves=Venezuela, ars=Argentina, mxn=Mexico,
brl=Brasil, clp=Chile, pen=Peru, pyg=Paraguay, bob=Bolivia,
uyu=Uruguay, usd=Ecuador/USA, dop=Rep.Dominicana,
hnl=Honduras, nio=Nicaragua, gtq=Guatemala,
mad=Marruecos, pkr=Pakistan

FORMATO:
Directo: {{"tipo":"respuesta","contenido":"texto"}}
Herramienta: {{"tipo":"herramienta","nombre":"tool","parametros":{{}}}}"""


# ============================================================
# BUCLE AGENTE
# ============================================================

class BucleAgente:

    def __init__(self):
        self.historial_pensamientos = []
        self.usuario_actual         = "anonimo"

    def set_usuario(self, usuario: str):
        self.usuario_actual = usuario

    def pensar_con_llm(self, pregunta: str) -> Optional[Dict]:
        hechos    = memoria.obtener_hechos(self.usuario_actual)
        historial = memoria.historial_usuario(
            self.usuario_actual, ultimas_n=3
        )

        contexto = ""
        if hechos:
            contexto += (
                f"Datos usuario: "
                f"{json.dumps(hechos, ensure_ascii=False)}\n"
            )
        if historial:
            contexto += "Conversacion reciente:\n"
            for p, r in historial:
                contexto += f"  U: {p[:60]}\n  R: {r[:60]}\n"

        system = SYSTEM_PROMPT.format(
            herramientas=registro.listar_para_prompt()
        )
        user = f"{contexto}\nPregunta: {pregunta}"

        respuesta_raw = cerebro.pensar(system, user)
        if not respuesta_raw:
            return None

        try:
            raw    = respuesta_raw.strip()
            inicio = raw.find('{')
            fin    = raw.rfind('}') + 1
            if inicio >= 0 and fin > inicio:
                decision = json.loads(raw[inicio:fin])
                logger.info(f"LLM decidio: {decision}")
                return decision
        except Exception as e:
            logger.warning(f"Error JSON del LLM: {e}")

        return None

    def pensar(self, pregunta: str) -> Dict:
        """
        CAPA 1: Reglas deterministas (preguntas obvias)
        CAPA 2: LLM (preguntas ambiguas)
        CAPA 3: RAG fallback final
        """
        p = pregunta.lower()

        # ── Recordar nombre ───────────────────────────────────
        if any(x in p for x in [
            'como me llamo', 'recuerdas mi nombre',
            'recuerdas como', 'sabes mi nombre',
            'quien soy', 'mi nombre', 'receurdas',
            'recuerda mi', 'sabes como me llamo'
        ]):
            hechos = memoria.obtener_hechos(self.usuario_actual)
            nombre = hechos.get('nombre')
            if nombre:
                return {
                    "tipo": "respuesta",
                    "contenido": f"Te llamas {nombre}"
                }
            return {
                "tipo": "respuesta",
                "contenido": "Aun no me has dicho tu nombre. Como te llamas?"
            }

        # ── Guardar nombre ────────────────────────────────────
        if 'me llamo' in p or 'mi nombre es' in p:
            partes = re.split(r'me llamo|mi nombre es', p)
            if len(partes) > 1:
                nombre_raw = re.sub(
                    r'[^a-z\s]', '', partes[1].strip()
                ).strip()
                if nombre_raw:
                    nombre = nombre_raw.split()[0].capitalize()
                    memoria.recordar_hecho(
                        self.usuario_actual, "nombre", nombre
                    )
                    return {
                        "tipo": "respuesta",
                        "contenido": f"Encantado, {nombre}!"
                    }

        # ── Nombre suelto ─────────────────────────────────────
        palabras = pregunta.strip().split()
        palabras_reservadas = [
            'salir', 'exit', 'hola', 'si', 'no', 'ok',
            'bye', 'adios', 'gracias', 'buenas', 'hello'
        ]
        if (len(palabras) == 1
                and palabras[0].isalpha()
                and len(palabras[0]) >= 2
                and palabras[0].lower() not in palabras_reservadas):
            nombre = palabras[0].capitalize()
            memoria.recordar_hecho(self.usuario_actual, "nombre", nombre)
            return {
                "tipo": "respuesta",
                "contenido": f"Encantado, {nombre}!"
            }

        # ── Horarios ──────────────────────────────────────────
        if any(x in p for x in [
            'horario', 'abren', 'cierran', 'hora',
            'abierto', 'cerrado', 'domingo', 'sabado',
            'festivo', 'lunes', 'martes', 'miercoles',
            'jueves', 'viernes'
        ]):
            return {
                "tipo": "herramienta",
                "nombre": "horarios",
                "parametros": {}
            }

        # ── Envios y requisitos (antes de servicios) ──────────
        if any(x in p for x in [
            'envio', 'envía', 'envío', 'enviar', 'envias',
            'remesa', 'remesas', 'western', 'ria', 'europhil',
            'mandar dinero', 'mandar plata', 'mandar euros',
            'mando dinero', 'mando plata', 'mando euros',
            'mandé', 'mandar', 'mando',
            'transferencia', 'transferir',
            'requisito', 'requisitos',
            'que necesito para', 'como envio', 'como envío',
            'como mando', 'como mandar', 'como enviar',
            'documentos para', 'que necesito',
            'giro', 'girar dinero', 'plata a', 'dinero a'
        ]):
            return {
                "tipo": "herramienta",
                "nombre": "rag_buscar",
                "parametros": {"pregunta": pregunta}
            }
        
        # ── Delivery especifico ───────────────────────────────
        if any(x in p for x in [
            'domicilio', 'delivery', 'reparto',
            'llevan a casa', 'traen a casa',
            'envian a casa', 'a domicilio'
        ]):
            return {
                "tipo": "respuesta",
                "contenido": delivery_info()
            }

        # ── Servicios generales ───────────────────────────────
        if any(x in p for x in [
            'servicio', 'ofrecen', 'que hacen',
            'que tienen', 'a que se dedican',
            'recarga', 'recargas', 'impresion', 'tienda online'
        ]):
            return {
                "tipo": "herramienta",
                "nombre": "servicios",
                "parametros": {}
            }

        # ── Descuentos ────────────────────────────────────────
        if 'descuento' in p:
            expresion = re.sub(r'[^0-9+\-*/.()\s]', '', pregunta).strip()
            return {
                "tipo": "herramienta",
                "nombre": "calculadora",
                "parametros": {"expresion": expresion}
            }

        # ── Operaciones matematicas ───────────────────────────
        if (any(op in pregunta for op in ['+', '-', '*', '/'])
                and any(c.isdigit() for c in pregunta)):
            expresion = re.sub(
                r'[^0-9+\-*/.()\s]', '', pregunta
            ).strip()
            return {
                "tipo": "herramienta",
                "nombre": "calculadora",
                "parametros": {"expresion": expresion}
            }

        # ── Conversiones con cantidad ─────────────────────────
        numeros = re.findall(r'\d+', pregunta)
        if numeros and any(x in p for x in ['euro', 'eur', 'cambio']):
            for pais, codigo in MAPA_PAISES_COMPLETO.items():
                if pais in p and len(pais) > 3:
                    return {
                        "tipo": "herramienta",
                        "nombre": "convertir_moneda",
                        "parametros": {
                            "monto": numeros[0],
                            "desde": "eur",
                            "hasta": codigo
                        }
                    }

        # ── Precio del euro en un pais ────────────────────────
        for pais, codigo in MAPA_PAISES_COMPLETO.items():
            if pais in p and len(pais) > 3:
                if any(x in p for x in [
                    'euro', 'precio', 'cuanto', 'cambio',
                    'cotizacion', 'vale', 'esta', 'cuesta'
                ]):
                    return {
                        "tipo": "herramienta",
                        "nombre": "convertir_moneda",
                        "parametros": {
                            "monto": "1",
                            "desde": "eur",
                            "hasta": codigo
                        }
                    }

        # ── Noticias ──────────────────────────────────────────
        if any(x in p for x in [
            'noticia', 'titular', 'news',
            'prensa', 'que paso', 'novedades'
        ]):
            return {
                "tipo": "herramienta",
                "nombre": "noticias",
                "parametros": {}
            }

        # ── CAPA 2: LLM para ambiguedades ─────────────────────
        logger.info("Pregunta ambigua → consultando LLM")
        decision = self.pensar_con_llm(pregunta)
        if decision and "tipo" in decision:
            return decision

        # ── CAPA 3: Fallback RAG ──────────────────────────────
        logger.info("Fallback → RAG")
        return {
            "tipo": "herramienta",
            "nombre": "rag_buscar",
            "parametros": {"pregunta": pregunta}
        }

    def actuar(self, decision: Dict) -> str:
        if decision.get("tipo") == "herramienta":
            return registro.ejecutar(
                decision.get("nombre", ""),
                decision.get("parametros", {})
            )
        return decision.get("contenido", "No pude procesar tu solicitud")

    def observar(self, decision: Dict, resultado: str) -> str:
        self.historial_pensamientos.append({
            "decision":  decision,
            "resultado": resultado,
            "timestamp": datetime.now().isoformat()
        })
        return resultado


# ============================================================
# AGENTE RORAIMA v3.4
# ============================================================

class AgenteRoraima:

    def __init__(self):
        self.bucle          = BucleAgente()
        self.usuario_actual = "anonimo"

    def saludar(self, usuario: str) -> str:
        usuario = re.sub(
            r'(?i)^(me llamo |soy |mi nombre es )',
            '', usuario
        ).strip().capitalize()

        if not usuario:
            usuario = "Anonimo"

        self.usuario_actual = usuario
        self.bucle.set_usuario(usuario)

        if usuario.lower() != "anonimo":
            memoria.recordar_hecho(usuario, "nombre", usuario)

        hechos    = memoria.obtener_hechos(usuario)
        nombre    = hechos.get('nombre', usuario)
        estado    = "Ollama activo" if cerebro.disponible else "Modo reglas"
        historial = memoria.historial_usuario(usuario)

        if historial:
            return (
                f"Hola de nuevo, {nombre}! "
                f"Bienvenido de vuelta. ({estado})"
            )
        return (
            f"Hola {nombre}! Soy Roraima, el asistente de "
            f"Multiservicios Roraima en Mungia. "
            f"En que puedo ayudarte? ({estado})"
        )

    def procesar(self, pregunta: str) -> str:
        try:
            logger.info(f"Usuario {self.usuario_actual}: {pregunta}")

            decision        = self.bucle.pensar(pregunta)
            resultado       = self.bucle.actuar(decision)
            resultado_final = self.bucle.observar(decision, resultado)

            herramienta = decision.get(
                "nombre", decision.get("tipo", "?")
            )
            memoria.guardar_conversacion(
                self.usuario_actual, pregunta,
                resultado_final, herramienta
            )

            logger.info(
                f"Respuesta [{herramienta}]: {resultado_final[:80]}..."
            )
            return resultado_final

        except Exception as e:
            logger.error(
                f"Error procesando '{pregunta}'", exc_info=True
            )
            return "Disculpa, tuve un problema. Puedes repetir?"


# ============================================================
# MODO INTERACTIVO
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("   AGENTE RORAIMA v3.4")
    print("   Multiservicios Roraima | Mungia, Bizkaia")
    print("=" * 55)
    print(
        f"Estado LLM : "
        f"{'Ollama activo' if cerebro.disponible else 'Modo reglas'}"
    )
    print(f"Divisas    : {len(DIVISAS)} monedas cargadas")
    print("Salir      : escribe 'salir'\n")

    agente  = AgenteRoraima()
    usuario = input("Como te llamas? ").strip()

    if not usuario:
        usuario = "anonimo"

    print(f"\nRoraima: {agente.saludar(usuario)}\n")

    while True:
        try:
            pregunta = input("Tu: ").strip()
        except KeyboardInterrupt:
            print("\nRoraima: Hasta luego!")
            break

        if not pregunta:
            continue

        if pregunta.lower() in [
            "salir", "exit", "quit", "bye", "adios"
        ]:
            print("Roraima: Hasta luego! Que tengas un buen dia.")
            break

        print(f"Roraima: {agente.procesar(pregunta)}\n")