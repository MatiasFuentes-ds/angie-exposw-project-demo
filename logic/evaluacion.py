# logic/evaluacion.py
# Decide la compatibilidad entre el hardware del usuario y cada modelo disponible.
# Retorna un semáforo (verde/amarillo/rojo) con un mensaje explicativo.
# Regla de diseño: solo lógica aquí, nunca datos de modelos. Los datos viven en data/modelos.py.

from data.modelos import get_todos_los_modelos

# ── Constantes de compatibilidad ──────────────────────────────────────────────

VERDE   = "verde"
AMARILLO = "amarillo"
ROJO    = "rojo"

EMOJI = {
    VERDE:    "🟢",
    AMARILLO: "🟡",
    ROJO:     "🔴",
}

# Umbral: si la RAM disponible cubre al menos este factor del mínimo requerido,
# se considera holgado. Ej: 1.5 → necesita 1.5× la RAM mínima para ser verde.
FACTOR_RAM_HOLGADO = 1.5


# ── Tipo de retorno ───────────────────────────────────────────────────────────

def _resultado(nivel: str, mensaje: str) -> dict:
    return {
        "nivel": nivel, 
        "emoji": EMOJI[nivel],
        "mensaje": mensaje,
    }


# ── Función principal de evaluación individual ────────────────────────────────

def evaluar_modelo(modelo: dict, specs: dict) -> dict:
    """
    Evalúa la compatibilidad de un modelo con el hardware del usuario.

    Parámetros
    ----------
    modelo : dict
        Un modelo tal como está definido en data/modelos.py.
    specs : dict
        Hardware del usuario con las claves:
            - ram_gb       (int)  : RAM total del sistema en GB
            - tiene_gpu    (bool) : si tiene GPU dedicada
            - vram_gb      (int)  : VRAM de la GPU en GB (0 si no tiene)
            - uso_deseado  (str)  : e.g. "conversación", "código", "análisis"

    Retorna
    -------
    dict con claves: nivel, emoji, mensaje
    """
    ram_usuario    = specs.get("ram_gb", 0)
    tiene_gpu      = specs.get("tiene_gpu", False)
    vram_usuario   = specs.get("vram_gb", 0)
    uso_deseado    = specs.get("uso_deseado", "")

    ram_requerida  = modelo["ram_min_gb"]
    vram_requerida = modelo["vram_min_gb"]
    requiere_gpu   = modelo["requiere_gpu"]
    casos_uso      = modelo["casos_uso"]

    # ── Rojo: no puede correr de ninguna manera ───────────────────────────────
    if ram_usuario < ram_requerida:
        falta = ram_requerida - ram_usuario
        return _resultado(
            ROJO,
            f"RAM insuficiente: necesita {ram_requerida} GB, tienes {ram_usuario} GB "
            f"(faltan {falta} GB).",
        )

    if requiere_gpu and not tiene_gpu:
        return _resultado(
            ROJO,
            f"Este modelo requiere GPU dedicada con al menos {vram_requerida} GB de VRAM.",
        )

    if requiere_gpu and vram_usuario < vram_requerida:
        falta = vram_requerida - vram_usuario
        return _resultado(
            ROJO,
            f"VRAM insuficiente: necesita {vram_requerida} GB, tienes {vram_usuario} GB "
            f"(faltan {falta} GB).",
        )

    # ── Verde: corre con holgura ──────────────────────────────────────────────
    ram_holgada = ram_usuario >= ram_requerida * FACTOR_RAM_HOLGADO
    gpu_holgada = (not vram_requerida) or (tiene_gpu and vram_usuario >= vram_requerida * FACTOR_RAM_HOLGADO)

    if ram_holgada and gpu_holgada:
        if uso_deseado and uso_deseado in casos_uso:
            return _resultado(
                VERDE,
                f"Compatible y optimizado para '{uso_deseado}'. Tu equipo lo maneja con holgura.",
            )
        return _resultado(
            VERDE,
            "Compatible. Tu equipo tiene recursos suficientes para correr este modelo con buen rendimiento.",
        )

    # ── Amarillo: puede correr pero al límite ─────────────────────────────────
    if uso_deseado and uso_deseado not in casos_uso:
        return _resultado(
            AMARILLO,
            f"Compatible técnicamente, pero este modelo no está optimizado para '{uso_deseado}'. "
            f"Casos de uso ideales: {', '.join(casos_uso)}.",
        )

    return _resultado(
        AMARILLO,
        f"Compatible pero ajustado: tienes {ram_usuario} GB de RAM y el modelo requiere {ram_requerida} GB. "
        "El rendimiento puede ser lento.",
    )


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
    modelos = get_todos_los_modelos()
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
    perfiles = {
        "Equipo débil  ": {"ram_gb": 4,  "tiene_gpu": False, "vram_gb": 0,  "uso_deseado": "conversación"},
        "Equipo medio  ": {"ram_gb": 16, "tiene_gpu": True,  "vram_gb": 6,  "uso_deseado": "código"},
        "Equipo potente": {"ram_gb": 64, "tiene_gpu": True,  "vram_gb": 48, "uso_deseado": "análisis"},
    }

    for nombre_perfil, specs in perfiles.items():
        print(f"\n{'='*60}")
        print(f"  Perfil: {nombre_perfil} | {specs}")
        print(f"{'='*60}")
        for r in evaluar_todos(specs):
            print(f"  {r['emoji']}  {r['nombre']:<25} → {r['mensaje']}")