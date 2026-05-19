"""
Agente Roraima v3.5 - Interfaz Streamlit
═══════════════════════════════════════════════
Frontend web para el agente Roraima v3.4
Cliente: Multiservicios Roraima (Mungia, Bizkaia)
"""

import sys
import os
from pathlib import Path

# Añadir src/ al path para importar el agente
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

import streamlit as st
from main import AgenteRoraima, cerebro, DIVISAS


# ============================================================
# CONFIGURACION DE PAGINA
# ============================================================

st.set_page_config(
    page_title="Roraima | Asistente IA",
    page_icon="🌎",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# ESTILOS PERSONALIZADOS
# ============================================================

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #0F3460 0%, #1A1A2E 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        color: white;
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: #E94560;
        margin: 0.3rem 0 0 0;
        font-size: 0.95rem;
    }
    .status-ok {
        background-color: #d4edda;
        color: #155724;
        padding: 0.4rem 0.8rem;
        border-radius: 5px;
        font-size: 0.85rem;
        display: inline-block;
    }
    .status-warn {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.4rem 0.8rem;
        border-radius: 5px;
        font-size: 0.85rem;
        display: inline-block;
    }
    .info-box {
        background-color: #f8f9fa;
        padding: 0.8rem;
        border-left: 4px solid #0F3460;
        border-radius: 5px;
        margin: 0.5rem 0;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# INICIALIZACION DEL AGENTE (una sola vez)
# ============================================================

@st.cache_resource
def inicializar_agente():
    """Crea el agente una sola vez y lo mantiene en memoria."""
    return AgenteRoraima()


# ============================================================
# ESTADO DE SESION
# ============================================================

if "agente" not in st.session_state:
    st.session_state.agente = inicializar_agente()

if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if "saludo_mostrado" not in st.session_state:
    st.session_state.saludo_mostrado = False


# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class="main-header">
    <h1>🌎 Roraima | Asistente IA</h1>
    <p>Multiservicios Roraima · Mungia, Bizkaia</p>
</div>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR - ESTADO Y INFO DEL NEGOCIO
# ============================================================

with st.sidebar:
    st.markdown("### ⚙️ Estado del Sistema")

    # Estado Ollama
    if cerebro.disponible:
        st.markdown(
            '<span class="status-ok">🟢 Ollama: Activo (llama3.2)</span>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<span class="status-warn">🟡 Ollama: Modo Reglas</span>',
            unsafe_allow_html=True
        )

    # Divisas cargadas
    st.markdown(
        f'<span class="status-ok">💱 {len(DIVISAS)} divisas en vivo</span>',
        unsafe_allow_html=True
    )

    st.markdown("---")

    # Info del usuario actual
    st.markdown("### 👤 Usuario")
    if st.session_state.usuario:
        st.info(f"**{st.session_state.usuario}**")
        if st.button("🔄 Cambiar usuario"):
            st.session_state.usuario = None
            st.session_state.mensajes = []
            st.session_state.saludo_mostrado = False
            st.rerun()
    else:
        st.warning("No identificado")

    st.markdown("---")

    # Ejemplos de preguntas
    st.markdown("### 💡 Prueba preguntar")
    ejemplos = [
        "¿Cuáles son los horarios?",
        "¿Qué servicios ofrecen?",
        "100 euros a Colombia",
        "¿Cómo envío dinero a Venezuela?",
        "Clima de Bilbao",
        "Noticias",
        "150 + 230",
        "¿Hacen delivery?"
    ]

    for ejemplo in ejemplos:
        if st.button(ejemplo, key=f"ej_{ejemplo}", use_container_width=True):
            if st.session_state.usuario:
                st.session_state.pregunta_ejemplo = ejemplo
                st.rerun()
            else:
                st.warning("Primero identifícate")

    st.markdown("---")

    # Info del negocio
    st.markdown("### 📍 Información")
    st.markdown("""
    <div class="info-box">
    <b>📍 Dirección:</b><br>
    Zubiaga Kalea 4, Mungia<br><br>
    <b>📱 WhatsApp:</b><br>
    +34 643 901 309<br><br>
    <b>🕒 Horario:</b><br>
    L-V: 10-14h / 16:30-21:30<br>
    Sáb: 11-14h / 17-21h<br>
    Dom: 11-16h
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# FLUJO PRINCIPAL: IDENTIFICACION O CHAT
# ============================================================

# Si no hay usuario identificado → pedir nombre
if not st.session_state.usuario:
    st.markdown("### 👋 Bienvenido")
    st.markdown("Para empezar, dime tu nombre:")

    col1, col2 = st.columns([3, 1])

    with col1:
        nombre_input = st.text_input(
            "Nombre",
            label_visibility="collapsed",
            placeholder="Escribe tu nombre..."
        )

    with col2:
        comenzar = st.button("Comenzar", type="primary", use_container_width=True)

    if comenzar and nombre_input.strip():
        st.session_state.usuario = nombre_input.strip()
        st.rerun()
    elif comenzar:
        st.error("Por favor escribe tu nombre")

# Si hay usuario → mostrar chat
else:
    # Saludo inicial (solo una vez por sesión)
    if not st.session_state.saludo_mostrado:
        saludo = st.session_state.agente.saludar(st.session_state.usuario)
        st.session_state.mensajes.append({
            "rol": "assistant",
            "contenido": saludo
        })
        st.session_state.saludo_mostrado = True

    # Mostrar historial de mensajes
    for msg in st.session_state.mensajes:
        with st.chat_message(msg["rol"]):
            st.markdown(msg["contenido"])

    # Manejar pregunta desde botón de ejemplo
    pregunta_pendiente = None
    if "pregunta_ejemplo" in st.session_state:
        pregunta_pendiente = st.session_state.pregunta_ejemplo
        del st.session_state.pregunta_ejemplo

    # Input del usuario
    pregunta_usuario = st.chat_input("Escribe tu pregunta...")

    # Usar la pregunta del ejemplo si existe, si no la del input
    pregunta = pregunta_pendiente or pregunta_usuario

    if pregunta:
        # Mostrar pregunta del usuario
        st.session_state.mensajes.append({
            "rol": "user",
            "contenido": pregunta
        })
        with st.chat_message("user"):
            st.markdown(pregunta)

        # Procesar con el agente
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                respuesta = st.session_state.agente.procesar(pregunta)
            st.markdown(respuesta)

        # Guardar respuesta en historial
        st.session_state.mensajes.append({
            "rol": "assistant",
            "contenido": respuesta
        })

        st.rerun()