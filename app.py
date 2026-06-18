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

# ── CSS personalizado ─────────────────────────────────────────────────────────
# Ajustes finos que config.toml no puede controlar directamente.

st.markdown("""
<style>
    /* Espaciado interno de secciones */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* Métricas: fondo de tarjeta sutil para separar del canvas */
    [data-testid="metric-container"] {
        background-color: #1a1d27;
        border: 1px solid #2d3148;
        border-radius: 10px;
        padding: 1rem 1.2rem;
    }

    /* Expanders: borde izquierdo índigo para jerarquía visual */
    [data-testid="stExpander"] {
        border-left: 3px solid #6366f1;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.6rem;
    }

    /* Línea divisoria más visible en modo oscuro */
    hr {
        border-color: #2d3148 !important;
        margin: 1.8rem 0 !important;
    }

    /* Caption más legible en oscuro */
    .stCaption {
        color: #94a3b8 !important;
    }
</style>
""", unsafe_allow_html=True)

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
    umbral_bajo = UMBRAL_RAM_SWAP
    umbral_alto = UMBRAL_RAM_CRITICA
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
        number={"suffix": sufijo, "font": {"size": 28, "color": "#e2e8f0"}},
        title={"text": titulo, "font": {"size": 14, "color": "#94a3b8"}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1, "tickcolor": "#4b5563"},
            "bar":  {"color": color, "thickness": 0.75},
            "bgcolor": "rgba(0,0,0,0)",       # fondo transparente para armonizar con dark mode
            "bordercolor": "rgba(0,0,0,0)",
            "steps": [
                {"range": [0, limite_amarillo],           "color": "rgba(34,197,94,0.12)"},
                {"range": [limite_amarillo, limite_rojo], "color": "rgba(245,158,11,0.12)"},
                {"range": [limite_rojo, max_val],         "color": "rgba(239,68,68,0.12)"},
            ],
        },
    ))
    fig.update_layout(
        height=200,
        margin=dict(t=40, b=10, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _barra_tokens(tps: float, max_tps: float = 60) -> go.Figure:
    color = "#22c55e" if tps >= 10 else "#f59e0b" if tps >= 4 else "#ef4444"
    fig = go.Figure(go.Bar(
        x=[tps], y=[""], orientation="h",
        marker_color=color,
        marker_line_width=0,
        text=[f"{tps} tok/s"], textposition="inside",
        textfont={"color": "#0f1117", "size": 14},
    ))
    fig.update_layout(
        height=80,
        xaxis={
            "range": [0, max_tps],
            "title": "tokens / segundo",
            "color": "#94a3b8",
            "gridcolor": "#2d3148",
        },
        yaxis={"visible": False},
        margin=dict(t=10, b=30, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
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

with st.container(border=True):
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
            options=["Windows", "macOS (Apple Silicon / M-Series)", "macOS (Intel)", "Linux"],
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
        uso_deseado = st.selectbox(
            "¿Para qué quieres usar el modelo?",
            options=_todos_los_casos_uso,
            index=0,
        )

    st.write("")  # espaciado antes del botón principal
    _, col_btn_evaluar, _ = st.columns([1, 2, 1])
    with col_btn_evaluar:
        enviado = st.button(
            "🔍 Evaluar mi equipo",
            use_container_width=True,
            type="primary",
        )

if enviado:
    st.session_state.specs = {
        "ram_gb":            ram_gb,
        "tiene_gpu":         tiene_gpu,
        "vram_gb":           vram_gb if tiene_gpu else 0,
        "uso_deseado":       uso_deseado,
        "sistema_operativo": sistema_operativo,
    }
    st.session_state.modelo_seleccionado = None
    st.session_state.modo_exploracion    = False

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Semáforo de compatibilidad
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
    with st.container(border=True):
        col_emoji, col_info, col_btn = st.columns([1, 7, 2])
        with col_emoji:
            st.markdown(f"### {r['emoji']}")
        with col_info:
            st.markdown(f"**{r['nombre']}** · `{r['parametros_b']}B parámetros`")
            st.caption(r["mensaje"])
            st.caption("Casos de uso: " + ", ".join(r["casos_uso"]))
        with col_btn:
            st.write("")  # alineación vertical
            if st.button("Ver simulación", key=f"sel_{r['id']}", use_container_width=True):
                st.session_state.modelo_seleccionado = r["id"]
                st.session_state.modo_exploracion    = False

    opciones_selector[r["nombre"]] = r["id"]

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Dashboard de simulación
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

st.write("")

# Métricas en tarjetas rápidas
m1, m2, m3, m4 = st.columns(4)
m1.metric("⚡ Velocidad",       f"{metricas['tokens_por_segundo']} tok/s")
m2.metric("🧠 Uso de RAM",      f"{metricas['uso_ram_pct']}%")
m3.metric("⏱️ Tiempo de carga", f"{metricas['tiempo_carga_seg']} s")
m4.metric("🌡️ Temperatura",     f"{metricas['temperatura_c']} °C")

st.write("")

# Gráficos visuales
st.markdown("#### Detalle de recursos")
with st.container(border=True):
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
with st.container(border=True):
    st.plotly_chart(
        _barra_tokens(metricas["tokens_por_segundo"]),
        use_container_width=True, key="barra_tps"
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECCIÓN 4 — Guía de instalación
# ══════════════════════════════════════════════════════════════════════════════

st.divider()
st.subheader("🛠️ Guía de instalación")
st.caption(f"Pasos para instalar **{modelo_data['nombre_display']}** en {specs_activas['sistema_operativo']}.")

with st.expander("Paso 1 — Instalar Ollama", expanded=True):
    so = specs_activas["sistema_operativo"]
    if so == "Windows":
        st.markdown("Descarga el instalador desde [ollama.com/download](https://ollama.com/download) y ejecútalo.")
    elif "macOS" in so:
        st.code("brew install ollama", language="bash")
    else:
        st.code("curl -fsSL https://ollama.com/install.sh | sh", language="bash")

with st.expander("Paso 2 — Descargar y correr el modelo", expanded=True):
    st.markdown("Ejecuta este comando en tu terminal:")
    st.code(modelo_data["comando_ollama"], language="bash")
    st.caption(
        f"⏳ Primera vez: Tamaño de descarga estimado: ~{modelo_data['peso_archivo_gb']} GB "
        f"(cuantización Q4_K_M). "
        f"Tiempo estimado de carga inicial: **{metricas['tiempo_carga_seg']} segundos**."
    )

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
    st.write("")
    _, col_btn_exp, _ = st.columns([1, 2, 1])
    with col_btn_exp:
        if st.button("Activar modo exploración", use_container_width=True):
            st.session_state.modo_exploracion = True
            st.rerun()
else:
    with st.container(border=True):
        st.markdown(f"**Modelo fijo:** {modelo_data['nombre_display']}")
        st.write("")
        ec1, ec2, ec3 = st.columns(3)

        with ec1:
            exp_ram = st.selectbox(
                "RAM hipotética",
                options=[4, 8, 12, 16, 24, 32, 48, 64, 96, 128],
                index=3,
                format_func=lambda x: f"{x} GB",
                key="exp_ram",
            )
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
            exp_uso = st.selectbox(
                "Uso deseado",
                options=_todos_los_casos_uso,
                key="exp_uso",
            )

        st.write("")
        _, col_btn_sim, _ = st.columns([1, 2, 1])
        with col_btn_sim:
            simular_exp = st.button(
                "⚡ Simular hardware hipotético",
                use_container_width=True,
                type="primary",
            )

    if simular_exp:
        specs_exp = {
            "ram_gb":            exp_ram,
            "tiene_gpu":         exp_gpu,
            "vram_gb":           exp_vram if exp_gpu else 0,
            "uso_deseado":       exp_uso,
            "sistema_operativo": exp_so,
        }
        met_exp = simular(modelo_id, specs_exp)

        st.write("")
        st.markdown("##### Resultado con hardware hipotético")
        veredicto_exp = met_exp["veredicto"]
        getattr(st, color_map.get(veredicto_exp["color"], "info"))(
            f"**{veredicto_exp['titulo']}** — {veredicto_exp['descripcion']}"
        )

        st.write("")
        with st.container(border=True):
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

    st.write("")
    _, col_btn_cerrar, _ = st.columns([1, 2, 1])
    with col_btn_cerrar:
        if st.button("✕ Cerrar modo exploración", use_container_width=True):
            st.session_state.modo_exploracion = False
            st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption("ANGIE · Matías Fuentes · Ingeniería Civil en Ciencia de Datos, PUCV · Expo Software 2026 · MIT License")