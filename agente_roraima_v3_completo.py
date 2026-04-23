"""
Agente Roraima v3.0 - Con Ollama como cerebro
══════════════════════════════════════════════
- Ollama (llama3.2) como LLM para razonar
- Fallback a reglas si Ollama no responde
- Memoria de largo plazo (SQLite thread-safe)
- Bucle agente (think → act → observe)
- Herramientas reales con Registry extensible
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
# CONFIGURACIÓN INICIAL
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
    sheet_id: str = os.getenv("SHEET_ID", "")
    sheet_name: str = os.getenv("SHEET_NAME", "Hoja%201")
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    newsapi_key: str = os.getenv("NEWSAPI_KEY", "")
    db_path: str = "memoria_agente.db"
    max_historial: int = 5
    ollama_model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"

    tasas_default: Dict[str, float] = field(default_factory=lambda: {
        'pyg': 7541.0, 'ars': 1497.17, 'cop': 4376.37,
        'ves': 502.92, 'mxn': 20.60, 'brl': 6.18,
        'clp': 1042.69, 'pen': 4.01, 'bob': 8.06,
        'usd': 1.17, 'uyu': 45.69
    })

config = Config()


# ============================================================
# CONEXIÓN CON OLLAMA
# ============================================================

class CerebroLLM:
    """Conexión con Ollama como cerebro del agente"""

    def __init__(self):
        self.modelo = None
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
            # Test rápido
            respuesta = self.modelo.invoke("Responde solo: OK")
            if respuesta:
                self.disponible = True
                logger.info(f"✅ Ollama conectado: {config.ollama_model}")
        except Exception as e:
            logger.warning(f"⚠️ Ollama no disponible: {e}")
            logger.info("ℹ️ El agente usará detección por reglas")

    def pensar(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Envía un prompt al LLM y retorna la respuesta"""
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
# REGISTRO DE HERRAMIENTAS
# ============================================================

class RegistroHerramientas:
    def __init__(self):
        self._herramientas = {}

    def registrar(self, nombre: str, funcion, descripcion: str = ""):
        self._herramientas[nombre] = {
            "funcion": funcion,
            "descripcion": descripcion
        }

    def ejecutar(self, nombre: str, params: Dict) -> str:
        if nombre not in self._herramientas:
            return f"Herramienta desconocida: {nombre}"
        try:
            logger.info(f"🔧 Ejecutando: {nombre} {params}")
            return self._herramientas[nombre]["funcion"](**params)
        except Exception as e:
            logger.error(f"Error en {nombre}: {e}", exc_info=True)
            return "Disculpa, tuve un problema procesando tu petición."

    def listar_para_prompt(self) -> str:
        """Genera descripción de herramientas para el LLM"""
        lineas = []
        for nombre, info in self._herramientas.items():
            lineas.append(f"- {nombre}: {info['descripcion']}")
        return "\n".join(lineas)


registro = RegistroHerramientas()


# ============================================================
# CARGA DE DATOS
# ============================================================

def cargar_divisas_desde_sheets() -> Dict[str, float]:
    if not config.sheet_id:
        logger.warning("SHEET_ID no configurado. Usando tasas por defecto.")
        return config.tasas_default

    url = f"https://docs.google.com/spreadsheets/d/{config.sheet_id}/gviz/tq?tqx=out:csv&sheet={config.sheet_name}"
    try:
        df = pd.read_csv(url)
        divisas = {}
        mapa_pais_codigo = {
            'argentina': 'ars', 'bolivia': 'bob', 'brasil': 'brl',
            'chile': 'clp', 'colombia': 'cop', 'ecuador': 'usd',
            'paraguay': 'pyg', 'peru': 'pen', 'uruguay': 'uyu',
            'venezuela': 'ves', 'mexico': 'mxn'
        }

        for idx in range(7, len(df)):
            fila = df.iloc[idx]
            pais = fila.iloc[0] if len(fila) > 0 and pd.notna(fila.iloc[0]) else None
            valor_raw = fila.iloc[5] if len(fila) > 5 and pd.notna(fila.iloc[5]) else None

            if pais and valor_raw:
                try:
                    if isinstance(valor_raw, str):
                        valor_raw = valor_raw.replace('.', '').replace(',', '.').strip()
                    valor_num = float(valor_raw)
                    pais_limpio = str(pais).strip().lower()
                    if ',' in pais_limpio:
                        pais_limpio = pais_limpio.split(',')[0].strip()
                    if pais_limpio in mapa_pais_codigo:
                        divisas[mapa_pais_codigo[pais_limpio]] = valor_num
                except Exception as e:
                    logger.debug(f"No se pudo parsear fila {idx}: {e}")

        logger.info(f"✅ Cargadas {len(divisas)} divisas desde Google Sheets")
        return divisas

    except Exception as e:
        logger.error(f"❌ Error cargando divisas: {e}", exc_info=True)
        return config.tasas_default


DIVISAS = cargar_divisas_desde_sheets()


# ============================================================
# HERRAMIENTAS
# ============================================================

def calculadora(expresion: str) -> str:
    try:
        expresion = str(expresion).lower()
        match_descuento = re.match(
            r'(\d+\.?\d*)\s*(?:euros?)?\s*con\s*(\d+\.?\d*)\s*%\s*(?:de\s*)?descuento',
            expresion
        )
        if match_descuento:
            monto = float(match_descuento.group(1))
            porcentaje = float(match_descuento.group(2))
            resultado = monto * (1 - porcentaje / 100)
            descuento = monto * (porcentaje / 100)
            return (
                f"Monto original: {monto:.2f}€\n"
                f"Descuento ({porcentaje}%): -{descuento:.2f}€\n"
                f"Total: {resultado:.2f}€"
            )

        expresion_limpia = expresion.replace('x', '*').replace(',', '.')
        expresion_limpia = re.sub(r'[^0-9+\-*/.()\s]', '', expresion_limpia)
        if not expresion_limpia.strip():
            return "No pude interpretar la expresión"
        resultado = numexpr.evaluate(expresion_limpia).item()
        return f"{int(resultado)}" if resultado == int(resultado) else f"{resultado:.2f}"
    except Exception as e:
        logger.debug(f"Error calculando {expresion}: {e}")
        return "No pude calcular esa expresión"


def convertir_moneda(monto: float, desde: str, hasta: str) -> str:
    try:
        monto = float(monto)
    except:
        return f"El monto '{monto}' no es válido"

    desde = desde.lower().strip()
    hasta = hasta.lower().strip()

    paises_a_codigo = {
        'colombia': 'cop', 'argentina': 'ars', 'paraguay': 'pyg',
        'venezuela': 'ves', 'mexico': 'mxn', 'brasil': 'brl',
        'chile': 'clp', 'peru': 'pen', 'bolivia': 'bob',
        'ecuador': 'usd', 'uruguay': 'uyu'
    }

    if hasta in paises_a_codigo:
        hasta = paises_a_codigo[hasta]
    if desde in paises_a_codigo:
        desde = paises_a_codigo[desde]
    if desde in ['eur', 'euro', 'euros']:
        desde = 'eur'
    if hasta in ['eur', 'euro', 'euros']:
        hasta = 'eur'

    tasas = DIVISAS if DIVISAS else config.tasas_default

    if desde == 'eur' and hasta in tasas:
        resultado = monto * tasas[hasta]
        return f"{monto:.2f} EUR = {resultado:.2f} {hasta.upper()}"
    if hasta == 'eur' and desde in tasas:
        resultado = monto / tasas[desde]
        return f"{monto:.2f} {desde.upper()} = {resultado:.2f} EUR"
    if desde in tasas and hasta in tasas:
        en_eur = monto / tasas[desde]
        resultado = en_eur * tasas[hasta]
        return f"{monto:.2f} {desde.upper()} = {resultado:.2f} {hasta.upper()}"

    return f"Moneda no soportada. Soporte: EUR, {', '.join(tasas.keys())}"


def clima(ciudad: str) -> str:
    if not config.openweather_api_key:
        return "El servicio de clima no está configurado."
    try:
        import requests
        url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={config.openweather_api_key}&units=metric&lang=es"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get("cod") == 200:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            return f"{ciudad}: {temp:.1f}°C, {desc}"
        return f"No pude obtener el clima de {ciudad}"
    except Exception as e:
        logger.error(f"Error clima: {e}")
        return "Error al consultar el clima"


def noticias(pais: Optional[str] = None, categoria: Optional[str] = None) -> str:
    if not config.newsapi_key:
        return "El servicio de noticias no está configurado."
    termino = pais if pais else "Venezuela"
    if categoria:
        termino = f"{termino} {categoria}"
    try:
        import requests
        url = f"https://newsapi.org/v2/everything?q={termino}&language=es&sortBy=publishedAt&pageSize=5&apiKey={config.newsapi_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data.get("status") == "ok" and data.get("articles"):
            titulares = []
            for a in data["articles"][:5]:
                titulo = re.sub(r'\s*[-\|].*$', '', a['title'])
                titulares.append(f"📰 {titulo}")
            return "📰 Noticias:\n" + "\n".join(titulares)
        return f"No encontré noticias sobre {termino}."
    except Exception as e:
        logger.error(f"Error noticias: {e}")
        return "Error al consultar noticias"


def horarios() -> str:
    return """Horario de atención:
Lunes a viernes: 10:00 a 14:00 y 16:30 a 21:30
Sábados: 11:00 a 14:00 y 17:00 a 21:00
Domingos y Festivos: 11:00 a 16:00"""


def servicios() -> str:
    return """Servicios disponibles:
- Envío de dinero (remesas): Western Union, RIA
- Recargas móviles: Movistar, Digitel, CANTV
- Impresiones: documentos en blanco y negro
- Delivery: en casco de Mungia, pedido mínimo 15€
- Tienda online: productos latinoamericanos"""


def envio_info() -> str:
    return """📦 Envío de dinero (Remesas)

Servicios disponibles:
- Western Union
- RIA

📋 Requisitos:
- Cédula o pasaporte vigente
- Nombre completo del destinatario
- País de destino
- Monto a enviar

💰 Comisión: 5% del monto enviado

📍 Disponible en: Multiservicios Roraima (Mungia)"""


def precio_pais(pais: str) -> Optional[str]:
    paises_map = {
        'paraguay': 'pyg', 'argentina': 'ars', 'colombia': 'cop',
        'venezuela': 'ves', 'mexico': 'mxn', 'brasil': 'brl',
        'chile': 'clp', 'peru': 'pen', 'bolivia': 'bob',
        'ecuador': 'usd', 'uruguay': 'uyu'
    }
    codigo = paises_map.get(pais.lower())
    if not codigo:
        return None
    if codigo in DIVISAS:
        return f"1 EUR = {DIVISAS[codigo]:.2f} {codigo.upper()}"
    if codigo in config.tasas_default:
        return f"1 EUR = {config.tasas_default[codigo]:.2f} {codigo.upper()}"
    return None


def rag_buscar(pregunta: str) -> str:
    pregunta_lower = pregunta.lower()
    palabras_envio = ['envío', 'enviar', 'envó', 'envo', 'remesa', 'western', 'ria', 'necesito para enviar']
    if any(p in pregunta_lower for p in palabras_envio):
        return envio_info()
    if any(p in pregunta_lower for p in ['horario', 'abren', 'cierran', 'domingo', 'sabado', 'festivo']):
        return horarios()
    if any(p in pregunta_lower for p in ['servicio', 'ofrecen', 'delivery', 'recarga', 'impresion', 'tienda']):
        return servicios()
    paises = ['paraguay', 'argentina', 'colombia', 'venezuela', 'mexico',
              'brasil', 'chile', 'peru', 'bolivia', 'ecuador', 'uruguay']
    for pais in paises:
        if pais in pregunta_lower:
            resultado = precio_pais(pais)
            if resultado:
                return resultado
    return f"No encontré información sobre '{pregunta}'"


# Registrar herramientas
registro.registrar("calculadora", calculadora, "Realiza cálculos matemáticos. Parámetros: expresion")
registro.registrar("convertir_moneda", convertir_moneda, "Convierte monedas EUR vs LATAM. Parámetros: monto, desde, hasta")
registro.registrar("rag_buscar", rag_buscar, "Busca en documentos internos (horarios, servicios, envíos, precios). Parámetros: pregunta")
registro.registrar("clima", clima, "Obtiene el clima actual de una ciudad. Parámetros: ciudad")
registro.registrar("noticias", noticias, "Obtiene noticias recientes. Parámetros: pais (opcional), categoria (opcional)")
registro.registrar("horarios", horarios, "Devuelve el horario de atención. Sin parámetros")
registro.registrar("servicios", servicios, "Lista los servicios disponibles. Sin parámetros")


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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL,
                    pregunta TEXT NOT NULL,
                    respuesta TEXT NOT NULL,
                    herramientas TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hechos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL,
                    clave TEXT NOT NULL,
                    valor TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    UNIQUE(usuario, clave)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv ON conversaciones(usuario, timestamp DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_hechos ON hechos(usuario)")

    def guardar_conversacion(self, usuario, pregunta, respuesta, herramienta):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversaciones (usuario, pregunta, respuesta, herramientas, timestamp) VALUES (?,?,?,?,?)",
                (usuario, pregunta, respuesta, herramienta, datetime.now().isoformat())
            )

    def recordar_hecho(self, usuario, clave, valor):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE hechos SET valor=?, timestamp=? WHERE usuario=? AND clave=?",
                (valor, datetime.now().isoformat(), usuario, clave)
            )
            if cursor.rowcount == 0:
                conn.execute(
                    "INSERT INTO hechos (usuario, clave, valor, timestamp) VALUES (?,?,?,?)",
                    (usuario, clave, valor, datetime.now().isoformat())
                )
        logger.info(f"✅ Recordado: {usuario} -> {clave} = {valor}")

    def obtener_hechos(self, usuario) -> Dict:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT clave, valor FROM hechos WHERE usuario = ?", (usuario,))
            return dict(cursor.fetchall())

    def historial_usuario(self, usuario, ultimas_n=5) -> List:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT pregunta, respuesta FROM conversaciones WHERE usuario=? ORDER BY timestamp DESC LIMIT ?",
                (usuario, ultimas_n)
            )
            return cursor.fetchall()


memoria = MemoriaLargoPlazo()


# ============================================================
# BUCLE AGENTE CON OLLAMA
# ============================================================

SYSTEM_PROMPT = """Eres Roraima, el asistente inteligente de Multiservicios Roraima en Mungia (Bizkaia).

Tu trabajo es ayudar a los clientes respondiendo sus preguntas usando las herramientas disponibles.

HERRAMIENTAS DISPONIBLES:
{herramientas}

REGLAS:
1. Responde SIEMPRE en formato JSON válido
2. Si puedes responder directamente sin herramientas, hazlo
3. Si necesitas una herramienta, indícala con sus parámetros
4. Sé breve, amable y directo
5. Responde siempre en español

FORMATO DE RESPUESTA (solo JSON):
- Respuesta directa: {{"tipo": "respuesta", "contenido": "tu respuesta"}}
- Usar herramienta: {{"tipo": "herramienta", "nombre": "nombre_herramienta", "parametros": {{"param": "valor"}}}}"""


class BucleAgente:
    def __init__(self):
        self.historial_pensamientos = []
        self.usuario_actual = "anónimo"

    def set_usuario(self, usuario):
        self.usuario_actual = usuario

    def pensar_con_llm(self, pregunta: str) -> Optional[Dict]:
        """Usa Ollama para decidir qué hacer"""
        hechos = memoria.obtener_hechos(self.usuario_actual)
        historial = memoria.historial_usuario(self.usuario_actual, ultimas_n=3)

        contexto = ""
        if hechos:
            contexto += f"Hechos del usuario: {json.dumps(hechos)}\n"
        if historial:
            contexto += "Conversaciones recientes:\n"
            for p, r in historial:
                contexto += f"  Usuario: {p[:80]}\n  Roraima: {r[:80]}\n"

        system = SYSTEM_PROMPT.format(herramientas=registro.listar_para_prompt())
        user = f"{contexto}\nPregunta del usuario: {pregunta}"

        respuesta_raw = cerebro.pensar(system, user)
        if not respuesta_raw:
            return None

        try:
            # Limpiar la respuesta por si tiene texto antes/después del JSON
            respuesta_raw = respuesta_raw.strip()
            # Buscar el JSON en la respuesta
            inicio = respuesta_raw.find('{')
            fin = respuesta_raw.rfind('}') + 1
            if inicio >= 0 and fin > inicio:
                json_str = respuesta_raw[inicio:fin]
                decision = json.loads(json_str)
                logger.info(f"🧠 LLM decidió: {decision}")
                return decision
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ LLM respondió JSON inválido: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error procesando respuesta LLM: {e}")

        return None

    def pensar_con_reglas(self, pregunta: str) -> Dict:
        """Fallback: detección por reglas (como la versión anterior)"""
        pregunta_lower = pregunta.lower()
        logger.info("📏 Usando detección por reglas")

        # Recordar nombre
        if any(p in pregunta_lower for p in ['cómo me llamo', 'como me llamo',
                                              'recuerdas mi nombre', 'recuerdas como',
                                              'sabes mi nombre', 'quién soy', 'quien soy']):
            hechos = memoria.obtener_hechos(self.usuario_actual)
            nombre = hechos.get('nombre')
            if nombre:
                return {"tipo": "respuesta", "contenido": f"¡Claro! Te llamas {nombre} 😊"}
            return {"tipo": "respuesta", "contenido": "Aún no me has dicho tu nombre. ¿Cómo te llamas?"}

        # Guardar nombre
        if 'me llamo' in pregunta_lower or 'mi nombre es' in pregunta_lower:
            partes = re.split(r'me llamo|mi nombre es', pregunta_lower)
            if len(partes) > 1:
                nombre_raw = re.sub(r'[^a-záéíóúñü\s]', '', partes[1].strip()).strip()
                if nombre_raw:
                    nombre = nombre_raw.split()[0].capitalize()
                    memoria.recordar_hecho(self.usuario_actual, "nombre", nombre)
                    return {"tipo": "respuesta", "contenido": f"¡Encantado de conocerte, {nombre}!"}
            return {"tipo": "respuesta", "contenido": "No pude captar tu nombre. ¿Puedes repetirlo?"}

        # Nombre suelto
        palabras = pregunta.strip().split()
        if len(palabras) == 1 and palabras[0].isalpha():
            if palabras[0].lower() not in ['salir', 'exit', 'quit', 'hola', 'si', 'no', 'ok'] and len(palabras[0]) >= 2:
                nombre = palabras[0].capitalize()
                memoria.recordar_hecho(self.usuario_actual, "nombre", nombre)
                return {"tipo": "respuesta", "contenido": f"¡Encantado de conocerte, {nombre}!"}

        # Descuentos
        if 'descuento' in pregunta_lower:
            return {"tipo": "herramienta", "nombre": "calculadora", "parametros": {"expresion": pregunta}}

        # Operaciones matemáticas
        if any(op in pregunta for op in ['+', '-', '*', '/']) and any(c.isdigit() for c in pregunta):
            return {"tipo": "herramienta", "nombre": "calculadora", "parametros": {"expresion": pregunta}}

        # Conversiones de moneda
        numeros = re.findall(r'\d+', pregunta)
        if numeros and 'euro' in pregunta_lower:
            paises = ['colombia', 'argentina', 'paraguay', 'venezuela', 'mexico', 'brasil', 'chile', 'peru']
            for pais in paises:
                if pais in pregunta_lower:
                    return {"tipo": "herramienta", "nombre": "convertir_moneda",
                            "parametros": {"monto": numeros[0], "desde": "EUR", "hasta": pais}}

        # Horarios
        if any(p in pregunta_lower for p in ['horario', 'abren', 'cierran', 'domingo', 'sabado', 'hoy']):
            return {"tipo": "herramienta", "nombre": "horarios", "parametros": {}}

        # Envíos
        if any(p in pregunta_lower for p in ['envío', 'enviar', 'remesa', 'western', 'ria']):
            return {"tipo": "herramienta", "nombre": "rag_buscar", "parametros": {"pregunta": pregunta}}

        # Servicios
        if any(p in pregunta_lower for p in ['servicio', 'ofrecen', 'tienen', 'delivery', 'recarga', 'tienda']):
            return {"tipo": "herramienta", "nombre": "rag_buscar", "parametros": {"pregunta": pregunta}}

        # Por defecto: RAG
        return {"tipo": "herramienta", "nombre": "rag_buscar", "parametros": {"pregunta": pregunta}}

    def pensar(self, pregunta: str) -> Dict:
        """Intenta con LLM, fallback a reglas"""
        # Intentar con Ollama primero
        decision = self.pensar_con_llm(pregunta)
        if decision and "tipo" in decision:
            return decision

        # Fallback a reglas
        return self.pensar_con_reglas(pregunta)

    def actuar(self, decision: Dict) -> str:
        """Ejecuta la decisión"""
        if decision.get("tipo") == "herramienta":
            nombre = decision.get("nombre", "")
            params = decision.get("parametros", {})
            return registro.ejecutar(nombre, params)
        return decision.get("contenido", "No pude procesar tu solicitud")

    def observar(self, decision: Dict, resultado: str) -> str:
        """Registra el resultado"""
        self.historial_pensamientos.append({
            "decision": decision,
            "resultado": resultado,
            "timestamp": datetime.now().isoformat()
        })
        return resultado


# ============================================================
# AGENTE COMPLETO v3.0
# ============================================================

class AgenteRoraima:
    def __init__(self):
        self.bucle = BucleAgente()
        self.usuario_actual = "anónimo"

    def saludar(self, usuario: str) -> str:
        self.usuario_actual = usuario
        self.bucle.set_usuario(usuario)

        # Guardar nombre en memoria
        if usuario and usuario != "anónimo":
            memoria.recordar_hecho(usuario, "nombre", usuario)

        hechos = memoria.obtener_hechos(usuario)
        estado_llm = "🧠 Ollama activo" if cerebro.disponible else "📏 Modo reglas"
        nombre = hechos.get('nombre', usuario)

        if hechos.get('nombre'):
            return f"Hola {nombre}! Bienvenido de vuelta a Multiservicios Roraima. ({estado_llm})"
        return f"Hola {nombre}! Soy Roraima, tu asistente. ¿En qué puedo ayudarte? ({estado_llm})"

    def procesar(self, pregunta: str) -> str:
        try:
            logger.info(f"👤 {self.usuario_actual}: {pregunta}")

            # 1. Pensar
            decision = self.bucle.pensar(pregunta)

            # 2. Actuar
            resultado = self.bucle.actuar(decision)

            # 3. Observar
            resultado_final = self.bucle.observar(decision, resultado)

            # 4. Guardar en memoria
            herramienta = decision.get("nombre", decision.get("tipo", "desconocida"))
            memoria.guardar_conversacion(self.usuario_actual, pregunta, resultado_final, herramienta)

            logger.info(f"🤖 Respuesta ({herramienta}): {resultado_final[:80]}...")
            return resultado_final

        except Exception as e:
            logger.error(f"Error procesando: {pregunta}", exc_info=True)
            return "Disculpa, tuve un pequeño problema. ¿Puedes repetir la pregunta?"


# ============================================================
# MODO INTERACTIVO
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🤖 AGENTE RORAIMA v3.0")
    print("   Ollama + Memoria + Herramientas Reales")
    print("=" * 50)

    estado = "🧠 Ollama activo" if cerebro.disponible else "📏 Modo reglas (Ollama no disponible)"
    print(f"Estado: {estado}")
    print("Comandos: 'salir' - terminar\n")

    agente = AgenteRoraima()

    usuario = input("👤 ¿Cómo te llamas? ").strip()
    if not usuario:
        usuario = "anónimo"

    print(f"\n🤖 {agente.saludar(usuario)}\n")

    while True:
        pregunta = input("❓ Tú: ").strip()
        if pregunta.lower() in ["salir", "exit", "quit"]:
            print("🤖 ¡Hasta luego!")
            break
        if not pregunta:
            continue
        respuesta = agente.procesar(pregunta)
        print(f"🤖 {respuesta}\n")