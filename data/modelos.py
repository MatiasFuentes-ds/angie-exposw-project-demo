# data/modelos.py
# Única fuente de verdad sobre modelos de IA locales.
# Todos los módulos del sistema leen desde aquí.

MODELOS: dict[str, dict] = {
    "phi3-mini": {
        "nombre_display": "Phi-3 Mini (3.8B)",
        "parametros_b": 3.8,
        "ram_min_gb": 4,
        "vram_min_gb": 0,          # puede correr solo en CPU
        "requiere_gpu": False,
        "casos_uso": ["conversación", "preguntas generales", "resumen"],
        "descripcion": "Modelo ultraligero de Microsoft. Ideal para equipos con poca RAM.",
        "ollama_tag": "phi3:mini",
        "comando_ollama": "ollama run phi3:mini",
        "tokens_por_sseg_base": 18.0,   # estimado en CPU, 8 GB RAM
    },
    "gemma2-2b": {
        "nombre_display": "Gemma 2 (2B)",
        "parametros_b": 2,
        "ram_min_gb": 4,
        "vram_min_gb": 0,
        "requiere_gpu": False,
        "casos_uso": ["conversación", "educación", "código simple"],
        "descripcion": "Modelo liviano de Google. Muy eficiente en CPU.",
        "ollama_tag": "gemma2:2b",
        "comando_ollama": "ollama run gemma2:2b",
        "tokens_por_seg_base": 20.0,
    },
    "mistral-7b": {
        "nombre_display": "Mistral 7B",
        "parametros_b": 7,
        "ram_min_gb": 8,
        "vram_min_gb": 6,
        "requiere_gpu": False,         # puede correr en CPU lento
        "casos_uso": ["código", "análisis", "conversación avanzada"],
        "descripcion": "Modelo de referencia para uso general. Requiere hardware intermedio.",
        "ollama_tag": "mistral",
        "comando_ollama": "ollama run mistral",
        "tokens_por_seg_base": 9.0,
    },
    "llama3-8b": {
        "nombre_display": "Llama 3 (8B)",
        "parametros_b": 8,
        "ram_min_gb": 8,
        "vram_min_gb": 6,
        "requiere_gpu": False,
        "casos_uso": ["código", "análisis", "razonamiento"],
        "descripcion": "Modelo robusto de Meta. Buena relación calidad/requisitos.",
        "ollama_tag": "llama3",
        "comando_ollama": "ollama run llama3",
        "tokens_por_seg_base": 8.5,
    },
    "llama3-70b": {
        "nombre_display": "Llama 3 (70B)",
        "parametros_b": 70,
        "ram_min_gb": 48,
        "vram_min_gb": 40,
        "requiere_gpu": True,
        "casos_uso": ["código complejo", "razonamiento avanzado", "análisis profesional"],
        "descripcion": "Modelo de alta capacidad. Requiere hardware de gama alta o servidor.",
        "ollama_tag": "llama3:70b",
        "comando_ollama": "ollama run llama3:70b",
        "tokens_por_seg_base": 3.0,
    },
}


def get_nombres_modelos() -> list[str]:
    """Retorna la lista de claves/IDs de todos los modelos disponibles."""
    return list(MODELOS.keys())


def get_modelo(nombre: str) -> dict:
    """
    Retorna el diccionario de specs de un modelo por su clave.
    Lanza KeyError si el nombre no existe.
    """
    if nombre not in MODELOS:
        raise KeyError(f"Modelo '{nombre}' no encontrado. Disponibles: {get_nombres_modelos()}")
    return MODELOS[nombre]


def get_todos_los_modelos() -> dict[str, dict]:
    """Retorna el diccionario completo de modelos (solo lectura conceptual)."""
    return MODELOS