# app.py — robusto para despliegue; muestra errores en pantalla y
# es compatible con streamlit-authenticator 0.2.x / 0.3.x

import os
import json
import zipfile
from io import BytesIO
import re
import base64
from collections.abc import Mapping
import time
import traceback
import inspect as _inspect

import pandas as pd
import streamlit as st

# ★ NUEVO: para serializar tipos de numpy/pandas
import numpy as np
from datetime import date, datetime

# ──────────────────────────────────────────────────────────────────────────────
# 0) CONFIG BÁSICA (nada de st.* antes de set_page_config)
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "medidatarips_logo.png")
page_icon = LOGO_PATH if os.path.isfile(LOGO_PATH) else None

st.set_page_config(
    page_title="Transformador RIPS PGP & EVENTO",
    layout="centered",
    page_icon=page_icon
)

# sello de build para verificar redeploys
st.caption(f"BUILD_MARK {int(time.time())}")

# estilo mínimo
st.markdown("<style>.block-container{padding-top:1.2rem}</style>", unsafe_allow_html=True)

# Dependencias críticas con mensajes claros si faltan
try:
    import yaml
    from yaml.loader import SafeLoader
except ModuleNotFoundError:
    st.error("Falta PyYAML. Agrega 'PyYAML==6.0.2' a requirements.txt y vuelve a desplegar.")
    st.stop()

try:
    import streamlit_authenticator as stauth
except ModuleNotFoundError:
    st.error("Falta 'streamlit-authenticator'. Agrega 'streamlit-authenticator==0.3.3' a requirements.txt y vuelve a desplegar.")
    st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# 1) AIRBAG: muestra tracebacks en pantalla
# ──────────────────────────────────────────────────────────────────────────────
def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Excepción en tiempo de ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()


# ──────────────────────────────────────────────────────────────────────────────
# 2) UTILIDADES GENERALES
# ──────────────────────────────────────────────────────────────────────────────
def to_plain(x):
    """Convierte estructuras Secrets/YAML a dict/list planos."""
    if isinstance(x, Mapping):
        return {k: to_plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_plain(v) for v in x]
    return x


def render_logo_left(path: str, height_px: int = 120):
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:flex-start;">'
            f'<img src="data:image/png;base64,{b64}" alt="Logo" style="height:{height_px}px;"></div>',
            unsafe_allow_html=True
        )
    except Exception as e:
        st.warning(f"No se pudo cargar el logo: {e}")


def show_sidebar_logo():
    try:
        if os.path.isfile(LOGO_PATH):
            st.sidebar.image(LOGO_PATH, use_container_width=True)
        else:
            st.sidebar.info("Sube 'medidatarips_logo.png' a la carpeta de la app.")
    except Exception as e:
        st.sidebar.warning(f"No pude mostrar el logo: {e}")

# ★ NUEVO: serializador seguro para JSON (numpy/pandas -> tipos nativos)
def json_friendly(o):
    if isinstance(o, (np.integer,)):       # np.int64, etc.
        return int(o)
    if isinstance(o, (np.floating,)):      # np.float64, etc.
        return float(o)
    if isinstance(o, (np.bool_,)):         # np.bool_
        return bool(o)
    if isinstance(o, (pd.Timestamp, datetime, date)):
        return o.isoformat()
    if o is pd.NaT:
        return None
    try:
        if pd.isna(o):                     # NaN, NA
            return None
    except Exception:
        pass
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    return str(o)                          # último recurso


# ──────────────────────────────────────────────────────────────────────────────
# 3) AUTENTICACIÓN
# ──────────────────────────────────────────────────────────────────────────────
def load_auth_config():
    # 1) Secrets
    try:
        if "credentials" in st.secrets and "cookie" in st.secrets:
            cfg = {
                "credentials": to_plain(st.secrets["credentials"]),
                "cookie":      to_plain(st.secrets["cookie"]),
            }
            if "preauthorized" in st.secrets:
                cfg["preauthorized"] = to_plain(st.secrets["preauthorized"])
            if "pre_authorized" in st.secrets:
                cfg["pre_authorized"] = to_plain(st.secrets["pre_authorized"])
            return cfg
    except Exception:
        pass
    # 2) YAML local
    try:
        with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
            return to_plain(yaml.load(f, Loader=SafeLoader))
    except FileNotFoundError:
        st.error("No encuentro 'config.yaml' y no hay 'st.secrets'. Sube uno de los dos.")
        st.stop()
    except Exception as e:
        st.error("Error leyendo 'config.yaml'. Revisa sintaxis.")
        st.exception(e)
        st.stop()


def build_authenticator(config: dict):
    if "credentials" not in config or "cookie" not in config:
        st.error("Config inválida. Faltan 'credentials' o 'cookie'.")
        st.stop()

    # normaliza usernames a minúsculas
    if "usernames" in config.get("credentials", {}):
        config["credentials"]["usernames"] = {
            str(k).strip().lower(): v for k, v in config["credentials"]["usernames"].items()
        }

    cookie = config["cookie"]
    creds = config["credentials"]
    pre   = config.get("preauthorized") or config.get("pre_authorized") or {}

    # algunos config entregan dict con 'emails', otros lista directa
    pre_emails = pre.get("emails", []) if isinstance(pre, dict) else pre

    # 0.3.x: keywords con 'key' y 'preauthorized'
    try:
        return stauth.Authenticate(
            credentials=creds,
            cookie_name=cookie["name"],
            key=cookie["key"],  # clave correcta para 0.3.x
            cookie_expiry_days=float(cookie["expiry_days"]),
            preauthorized=pre if isinstance(pre, dict) else {"emails": pre_emails},
        )
    except TypeError:
        # 0.2.x: firma posicional
        return stauth.Authenticate(
            creds,
            cookie["name"],
            cookie["key"],
            float(cookie["expiry_days"]),
            pre_emails,
        )


# ──────────────────────────────────────────────────────────────────────────────
# 4) DOMINIO RIPS + TRANSFORMACIONES
# ──────────────────────────────────────────────────────────────────────────────
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

        if k == "codMunicipioResidencia":
            s = str(v).strip()
            s = re.sub(r"\.0$", "", s)
            s = re.sub(r"\D", "", s)
            limpio[k] = s.zfill(5) if s else None
            continue

        if k in CAMPOS_NUMERICOS:
            try:
                if isinstance(v, str) and v.strip() == "":
                    limpio[k] = None
                else:
                    fv = float(v)
                    limpio[k] = int(fv) if fv.is_integer() else fv
            except Exception:
                limpio[k] = None
        elif k in CAMPOS_CODIGOS:
            s = str(v).strip()
            s = re.sub(r"\.0$", "", s)
            limpio[k] = s.zfill(2) if s else None
        else:
            limpio[k] = v.strip() if isinstance(v, str) else str(v).strip()
    return limpio


def json_to_excel(files, tipo_factura):
    datos = {tipo: [] for tipo in ["usuarios"] + list(set([s.lower() for s in TIPOS_SERVICIOS]))}
    for archivo in files:
        try:
            data = json.load(archivo)
        except Exception as e:
            st.error(f"Archivo JSON inválido: {getattr(archivo,'name','<sin nombre>')}")
            st.exception(e)
            return None

        num_factura = data.get("numFactura", "SIN_FACTURA")
        archivo_origen = os.path.splitext(getattr(archivo, "name", "archivo"))[0]
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
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            if registros:
                df = pd.DataFrame(registros)
                sheet = tipo.capitalize()[:31]
                df.to_excel(writer, sheet_name=sheet, index=False)
    output.seek(0)
    return output


def excel_to_json(archivo_excel, tipo_factura, nit_obligado):
    try:
        xlsx = pd.read_excel(archivo_excel, sheet_name=None)
    except Exception as e:
        st.error("No pude leer el Excel. Verifica formato y hojas.")
        st.exception(e)
        return None

    dataframes = {str(k).lower(): v for k, v in xlsx.items()}
    if "usuarios" not in dataframes:
        st.error("❌ El archivo no contiene una hoja llamada 'usuarios'.")
        return None

    # ★ BLINDAJE: evita NaN/NaT desde el inicio (opcional pero sano)
    for k, df in dataframes.items():
        dataframes[k] = df.where(pd.notna(df), None)

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
        # ★ CLAVE: usar default=json_friendly
        return {
            "tipo": "único",
            "contenido": json.dumps(salida_json, ensure_ascii=False, indent=2, default=json_friendly),
            "nombre": f"Factura_RIPS_{tipo_factura}.json"
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
                    registros = df_tipo[(df_tipo["numFactura"] == factura) & (df_tipo["documento_usuario"] == doc)]
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
            # ★ CLAVE: usar default=json_friendly aquí también
            salida_archivos[f"{factura}_RIPS.json"] = json.dumps(
                salida_json, ensure_ascii=False, indent=2, default=json_friendly
            )

        return {"tipo": "zip", "contenido": salida_archivos}


# ──────────────────────────────────────────────────────────────────────────────
# 5) UI PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
def main():
    # Auth
    config = load_auth_config()
    authenticator = build_authenticator(config)

    # login (firma 0.2.x / 0.3.x)
    login_params = list(_inspect.signature(authenticator.login).parameters.keys())
    if login_params and login_params[0] == "location":
        name, auth_status, username = authenticator.login("main", "🔐 Iniciar sesión")
    else:
        name, auth_status, username = authenticator.login("🔐 Iniciar sesión", "main")

    if auth_status is False:
        st.error("❌ Usuario o contraseña incorrectos.")
        st.stop()
    elif auth_status is None:
        st.warning("Por favor ingresa tus credenciales.")
        st.stop()

    # logout
    logout_params = list(_inspect.signature(authenticator.logout).parameters.keys())
    if logout_params and logout_params[0] == "button_name":
        authenticator.logout("🚪 Cerrar sesión", "sidebar")
    elif "location" in logout_params:
        authenticator.logout(location="sidebar")
    else:
        authenticator.logout("🚪 Cerrar sesión")

    # UI
    show_sidebar_logo()
    render_logo_left(LOGO_PATH, height_px=90)
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
            if excel_data:
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=excel_data,
                    file_name=f"RIPS_Consolidado_{tipo_factura}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

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
                    file_name=resultado["nombre"],
                    mime="application/json"
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
                    file_name="RIPS_Evento_JSONs.zip",
                    mime="application/zip"
                )


# ──────────────────────────────────────────────────────────────────────────────
# 6) BOOT CON AIRBAG
# ──────────────────────────────────────────────────────────────────────────────
guard(main)







