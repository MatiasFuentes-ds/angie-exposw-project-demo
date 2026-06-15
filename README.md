# ANGIE

**Agent for Native Generative Intelligence Environments**

> Descubre qué modelos de IA puedes correr en tu equipo, simula su comportamiento y obtén una guía de instalación personalizada — antes de descargar un solo archivo.

🏆 Proyecto presentado en **Expo Software 2026** — Escuela de Ingeniería Informática, Pontificia Universidad Católica de Valparaíso (PUCV).

---

## 🧩 El problema

Correr modelos de IA de forma local es hoy territorio casi exclusivo de usuarios técnicos. Requiere entender conceptos como VRAM, cuantización, backends de inferencia y configuración por terminal.

El resultado: usuarios semi-técnicos —estudiantes, entusiastas, desarrolladores curiosos— descargan modelos que su equipo no puede ejecutar, pierden tiempo en prueba y error, y terminan abandonando la IA local antes de comprobar su verdadero potencial.

**Nadie les dice si pueden hacerlo antes de intentarlo.**

---

## 💡 La solución

ANGIE es una aplicación web que actúa como copiloto para la IA local:

1. **Evalúa** las especificaciones de tu equipo (RAM, GPU/VRAM, sistema operativo, uso previsto).
2. **Recomienda** qué modelos son viables, mostrando un semáforo de compatibilidad (🟢🟡🔴).
3. **Simula** el comportamiento del modelo elegido en tu hardware: uso de CPU/RAM, velocidad estimada (tokens/seg), tiempo de respuesta y temperatura aproximada.
4. **Guía** la instalación real paso a paso, adaptada a tu sistema operativo y al modelo seleccionado.

Todo esto sin instalar nada hasta que el usuario decida hacerlo de forma informada.

---

## ✨ Características principales

- 🖥️ Formulario simple de especificaciones de hardware (sin jerga técnica).
- 🚦 Evaluación de compatibilidad con modelos populares (Phi-3, Gemma, Mistral, Llama, etc.).
- 📊 Simulación visual en tiempo real del rendimiento estimado.
- 🛠️ Guía de instalación personalizada (Ollama / LM Studio / llama.cpp).
- 🔄 Modo exploración: simula hardware hipotético para evaluar upgrades.
- 🔒 Procesamiento local — sin envío de datos sensibles del equipo a servidores externos.

---

## 🏗️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| Interfaz | Streamlit |
| Visualización | Plotly / componentes nativos de Streamlit |
| Lógica de evaluación y simulación | Python (reglas + datos de benchmarks) |
| Datos de modelos | Diccionario/JSON con specs de modelos populares (Phi-3, Gemma, Mistral, Llama) |
| Deploy | Streamlit Community Cloud |

> Se eligió Streamlit por sobre un stack frontend tradicional (React) para priorizar velocidad de desarrollo y mantener todo el flujo —datos, lógica y UI— en Python puro durante el MVP.

---

## 🚀 Cómo correr el proyecto localmente

```bash
# Clonar el repositorio
git clone https://github.com/<tu-usuario>/angie.git
cd angie

# Crear entorno virtual (opcional pero recomendado)
python -m venv venv
source venv/bin/activate    # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Iniciar la aplicación
streamlit run app.py
```

La aplicación quedará disponible en `http://localhost:8501`

---

## 📂 Estructura del proyecto

```
angie/
├── app.py                # Punto de entrada de Streamlit (UI principal)
├── data/
│   └── modelos.py         # Specs de modelos (RAM, VRAM, parámetros)
├── logic/
│   ├── evaluacion.py       # Lógica de compatibilidad (semáforo 🟢🟡🔴)
│   └── simulacion.py       # Estimación de rendimiento (tokens/seg, RAM, carga)
├── assets/                # Logo e imágenes
├── requirements.txt
└── README.md
```

---

## 🗺️ Roadmap

**MVP — Expo Software 2026**
- [ ] Formulario de especificaciones de hardware
- [ ] Evaluación de compatibilidad (semáforo 🟢🟡🔴) con modelos populares
- [ ] Simulación visual de rendimiento (tokens/seg, uso de RAM, tiempo de carga)
- [ ] Guía de instalación básica (comando Ollama por modelo)
- [ ] Modo exploración (recalcular con specs hipotéticas)
- [ ] Deploy en Streamlit Community Cloud

**Versión futura**
- [ ] Guías de instalación dinámicas y detalladas por sistema operativo
- [ ] Comparador de hardware (actual vs. hipotético) lado a lado
- [ ] Modo voz / conversacional
- [ ] Benchmarks reales (no estimados) y monitoreo de modelos instalados de verdad
- [ ] Migración a stack web completo (React + FastAPI) para producto final

---

## 🎓 Contexto

ANGIE fue desarrollado como proyecto individual para **Expo Software 2026**, organizada por la Unidad de Vinculación con el Medio de la Escuela de Ingeniería Informática, PUCV.

**Autor:** Matías Fuentes — Ingeniería Civil en Ciencia de Datos, PUCV

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Ver el archivo `LICENSE` para más detalles.
