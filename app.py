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
st.markdown("<style>.block-container{padding-top:1.2rem}</style>", unsafe_allow_html=True)

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

# ========================= CONFIG TIPOS =========================

CAMPOS_TEXTO = {...}
CAMPOS_NUMERICOS = {...}

# ========================= FUNCION TIPADO =========================

def forzar_tipos(diccionario):
    if isinstance(diccionario, dict):
        for k, v in diccionario.items():
            if isinstance(v, dict):
                diccionario[k] = forzar_tipos(v)
            elif isinstance(v, list):
                diccionario[k] = [forzar_tipos(i) if isinstance(i, dict) else i for i in v]
            else:
                if k in CAMPOS_TEXTO:
                    diccionario[k] = None if v in [None,""] else str(v)
                elif k in CAMPOS_NUMERICOS:
                    try:
                        diccionario[k] = None if v in [None,""] else float(v) if "." in str(v) else int(v)
                    except:
                        diccionario[k] = None
                else:
                    diccionario[k] = None if v in [None] else v
    return diccionario

# ========================= UTILIDADES =========================

def json_friendly(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if o is pd.NaT: return None
    try:
        if pd.isna(o): return None
    except: pass
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.strftime("%Y-%m-%d-%H:%M")
    if isinstance(o, date):
        return o.strftime("%Y-%m-%d")
    return o

# 🔥 FIX CRÍTICO
def _to_str_preserve(v):
    if v is None: return None
    s = str(v)
    return None if s.lower() in {"nan","none",""} else s

# ========================= LIMPIAR FECHAS =========================

def limpiar_fechas(diccionario):
    if isinstance(diccionario, dict):
        for k, v in diccionario.items():
            if isinstance(v, dict):
                diccionario[k] = limpiar_fechas(v)
            elif isinstance(v, list):
                diccionario[k] = [limpiar_fechas(i) if isinstance(i, dict) else i for i in v]
            else:
                if isinstance(v, str) and "fecha" in k.lower():
                    if len(v) >= 19: v = v[:16]
                    if " " in v:
                        fecha, hora = v.split(" ")
                    else:
                        fecha, hora = v, None

                    if k == "fechaNacimiento":
                        diccionario[k] = fecha
                    else:
                        diccionario[k] = f"{fecha}-{hora[:5]}" if hora else fecha
    return diccionario

# ========================= ORDEN ESTRUCTURA =========================

ORDEN_SERVICIOS = {
    "consultas":[...],
    "procedimientos":[...],
    "urgencias":[...],
    "hospitalizacion":[...],
    "reciennacidos":[...],
    "medicamentos":[...],
    "otrosservicios":[...]
}

def ordenar_campos_servicios(servicios_dict):
    nuevo = {}
    for tipo, registros in servicios_dict.items():
        orden = ORDEN_SERVICIOS.get(tipo.lower(), [])
        lista = []
        for r in registros:
            ordenado = {k: r.get(k) for k in orden if k in r}
            for k in r:
                if k not in ordenado:
                    ordenado[k] = r[k]
            lista.append(ordenado)
        nuevo[tipo] = lista
    return nuevo

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
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
            usuario_limpio.pop("archivo_origen", None)
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
                        columns=["numFactura","documento_usuario","archivo_origen"],
                        errors="ignore"
                    )

                    registros_limpios = [r.to_dict() for _, r in registros.iterrows()]
                    servicios_dict[tipo] = registros_limpios

            # 🔥 ORDEN AQUÍ
            servicios_dict = ordenar_campos_servicios(servicios_dict)

            usuario_limpio["servicios"] = servicios_dict
            usuarios_final.append(usuario_limpio)

        salida_json = forzar_tipos({
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura_str,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        })

        # 🔥 FECHAS AQUÍ
        salida_json = limpiar_fechas(salida_json)

        salida_archivos[f"{factura_str}_RIPS.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2,
            default=json_friendly
        )

    return {"tipo":"zip","contenido":salida_archivos}
