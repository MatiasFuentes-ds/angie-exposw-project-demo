# app.py
# Capa de presentación de ANGIE. No contiene lógica de negocio.
# Solo llama funciones de logic/ y data/ y renderiza sus resultados.

import streamlit as st
import plotly.graph_objects as go

from data.modelos import get_modelo, get_nombres_modelos, get_todos_los_modelos
from logic.evaluacion import evaluar_todos
from logic.simulacion import simular, UMBRAL_RAM_SWAP, UMBRAL_RAM_CRITICA

# ── Configuración de página ───────────────────────────────────────────────────

st.set_page_config(
    page_title="ANGIE",
    page_icon="assets/logo.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inicialización de estado persistente ──────────────────────────────────────
# Todo lo que necesita sobrevivir entre re-ejecuciones de Streamlit va aquí.

if "specs" not in st.session_state:
    st.session_state.specs = None

if "modelo_seleccionado" not in st.session_state:
    st.session_state.modelo_seleccionado = None

if "modo_exploracion" not in st.session_state:
    st.session_state.modo_exploracion = False

# ── Lista dinámica de casos de uso ────────────────────────────────────────────
# Extraída en tiempo de carga para que los selectbox siempre reflejen
# exactamente los strings presentes en data/modelos.py, sin hardcoding.

_todos_los_casos_uso: list[str] = sorted({
    caso
    for modelo in get_todos_los_modelos().values()
    for caso in modelo["casos_uso"]
})

# ── Helpers de visualización ──────────────────────────────────────────────────

_COLOR_NIVEL = {"verde": "#22c55e", "amarillo": "#f59e0b", "rojo": "#ef4444"}


def _gauge(valor: float, titulo: str, sufijo: str = "%", max_val: float = 100) -> go.Figure:
    """
    Medidor tipo gauge con umbrales sincronizados con el backend.
    Los límites de color UMBRAL_RAM_SWAP y UMBRAL_RAM_CRITICA se importan
    directamente de logic/simulacion.py para garantizar paridad total con
    la lógica de semáforo del backend.
    """
    umbral_bajo  = UMBRAL_RAM_SWAP     # 88 → zona amarilla (riesgo de swap)
    umbral_alto  = UMBRAL_RAM_CRITICA  # 85 → zona roja (al límite)
    # Nota: UMBRAL_RAM_CRITICA < UMBRAL_RAM_SWAP en el backend.
    # Para el gauge usamos el menor como inicio del amarillo y el mayor como inicio del rojo.
    limite_amarillo = min(umbral_bajo, umbral_alto)
    limite_rojo     = max(umbral_bajo, umbral_alto)

    color = (
        "#22c55e" if valor < limite_amarillo
        else "#f59e0b" if valor < limite_rojo
        else "#ef4444"
    )

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valor,
        number={"suffix": sufijo, "font": {"size": 28}},
        title={"text": titulo, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1},
            "bar":  {"color": color},
            "bgcolor": "white",
            "steps": [
                {"range": [0, limite_amarillo],          "color": "#dcfce7"},
                {"range": [limite_amarillo, limite_rojo], "color": "#fef9c3"},
                {"range": [limite_rojo, max_val],         "color": "#fee2e2"},
            ],
        },
    ))
    fig.update_layout(height=200, margin=dict(t=40, b=10, l=20, r=20))
    return fig


def _barra_tokens(tps: float, max_tps: float = 60) -> go.Figure:
    color = "#22c55e" if tps >= 10 else "#f59e0b" if tps >= 4 else "#ef4444"
    fig = go.Figure(go.Bar(
        x=[tps], y=[""], orientation="h",
        marker_color=color,
        text=[f"{tps} tok/s"], textposition="inside",
    ))
    fig.update_layout(
        height=80,
        xaxis={"range": [0, max_tps], "title": "tokens / segundo"},
        yaxis={"visible": False},
        margin=dict(t=10, b=30, l=10, r=10),
    )
    return fig

# ── Header ────────────────────────────────────────────────────────────────────

col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.image("assets/logo.png", width=72)
with col_titulo:
    st.markdown("## ANGIE")
    st.caption("Agent for Native Generative Intelligence Environments · PUCV Expo Software 2026")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Formulario de especificaciones
# ══════════════════════════════════════════════════════════════════════════════

st.subheader("🖥️ ¿Qué equipo tienes?")
st.caption("Ingresa las specs de tu máquina. No usamos estos datos fuera de tu sesión.")

with st.container():
    col1, col2, col3 = st.columns(3)

    with col1:
        ram_gb = st.selectbox(
            "RAM del sistema",
            options=[4, 8, 12, 16, 24, 32, 48, 64, 96, 128],
            index=1,
            format_func=lambda x: f"{x} GB",
        )
        sistema_operativo = st.selectbox(
            "Sistema operativo",
            options=["Windows", "macOS (Apple Silicon / M-Series)", "macOS (Intel)", "Linux"]
        )

    with col2:
        tiene_gpu = st.toggle("Tengo GPU dedicada (NVIDIA / AMD)", value=False)
        vram_gb = st.selectbox(
            "VRAM de la GPU",
            options=[0, 2, 4, 6, 8, 10, 12, 16, 24, 40, 48, 80],
            index=0,
            format_func=lambda x: "Sin GPU / No sé" if x == 0 else f"{x} GB",
            disabled=not tiene_gpu,
        )

    with col3:
        # Opciones extraídas dinámicamente de data/modelos.py
        uso_deseado = st.selectbox(
            "¿Para qué quieres usar el modelo?",
            options=_todos_los_casos_uso,
            index=0,
        )
        st.markdown("")  # espaciado visual

    enviado = st.button("🔍 Evaluar mi equipo", use_container_width=True, type="primary")

if enviado:
    st.session_state.specs = {
        "ram_gb":            ram_gb,
        "tiene_gpu":         tiene_gpu,
        "vram_gb":           vram_gb if tiene_gpu else 0,
        "uso_deseado":       uso_deseado,
        "sistema_operativo": sistema_operativo,
    }
    st.session_state.modelo_seleccionado = None  # resetea selección anterior
    st.session_state.modo_exploracion    = False

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Semáforo de compatibilidad
# (Solo se renderiza cuando hay specs guardadas)
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.specs is None:
    st.info("👆 Completa el formulario para ver qué modelos puedes correr en tu equipo.")
    st.stop()

specs_activas = st.session_state.specs
resultados    = evaluar_todos(specs_activas)

st.divider()
st.subheader("🚦 Compatibilidad con tu equipo")
st.caption(
    f"RAM: {specs_activas['ram_gb']} GB · "
    f"SO: {specs_activas['sistema_operativo']} · "
    f"GPU: {'Sí (' + str(specs_activas['vram_gb']) + ' GB VRAM)' if specs_activas['tiene_gpu'] else 'No'} · "
    f"Uso deseado: {specs_activas['uso_deseado']}"
)

opciones_selector = {}

for r in resultados:
    col_emoji, col_info, col_btn = st.columns([1, 7, 2])
    with col_emoji:
        st.markdown(f"### {r['emoji']}")
    with col_info:
        st.markdown(f"**{r['nombre']}** · `{r['parametros_b']}B parámetros`")
        st.caption(r["mensaje"])
        st.caption("Casos de uso: " + ", ".join(r["casos_uso"]))
    with col_btn:
        if st.button("Ver simulación", key=f"sel_{r['id']}", use_container_width=True):
            st.session_state.modelo_seleccionado = r["id"]
            st.session_state.modo_exploracion    = False

    opciones_selector[r["nombre"]] = r["id"]

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Dashboard de simulación
# (Solo se renderiza cuando hay un modelo seleccionado)
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.modelo_seleccionado is None:
    st.info("👆 Selecciona un modelo para ver la simulación detallada de rendimiento.")
    st.stop()

modelo_id   = st.session_state.modelo_seleccionado
modelo_data = get_modelo(modelo_id)
metricas    = simular(modelo_id, specs_activas)

st.divider()
st.subheader(f"📊 Simulación — {modelo_data['nombre_display']}")
st.caption(f"Modo de ejecución estimado: **{metricas['modo_ejecucion']}**")

# Veredicto principal
veredicto = metricas["veredicto"]
color_map  = {"success": "success", "warning": "warning", "error": "error"}
getattr(st, color_map.get(veredicto["color"], "info"))(
    f"**{veredicto['titulo']}** — {veredicto['descripcion']}"
)

# Métricas en tarjetas rápidas
m1, m2, m3, m4 = st.columns(4)
m1.metric("⚡ Velocidad",       f"{metricas['tokens_por_segundo']} tok/s")
m2.metric("🧠 Uso de RAM",      f"{metricas['uso_ram_pct']}%")
m3.metric("⏱️ Tiempo de carga", f"{metricas['tiempo_carga_seg']} s")
m4.metric("🌡️ Temperatura",     f"{metricas['temperatura_c']} °C")

# Gráficos visuales
st.markdown("#### Detalle de recursos")
g1, g2, g3 = st.columns(3)

with g1:
    st.plotly_chart(
        _gauge(metricas["uso_ram_pct"], "Uso de RAM", "%"),
        use_container_width=True, key="gauge_ram"
    )
with g2:
    st.plotly_chart(
        _gauge(metricas["uso_cpu_pct"], "Uso de CPU", "%"),
        use_container_width=True, key="gauge_cpu"
    )
with g3:
    st.plotly_chart(
        _gauge(metricas["temperatura_c"], "Temperatura", "°C", max_val=100),
        use_container_width=True, key="gauge_temp"
    )

st.markdown("#### Velocidad de generación")
st.plotly_chart(_barra_tokens(metricas["tokens_por_segundo"]), use_container_width=True, key="barra_tps")

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — Guía de instalación
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("🛠️ Guía de instalación")
st.caption(f"Pasos para instalar **{modelo_data['nombre_display']}** en {specs_activas['sistema_operativo']}.")

# Paso 1: Instalar Ollama
with st.expander("Paso 1 — Instalar Ollama", expanded=True):
    so = specs_activas["sistema_operativo"]
    if so == "Windows":
        st.markdown("Descarga el instalador desde [ollama.com/download](https://ollama.com/download) y ejecútalo.")
    elif so == "macOS":
        st.code("brew install ollama", language="bash")
    else:
        st.code("curl -fsSL https://ollama.com/install.sh | sh", language="bash")

# Paso 2: Descargar y correr el modelo
with st.expander("Paso 2 — Descargar y correr el modelo", expanded=True):
    st.markdown("Ejecuta este comando en tu terminal:")
    st.code(modelo_data["comando_ollama"], language="bash")
    st.caption(
        # Corrección: usa peso_archivo_gb (tamaño real del archivo .gguf)
        # en lugar de parametros_b (cantidad de parámetros, no es una unidad de peso de archivo)
        f"⏳ Primera vez: Tamaño de descarga estimado: ~{modelo_data['peso_archivo_gb']} GB "
        f"(cuantización Q4_K_M). "
        f"Tiempo estimado de carga inicial: **{metricas['tiempo_carga_seg']} segundos**."
    )

# Paso 3: Verificar
with st.expander("Paso 3 — Verificar que funciona"):
    st.markdown("Una vez iniciado, escribe un mensaje en el prompt interactivo de Ollama:")
    st.code(">>> Hola, ¿cómo estás?", language="text")
    st.markdown("También puedes consultar los modelos instalados con:")
    st.code("ollama list", language="bash")

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 5 — Modo exploración
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("🔄 Modo exploración")
st.caption("Simula cómo se comportaría este modelo en un equipo hipotético distinto al tuyo.")

if not st.session_state.modo_exploracion:
    if st.button("Activar modo exploración", use_container_width=False):
        st.session_state.modo_exploracion = True
        st.rerun()
else:
    with st.container():
        st.markdown(f"**Modelo fijo:** {modelo_data['nombre_display']}")
        ec1, ec2, ec3 = st.columns(3)

        with ec1:
            exp_ram = st.selectbox(
                "RAM hipotética",
                options=[4, 8, 12, 16, 24, 32, 48, 64, 96, 128],
                index=3,
                format_func=lambda x: f"{x} GB",
                key="exp_ram",
            )
            # Corrección: selector de SO hipotético para activar lógica de
            # memoria unificada (Apple Silicon) en el backend de simulacion.py
            exp_so = st.selectbox(
                "Sistema Operativo hipotético",
                options=["Windows", "macOS (Apple Silicon / M-Series)", "macOS (Intel)", "Linux"],
                key="exp_so",
            )

        with ec2:
            exp_gpu = st.toggle("GPU dedicada", value=True, key="exp_gpu")
            exp_vram = st.selectbox(
                "VRAM hipotética",
                options=[0, 4, 6, 8, 12, 16, 24, 40, 48],
                index=3,
                format_func=lambda x: "Sin GPU" if x == 0 else f"{x} GB",
                disabled=not exp_gpu,
                key="exp_vram",
            )

        with ec3:
            # Opciones extraídas dinámicamente de data/modelos.py
            exp_uso = st.selectbox(
                "Uso deseado",
                options=_todos_los_casos_uso,
                key="exp_uso",
            )

        simular_exp = st.button("⚡ Simular hardware hipotético", use_container_width=True)

    if simular_exp:
        # Corrección: sistema_operativo inyectado en specs_exp para que
        # simulacion.py y evaluacion.py puedan detectar Apple Silicon correctamente
        specs_exp = {
            "ram_gb":            exp_ram,
            "tiene_gpu":         exp_gpu,
            "vram_gb":           exp_vram if exp_gpu else 0,
            "uso_deseado":       exp_uso,
            "sistema_operativo": exp_so,
        }
        met_exp = simular(modelo_id, specs_exp)

        st.markdown("##### Resultado con hardware hipotético")
        veredicto_exp = met_exp["veredicto"]
        getattr(st, color_map.get(veredicto_exp["color"], "info"))(
            f"**{veredicto_exp['titulo']}** — {veredicto_exp['descripcion']}"
        )

        ex1, ex2, ex3, ex4 = st.columns(4)
        ex1.metric(
            "⚡ Velocidad",
            f"{met_exp['tokens_por_segundo']} tok/s",
            delta=f"{met_exp['tokens_por_segundo'] - metricas['tokens_por_segundo']:+.1f} vs tu equipo",
        )
        ex2.metric(
            "🧠 Uso RAM",
            f"{met_exp['uso_ram_pct']}%",
            delta=f"{met_exp['uso_ram_pct'] - metricas['uso_ram_pct']:+.1f}%",
            delta_color="inverse",
        )
        ex3.metric(
            "⏱️ Carga",
            f"{met_exp['tiempo_carga_seg']} s",
            delta=f"{met_exp['tiempo_carga_seg'] - metricas['tiempo_carga_seg']:+.1f} s",
            delta_color="inverse",
        )
        ex4.metric(
            "🌡️ Temperatura",
            f"{met_exp['temperatura_c']} °C",
            delta=f"{met_exp['temperatura_c'] - metricas['temperatura_c']:+.1f} °C",
            delta_color="inverse",
        )

    if st.button("Cerrar modo exploración"):
        st.session_state.modo_exploracion = False
        st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption("ANGIE · Matías Fuentes · Ingeniería Civil en Ciencia de Datos, PUCV · Expo Software 2026 · MIT License")