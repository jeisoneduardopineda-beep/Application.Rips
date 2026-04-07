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
    "vrServicio",
    "valorPagoModerador",
    "consecutivo",
    "codServicio",
    "concentracionMedicamento",
    "unidadMinDispensa",
    "cantidadMedicamento",
    "diasTratamiento",
    "vrUnitMedicamento",
    "unidadMedida",
    "cantidadOS",
    "vrUnitOS"
}

# ========================= FUNCION TIPADO =========================

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
                    if v is None or v == "" or str(v).lower() in ["nan", "none"]:
                        diccionario[k] = None
                    else:
                        diccionario[k] = str(v)

                elif k in CAMPOS_NUMERICOS:
                    try:
                        if v is None or v == "" or str(v).lower() in ["nan", "none"]:
                            diccionario[k] = None
                        else:
                            if "." in str(v):
                                diccionario[k] = float(v)
                            else:
                                diccionario[k] = int(v)
                    except:
                        diccionario[k] = None

                else:
                    if v is None or str(v).lower() in ["nan", "none"]:
                        diccionario[k] = None
                    else:
                        diccionario[k] = v

    return diccionario


# ========================= 🔥 FUNCION AGREGADA =========================

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

            # ORDEN SOLO PARA PROCEDIMIENTOS
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

# ========================= UTILIDADES =========================

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

def _to_str_preserve(v):
    if v is None:
        return None
    s = str(v)
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

# ========================= JSON ➜ EXCEL =========================
# (SIN CAMBIOS)

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    dataframes = {str(k).lower(): v for k, v in xlsx.items()}

    if "usuarios" not in dataframes:
        st.error("El Excel no contiene hoja usuarios")
        return None

    for k, df in dataframes.items():
        df = df.where(pd.notna(df), None)
        dataframes[k] = df

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
            doc = usuario_dict.get("numDocumentoIdentificacion") or usuario_dict.get("documento_usuario")

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
                        columns=["numFactura", "documento_usuario", "archivo_origen"],
                        errors="ignore"
                    )

                    registros_limpios = [r.to_dict() for _, r in registros.iterrows()]
                    tipo_json = MAPA_SERVICIOS_JSON.get(tipo.lower(), tipo)
                    servicios_dict[tipo_json] = registros_limpios

            usuario_limpio["servicios"] = servicios_dict
            usuarios_final.append(usuario_limpio)

        salida_json = forzar_tipos({
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura_str,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        })

        # 🔥 AQUI SE APLICA TU AJUSTE
        salida_json = ajustar_fechas_y_procedimientos(salida_json)

        salida_archivos[f"{factura_str}_RIPS.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2,
            default=json_friendly
        )

    if tipo_factura == "PGP":
        contenido = list(salida_archivos.values())[0]
        return {
            "tipo": "único",
            "contenido": contenido,
            "nombre": f"Factura_RIPS_{tipo_factura}.json"
        }

    return {"tipo": "zip", "contenido": salida_archivos}

# ========================= MAIN =========================
# (SIN CAMBIOS)

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Excepción en tiempo de ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()

guard(main)
