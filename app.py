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

# ========================= TIPOS =========================

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
                    diccionario[k] = None if not v else str(v)
                elif k in CAMPOS_NUMERICOS:
                    try:
                        diccionario[k] = None if not v else int(float(v))
                    except:
                        diccionario[k] = None
                else:
                    diccionario[k] = None if not v else v
    return diccionario

# ========================= FORMATO FECHAS + ORDEN =========================

def ajustar_fechas_y_procedimientos(data):

    def convertir(k, v):
        if not v or "fecha" not in k.lower():
            return v
        try:
            dt = pd.to_datetime(v, errors="coerce")
            if pd.isna(dt):
                return None

            if k == "fechaNacimiento":
                return dt.strftime("%Y-%m-%d")

            if k in ["fechaInicioAtencion","fechaDispensAdmon","fechaEgreso"]:
                return dt.strftime("%Y-%m-%d-%H:%M")

            return v
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

            # ORDEN PROCEDIMIENTOS
            if "codProcedimiento" in nuevo:
                orden = [
                    "codPrestador",
                    "fechaInicioAtencion",
                    "idMIPRES",
                    "numAutorizacion",
                    "codProcedimiento"
                ]
                nuevo = {k: nuevo.get(k) for k in orden if k in nuevo} | {
                    k: v for k, v in nuevo.items() if k not in orden
                }

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

        for _, usuario in usuarios_df[usuarios_df["numFactura"] == factura].iterrows():

            usuario_dict = usuario.to_dict()
            doc = usuario_dict.get("numDocumentoIdentificacion")

            servicios_dict = {}

            for tipo in dataframes:
                if tipo == "usuarios":
                    continue

                df_tipo = dataframes[tipo]

                registros = df_tipo[
                    (df_tipo["numFactura"] == factura) &
                    (df_tipo["documento_usuario"] == doc)
                ]

                if not registros.empty:
                    registros = registros.drop(
                        columns=["numFactura","documento_usuario","archivo_origen"],
                        errors="ignore"
                    )
                    servicios_dict[tipo] = [r.to_dict() for _, r in registros.iterrows()]

            usuario_dict["servicios"] = servicios_dict
            usuarios_final.append(usuario_dict)

        salida_json = forzar_tipos({
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        })

        # 🔥 AQUI SE APLICA TODO
        salida_json = ajustar_fechas_y_procedimientos(salida_json)

        salida_archivos[f"{factura}.json"] = json.dumps(salida_json, indent=2, ensure_ascii=False)

    return {
        "tipo": "único",
        "contenido": list(salida_archivos.values())[0],
        "nombre": "RIPS.json"
    }

# ========================= MAIN =========================

def main():

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        login()
        return

    st.subheader("Transformador RIPS")

    archivo_excel = st.file_uploader("Sube Excel", type=["xlsx"])

    if archivo_excel and st.button("Convertir"):

        resultado = excel_to_json(archivo_excel, "PGP", "900364721")

        st.download_button(
            "Descargar JSON",
            data=resultado["contenido"].encode("utf-8"),
            file_name="rips.json"
        )

main()
