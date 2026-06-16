# logic/simulacion.py
# Genera las métricas de rendimiento estimado para un modelo en el hardware del usuario.
# Todas las fórmulas son heurísticas documentadas — ningún número es arbitrario.
# Regla de diseño: función pura que recibe specs + modelo, retorna resultados. Sin efectos secundarios.

from data.modelos import get_modelo
from logic.evaluacion import evaluar_modelo, VERDE, AMARILLO, ROJO


# ── Constantes del modelo de simulación ───────────────────────────────────────

# Overhead del SO + procesos base antes de cargar el modelo (GB).
OVERHEAD_SO_GB = 2.5

# Overhead de KV Cache por cada 1k de tokens de contexto (GB).
# Estimación: ~0.1 GB/1k tokens para modelos 7B-8B en Q4; escala con el tamaño del modelo.
OVERHEAD_KV_CACHE_POR_1K_GB = 0.1

# Ancho de banda de disco asumido: SSD NVMe estándar (GB/s).
# Fuente: Samsung 970 Evo / WD Black SN770 → ~2.5 GB/s lectura secuencial.
ANCHO_BANDA_DISCO_GB_S = 2.5

# Factor de penalización por swapping: si la RAM está al límite, el sistema
# pagina al disco y la carga se ralentiza drásticamente.
FACTOR_SWAP_PENALIZACION = 3.5

# Umbral de uso de RAM a partir del cual se activa el swapping (%).
UMBRAL_RAM_SWAP = 88

# Temperatura base de CPU bajo carga sostenida de inferencia (°C).
TEMP_BASE_CPU = 62

# Temperatura base de GPU / Neural Engine bajo inferencia (°C).
TEMP_BASE_GPU = 58

# Temperatura base de Apple Silicon bajo carga (°C). Menor que GPU discreta
# por el diseño de TDP del SoC en sistemas M-series.
TEMP_BASE_APPLE_SILICON = 52

# Umbral de uso de RAM para considerar que el sistema está "al límite" (%).
UMBRAL_RAM_CRITICA = 85


# ── Helper: detección de paradigma de ejecución ───────────────────────────────

def _detectar_modo_gpu(modelo: dict, specs: dict) -> tuple[bool, bool]:
    """
    Determina si hay aceleración GPU activa y si es memoria unificada (Apple Silicon).

    Retorna
    -------
    (gpu_activa: bool, es_apple_silicon: bool)

    Lógica de memoria unificada:
        En macOS (Apple M-series), la RAM del sistema ES la VRAM.
        No se necesita GPU discreta: si ram_gb >= vram_min_gb del modelo,
        se considera que el Neural Engine / GPU integrada puede acelerar la inferencia.
    """
    so = specs.get("sistema_operativo", "")
    ram_usuario  = specs.get("ram_gb", 0)
    tiene_gpu    = specs.get("tiene_gpu", False)
    vram_usuario = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]

    es_apple_silicon = (so == "macOS")

    if es_apple_silicon:
        # Memoria unificada: la RAM actúa como VRAM
        gpu_activa = ram_usuario >= vram_requerida
    else:
        # GPU discreta tradicional
        gpu_activa = tiene_gpu and vram_usuario >= vram_requerida

    return gpu_activa, es_apple_silicon


# ── Funciones de cálculo ──────────────────────────────────────────────────────

def _calcular_tokens_por_segundo(modelo: dict, specs: dict) -> float:
    """
    Estima tokens/seg usando el factor_aceleracion_gpu empírico del modelo.

    Fórmula:
        CPU puro:
            factor_ram = min(ram_usuario / (ram_min * 1.5), 1.5)
            tps = tokens_por_seg_base * factor_ram

        Con GPU activa (discreta o Apple Silicon):
            tps = tokens_por_seg_base * factor_aceleracion_gpu

        Apple Silicon aplica el mismo factor_aceleracion_gpu porque el Neural Engine
        de los chips M-series tiene rendimiento comparable a una GPU de consumo medio
        (RTX 3060/4060) para cargas de inferencia Q4.

    No se usa un FACTOR_PENALIZACION_CPU global: la velocidad GPU se deriva
    directamente del multiplicador empírico registrado por modelo.
    """
    base              = modelo["tokens_por_seg_base"]
    factor_gpu        = modelo["factor_aceleracion_gpu"]
    ram_usuario       = specs.get("ram_gb", 8)
    ram_requerida     = modelo["ram_min_gb"]

    gpu_activa, _ = _detectar_modo_gpu(modelo, specs)

    if gpu_activa:
        tps = base * factor_gpu
    else:
        factor_ram = min(ram_usuario / max(ram_requerida * 1.5, 1), 1.5)
        tps = base * factor_ram

    return round(tps, 1)


def _calcular_uso_ram_pct(modelo: dict, specs: dict) -> float:
    """
    Estima el porcentaje de RAM del sistema que consumirá el modelo,
    incluyendo el overhead dinámico del KV Cache según la ventana de contexto.

    Fórmula:
        ram_modelo_gb   = peso_archivo_gb                    (peso real del archivo cuantizado)
        overhead_so_gb  = OVERHEAD_SO_GB                     (~2.5 GB para OS + procesos base)
        overhead_kv_gb  = contexto_max_k * 0.1               (0.1 GB por cada 1k tokens de contexto)
        ram_consumida   = ram_modelo_gb + overhead_so_gb + overhead_kv_gb
        uso_pct         = (ram_consumida / ram_total) * 100

    Usar peso_archivo_gb en vez de ram_min_gb es más preciso:
    refleja el footprint real del archivo .gguf en memoria, no el requisito mínimo
    declarado por el fabricante (que puede subestimar el consumo real).
    """
    ram_usuario    = specs.get("ram_gb", 8)
    peso_gb        = modelo["peso_archivo_gb"]
    contexto_k     = modelo["contexto_max_k"]

    overhead_kv_gb = contexto_k * OVERHEAD_KV_CACHE_POR_1K_GB
    ram_consumida  = peso_gb + OVERHEAD_SO_GB + overhead_kv_gb

    uso_pct = (ram_consumida / ram_usuario) * 100
    return round(min(uso_pct, 100.0), 1)


def _calcular_uso_cpu_pct(modelo: dict, specs: dict) -> float:
    """
    Estima el uso de CPU durante la inferencia.

    Lógica:
        - CPU puro: todo el cómputo cae en el procesador → uso alto (60-95%).
        - GPU discreta activa: CPU solo coordina → uso bajo (20-35%).
        - Apple Silicon: el Neural Engine asume la inferencia, CPU libre → uso bajo (15-25%).
          Los chips M-series separan el Neural Engine del CPU, por eso el uso es menor
          incluso que con una GPU discreta convencional.

    Fórmula:
        uso_sin_gpu       = 60 + (uso_ram_pct / 100) * 35  → rango 60-95%
        uso_con_gpu       = 20 + (uso_ram_pct / 100) * 15  → rango 20-35%
        uso_apple_silicon = 15 + (uso_ram_pct / 100) * 10  → rango 15-25%
    """
    uso_ram = _calcular_uso_ram_pct(modelo, specs)
    gpu_activa, es_apple_silicon = _detectar_modo_gpu(modelo, specs)

    if es_apple_silicon and gpu_activa:
        uso_cpu = 15 + (uso_ram / 100) * 10
    elif gpu_activa:
        uso_cpu = 20 + (uso_ram / 100) * 15
    else:
        uso_cpu = 60 + (uso_ram / 100) * 35

    return round(min(uso_cpu, 100.0), 1)


def _calcular_tiempo_carga_seg(modelo: dict, specs: dict) -> float:
    """
    Estima los segundos para cargar el modelo en memoria antes de la primera respuesta.
    El cálculo está anclado al peso físico del archivo, no a la cantidad de parámetros.

    Fórmula base (SSD NVMe, lectura secuencial):
        t_base = peso_archivo_gb / ANCHO_BANDA_DISCO_GB_S
               = peso_archivo_gb / 2.5   (GB/s de un NVMe estándar)

    Penalización por swapping:
        Si uso_ram_pct >= UMBRAL_RAM_SWAP, el sistema está paginando a disco.
        La carga se multiplica por FACTOR_SWAP_PENALIZACION (3.5×) porque el
        sistema operativo intercala lecturas del modelo con escrituras de swap,
        degradando el ancho de banda efectivo de disco severamente.

    Apple Silicon:
        El controlador de memoria unificada tiene mayor ancho de banda interno
        (~100 GB/s en M2/M3 vs ~3.5 GB/s de un NVMe externo), pero el modelo
        igual se lee del disco SSD antes de cargarse en memoria.
        Se aplica un factor 0.8× (10-20% más rápido) por el controlador de I/O
        integrado en el SoC.
    """
    peso_gb       = modelo["peso_archivo_gb"]
    uso_ram       = _calcular_uso_ram_pct(modelo, specs)
    gpu_activa, es_apple_silicon = _detectar_modo_gpu(modelo, specs)

    t_base = peso_gb / ANCHO_BANDA_DISCO_GB_S

    # Penalización por swapping
    if uso_ram >= UMBRAL_RAM_SWAP:
        t_base *= FACTOR_SWAP_PENALIZACION

    # Ligera ventaja de I/O en Apple Silicon
    if es_apple_silicon:
        t_base *= 0.8

    return round(max(t_base, 0.5), 1)  # mínimo 0.5 s


def _calcular_temperatura_c(modelo: dict, specs: dict) -> float:
    """
    Estima la temperatura del componente principal durante inferencia sostenida.

    Lógica por modo de ejecución:
        - CPU puro       → temperatura de CPU. Sube con % de uso de CPU.
        - GPU discreta   → temperatura de GPU. Sube con ratio VRAM usada/disponible.
        - Apple Silicon  → temperatura del SoC. Base más baja por TDP acotado (~15-30W).
                           Sube con el uso de RAM (proxy de carga del Neural Engine).

    Fórmulas:
        temp_cpu          = TEMP_BASE_CPU + (uso_cpu / 100) * 28     → ~62-90°C
        temp_gpu_discreta = TEMP_BASE_GPU + (vram_ratio) * 30        → ~58-88°C
        temp_apple_silicon = TEMP_BASE_APPLE_SILICON + (uso_ram / 100) * 22  → ~52-74°C
    """
    gpu_activa, es_apple_silicon = _detectar_modo_gpu(modelo, specs)
    uso_ram    = _calcular_uso_ram_pct(modelo, specs)
    uso_cpu    = _calcular_uso_cpu_pct(modelo, specs)
    vram_usuario   = specs.get("vram_gb", 0)
    vram_requerida = modelo["vram_min_gb"]

    if es_apple_silicon and gpu_activa:
        temp = TEMP_BASE_APPLE_SILICON + (uso_ram / 100) * 22
    elif gpu_activa:
        vram_ratio = min(vram_requerida / max(vram_usuario, 1), 1.0)
        temp = TEMP_BASE_GPU + vram_ratio * 30
    else:
        temp = TEMP_BASE_CPU + (uso_cpu / 100) * 28

    return round(min(temp, 95.0), 1)


def _generar_veredicto(uso_ram: float, tps: float, nivel_evaluacion: str) -> dict:
    """
    Genera el texto de veredicto reutilizando el nivel del semáforo de evaluacion.py
    para mantener consistencia entre el semáforo inicial y la simulación detallada.

    Retorna dict con: titulo, descripcion, color
    """
    if nivel_evaluacion == ROJO:
        return {
            "titulo":      "⛔ No recomendado",
            "descripcion": "Tu equipo no cumple los requisitos mínimos. El modelo podría no iniciar o bloquearse.",
            "color":       "error",
        }

    if nivel_evaluacion == AMARILLO or uso_ram >= UMBRAL_RAM_CRITICA:
        return {
            "titulo":      "⚠️ Funciona al límite",
            "descripcion": (
                f"El modelo arrancará, pero con {uso_ram}% de uso de RAM y ~{tps} tok/s "
                "el equipo estará bajo presión. No apto para uso continuo prolongado."
            ),
            "color": "warning",
        }

    return {
        "titulo":      "✅ Funciona bien",
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
        Hardware del usuario:
            - ram_gb            (int)  : RAM total del sistema en GB
            - tiene_gpu         (bool) : True si tiene GPU discreta (ignorado en macOS)
            - vram_gb           (int)  : VRAM de GPU discreta (ignorado en macOS)
            - uso_deseado       (str)  : caso de uso
            - sistema_operativo (str)  : "Windows" | "macOS" | "Linux"

    Retorna
    -------
    dict con métricas listas para app.py:
        tokens_por_segundo, uso_ram_pct, uso_cpu_pct, tiempo_carga_seg,
        temperatura_c, modo_ejecucion, contexto_max_k, veredicto
    """
    modelo     = get_modelo(modelo_id)
    evaluacion = evaluar_modelo(modelo, specs)

    gpu_activa, es_apple_silicon = _detectar_modo_gpu(modelo, specs)

    tps      = _calcular_tokens_por_segundo(modelo, specs)
    uso_ram  = _calcular_uso_ram_pct(modelo, specs)
    uso_cpu  = _calcular_uso_cpu_pct(modelo, specs)
    t_carga  = _calcular_tiempo_carga_seg(modelo, specs)
    temp     = _calcular_temperatura_c(modelo, specs)
    veredicto = _generar_veredicto(uso_ram, tps, evaluacion["nivel"])

    if es_apple_silicon and gpu_activa:
        modo = "Neural Engine 🍎"
    elif gpu_activa:
        modo = "GPU 🎮"
    else:
        modo = "CPU 🖥️"

    return {
        "tokens_por_segundo": tps,
        "uso_ram_pct":        uso_ram,
        "uso_cpu_pct":        uso_cpu,
        "tiempo_carga_seg":   t_carga,
        "temperatura_c":      temp,
        "modo_ejecucion":     modo,
        "contexto_max_k":     modelo["contexto_max_k"],
        "veredicto":          veredicto,
    }


# ── Bloque de prueba (ejecutar: python logic/simulacion.py) ───────────────────

if __name__ == "__main__":
    perfiles = {
        "Equipo débil (Windows)  ": {
            "ram_gb": 4, "tiene_gpu": False, "vram_gb": 0,
            "uso_deseado": "conversación", "sistema_operativo": "Windows",
        },
        "Equipo medio (Linux)    ": {
            "ram_gb": 16, "tiene_gpu": True, "vram_gb": 8,
            "uso_deseado": "código", "sistema_operativo": "Linux",
        },
        "MacBook Pro M2 (16 GB)  ": {
            "ram_gb": 16, "tiene_gpu": False, "vram_gb": 0,
            "uso_deseado": "análisis", "sistema_operativo": "macOS",
        },
        "MacBook Pro M3 Max (36 GB)": {
            "ram_gb": 36, "tiene_gpu": False, "vram_gb": 0,
            "uso_deseado": "código complejo", "sistema_operativo": "macOS",
        },
        "Equipo potente (Windows) ": {
            "ram_gb": 64, "tiene_gpu": True, "vram_gb": 48,
            "uso_deseado": "análisis", "sistema_operativo": "Windows",
        },
    }
    modelos_prueba = ["phi3-mini", "mistral-7b", "llama3-8b", "llama3-70b"]

    for nombre_perfil, specs in perfiles.items():
        print(f"\n{'='*80}")
        so = specs['sistema_operativo']
        ram = specs['ram_gb']
        gpu_info = f"Apple Silicon ({ram} GB unificada)" if so == "macOS" else f"GPU discreta: {specs['tiene_gpu']} ({specs['vram_gb']} GB VRAM)"
        print(f"  Perfil: {nombre_perfil} | RAM: {ram} GB | {gpu_info}")
        print(f"{'='*80}")
        for modelo_id in modelos_prueba:
            try:
                r = simular(modelo_id, specs)
                print(
                    f"  {modelo_id:<15} | {r['modo_ejecucion']:<22} | "
                    f"{r['tokens_por_segundo']:>6.1f} tok/s | "
                    f"RAM {r['uso_ram_pct']:>5.1f}% | "
                    f"CPU {r['uso_cpu_pct']:>5.1f}% | "
                    f"Carga {r['tiempo_carga_seg']:>5.1f}s | "
                    f"{r['temperatura_c']:>4.0f}°C | "
                    f"ctx {r['contexto_max_k']}k | "
                    f"{r['veredicto']['titulo']}"
                )
            except KeyError as e:
                print(f"  {modelo_id:<15} | ERROR: {e}")