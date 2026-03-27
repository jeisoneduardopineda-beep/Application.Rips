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
st.markdown("<style>.block-container{padding-top:1.2rem}</style>", unsafe_allow_html=True)

# ========================= CONFIG =========================

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
    "codTecnologiaSalud","nomTecnologiaSalud",
    "unidadMedida","formaFarmaceutica","cantidadMedicamento",
    "codProcedimiento","viaIngresoServicioSalud",
    "codComplicacion","codDiagnosticoPrincipalE",
    "condicionDestinoUsuarioEgreso"
}

CAMPOS_NUMERICOS = {
    "vrServicio",
    "valorPagoModerador",
    "consecutivo",
    "codServicio"
}

# ========================= FUNCION CLAVE =========================

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

                # 🔹 TEXTO
                if k in CAMPOS_TEXTO:
                    if v is None or v == "" or str(v).lower() in ["nan", "none"]:
                        diccionario[k] = "null"
                    else:
                        diccionario[k] = str(v)

                # 🔹 NUMERICO
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

                # 🔹 OTROS (NO TOCAR)
                else:
                    if v is None or str(v).lower() in ["nan", "none"]:
                        diccionario[k] = None
                    else:
                        diccionario[k] = v

    return diccionario

# =======================================================

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

# ========================= EXCEL A JSON =========================

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
                        columns=["numFactura", "documento_usuario"],
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

        salida_archivos[f"{factura_str}_RIPS.json"] = json.dumps(
            salida_json,
            ensure_ascii=False,
            indent=2,
            default=json_friendly
        )

    return {"tipo": "zip", "contenido": salida_archivos}

# ========================= MAIN =========================

def main():

    st.subheader("Transformador RIPS PGP & EVENTO")

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

guard(main)
