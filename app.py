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

# ========================= ORDEN SERVICIOS =========================

ORDEN_SERVICIOS = {
    "consultas": [...],  # (lo dejo abreviado aquí por espacio, pero en tu código pega TODO igual que lo enviaste)
    "procedimientos": [...],
    "urgencias": [...],
    "hospitalizacion": [...],
    "reciennacidos": [...],
    "medicamentos": [...],
    "otrosservicios": [...]
}

def ordenar_campos_servicios(tipo, lista_registros):
    orden = ORDEN_SERVICIOS.get(tipo.lower())
    if not orden:
        return lista_registros

    salida = []
    for reg in lista_registros:
        nuevo = {}

        for campo in orden:
            nuevo[campo] = reg.get(campo)

        for k, v in reg.items():
            if k not in nuevo:
                nuevo[k] = v

        salida.append(nuevo)

    return salida

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

# ========================= CONFIG =========================

CAMPOS_TEXTO = {...}  # igual que tu código
CAMPOS_NUMERICOS = {...}

# ========================= TIPADO =========================

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
    return diccionario

# ========================= FECHAS =========================

def formatear_fechas(diccionario):
    if isinstance(diccionario, dict):
        for k, v in diccionario.items():
            if isinstance(v, dict):
                diccionario[k] = formatear_fechas(v)
            elif isinstance(v, list):
                diccionario[k] = [formatear_fechas(i) if isinstance(i, dict) else i for i in v]
            else:
                if isinstance(v, (pd.Timestamp, datetime)):
                    diccionario[k] = v.strftime("%Y-%m-%d-%H:%M")
    return diccionario

# ========================= JSON ➜ EXCEL =========================

def json_to_excel(files, tipo_factura):

    datos = {}

    for archivo in files:
        data = json.load(archivo)

        for usuario in data.get("usuarios", []):
            servicios = usuario.get("servicios", {})

            for tipo, registros in servicios.items():
                tipo = tipo.lower()

                registros = ordenar_campos_servicios(tipo, registros)

                if tipo not in datos:
                    datos[tipo] = []

                datos[tipo].extend(registros)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            df = pd.DataFrame(registros)
            df.to_excel(writer, sheet_name=tipo[:31], index=False)

    output.seek(0)
    return output

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    salida = {}

    for hoja, df in xlsx.items():

        registros = [r.to_dict() for _, r in df.iterrows()]
        registros = ordenar_campos_servicios(hoja.lower(), registros)

        salida[hoja] = registros

    resultado = {
        "numDocumentoIdObligado": nit_obligado,
        "numFactura": "FACTURA_PRUEBA",
        "usuarios": [
            {
                "servicios": salida
            }
        ]
    }

    resultado = forzar_tipos(resultado)
    resultado = formatear_fechas(resultado)

    return json.dumps(resultado, indent=2, ensure_ascii=False)

# ========================= MAIN =========================

def main():

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        login()
        return

    modo = st.radio("Modo", ["JSON ➜ Excel", "Excel ➜ JSON"])

    if modo == "JSON ➜ Excel":
        archivos = st.file_uploader("Sube JSON", type=["json"], accept_multiple_files=True)
        if archivos and st.button("Convertir"):
            excel = json_to_excel(archivos, "PGP")
            st.download_button("Descargar", excel, "rips.xlsx")

    else:
        archivo = st.file_uploader("Sube Excel", type=["xlsx"])
        if archivo and st.button("Convertir"):
            json_out = excel_to_json(archivo, "PGP", "900364721")
            st.download_button("Descargar", json_out, "rips.json")

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Error")
        st.code(str(e))

guard(main)
