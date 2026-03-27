# app.py — robusto para despliegue

import os
import json
import zipfile
from io import BytesIO
import re
import base64
from collections.abc import Mapping
import time
import traceback

import pandas as pd
import streamlit as st
import numpy as np
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "medidatarips_logo.png")
page_icon = LOGO_PATH if os.path.isfile(LOGO_PATH) else None

st.set_page_config(
    page_title="Transformador RIPS PGP & EVENTO",
    layout="centered",
    page_icon=page_icon
)

# ========================= CAMPOS NUMERICOS =========================
CAMPOS_NUMERICOS = {
    "numDocumentoIdObligado",
    "codPrestador",
    "codPaisOrigen",
    "numDocumentoIdentificacion",
    "cantidadMedicamento",
    "conceptoRecaudo"
}

# ========================= TIPADOR =========================
def tipar_valores(diccionario):
    if isinstance(diccionario, dict):
        for k, v in diccionario.items():

            if isinstance(v, dict):
                diccionario[k] = tipar_valores(v)

            elif isinstance(v, list):
                diccionario[k] = [tipar_valores(i) if isinstance(i, dict) else i for i in v]

            else:
                if k in CAMPOS_NUMERICOS:
                    try:
                        if v is None or v == "":
                            diccionario[k] = None
                        else:
                            diccionario[k] = int(float(v))
                    except:
                        diccionario[k] = None
                else:
                    diccionario[k] = v

    return diccionario

# ========================= JSON FRIENDLY =========================
def json_friendly(o):

    if isinstance(o, (np.integer,)):
        return int(o)

    if isinstance(o, (np.floating,)):
        return float(o)

    if isinstance(o, (np.bool_,)):
        return bool(o)

    if o is pd.NaT:
        return None

    try:
        if pd.isna(o):
            return None
    except:
        pass

    if isinstance(o, (pd.Timestamp, datetime)):
        return o.strftime("%Y-%m-%d %H:%M")

    if isinstance(o, date):
        return o.strftime("%Y-%m-%d")

    return o  # 🔥 ya no convierte todo a string

# ========================= FUNCIONES BASE =========================

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Excepción en tiempo de ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()

def _to_str_preserve(v):

    if v is None:
        return None

    if isinstance(v, (int, np.integer)):
        return str(int(v))

    if isinstance(v, (float, np.floating)):
        if float(v).is_integer():
            return str(int(v))
        return format(float(v), "f").rstrip("0").rstrip(".")

    s = str(v).strip()
    s = re.sub(r"\.0$", "", s)

    if s.lower() in {"nan", "none", ""}:
        return None

    return s

TIPOS_SERVICIOS = [
    "consultas","procedimientos","hospitalizacion","hospitalizaciones",
    "urgencias","reciennacidos","medicamentos","otrosServicios"
]

MAPA_SERVICIOS_JSON = {
    "consultas": "consultas",
    "procedimientos": "procedimientos",
    "hospitalizacion": "hospitalizacion",
    "hospitalizaciones": "hospitalizaciones",
    "urgencias": "urgencias",
    "reciennacidos": "reciennacidos",
    "medicamentos": "medicamentos",
    "otrosservicios": "otrosServicios"
}

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None)
    dataframes = {str(k).lower(): v for k, v in xlsx.items()}

    usuarios_df = dataframes["usuarios"]
    tipos_servicios = [k for k in dataframes if k != "usuarios"]

    salida_archivos = {}

    facturas = usuarios_df["numFactura"].dropna().unique()

    for factura in facturas:

        factura_str = _to_str_preserve(factura)
        usuarios_final = []

        usuarios_factura = usuarios_df[usuarios_df["numFactura"] == factura_str]

        for _, usuario in usuarios_factura.iterrows():

            usuario_dict = usuario.to_dict()
            doc = usuario_dict.get("numDocumentoIdentificacion")

            usuario_limpio = usuario_dict.copy()
            usuario_limpio.pop("numFactura", None)

            servicios_dict = {}

            for tipo in tipos_servicios:

                df_tipo = dataframes[tipo]

                registros = df_tipo[
                    (df_tipo["numFactura"] == factura_str) &
                    (df_tipo["documento_usuario"] == doc)
                ]

                if not registros.empty:

                    registros = registros.drop(
                        columns=["numFactura", "documento_usuario"],
                        errors="ignore"
                    )

                    registros_limpios = [r.to_dict() for _, r in registros.iterrows()]

                    tipo_json = MAPA_SERVICIOS_JSON.get(tipo.lower(), tipo)
                    servicios_dict[tipo_json] = registros_limpios

            usuario_limpio["servicios"] = servicios_dict
            usuarios_final.append(usuario_limpio)

        salida_json = tipar_valores({
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura_str,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        })

        salida_archivos[f"{factura_str}_RIPS.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2,
            default=json_friendly
        )

    return {"tipo": "zip", "contenido": salida_archivos}

# ========================= MAIN =========================

def main():

    st.subheader("Transformador RIPS PGP & EVENTO")

    archivo_excel = st.file_uploader("Sube Excel", type=["xlsx"])

    if archivo_excel and st.button("Convertir"):

        resultado = excel_to_json(archivo_excel, "PGP", "900364721")

        buffer = BytesIO()

        with zipfile.ZipFile(buffer, "w") as zipf:
            for nombre, contenido in resultado["contenido"].items():
                zipf.writestr(nombre, contenido)

        buffer.seek(0)

        st.download_button(
            "Descargar ZIP",
            data=buffer,
            file_name="RIPS_JSON.zip"
        )

guard(main)
