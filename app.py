# app.py — robusto para despliegue; muestra errores en pantalla

import os
import json
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

st.caption(f"BUILD_MARK {int(time.time())}")
st.markdown("<style>.block-container{padding-top:1.2rem}</style>", unsafe_allow_html=True)


def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Error en ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()


def to_plain(x):
    if isinstance(x, Mapping):
        return {k: to_plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [to_plain(v) for v in x]
    return x


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

    return str(o)


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

    if s.lower() in {"nan", "none", ""}:
        return None

    return s


TIPOS_SERVICIOS = [
    "consultas",
    "procedimientos",
    "hospitalizacion",
    "urgencias",
    "reciennacidos",
    "medicamentos",
    "otrosservicios"
]


# ---------------------------
# JSON → EXCEL
# ---------------------------

def json_to_excel(files):

    datos = {"usuarios": []}

    for s in TIPOS_SERVICIOS:
        datos[s] = []

    for archivo in files:

        data = json.load(archivo)

        num_factura = _to_str_preserve(data.get("numFactura"))

        for usuario in data.get("usuarios", []):

            servicios = usuario.get("servicios", {})

            u = usuario.copy()
            u.pop("servicios", None)

            datos["usuarios"].append(u)

            for tipo, registros in servicios.items():

                tipo = tipo.lower()

                if tipo in datos:

                    for r in registros:

                        r = r.copy()

                        r["documento_usuario"] = usuario.get(
                            "numDocumentoIdentificacion"
                        )

                        r["numFactura"] = num_factura

                        datos[tipo].append(r)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        for hoja, registros in datos.items():

            if registros:

                df = pd.DataFrame(registros)

                df.to_excel(writer, sheet_name=hoja.capitalize(), index=False)

    output.seek(0)

    return output


# ---------------------------
# EXCEL → JSON
# ---------------------------

def excel_to_json(file, nit_obligado):

    xls = pd.ExcelFile(file)

    if "Usuarios" not in xls.sheet_names:
        st.error("El Excel debe tener hoja 'Usuarios'")
        return None

    usuarios_df = pd.read_excel(xls, "Usuarios")

    usuarios_dict = {}

    for _, row in usuarios_df.iterrows():

        doc = _to_str_preserve(row.get("numDocumentoIdentificacion"))

        usuario = row.dropna().to_dict()

        usuario["servicios"] = {}

        usuarios_dict[doc] = usuario

    for hoja in xls.sheet_names:

        if hoja.lower() == "usuarios":
            continue

        df = pd.read_excel(xls, hoja)

        for _, row in df.iterrows():

            doc = _to_str_preserve(row.get("documento_usuario"))

            if doc not in usuarios_dict:
                continue

            servicio = row.dropna().to_dict()

            servicio.pop("documento_usuario", None)

            tipo = hoja.lower()

            if tipo not in usuarios_dict[doc]["servicios"]:
                usuarios_dict[doc]["servicios"][tipo] = []

            usuarios_dict[doc]["servicios"][tipo].append(servicio)

    estructura = {
        "numDocumentoIdObligado": nit_obligado,
        "numFactura": "SIN_FACTURA",
        "usuarios": list(usuarios_dict.values())
    }

    buffer = BytesIO()

    buffer.write(
        json.dumps(
            to_plain(estructura),
            indent=2,
            ensure_ascii=False,
            default=json_friendly
        ).encode("utf-8")
    )

    buffer.seek(0)

    return buffer


# ---------------------------
# UI
# ---------------------------

def main():

    st.subheader("📄 Transformador RIPS MODALIDAD: PGP, CAPITA y EVENTO")

    modo = st.radio(
        "Selecciona el tipo de conversión:",
        [
            "JSON ➜ Excel",
            "Excel ➜ JSON"
        ]
    )

    nit = st.text_input(
        "NIT del Obligado a Facturar",
        value="900364721"
    )

    # JSON → Excel

    if modo == "JSON ➜ Excel":

        archivos = st.file_uploader(
            "Selecciona JSON",
            type=["json"],
            accept_multiple_files=True
        )

        if archivos and st.button("Convertir"):

            excel = json_to_excel(archivos)

            st.download_button(
                "Descargar Excel",
                excel,
                "RIPS_consolidado.xlsx"
            )

    # Excel → JSON

    if modo == "Excel ➜ JSON":

        archivo_excel = st.file_uploader(
            "Selecciona Excel",
            type=["xlsx"]
        )

        if archivo_excel and st.button("Convertir"):

            json_data = excel_to_json(archivo_excel, nit)

            st.download_button(
                "Descargar JSON",
                json_data,
                "RIPS.json"
            )


guard(main)
