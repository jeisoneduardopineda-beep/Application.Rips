# -*- coding: utf-8 -*-

import os
import json
import zipfile
from io import BytesIO
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

# ========================= UTILIDADES =========================

def _to_str_preserve(v):
    if v is None:
        return None
    s = str(v)
    if s.lower() in {"nan", "none", ""}:
        return None
    return s

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
    return o

def formatear_fechas(data):

    def convertir(k, v):
        if v is None:
            return None
        try:
            if isinstance(v, (pd.Timestamp, datetime)):
                dt = v
            else:
                dt = pd.to_datetime(v, errors="coerce")

            if pd.isna(dt):
                return v

            if k == "fechaNacimiento":
                return dt.strftime("%Y-%m-%d")

            if k in ["fechaInicioAtencion","fechaDispensAdmon","fechaEgreso","fechaSuministroTecnologia"]:
                return dt.strftime("%Y-%m-%d %H:%M")

            return v
        except:
            return v

    def recorrer(obj):
        if isinstance(obj, dict):
            return {k: recorrer(convertir(k, v)) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [recorrer(i) for i in obj]
        return obj

    return recorrer(data)

# ========================= AUTENTICACION =========================

USUARIOS = {
    "jeison": "jeison1411",
    "facturacion1": "rips2024",
    "admin": "rips2026",
    "auditoria": "audit2024"
}

def login():
    st.title("🔐 Inicio de sesión")

    usuario = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if usuario in USUARIOS and USUARIOS[usuario] == password:
            st.session_state["autenticado"] = True
            st.session_state["usuario"] = usuario
            st.success("Acceso concedido")
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

# ========================= TIPOS =========================

CAMPOS_TEXTO = {
    "numDocumentoIdObligado","numFactura","tipoNota","numNota",
    "tipoDocumentoIdentificacion","numDocumentoIdentificacion"
}

CAMPOS_NUMERICOS = {
    "vrServicio","valorPagoModerador","consecutivo","codServicio"
}

def forzar_tipos(diccionario):
    if isinstance(diccionario, dict):
        for k, v in diccionario.items():

            if isinstance(v, dict):
                diccionario[k] = forzar_tipos(v)

            elif isinstance(v, list):
                diccionario[k] = [forzar_tipos(i) if isinstance(i, dict) else i for i in v]

            else:
                if k in CAMPOS_TEXTO:
                    diccionario[k] = None if v in [None, "", "nan"] else str(v)

                elif k in CAMPOS_NUMERICOS:
                    try:
                        diccionario[k] = None if v in [None, "", "nan"] else float(v)
                    except:
                        diccionario[k] = None

                else:
                    diccionario[k] = None if v in [None, "", "nan"] else v

    return diccionario

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    dataframes = {str(k).lower(): v for k, v in xlsx.items()}

    usuarios_df = dataframes["usuarios"]
    salida_archivos = {}

    facturas = usuarios_df["numFactura"].dropna().unique()

    for factura in facturas:

        factura_str = _to_str_preserve(factura)
        usuarios_final = []

        usuarios_factura = usuarios_df[usuarios_df["numFactura"] == factura_str]

        for _, usuario in usuarios_factura.iterrows():

            usuario_dict = usuario.to_dict()
            usuario_limpio = usuario_dict.copy()

            usuario_limpio.pop("archivo_origen", None)
            usuario_limpio.pop("numFactura", None)

            usuario_limpio["servicios"] = {}
            usuarios_final.append(usuario_limpio)

        salida_json = forzar_tipos({
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura_str,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        })

        salida_json = formatear_fechas(salida_json)

        salida_archivos[f"{factura_str}.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2,
            default=json_friendly
        )

    return {"tipo": "zip", "contenido": salida_archivos}

# ========================= MAIN =========================

def main():

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        login()
        return

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

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Excepción en tiempo de ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()

guard(main)
