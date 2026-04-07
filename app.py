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

CAMPOS_TEXTO = {
    "numDocumentoIdObligado","numFactura","tipoNota","numNota",
    "tipoDocumentoIdentificacion","numDocumentoIdentificacion","tipoUsuario",
    "codSexo","codPaisResidencia","codMunicipioResidencia",
    "codZonaTerritorialResidencia","incapacidad",
    "numAutorizacion","codConsulta","modalidadGrupoServicioTecSal",
    "grupoServicios","finalidadTecnologiaSalud",
    "causaMotivoAtencion","codDiagnosticoPrincipal",
    "codDiagnosticoRelacionado1","codDiagnosticoRelacionado2",
    "codDiagnosticoRelacionado3","tipoDiagnosticoPrincipal",
    "conceptoRecaudo","numFEVPagoModerador","idMIPRES",
    "codDiagnosticoRelacionado","tipoMedicamento",
    "codTecnologiaSalud","nomTecnologiaSalud","formaFarmaceutica",
    "codProcedimiento","viaIngresoServicioSalud",
    "codComplicacion","codDiagnosticoPrincipalE",
    "condicionDestinoUsuarioEgreso"
}

CAMPOS_NUMERICOS = {
    "vrServicio","valorPagoModerador","consecutivo","codServicio",
    "concentracionMedicamento","unidadMinDispensa","cantidadMedicamento",
    "diasTratamiento","vrUnitMedicamento","unidadMedida",
    "cantidadOS","vrUnitOS"
}

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
                    if v is None or v == "" or str(v).lower() in ["nan","none"]:
                        diccionario[k] = None
                    else:
                        diccionario[k] = str(v)

                elif k in CAMPOS_NUMERICOS:
                    try:
                        if v is None or v == "" or str(v).lower() in ["nan","none"]:
                            diccionario[k] = None
                        else:
                            diccionario[k] = float(v) if "." in str(v) else int(v)
                    except:
                        diccionario[k] = None
                else:
                    diccionario[k] = None if v is None else v

    return diccionario

# ========================= 🔥 AJUSTE FECHAS =========================

def ajustar_fechas(data):

    def convertir(campo, valor):

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

                v = convertir(k, v)

                if isinstance(v, dict):
                    v = recorrer(v)

                elif isinstance(v, list):
                    v = [recorrer(i) if isinstance(i, dict) else i for i in v]

                nuevo[k] = v

            return nuevo

        return obj

    return recorrer(data)

# ========================= UTILIDADES =========================

def json_friendly(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if o is pd.NaT: return None
    if isinstance(o, (pd.Timestamp, datetime)): return o.strftime("%Y-%m-%d %H:%M")
    if isinstance(o, date): return o.strftime("%Y-%m-%d")
    return o

def _to_str_preserve(v):
    if v is None: return None
    s = str(v)
    return None if s.lower() in {"nan","none",""} else s

# ========================= JSON ➜ EXCEL =========================

def json_to_excel(files, tipo_factura):

    datos = {"usuarios":[]}

    for archivo in files:

        data = json.load(archivo)
        num_factura = _to_str_preserve(data.get("numFactura"))

        for usuario in data.get("usuarios",[]):

            usuario_limpio = usuario.copy()
            usuario_limpio.pop("servicios",None)
            usuario_limpio["numFactura"] = num_factura

            datos["usuarios"].append(usuario_limpio)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df = pd.DataFrame(datos["usuarios"])
        df.to_excel(writer, sheet_name="Usuarios", index=False)

    output.seek(0)
    return output

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    usuarios_df = xlsx["usuarios"]

    salida_archivos = {}

    for factura in usuarios_df["numFactura"].dropna().unique():

        usuarios_final = []

        for _, usuario in usuarios_df.iterrows():

            usuario_dict = usuario.to_dict()
            usuario_dict.pop("numFactura",None)

            usuarios_final.append(usuario_dict)

        salida_json = forzar_tipos({
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        })

        # 🔥 AQUÍ SE APLICA EL AJUSTE
        salida_json = ajustar_fechas(salida_json)

        salida_archivos[f"{factura}.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2,
            default=json_friendly
        )

    return {"tipo":"zip","contenido":salida_archivos}

# ========================= MAIN =========================

def main():

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        login()
        return

    st.subheader("Transformador RIPS")

    modo = st.radio("Tipo", ["Excel ➜ JSON"])

    nit = st.text_input("NIT")

    archivo = st.file_uploader("Excel", type=["xlsx"])

    if archivo and st.button("Convertir"):

        resultado = excel_to_json(archivo,"PGP",nit)

        for nombre, contenido in resultado["contenido"].items():
            st.download_button(nombre,contenido,nombre)

# ========================= GUARD =========================

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Error en ejecución")
        st.code(traceback.format_exc())

guard(main)
