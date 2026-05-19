# Agente Roraima v3.5

Asistente conversacional con IA para Multiservicios Roraima (Mungia, Bizkaia).

Sistema hibrido de reglas deterministas + LLM local con memoria persistente, RAG, y conexion en vivo a Google Sheets para cotizaciones de divisas.

---

## Caso de uso

Multiservicios Roraima es un negocio real en Mungia (Bizkaia) que ofrece:

- Envio de dinero (Western Union, RIA, Europhil)
- Recargas moviles (Nacionales e Internacionales)
- Servicios de impresion
- Delivery local
- Productos latinoamericanos
- Cotizacion de divisas

Este agente fue disenado para automatizar la atencion de consultas frecuentes, liberando tiempo del personal en tienda.

---

## Caracteristicas tecnicas

### Arquitectura hibrida de 3 capas

1. CAPA 1: Reglas deterministas (preguntas obvias y frecuentes)
2. CAPA 2: LLM con Ollama + llama3.2 (preguntas ambiguas)
3. CAPA 3: RAG fallback (siempre responde)

### Stack tecnologico

- Python 3.11+
- LangChain para orquestacion
- Ollama + llama3.2 (LLM local)
- SQLite (memoria persistente thread-safe)
- Google Sheets API (19 divisas en vivo)
- Streamlit (interfaz web frontend)
- OpenWeather API (clima)
- NewsAPI (noticias)

### Funcionalidades

- Memoria de largo plazo por usuario (SQLite)
- 19 divisas actualizadas en tiempo real
- Interfaz web tipo chat (Streamlit)
- Modo CLI alternativo
- 7 herramientas integradas (tools)
- Logging profesional de eventos

---

## Instalacion y Uso

### Prerrequisitos

- Python 3.11+
- Ollama instalado y corriendo
- Modelo llama3.2 descargado (ollama pull llama3.2)

### Setup

    git clone https://github.com/juliocalderaro/agente-roraima.git
    cd agente-roraima
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    cp .env.example .env

### Ejecucion

Modo Web (Streamlit):

    streamlit run app_streamlit.py

Modo Consola (CLI):

    python src/main.py

---

## Estructura del proyecto

    agente-roraima/
    |-- README.md
    |-- LIMITACIONES.md
    |-- LICENSE
    |-- requirements.txt
    |-- app_streamlit.py
    |-- .env.example
    |-- src/
    |   |-- main.py
    |-- data/
    |-- docs/
    |-- logs/
    |-- tests/

---

## Validacion y Pruebas

El motor del agente ha sido validado con una bateria de pruebas funcionales:

- Test 1: Calculos matematicos
- Test 2: Conversion de divisas
- Test 3: Informacion de horarios
- Test 4: Informacion de servicios
- Test 5: Informacion de envios
- Test 6: Informacion de delivery
- Test 7: Consulta de clima
- Test 8: Consulta de noticias
- Test 9: Memoria de usuario

Resultado: 9/9 aprobados

---

## Limitaciones conocidas y Transparencia

Ver documento LIMITACIONES.md para una descripcion completa y honesta de:

- Que hace bien el agente
- Que hace de forma limitada
- Por que se diseno asi
- Como se resuelven estos puntos en el roadmap a futuro

Documentar lo que un sistema de IA no hace perfectamente es una decision de transparencia profesional.

---

## Roadmap

| Version | Estado | Descripcion                              |
|---------|--------|------------------------------------------|
| v3.4    | OK     | Motor del agente validado                |
| v3.5    | OK     | Interfaz Streamlit (esta version)        |
| v4.0    | TODO   | Migracion a GCP + WhatsApp Business API  |

---

## Autor

Julio Cesar Calderaro
Senior BI and Data Specialist | AI Solutions Consultant

- Consultoria: InPyme (https://inpymecom.wordpress.com/)
- LinkedIn: https://www.linkedin.com/in/juliocalderaro
- Portfolio: https://juliocalderaro.wixsite.com/juliocalderaro

---

## Reconocimientos

Proyecto desarrollado como parte de un programa autodidacta de IA Generativa, aplicado a un negocio real para validar el aprendizaje tecnico con casos de uso concretos.

"Reglas deterministas primero, LLM despues"
- Principio arquitectonico del proyecto
