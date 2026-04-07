# -*- coding: utf-8 -*-

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
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

# ========================= TIPOS =========================

CAMPOS_TEXTO = {...}  # (igual que tu código)
CAMPOS_NUMERICOS = {...}

# ========================= TIPADO =========================

def forzar_tipos(diccionario):
    if isinstance(diccionario, dict):
        for k, v in diccionario.items():

            if isinstance(v, dict):
                diccionario[k] = forzar_tipos(v)

            elif isinstance(v, list):
                diccionario[k] = [
                    forzar_tipos(i) if isinstance(i, dict) else i
                    for i in v
                ]

            else:
                if k in CAMPOS_TEXTO:
                    diccionario[k] = None if v in [None, "", "nan"] else str(v)

                elif k in CAMPOS_NUMERICOS:
                    try:
                        diccionario[k] = None if v in [None, "", "nan"] else float(v)
                    except:
                        diccionario[k] = None

                else:
                    diccionario[k] = None if v in [None, "nan"] else v

    return diccionario

# ========================= 🔥 AJUSTES SOLICITADOS =========================

def ajustar_fechas_y_procedimientos(data):

    def formatear_fecha(campo, valor):
        if valor is None:
            return None

        try:
            dt = pd.to_datetime(valor, errors="coerce")

            if pd.isna(dt):
                return None

            if campo == "fechaNacimiento":
                return dt.strftime("%Y-%m-%d")

            if campo in ["fechaInicioAtencion", "fechaDispensAdmon", "fechaEgreso"]:
                return dt.strftime("%Y-%m-%d-%H:%M")

            return valor
        except:
            return None

    def recorrer(obj):

        if isinstance(obj, dict):
            nuevo = {}

            for k, v in obj.items():

                v = formatear_fecha(k, v)

                if isinstance(v, dict):
                    v = recorrer(v)

                elif isinstance(v, list):
                    v = [recorrer(i) if isinstance(i, dict) else i for i in v]

                nuevo[k] = v

            # 🔥 ORDEN DE PROCEDIMIENTOS
            if "codProcedimiento" in nuevo:

                orden = [
                    "codPrestador",
                    "fechaInicioAtencion",
                    "idMIPRES",
                    "numAutorizacion",
                    "codProcedimiento"
                ]

                nuevo_ordenado = {}

                for campo in orden:
                    if campo in nuevo:
                        nuevo_ordenado[campo] = nuevo[campo]

                for k, v in nuevo.items():
                    if k not in nuevo_ordenado:
                        nuevo_ordenado[k] = v

                return nuevo_ordenado

            return nuevo

        return obj

    return recorrer(data)

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    dataframes = {str(k).lower(): v for k, v in xlsx.items()}

    usuarios_df = dataframes["usuarios"]

    salida_archivos = {}

    for factura in usuarios_df["numFactura"].dropna().unique():

        usuarios_final = []

        usuarios_factura = usuarios_df[usuarios_df["numFactura"] == factura]

        for _, usuario in usuarios_factura.iterrows():

            usuario_dict = usuario.to_dict()

            usuario_dict.pop("numFactura", None)

            usuario_dict["servicios"] = {}

            usuarios_final.append(usuario_dict)

        salida_json = {
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        }

        salida_json = forzar_tipos(salida_json)

        # 🔥 AQUÍ TU AJUSTE
        salida_json = ajustar_fechas_y_procedimientos(salida_json)

        salida_archivos[f"{factura}.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2
        )

    return salida_archivos

# ========================= MAIN (ARREGLADO) =========================

def main():

    if not st.session_state.get("autenticado"):
        login()
        return

    st.title("Transformador RIPS")

    modo = st.radio("Tipo de conversión", [
        "Excel ➜ JSON (PGP-CAPITA)"
    ])

    nit = st.text_input("NIT obligado")

    archivo = st.file_uploader("Sube Excel", type=["xlsx"])

    if archivo and st.button("Convertir"):

        resultado = excel_to_json(archivo, "PGP", nit)

        for nombre, contenido in resultado.items():
            st.download_button(
                label=f"Descargar {nombre}",
                data=contenido,
                file_name=nombre
            )

# ========================= GUARD =========================

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Error en ejecución")
        st.code(traceback.format_exc())

guard(main)
