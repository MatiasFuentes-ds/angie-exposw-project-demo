# ANGIE

**Agent for Native Generative Intelligence Environments**

> Descubre qué modelos de IA puedes correr en tu equipo, simula su comportamiento y obtén una guía de instalación personalizada — antes de descargar un solo archivo.

🏆 Proyecto presentado en **Expo Software 2026** — Escuela de Ingeniería Informática, Pontificia Universidad Católica de Valparaíso (PUCV).

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
| Frontend | React + Tailwind CSS |
| Visualización | Recharts |
| Lógica de simulación | Modelo de estimación basado en benchmarks (Python / JS) |
| Backend (futuro) | FastAPI |

---

## 🚀 Cómo correr el proyecto localmente

```bash
# Clonar el repositorio
git clone https://github.com/MatiasFuentes-ds/angie.git
cd angie

# Instalar dependencias
npm install

# Iniciar el entorno de desarrollo
npm run dev
```

La aplicación quedará disponible en `http://localhost:3000`

---

## 📂 Estructura del proyecto

```
angie/
├── src/
│   ├── components/      # Componentes de UI
│   ├── data/             # Benchmarks y datos de modelos
│   ├── logic/            # Lógica de evaluación y simulación
│   └── pages/            # Vistas principales
├── public/
└── README.md
```

---

## 🗺️ Roadmap

- [x] MVP: evaluación de hardware + recomendación de modelos
- [x] Simulación visual de rendimiento
- [ ] Guías de instalación dinámicas por sistema operativo
- [ ] Comparador de hardware (actual vs. hipotético)
- [ ] Modo voz / conversacional
- [ ] Dashboard de monitoreo en tiempo real (modelos instalados realmente)

---

## 🎓 Contexto

ANGIE fue desarrollado como proyecto individual para **Expo Software 2026**, organizada por la Unidad de Vinculación con el Medio de la Escuela de Ingeniería Informática, PUCV.

**Autor:** Mathias — Ingeniería Civil en Ciencia de Datos, PUCV

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Ver el archivo `LICENSE` para más detalles.
