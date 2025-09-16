# app.py — endurecido para despliegue y compatible con streamlit-authenticator 0.3.x y 0.2.x
import os
import sys
import json
import zipfile
from io import BytesIO
import re
import base64
import pandas as pd
import streamlit as st
import yaml
from yaml.loader import SafeLoader
import inspect  # <- para detectar la firma real de Authenticate

# -------------------------------------------------------------------
# Config de página + LOGO
# -------------------------------------------------------------------
LOGO_PATH = "medidatarips_logo.png"  # coloca aquí tu archivo de logo
page_icon = LOGO_PATH if os.path.exists(LOGO_PATH) else None

st.set_page_config(
    page_title="Transformador RIPS PGP & EVENTO",
    layout="centered",
    page_icon=page_icon
)

# (Opcional) Ajuste visual para que el logo “respire” mejor arriba
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

def render_logo_left(path: str, height_px: int = 120):
    """Muestra el logo 100% a la izquierda usando HTML seguro con base64."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <div style="display:flex; align-items:center; justify-content:flex-start;">
                <img src="data:image/png;base64,{b64}" alt="Logo MedidataRIPS" style="height:{height_px}px;">
            </div>
            """,
            unsafe_allow_html=True
        )
    except Exception as e:
        st.warning(f"No se pudo cargar el logo: {e}")

# -------------------------------------------------------------------
# Autenticación
#   1) Primero intenta st.secrets (ideal en la nube)
#   2) Si no hay, usa config.yaml
#   3) Valida claves mínimas y maneja errores en UI
# -------------------------------------------------------------------
try:
    import streamlit_authenticator as stauth
except Exception as e:
    st.error("No pude importar 'streamlit_authenticator'. Asegura streamlit-authenticator en requirements.txt.")
    st.exception(e)
    st.stop()

# --- Cargar config desde secrets o YAML ---
config = None

# 1) st.secrets (recomendado en despliegue)
try:
    if "credentials" in st.secrets and "cookie" in st.secrets:
        config = {
            "credentials": dict(st.secrets["credentials"]),
            "cookie": dict(st.secrets["cookie"]),
        }
        if "preauthorized" in st.secrets:
            config["preauthorized"] = dict(st.secrets["preauthorized"])
        if "pre_authorized" in st.secrets:
            config["pre_authorized"] = dict(st.secrets["pre_authorized"])
except Exception:
    pass  # seguimos a YAML

# 2) config.yaml local
if config is None:
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.load(f, Loader=SafeLoader)
    except FileNotFoundError:
        st.error("No encuentro 'config.yaml' y no hay 'st.secrets'. Sube uno de los dos.")
        st.stop()
    except Exception as e:
        st.error("Error leyendo 'config.yaml'. Revisa la sintaxis YAML.")
        st.exception(e)
        st.stop()

# 3) Validación mínima para evitar KeyError luego
if "credentials" not in config or "cookie" not in config:
    st.error("Config inválida. Faltan secciones 'credentials' o 'cookie'.")
    st.stop()

# normaliza usernames a minúsculas (evita fallos por mayúsculas/espacios)
if "usernames" in config.get("credentials", {}):
    config["credentials"]["usernames"] = {
        str(k).strip().lower(): v for k, v in config["credentials"]["usernames"].items()
    }

# --- Instanciar Authenticate compatible sin duplicar widgets ---
preauth_cfg = config.get("pre_authorized") or config.get("preauthorized") or {}
emails_list = preauth_cfg.get("emails", []) if isinstance(preauth_cfg, dict) else preauth_cfg

try:
    params = inspect.signature(stauth.Authenticate.__init__).parameters
    if "pre_authorized" in params:
        # 0.3.x con pre_authorized
        authenticator = stauth.Authenticate(
            credentials=config["credentials"],
            cookie_name=config["cookie"]["name"],
            cookie_key=config["cookie"]["key"],
            cookie_expiry_days=config["cookie"]["expiry_days"],
            pre_authorized=preauth_cfg,
        )
    elif "preauthorized" in params:
        # 0.3.x variante con preauthorized
        authenticator = stauth.Authenticate(
            credentials=config["credentials"],
            cookie_name=config["cookie"]["name"],
            cookie_key=config["cookie"]["key"],
            cookie_expiry_days=config["cookie"]["expiry_days"],
            preauthorized=preauth_cfg,
        )
    else:
        # 0.2.x posicional (quinto argumento)
        authenticator = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
            emails_list,
        )
except Exception as e:
    st.error("No pude instanciar Authenticate. Revisa tu config/versión.")
    st.exception(e)
    st.stop()

name, authentication_status, username = authenticator.login("🔐 Iniciar sesión", "main")

# -------------------------------------------------------------------
# Estados de login
# -------------------------------------------------------------------
if authentication_status is False:
    st.error("❌ Usuario o contraseña incorrectos.")
    st.stop()
elif authentication_status is None:
    st.warning("Por favor ingresa tus credenciales.")
    st.stop()

# Autenticado
authenticator.logout("🚪 Cerrar sesión", "sidebar")

# --- LOGO en sidebar (opcional) ---
if os.path.exists(LOGO_PATH):
    st.sidebar.image(LOGO_PATH, use_container_width=True)

# --- LOGO arriba totalmente a la izquierda ---
render_logo_left(LOGO_PATH, height_px=150)

st.title(f"🔄 Bienvenido {name}")

# ===========================================================
#                CONVERSOR RIPS  PGP / EVENTO
# ===========================================================
TIPOS_SERVICIOS = [
    "consultas", "procedimientos", "hospitalizacion", "hospitalizaciones",
    "urgencias", "reciennacidos", "medicamentos", "otrosServicios",
]

CAMPOS_NUMERICOS = [
    "consecutivo", "codServicio", "vrServicio", "valorPagoModerador",
    "concentracionMedicamento", "unidadMedida", "unidadMinDispensa",
    "cantidadMedicamento", "diasTratamiento", "vrUnitMedicamento",
    "idMIPRES", "cantidadOS", "vrUnitOS",
]

CAMPOS_CODIGOS = [
    "tipoUsuario", "viaIngresoServicioSalud", "modalidadGrupoServicioTecSal",
    "grupoServicios", "finalidadTecnologiaSalud", "conceptoRecaudo",
    "tipoMedicamento", "tipoOS", "codZonaTerritorialResidencia", "codMunicipioResidencia",
    "codPaisResidencia", "codPaisOrigen",
]

def limpiar_valores(d):
    limpio = {}
    for k, v in d.items():
        try:
            es_na = pd.isna(v)
        except Exception:
            es_na = False
        if es_na:
            limpio[k] = None
            continue

        # codMunicipioResidencia como string 5 dígitos
        if k == "codMunicipioResidencia":
            s = str(v).strip()
            s = re.sub(r"\.0$", "", s)
            s = re.sub(r"\D", "", s)
            limpio[k] = s.zfill(5) if s else None
            continue

        if k in CAMPOS_NUMERICOS:
            try:
                fv = float(v)
                limpio[k] = int(fv) if fv.is_integer() else fv
            except Exception:
                limpio[k] = None
        elif k in CAMPOS_CODIGOS:
            s = str(v).strip()
            s = re.sub(r"\.0$", "", s)
            limpio[k] = s.zfill(2) if s else None
        else:
            limpio[k] = v.strip() si_es_str(v:=v)
    return limpio

def si_es_str(v):
    return v if isinstance(v, str) else str(v)

def json_to_excel(files, tipo_factura):
    datos = {tipo: [] for tipo in ["usuarios"] + list(set([s.lower() for s in TIPOS_SERVICIOS]))}
    for archivo in files:
        data = json.load(archivo)
        num_factura = data.get("numFactura", "SIN_FACTURA")
        archivo_origen = os.path.splitext(archivo.name)[0]
        usuarios = data.get("usuarios", [])

        for usuario in usuarios:
            servicios = usuario.get("servicios", {})
            usuario_limpio = usuario.copy()
            usuario_limpio.pop("servicios", None)
            usuario_limpio["archivo_origen"] = archivo_origen
            usuario_limpio["numFactura"] = num_factura
            datos["usuarios"].append(usuario_limpio)

            for tipo, registros in servicios.items():
                tipo_normalizado = tipo.lower()
                if tipo_normalizado in datos:
                    for reg in registros:
                        reg = reg.copy()
                        reg["numFactura"] = num_factura
                        reg["documento_usuario"] = usuario.get("numDocumentoIdentificacion")
                        reg["archivo_origen"] = archivo_origen
                        datos[tipo_normalizado].append(reg)

    output = BytesIO()
    # Usamos openpyxl (ya en requirements)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            if registros:
                df = pd.DataFrame(registros)
                sheet = tipo.capitalize()[:31]  # Evita nombres >31 chars
                df.to_excel(writer, sheet_name=sheet, index=False)
    output.seek(0)
    return output

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):
    xlsx = pd.read_excel(archivo_excel, sheet_name=None)
    dataframes = {k.lower(): v for k, v in xlsx.items()}
    if "usuarios" not in dataframes:
        st.error("❌ El archivo no contiene una hoja llamada 'usuarios'.")
        return None

    usuarios_df = dataframes["usuarios"]
    tipos_servicios = [k for k in dataframes if k != "usuarios"]

    if tipo_factura == "PGP":
        facturas = usuarios_df["numFactura"].dropna().unique()
        if len(facturas) != 1:
            st.error("❌ Para PGP solo se permite una única factura.")
            return None

        factura = facturas[0]
        usuarios_final = []

        for _, usuario in usuarios_df.iterrows():
            usuario_dict = usuario.to_dict()
            doc = usuario_dict.get("numDocumentoIdentificacion") or usuario_dict.get("documento_usuario")
            usuario_limpio = limpiar_valores(usuario_dict)
            usuario_limpio.pop("archivo_origen", None)
            usuario_limpio.pop("numFactura", None)

            servicios_dict = {}
            for tipo in tipos_servicios:
                df_tipo = dataframes[tipo]
                registros = df_tipo[df_tipo["documento_usuario"] == doc]
                if not registros.empty:
                    registros = registros.drop(columns=["numFactura", "documento_usuario", "archivo_origen"], errors="ignore")
                    registros_limpios = [limpiar_valores(r) for _, r in registros.iterrows()]
                    servicios_dict[tipo] = registros_limpios

            usuario_limpio["servicios"] = servicios_dict
            usuarios_final.append(usuario_limpio)

        salida_json = {
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final,
        }

        return {
            "tipo": "único",
            "contenido": json.dumps(salida_json, ensure_ascii=False, indent=2),
            "nombre": f"Factura_RIPS_{tipo_factura}.json",
        }

    else:
        salida_archivos = {}
        for factura in usuarios_df["numFactura"].dropna().unique():
            usuarios_factura = usuarios_df[usuarios_df["numFactura"] == factura]
            usuarios_final = []

            for _, usuario in usuarios_factura.iterrows():
                usuario_dict = usuario.to_dict()
                doc = usuario_dict.get("numDocumentoIdentificacion") or usuario_dict.get("documento_usuario")
                usuario_limpio = limpiar_valores(usuario_dict)
                usuario_limpio.pop("archivo_origen", None)
                usuario_limpio.pop("numFactura", None)

                servicios_dict = {}
                for tipo in tipos_servicios:
                    df_tipo = dataframes[tipo]
                    registros = df_tipo[
                        (df_tipo["numFactura"] == factura) &
                        (df_tipo["documento_usuario"] == doc)
                    ]
                    if not registros.empty:
                        registros = registros.drop(columns=["numFactura", "documento_usuario", "archivo_origen"], errors="ignore")
                        registros_limpios = [limpiar_valores(r) for _, r in registros.iterrows()]
                        servicios_dict[tipo] = registros_limpios

                usuario_limpio["servicios"] = servicios_dict
                usuarios_final.append(usuario_limpio)

            salida_json = {
                "numDocumentoIdObligado": nit_obligado,
                "numFactura": factura,
                "tipoNota": None,
                "numNota": None,
                "usuarios": usuarios_final,
            }

            salida_archivos[f"{factura}_RIPS.json"] = json.dumps(salida_json, ensure_ascii=False, indent=2)

        return {"tipo": "zip", "contenido": salida_archivos}

# -------------------------------------------------------------------
# UI
# -------------------------------------------------------------------
st.subheader("📄 Transformador RIPS: PGP y EVENTO")

modo = st.radio(
    "Selecciona el tipo de conversión:",
    ["📥 JSON ➜ Excel (PGP)", "📤 Excel ➜ JSON (PGP)",
     "📥 JSON ➜ Excel (Evento)", "📤 Excel ➜ JSON (Evento)"]
)

nit_obligado = st.text_input("🔢 NIT del Obligado a Facturar", value="900364721")

resultado = None

if "JSON ➜ Excel" in modo:
    archivos = st.file_uploader("📂 Selecciona uno o varios archivos JSON", type=["json"], accept_multiple_files=True)
    if archivos and st.button("🚀 Convertir a Excel"):
        tipo_factura = "PGP" if "PGP" in modo else "EVENTO"
        excel_data = json_to_excel(archivos, tipo_factura)
        st.download_button("⬇️ Descargar Excel", data=excel_data, file_name=f"RIPS_Consolidado_{tipo_factura}.xlsx")

elif "Excel ➜ JSON" in modo:
    archivo_excel = st.file_uploader("📂 Selecciona archivo Excel", type=["xlsx"])
    if archivo_excel and st.button("🚀 Convertir a JSON"):
        tipo_factura = "PGP" if "PGP" in modo else "EVENTO"
        resultado = excel_to_json(archivo_excel, tipo_factura, nit_obligado)

    if resultado:
        if resultado["tipo"] == "único":
            st.download_button(
                "⬇️ Descargar JSON",
                data=resultado["contenido"].encode("utf-8"),
                file_name=resultado["nombre"]
            )
        elif resultado["tipo"] == "zip":
            buffer = BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for nombre, contenido in resultado["contenido"].items():
                    zipf.writestr(nombre, contenido)
            buffer.seek(0)
            st.download_button(
                "⬇️ Descargar ZIP de JSONs",
                data=buffer,
                file_name="RIPS_Evento_JSONs.zip"
            )
