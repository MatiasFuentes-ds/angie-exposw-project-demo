# logic/evaluacion.py
# Decide la compatibilidad entre el hardware del usuario y cada modelo disponible.
# Retorna un semáforo (verde/amarillo/rojo) con un mensaje explicativo.
# Regla de diseño: solo lógica aquí, nunca datos de modelos. Los datos viven en data/modelos.py.
# El color del semáforo es dictado 100% por capacidad física de hardware.
# Los casos de uso solo agregan advertencias informativas, nunca degradan el nivel.

from data.modelos import get_todos_los_modelos


# ── Constantes de compatibilidad ──────────────────────────────────────────────

VERDE    = "verde"
AMARILLO = "amarillo"
ROJO     = "rojo"

EMOJI = {
    VERDE:    "🟢",
    AMARILLO: "🟡",
    ROJO:     "🔴",
}

# Overhead del SO + procesos base antes de cargar el modelo (GB).
# Debe mantenerse en paridad con simulacion.py.
OVERHEAD_SO_GB = 2.5

# Overhead de KV Cache por cada 1k de tokens de contexto (GB).
# Estimación: ~0.1 GB/1k tokens para modelos 7B-8B en Q4.
# Debe mantenerse en paridad con simulacion.py.
OVERHEAD_KV_CACHE_POR_1K_GB = 0.1

# Factor de holgura de RAM: necesita al menos 20% más de la RAM requerida real para ser VERDE.
FACTOR_HOLGURA_RAM = 1.2

# Holgura de VRAM discreta: 1 GB extra sobre el mínimo requerido para ser VERDE.
HOLGURA_VRAM_DISCRETA_GB = 1


# ── Tipo de retorno ───────────────────────────────────────────────────────────

def _resultado(nivel: str, mensaje: str) -> dict:
    return {
        "nivel":  nivel,
        "emoji":  EMOJI[nivel],
        "mensaje": mensaje,
    }


# ── Helper: cálculo de RAM requerida real ─────────────────────────────────────

def _ram_requerida_real(modelo: dict) -> float:
    """
    Calcula el requisito de RAM físico real del modelo, incluyendo:
        - Peso del archivo cuantizado (peso_archivo_gb)
        - Overhead del sistema operativo (OVERHEAD_SO_GB)
        - Overhead del KV Cache según la ventana de contexto (contexto_max_k)

    Fórmula:
        ram_real = peso_archivo_gb + OVERHEAD_SO_GB + (contexto_max_k * OVERHEAD_KV_CACHE_POR_1K_GB)

    Esta función reemplaza el uso estático de modelo["ram_min_gb"] para la evaluación,
    alineando la lógica con la RAM que el motor de simulación realmente usa.
    """
    return (
        modelo["peso_archivo_gb"]
        + OVERHEAD_SO_GB
        + modelo["contexto_max_k"] * OVERHEAD_KV_CACHE_POR_1K_GB
    )


# ── Helper: detección de arquitectura Apple Silicon ───────────────────────────

def _es_apple_silicon(specs: dict) -> bool:
    """
    Detecta si el equipo usa arquitectura de Memoria Unificada (Apple M-series).
    """
    return specs.get("sistema_operativo", "") == "macOS (Apple Silicon / M-Series)"

# ── Función principal de evaluación individual ────────────────────────────────

def evaluar_modelo(modelo: dict, specs: dict) -> dict:
    """
    Evalúa la compatibilidad física de un modelo con el hardware del usuario.

    El semáforo está determinado 100% por la capacidad física del hardware.
    Los casos de uso son informativos y solo agregan una advertencia al mensaje
    sin alterar el nivel (VERDE sigue siendo VERDE aunque el uso no coincida).

    Parámetros
    ----------
    modelo : dict
        Un modelo tal como está definido en data/modelos.py.
    specs : dict
        Hardware del usuario con las claves:
            - ram_gb            (int)  : RAM total del sistema en GB
            - tiene_gpu         (bool) : si tiene GPU dedicada discreta
            - vram_gb           (int)  : VRAM de la GPU en GB (0 si no tiene)
            - uso_deseado       (str)  : e.g. "conversación", "código", "análisis"
            - sistema_operativo (str)  : "Windows" | "macOS" | "Linux"

    Retorna
    -------
    dict con claves: nivel, emoji, mensaje
    """
    ram_usuario    = specs.get("ram_gb", 0)
    tiene_gpu      = specs.get("tiene_gpu", False)
    vram_usuario   = specs.get("vram_gb", 0)
    uso_deseado    = specs.get("uso_deseado", "")
    apple_silicon  = _es_apple_silicon(specs)

    vram_requerida = modelo["vram_min_gb"]
    requiere_gpu   = modelo["requiere_gpu"]
    casos_uso      = modelo["casos_uso"]

    # RAM requerida real: basada en peso físico + overheads, no en ram_min_gb estático
    ram_real = _ram_requerida_real(modelo)

    # ── Advertencia informativa de caso de uso (no altera el nivel) ───────────
    advertencia_uso = ""
    if uso_deseado and uso_deseado not in casos_uso:
        advertencia_uso = (
            f" (Nota: Este modelo no está especializado para '{uso_deseado}'. "
            f"Casos de uso ideales: {', '.join(casos_uso)}.)"
        )

    # ── ROJO: bloqueos físicos absolutos ─────────────────────────────────────

    # 1. RAM insuficiente para cargar el modelo con sus overheads reales
    if ram_usuario < ram_real:
        falta = round(ram_real - ram_usuario, 1)
        return _resultado(
            ROJO,
            f"RAM insuficiente: se necesitan ~{ram_real:.1f} GB reales "
            f"(archivo + SO + KV Cache), tienes {ram_usuario} GB (faltan {falta} GB).",
        )

    # 2. Requiere GPU discreta y el equipo no tiene (solo aplica fuera de Apple Silicon)
    if requiere_gpu and not apple_silicon and not tiene_gpu:
        return _resultado(
            ROJO,
            f"Este modelo requiere GPU dedicada con al menos {vram_requerida} GB de VRAM.",
        )

    # 3. Tiene GPU discreta pero VRAM insuficiente (solo aplica fuera de Apple Silicon)
    if requiere_gpu and not apple_silicon and tiene_gpu and vram_usuario < vram_requerida:
        falta = vram_requerida - vram_usuario
        return _resultado(
            ROJO,
            f"VRAM insuficiente: necesita {vram_requerida} GB, tienes {vram_usuario} GB "
            f"(faltan {falta} GB).",
        )

    # 4. Apple Silicon: la RAM actúa como VRAM — verificar que la RAM cubre la VRAM requerida
    if requiere_gpu and apple_silicon and ram_usuario < vram_requerida:
        falta = vram_requerida - ram_usuario
        return _resultado(
            ROJO,
            f"Memoria unificada insuficiente: este modelo necesita al menos "
            f"{vram_requerida} GB de memoria (actúa como VRAM en Apple Silicon), "
            f"tienes {ram_usuario} GB (faltan {falta} GB).",
        )

    # ── VERDE: holgura suficiente en todos los recursos ───────────────────────

    ram_holgada = ram_usuario >= ram_real * FACTOR_HOLGURA_RAM

    if apple_silicon:
        # En memoria unificada, la holgura de "GPU" se evalúa igual que la RAM
        gpu_holgada = ram_usuario >= ram_real * FACTOR_HOLGURA_RAM
    else:
        # GPU discreta: holgura si tiene 1 GB extra sobre el mínimo requerido
        gpu_holgada = (
            not vram_requerida
            or (tiene_gpu and vram_usuario >= vram_requerida + HOLGURA_VRAM_DISCRETA_GB)
        )

    if ram_holgada and gpu_holgada:
        if apple_silicon:
            base_msg = (
                f"Compatible con holgura en Apple Silicon "
                f"(memoria unificada: {ram_usuario} GB actúan como RAM+VRAM)."
            )
        elif tiene_gpu and vram_requerida:
            base_msg = (
                f"Compatible con holgura. RAM: {ram_usuario} GB "
                f"(necesita ~{ram_real:.1f} GB) · VRAM: {vram_usuario} GB "
                f"(mínimo: {vram_requerida} GB)."
            )
        else:
            base_msg = (
                f"Compatible con holgura. RAM: {ram_usuario} GB "
                f"(necesita ~{ram_real:.1f} GB). Corre bien en CPU."
            )
        return _resultado(VERDE, base_msg + advertencia_uso)

    # ── AMARILLO: aprueba los mínimos pero sin holgura ────────────────────────

    if apple_silicon:
        base_msg = (
            f"Compatible al límite en Apple Silicon: {ram_usuario} GB de memoria unificada "
            f"cubren los {ram_real:.1f} GB requeridos, pero con margen ajustado."
        )
    elif not ram_holgada and tiene_gpu and gpu_holgada:
        base_msg = (
            f"RAM ajustada: tienes {ram_usuario} GB y se necesitan ~{ram_real:.1f} GB. "
            "La VRAM es suficiente, pero el sistema puede ir lento por presión de RAM."
        )
    elif ram_holgada and not gpu_holgada and vram_requerida:
        base_msg = (
            f"RAM suficiente, pero VRAM ajustada: tienes {vram_usuario} GB "
            f"y el modelo requiere {vram_requerida} GB (se recomiendan "
            f"{vram_requerida + HOLGURA_VRAM_DISCRETA_GB} GB para holgura)."
        )
    else:
        base_msg = (
            f"Compatible al límite: RAM {ram_usuario} GB / ~{ram_real:.1f} GB requeridos. "
            "El rendimiento puede verse afectado bajo carga sostenida."
        )

    return _resultado(AMARILLO, base_msg + advertencia_uso)


# ── Evaluación de todos los modelos ──────────────────────────────────────────

# Orden de prioridad para ordenar resultados de mejor a peor
_ORDEN_NIVEL = {VERDE: 0, AMARILLO: 1, ROJO: 2}


def evaluar_todos(specs: dict) -> list[dict]:
    """
    Evalúa todos los modelos disponibles contra las specs del usuario.

    Retorna
    -------
    Lista de dicts ordenada de mejor a peor compatibilidad, donde cada item es:
        {
            "id":           str,   # clave del modelo en MODELOS
            "nombre":       str,   # nombre para mostrar en la UI
            "nivel":        str,   # "verde" | "amarillo" | "rojo"
            "emoji":        str,   # 🟢 | 🟡 | 🔴
            "mensaje":      str,   # explicación legible
            "casos_uso":    list,  # lista de usos del modelo
            "parametros_b": float, # tamaño del modelo en miles de millones
        }
    """
    modelos    = get_todos_los_modelos()
    resultados = []

    for modelo_id, modelo_data in modelos.items():
        evaluacion = evaluar_modelo(modelo_data, specs)
        resultados.append({
            "id":           modelo_id,
            "nombre":       modelo_data["nombre_display"],
            "casos_uso":    modelo_data["casos_uso"],
            "parametros_b": modelo_data["parametros_b"],
            **evaluacion,
        })

    resultados.sort(key=lambda r: _ORDEN_NIVEL[r["nivel"]])
    return resultados


# ── Bloque de prueba (ejecutar directamente: python logic/evaluacion.py) ──────

if __name__ == "__main__":
    # Los mismos 5 perfiles de simulacion.py para verificar paridad uno a uno
    perfiles = {
        "Equipo débil (Windows)    ": {
            "ram_gb": 4,  "tiene_gpu": False, "vram_gb": 0,
            "uso_deseado": "conversación", "sistema_operativo": "Windows",
        },
        "Equipo medio (Linux)      ": {
            "ram_gb": 16, "tiene_gpu": True,  "vram_gb": 8,
            "uso_deseado": "código",       "sistema_operativo": "Linux",
        },
        "MacBook Pro M2 (16 GB)    ": {
            "ram_gb": 16, "tiene_gpu": False, "vram_gb": 0,
            "uso_deseado": "análisis",     "sistema_operativo": "macOS",
        },
        "MacBook Pro M3 Max (36 GB)": {
            "ram_gb": 36, "tiene_gpu": False, "vram_gb": 0,
            "uso_deseado": "código complejo", "sistema_operativo": "macOS",
        },
        "Equipo potente (Windows)  ": {
            "ram_gb": 64, "tiene_gpu": True,  "vram_gb": 48,
            "uso_deseado": "análisis",     "sistema_operativo": "Windows",
        },
    }

    for nombre_perfil, specs in perfiles.items():
        so  = specs["sistema_operativo"]
        ram = specs["ram_gb"]
        gpu = (f"Apple Silicon ({ram} GB unificada)" if so == "macOS"
               else f"GPU: {specs['tiene_gpu']} ({specs['vram_gb']} GB VRAM)")
        print(f"\n{'='*75}")
        print(f"  Perfil: {nombre_perfil} | RAM: {ram} GB | {gpu}")
        print(f"{'='*75}")
        for r in evaluar_todos(specs):
            print(f"  {r['emoji']}  {r['nombre']:<25} → {r['mensaje']}")