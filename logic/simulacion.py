# logic/simulacion.py
# Genera las métricas de rendimiento estimado para un modelo en el hardware del usuario.
# Todas las fórmulas son heurísticas documentadas — ningún número es arbitrario.
# Regla de diseño: función pura que recibe specs + modelo, retorna resultados. Sin efectos secundarios.

from data.modelos import get_modelo
from logic.evaluacion import evaluar_modelo, VERDE, AMARILLO, ROJO


# ── Constantes del modelo de simulación ───────────────────────────────────────

# Factor de penalización de velocidad cuando el modelo corre solo en CPU.
# Benchmarks reales de Ollama muestran ~4-6× más lento en CPU vs GPU dedicada.
FACTOR_PENALIZACION_CPU = 0.22

# La RAM del sistema operativo + procesos base ocupa aprox. un 20-25% antes de cargar el modelo.
OVERHEAD_SO_GB = 2.5

# Temperatura base de CPU bajo carga sostenida de inferencia (°C).
TEMP_BASE_CPU = 62

# Temperatura base de GPU bajo inferencia (°C).
TEMP_BASE_GPU = 58

# Umbral de uso de RAM para considerar que el sistema está "al límite" (%).
UMBRAL_RAM_CRITICA = 85


# ── Funciones de cálculo ──────────────────────────────────────────────────────

def _calcular_tokens_por_segundo(modelo: dict, specs: dict) -> float:
    """
    Estima tokens/seg basándose en:
    - La velocidad base del modelo (calibrada para un equipo con 16 GB RAM, sin GPU).
    - Un factor de escala según la RAM disponible: más RAM → menos swapping → más velocidad.
    - Si tiene GPU con VRAM suficiente, se aplica un boost multiplicativo.

    Fórmula:
        factor_ram = min(ram_usuario / (ram_requerida * 1.5), 1.5)
        tps = base * factor_ram  [sin GPU]
        tps = base * factor_ram / FACTOR_PENALIZACION_CPU  [con GPU suficiente]
    """
    base = modelo["tokens_por_seg_base"]
    ram_usuario   = specs.get("ram_gb", 8)
    ram_requerida = modelo["ram_min_gb"]
    tiene_gpu     = specs.get("tiene_gpu", False)
    vram_usuario  = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]

    factor_ram = min(ram_usuario / max(ram_requerida * 1.5, 1), 1.5)
    tps = base * factor_ram

    if tiene_gpu and vram_requerida > 0 and vram_usuario >= vram_requerida:
        tps = tps / FACTOR_PENALIZACION_CPU

    return round(min(tps, base * 3.0), 1)  # techo: 3× la base para no exagerar


def _calcular_uso_ram_pct(modelo: dict, specs: dict) -> float:
    """
    Estima el porcentaje de RAM del sistema que consumirá el modelo.

    Fórmula:
        ram_consumida = ram_requerida_modelo + OVERHEAD_SO
        uso_pct = (ram_consumida / ram_total) * 100

    El overhead del SO representa los ~2.5 GB que consume el sistema operativo
    y procesos base antes de cargar el modelo.
    """
    ram_usuario   = specs.get("ram_gb", 8)
    ram_requerida = modelo["ram_min_gb"]

    ram_consumida = ram_requerida + OVERHEAD_SO_GB
    uso_pct = (ram_consumida / ram_usuario) * 100
    return round(min(uso_pct, 100.0), 1)


def _calcular_uso_cpu_pct(modelo: dict, specs: dict) -> float:
    """
    Estima el uso de CPU durante la inferencia.

    Lógica:
    - Sin GPU: el modelo corre enteramente en CPU → uso alto (55-95% según presión de RAM).
    - Con GPU suficiente: la GPU asume la mayor parte → CPU solo coordina (~20-35%).
    - La presión de RAM (uso_ram_pct) amplifica el trabajo del CPU por swapping.

    Fórmula base:
        uso_cpu_sin_gpu = 60 + (uso_ram_pct / 100) * 35   → rango 60-95%
        uso_cpu_con_gpu = 20 + (uso_ram_pct / 100) * 15   → rango 20-35%
    """
    tiene_gpu     = specs.get("tiene_gpu", False)
    vram_usuario  = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]
    uso_ram = _calcular_uso_ram_pct(modelo, specs)

    gpu_activa = tiene_gpu and vram_requerida > 0 and vram_usuario >= vram_requerida

    if gpu_activa:
        uso_cpu = 20 + (uso_ram / 100) * 15
    else:
        uso_cpu = 60 + (uso_ram / 100) * 35

    return round(min(uso_cpu, 100.0), 1)


def _calcular_tiempo_carga_seg(modelo: dict, specs: dict) -> float:
    """
    Estima los segundos que tarda el modelo en cargar en memoria antes de la primera respuesta.

    Lógica:
    - El tiempo de carga escala con el tamaño del modelo (parámetros_b).
    - Se reduce proporcionalmente si hay RAM holgada (menos fragmentación).
    - Con GPU activa, la carga es significativamente más rápida.

    Fórmula:
        t_base = parametros_b * 1.8  (segundos por cada 1B de parámetros en CPU medio)
        factor_ram = max(ram_requerida / ram_usuario, 0.5)  (penaliza RAM ajustada)
        t_final = t_base * factor_ram   [CPU]
        t_final = t_base * factor_ram * 0.35  [GPU]
    """
    parametros  = modelo["parametros_b"]
    ram_usuario  = specs.get("ram_gb", 8)
    ram_requerida = modelo["ram_min_gb"]
    tiene_gpu    = specs.get("tiene_gpu", False)
    vram_usuario = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]

    t_base = parametros * 1.8
    factor_ram = max(ram_requerida / ram_usuario, 0.5)
    t_carga = t_base * factor_ram

    gpu_activa = tiene_gpu and vram_requerida > 0 and vram_usuario >= vram_requerida
    if gpu_activa:
        t_carga *= 0.35

    return round(max(t_carga, 1.0), 1)  # mínimo 1 segundo


def _calcular_temperatura_c(modelo: dict, specs: dict) -> float:
    """
    Estima la temperatura aproximada del componente principal durante inferencia sostenida.

    Lógica:
    - Sin GPU: reporta temperatura de CPU. Sube con el porcentaje de uso de CPU.
    - Con GPU activa: reporta temperatura de GPU. Sube con el uso de VRAM.

    Fórmula:
        uso_cpu_pct = _calcular_uso_cpu_pct(...)
        temp_cpu = TEMP_BASE + (uso_cpu_pct / 100) * 28   → rango ~62-90°C
        temp_gpu = TEMP_BASE_GPU + (vram_usada / vram_total) * 30  → rango ~58-88°C
    """
    tiene_gpu     = specs.get("tiene_gpu", False)
    vram_usuario  = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]
    gpu_activa = tiene_gpu and vram_requerida > 0 and vram_usuario >= vram_requerida

    if gpu_activa:
        uso_vram_ratio = min(vram_requerida / vram_usuario, 1.0)
        temp = TEMP_BASE_GPU + uso_vram_ratio * 30
    else:
        uso_cpu = _calcular_uso_cpu_pct(modelo, specs)
        temp = TEMP_BASE_CPU + (uso_cpu / 100) * 28

    return round(min(temp, 95.0), 1)


def _generar_veredicto(uso_ram: float, tps: float, nivel_evaluacion: str) -> dict:
    """
    Genera el texto de veredicto reutilizando el nivel del semáforo de evaluacion.py
    para mantener consistencia entre el semáforo inicial y la simulación detallada.

    Retorna dict con: titulo, descripcion, color_streamlit
    """
    if nivel_evaluacion == ROJO:
        return {
            "titulo": "⛔ No recomendado",
            "descripcion": "Tu equipo no cumple los requisitos mínimos. El modelo podría no iniciar o bloquearse.",
            "color": "error",
        }

    if nivel_evaluacion == AMARILLO or uso_ram >= UMBRAL_RAM_CRITICA:
        return {
            "titulo": "⚠️ Funciona al límite",
            "descripcion": (
                f"El modelo arrancará, pero con {uso_ram}% de uso de RAM y ~{tps} tok/s "
                "el equipo estará bajo presión. No apto para uso continuo prolongado."
            ),
            "color": "warning",
        }

    return {
        "titulo": "✅ Funciona bien",
        "descripcion": (
            f"Tu equipo puede correr este modelo con comodidad (~{tps} tok/s). "
            "Uso de recursos dentro de rangos normales."
        ),
        "color": "success",
    }


# ── Función principal pública ─────────────────────────────────────────────────

def simular(modelo_id: str, specs: dict) -> dict:
    """
    Genera el reporte completo de simulación para un modelo y unas specs de hardware.

    Parámetros
    ----------
    modelo_id : str
        Clave del modelo tal como está definida en data/modelos.py.
    specs : dict
        Hardware del usuario. Mismas claves que en evaluacion.py:
            - ram_gb       (int)
            - tiene_gpu    (bool)
            - vram_gb      (int)
            - uso_deseado  (str)

    Retorna
    -------
    dict con las métricas listas para renderizar en app.py:
        {
            "tokens_por_segundo": float,   # velocidad de generación estimada
            "uso_ram_pct":        float,   # % de RAM del sistema en uso
            "uso_cpu_pct":        float,   # % de CPU durante inferencia
            "tiempo_carga_seg":   float,   # segundos hasta primera respuesta
            "temperatura_c":      float,   # °C del componente principal
            "modo_ejecucion":     str,     # "GPU" | "CPU"
            "veredicto":          dict,    # {titulo, descripcion, color}
        }
    """
    modelo = get_modelo(modelo_id)
    evaluacion = evaluar_modelo(modelo, specs)

    tiene_gpu     = specs.get("tiene_gpu", False)
    vram_usuario  = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]
    gpu_activa = tiene_gpu and vram_requerida > 0 and vram_usuario >= vram_requerida

    tps       = _calcular_tokens_por_segundo(modelo, specs)
    uso_ram   = _calcular_uso_ram_pct(modelo, specs)
    uso_cpu   = _calcular_uso_cpu_pct(modelo, specs)
    t_carga   = _calcular_tiempo_carga_seg(modelo, specs)
    temp      = _calcular_temperatura_c(modelo, specs)
    veredicto = _generar_veredicto(uso_ram, tps, evaluacion["nivel"])

    return {
        "tokens_por_segundo": tps,
        "uso_ram_pct":        uso_ram,
        "uso_cpu_pct":        uso_cpu,
        "tiempo_carga_seg":   t_carga,
        "temperatura_c":      temp,
        "modo_ejecucion":     "GPU 🎮" if gpu_activa else "CPU 🖥️",
        "veredicto":          veredicto,
    }


# ── Bloque de prueba (ejecutar: python logic/simulacion.py) ───────────────────

if __name__ == "__main__":
    perfiles = {
        "Equipo débil  ": {"ram_gb": 4,  "tiene_gpu": False, "vram_gb": 0,  "uso_deseado": "conversación"},
        "Equipo medio  ": {"ram_gb": 16, "tiene_gpu": True,  "vram_gb": 6,  "uso_deseado": "código"},
        "Equipo potente": {"ram_gb": 64, "tiene_gpu": True,  "vram_gb": 48, "uso_deseado": "análisis"},
    }
    modelos_prueba = ["phi3-mini", "mistral-7b", "llama3-70b"]

    for nombre_perfil, specs in perfiles.items():
        print(f"\n{'='*65}")
        print(f"  Perfil: {nombre_perfil} | RAM {specs['ram_gb']}GB | GPU: {specs['tiene_gpu']} ({specs['vram_gb']}GB VRAM)")
        print(f"{'='*65}")
        for modelo_id in modelos_prueba:
            try:
                r = simular(modelo_id, specs)
                print(
                    f"  {modelo_id:<15} | {r['modo_ejecucion']:<10} | "
                    f"{r['tokens_por_segundo']:>6.1f} tok/s | "
                    f"RAM {r['uso_ram_pct']:>5.1f}% | "
                    f"CPU {r['uso_cpu_pct']:>5.1f}% | "
                    f"Carga {r['tiempo_carga_seg']:>5.1f}s | "
                    f"{r['temperatura_c']:>4.0f}°C | "
                    f"{r['veredicto']['titulo']}"
                )
            except KeyError as e:
                print(f"  {modelo_id:<15} | ERROR: {e}")