# Limitaciones Técnicas Conocidas

## Sobre este documento

Este agente fue desarrollado como proyecto de aprendizaje
dentro del programa autodidacta de IA Generativa.
Las limitaciones aquí documentadas son intencionales y
forman parte del aprendizaje técnico del proyecto.

La transparencia sobre lo que el sistema NO hace bien es,
en sí misma, una decisión profesional.

---

## ✅ Lo que el agente HACE bien

- Responde correctamente a consultas sobre:
  - Horarios de atención
  - Servicios ofrecidos
  - Información de envíos de dinero (operadores, requisitos)
  - Cotizaciones de 19 divisas en tiempo real desde Google Sheets
  - Conversiones EUR ↔ monedas latinoamericanas
  - Información de delivery
  - Cálculos matemáticos básicos
  - Clima (vía OpenWeather API)
  - Noticias (vía NewsAPI)

- Mantiene memoria persistente por usuario (SQLite)
- Recuerda nombres y conversaciones previas
- Interfaz web tipo chat (Streamlit)
- Modo CLI alternativo

---

## ⚠️ Limitaciones conocidas

### 1. Clasificación basada en keywords

El sistema usa reglas deterministas con palabras clave.
Esto significa que:

- Funciona muy bien cuando la pregunta contiene
  palabras esperadas ("envío", "servicios", "horario")
- Puede confundir intenciones cuando una pregunta
  contiene palabras de múltiples dominios
  (ejemplo: "Cómo mando plata a Colombia" puede
  activar la regla de conversión de divisas en
  lugar de la regla de información de envíos)

### 2. Hardware limitado para LLM

El proyecto corre en hardware con 8GB de RAM, lo que
limita el uso de modelos a 3B parámetros (llama3.2).

Consecuencias:
- El LLM puede generar respuestas imprecisas en
  preguntas ambiguas
- No se puede usar fine-tuning local
- No se puede ejecutar RAG con modelos mayores

### 3. Respuestas del LLM en zona ambigua

Cuando una pregunta no matchea ninguna regla
determinista, el LLM (capa 2) toma la decisión.
En esos casos puede:

- Generar respuestas correctas pero variables
  entre ejecuciones
- Ocasionalmente inventar información
  (mitigado parcialmente con prompts estrictos)

### 4. Sin integración real a WhatsApp

El motor del agente está validado y funcional,
pero NO está conectado a WhatsApp Business API.

El canal de atención real del cliente
(Multiservicios Roraima) funciona con
WhatsAuto (bot estático), no con este agente.

La integración con WhatsApp Business API está
documentada en el roadmap v4.0 (GCP + Gemini)
pero no implementada.

---

## 🎯 Por qué se documentan estas limitaciones

Este proyecto demuestra:

1. **Conocimiento técnico real:** arquitectura híbrida
   (reglas + LLM + RAG), integración con APIs,
   persistencia de datos, interfaz web

2. **Criterio profesional:** entender los límites
   de la IA Generativa con hardware limitado

3. **Honestidad técnica:** documentar lo que falla
   en lugar de ocultarlo

4. **Visión de producto:** distinguir entre
   "prototipo funcional" y "sistema en producción"

---

## 🚀 Roadmap futuro (v4.0)

Las limitaciones actuales se resuelven en la
versión documentada para GCP:

- Cloud Run + Gemini API (modelos mayores)
- Cloud SQL PostgreSQL (escalabilidad)
- WhatsApp Business API (canal real)
- Cloud Storage para vectores RAG

Documento: `roraima_roadmap_gcp.md`

---

## 📊 Cobertura aproximada

Basado en pruebas con preguntas reales del negocio:

- Consultas operativas comunes: ~90% acierto
- Consultas de divisas: ~95% acierto
- Conversaciones contextuales: ~85% acierto
- Edge cases con ambigüedad: ~60% acierto

**Total ponderado: ~85% acierto**

Este nivel se considera aceptable para un sistema
de asistencia que opera con supervisión humana,
no para reemplazo total de atención al cliente.