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
import inspect as _inspect

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


# -------------------------------------------------
# CONTROL DE ERRORES
# -------------------------------------------------

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Excepción en tiempo de ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()


# -------------------------------------------------
# UTILIDADES
# -------------------------------------------------

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
    "hospitalizaciones",
    "urgencias",
    "reciennacidos",
    "medicamentos",
    "otrosServicios",
]


# -------------------------------------------------
# JSON → EXCEL
# -------------------------------------------------

def json_to_excel(files, tipo_factura):

    datos = {tipo: [] for tipo in ["usuarios"] + list(set([s.lower() for s in TIPOS_SERVICIOS]))}

    for archivo in files:

        try:
            data = json.load(archivo)
        except Exception as e:
            st.error(f"Archivo JSON inválido: {archivo.name}")
            st.exception(e)
            return None

        num_factura = _to_str_preserve(data.get("numFactura", "SIN_FACTURA"))
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

                tipo = tipo.lower()

                if tipo in datos:

                    for reg in registros:

                        reg = reg.copy()
                        reg["numFactura"] = num_factura
                        reg["documento_usuario"] = usuario.get("numDocumentoIdentificacion")
                        reg["archivo_origen"] = archivo_origen

                        datos[tipo].append(reg)

    output = BytesIO()

    hojas_creadas = 0

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        for tipo, registros in datos.items():

            if registros:

                df = pd.DataFrame(registros)

                if not df.empty:

                    sheet = tipo.capitalize()[:31]

                    df.to_excel(writer, sheet_name=sheet, index=False)

                    hojas_creadas += 1

        if hojas_creadas == 0:

            df = pd.DataFrame({
                "mensaje": ["No se encontraron datos válidos en los JSON"]
            })

            df.to_excel(writer, sheet_name="Info", index=False)

    output.seek(0)

    return output


# -------------------------------------------------
# EXCEL → JSON
# -------------------------------------------------

def excel_to_json(file, nit_obligado):

    xls = pd.ExcelFile(file)

    if "Usuarios" not in xls.sheet_names:
        st.error("El Excel debe contener la hoja 'Usuarios'")
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


# -------------------------------------------------
# INTERFAZ
# -------------------------------------------------

def main():

    st.subheader("📄 Transformador RIPS MODALIDAD: PGP, CAPITA y EVENTO")

    modo = st.radio(
        "Selecciona el tipo de conversión:",
        [
            "📥 JSON ➜ Excel (PGP-CAPITA)",
            "📤 Excel ➜ JSON (PGP-CAPITA)",
            "📥 JSON ➜ Excel (Evento)",
            "📤 Excel ➜ JSON (Evento)"
        ]
    )

    nit_obligado = st.text_input("🔢 NIT del Obligado a Facturar", value="900364721")

    # JSON → Excel

    if "JSON ➜ Excel" in modo:

        archivos = st.file_uploader(
            "📂 Selecciona uno o varios archivos JSON",
            type=["json"],
            accept_multiple_files=True
        )

        if archivos and st.button("🚀 Convertir a Excel"):

            tipo_factura = "PGP" if "PGP-CAPITA" in modo else "EVENTO"

            excel_data = json_to_excel(archivos, tipo_factura)

            if excel_data:

                st.download_button(
                    "⬇️ Descargar Excel",
                    data=excel_data,
                    file_name=f"RIPS_Consolidado_{tipo_factura}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # Excel → JSON

    if "Excel ➜ JSON" in modo:

        archivo_excel = st.file_uploader(
            "📂 Selecciona archivo Excel",
            type=["xlsx"]
        )

        if archivo_excel and st.button("🚀 Convertir a JSON"):

            json_data = excel_to_json(archivo_excel, nit_obligado)

            if json_data:

                st.download_button(
                    "⬇️ Descargar JSON",
                    data=json_data,
                    file_name="RIPS_generado.json",
                    mime="application/json"
                )


guard(main)
