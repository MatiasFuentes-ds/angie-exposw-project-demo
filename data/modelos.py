# data/modelos.py
# Única fuente de verdad sobre modelos de IA locales.
# Todos los módulos del sistema leen desde aquí.
#
# Fuentes de los valores empíricos:
#   - Tamaños de archivo: ollama.com/library + HuggingFace GGUF oficial
#   - Contexto por defecto: docs.ollama.com/context-length (< 24 GB VRAM → 4k ctx)
#   - Benchmarks CPU/GPU: ai-ollama.github.io, databasemart.com/blog, openllmbenchmarks.com
#   - Cuantización por defecto de Ollama: Q4_K_M en todos los modelos salvo gemma2:2b (Q4_0)

MODELOS: dict[str, dict] = {
    "phi3-mini": {
        "nombre_display":  "Phi-3 Mini (3.8B)",
        "parametros_b":    3.8,
        "ram_min_gb":      4,            # Q4_K_M ocupa ~2.2 GB; 4 GB RAM es el mínimo real
        "vram_min_gb":     0,            # corre en CPU sin problema
        "requiere_gpu":    False,
        "casos_uso":       ["conversación", "preguntas generales", "resumen"],
        "descripcion":     "Modelo ultraligero de Microsoft. Ideal para equipos con poca RAM.",
        "ollama_tag":      "phi3:mini",
        "comando_ollama":  "ollama run phi3:mini",
        # ── Valores empíricos ─────────────────────────────────────────────────
        "tokens_por_seg_base":   22.0,   # CPU i7/Ryzen 7, 8 GB RAM, Q4_K_M → ~20-25 t/s
        "peso_archivo_gb":        2.2,   # Q4_K_M, fuente: microsoft/Phi-3-mini-4k-instruct-gguf (HF)
        "contexto_max_k":           4,   # 4k nativo (phi3:mini); Ollama por defecto < 24 GB VRAM = 4k ctx
        "factor_aceleracion_gpu": 3.5,   # RTX 3060/4060: ~70-80 t/s vs ~22 t/s CPU → factor ≈ 3.5×
    },

    "gemma2-2b": {
        "nombre_display":  "Gemma 2 (2B)",
        "parametros_b":    2,
        "ram_min_gb":      4,            # archivo 1.6 GB; 4 GB RAM permite holgura de SO
        "vram_min_gb":     0,
        "requiere_gpu":    False,
        "casos_uso":       ["conversación", "educación", "código simple"],
        "descripcion":     "Modelo liviano de Google. Muy eficiente en CPU.",
        "ollama_tag":      "gemma2:2b",
        "comando_ollama":  "ollama run gemma2:2b",
        # ── Valores empíricos ─────────────────────────────────────────────────
        "tokens_por_seg_base":   28.0,   # CPU moderno, Q4_0 → más rápido que phi3 por menor tamaño
        "peso_archivo_gb":        1.6,   # fuente: ollama.com/library/gemma2 (tag gemma2:2b = 1.6 GB)
        "contexto_max_k":           8,   # gemma2 soporta 8k nativo; confirmado en ollama.com/library/gemma2
        "factor_aceleracion_gpu": 4.0,   # modelos < 2 GB caben completos en VRAM → aceleración máxima ~4×
    },

    "mistral-7b": {
        "nombre_display":  "Mistral 7B",
        "parametros_b":    7,
        "ram_min_gb":      8,            # Q4_K_M ocupa 4.4 GB; 8 GB RAM es el mínimo viable con SO
        "vram_min_gb":     6,            # 4.4 GB modelo + ~1 GB KV cache → 6 GB VRAM mínimo real
        "requiere_gpu":    False,        # corre en CPU, lento pero funcional
        "casos_uso":       ["código", "análisis", "conversación avanzada"],
        "descripcion":     "Modelo de referencia para uso general. Requiere hardware intermedio.",
        "ollama_tag":      "mistral",
        "comando_ollama":  "ollama run mistral",
        # ── Valores empíricos ─────────────────────────────────────────────────
        "tokens_por_seg_base":   9.0,    # CPU i7/Ryzen 7, Q4_K_M → 8-14 t/s (ai-ollama.github.io)
        "peso_archivo_gb":        4.4,   # Q4_K_M, fuente: ollama.com/library/mistral:7b (oficial)
        "contexto_max_k":          32,   # Mistral 7B v0.2 soporta 32k nativo; Ollama lo expone con < 24 GB VRAM como 4k por defecto
        "factor_aceleracion_gpu": 5.0,   # RTX 3060: ~40-55 t/s vs ~9 t/s CPU → factor ≈ 5× (ai-ollama.github.io)
    },

    "llama3-8b": {
        "nombre_display":  "Llama 3 (8B)",
        "parametros_b":    8,
        "ram_min_gb":      8,            # Q4_K_M ocupa 4.7 GB; 8 GB mínimo con SO incluido
        "vram_min_gb":     6,            # 4.7 GB modelo + ~1 GB KV cache → 6 GB VRAM mínimo
        "requiere_gpu":    False,
        "casos_uso":       ["código", "análisis", "razonamiento"],
        "descripcion":     "Modelo robusto de Meta. Buena relación calidad/requisitos.",
        "ollama_tag":      "llama3",
        "comando_ollama":  "ollama run llama3",
        # ── Valores empíricos ─────────────────────────────────────────────────
        "tokens_por_seg_base":   8.5,    # CPU moderno Q4_K_M → similar a Mistral 7B, ~8-12 t/s
        "peso_archivo_gb":        4.7,   # Q4_K_M, fuente: journal.hexmos.com + ollama library (4.7 GB)
        "contexto_max_k":           8,   # Llama 3 8B soporta 8k nativo en Ollama por defecto
        "factor_aceleracion_gpu": 5.5,   # RTX 3060/4060: ~40-60 t/s vs ~8.5 t/s CPU → factor ≈ 5.5×
    },

    "llama3-70b": {
        "nombre_display":  "Llama 3 (70B)",
        "parametros_b":    70,
        "ram_min_gb":      48,           # Q4_K_M pesa ~40 GB; mínimo 48 GB para cargar + SO + KV cache
        "vram_min_gb":     48,           # necesita GPU de 48 GB (L40S/A6000) para ejecución pura GPU
        "requiere_gpu":    True,
        "casos_uso":       ["código complejo", "razonamiento avanzado", "análisis profesional"],
        "descripcion":     "Modelo de alta capacidad. Requiere hardware de gama alta o servidor.",
        "ollama_tag":      "llama3:70b",
        "comando_ollama":  "ollama run llama3:70b",
        # ── Valores empíricos ─────────────────────────────────────────────────
        "tokens_por_seg_base":   1.5,    # CPU-only, 64 GB RAM, Q4_K_M → 1-2 t/s (dev.to/studiomeyer 2026)
        "peso_archivo_gb":       40.0,   # Q4_K_M, fuente: journal.hexmos.com (~39-40 GB confirmado)
        "contexto_max_k":           8,   # Llama 3 70B soporta 8k en Ollama con < 48 GB VRAM
        "factor_aceleracion_gpu": 10.0,  # L40S 48 GB: ~15 t/s vs ~1.5 t/s CPU → factor ≈ 10×
        # Nota: en RTX 3060/4060 (8-12 GB VRAM) este modelo no cabe → CPU offloading parcial,
        # rendimiento real ~2-3 t/s. El factor_aceleracion_gpu asume GPU con VRAM suficiente (≥ 48 GB).
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