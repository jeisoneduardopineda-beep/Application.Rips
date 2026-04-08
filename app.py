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

# ========================= 🔥 FORMATO FECHAS =========================

def convertir(k, v):
    if v is None:
        return None

    try:
        # 👉 Si ya es datetime, no lo reproceses
        if isinstance(v, (pd.Timestamp, datetime)):
            dt = v
        else:
            # 👉 Convierte solo si es necesario
            dt = pd.to_datetime(v, errors="coerce")

        if pd.isna(dt):
            return v

        # 👉 SOLO fecha (sin hora)
        if k == "fechaNacimiento":
            return dt.strftime("%Y-%m-%d")

        # 👉 Fecha con hora (mantiene la hora real)
        if k in ["fechaInicioAtencion","fechaDispensAdmon","fechaEgreso","fechaSuministroTecnologia"]:
            return dt.strftime("%Y-%m-%d %H:%M")

        return v

    except:
        return v

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
def _to_str_preserve(v):
    if v is None:
        return None
    s = str(v)
    if s.lower() in {"nan", "none", ""}:
        return None
    return s
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

        # 🔥 AQUÍ ESTÁ TU AJUSTE
        salida_json = formatear_fechas(salida_json)

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

def main():

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        login()
        return

    st.sidebar.write(f"Usuario: {st.session_state['usuario']}")

    if st.sidebar.button("Cerrar sesión"):
        st.session_state["autenticado"] = False
        st.rerun()

    st.subheader("Transformador RIPS PGP & EVENTO")

    modo = st.radio(
        "Tipo de conversión",
        [
            "JSON ➜ Excel (PGP-CAPITA)",
            "Excel ➜ JSON (PGP-CAPITA)",
            "JSON ➜ Excel (Evento)",
            "Excel ➜ JSON (Evento)"
        ]
    )

    nit_obligado = st.text_input("NIT obligado", value="900364721")

    resultado = None

    if "JSON ➜ Excel" in modo:

        archivos = st.file_uploader("Sube JSON", type=["json"], accept_multiple_files=True)

        if archivos and st.button("Convertir"):

            tipo_factura = "PGP" if "PGP-CAPITA" in modo else "EVENTO"

            excel_data = json_to_excel(archivos, tipo_factura)

            st.download_button(
                "Descargar Excel",
                data=excel_data,
                file_name=f"RIPS_Consolidado_{tipo_factura}.xlsx"
            )

    elif "Excel ➜ JSON" in modo:

        archivo_excel = st.file_uploader("Sube Excel", type=["xlsx"])

        if archivo_excel and st.button("Convertir"):

            tipo_factura = "PGP" if "PGP-CAPITA" in modo else "EVENTO"

            resultado = excel_to_json(archivo_excel, tipo_factura, nit_obligado)

        if resultado:

            if resultado["tipo"] == "único":

                st.download_button(
                    "Descargar JSON",
                    data=resultado["contenido"].encode("utf-8"),
                    file_name=resultado["nombre"]
                )

            else:

                buffer = BytesIO()

                with zipfile.ZipFile(buffer, "w") as zipf:

                    for nombre, contenido in resultado["contenido"].items():
                        zipf.writestr(nombre, contenido)

                buffer.seek(0)

                st.download_button(
                    "Descargar ZIP",
                    data=buffer,
                    file_name="RIPS_Evento_JSONs.zip"
                )

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Excepción en tiempo de ejecución")
        st.code("".join(traceback.format_exception(e)), language="python")
        st.stop()

guard(main)
