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

# ========================= ORDEN SERVICIOS =========================

ORDEN_SERVICIOS = {
    "consultas": [
        "codPrestador","fechaInicioAtencion","numAutorizacion","codConsulta",
        "modalidadGrupoServicioTecSal","grupoServicios","codServicio",
        "finalidadTecnologiaSalud","causaMotivoAtencion","codDiagnosticoPrincipal",
        "codDiagnosticoRelacionado1","codDiagnosticoRelacionado2","codDiagnosticoRelacionado3",
        "tipoDiagnosticoPrincipal","tipoDocumentoIdentificacion","numDocumentoIdentificacion",
        "vrServicio","conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"
    ],
    "procedimientos": [
        "codPrestador","fechaInicioAtencion","idMIPRES","numAutorizacion","codProcedimiento",
        "viaIngresoServicioSalud","modalidadGrupoServicioTecSal","grupoServicios","codServicio",
        "finalidadTecnologiaSalud","tipoDocumentoIdentificacion","numDocumentoIdentificacion",
        "codDiagnosticoPrincipal","codDiagnosticoRelacionado","codComplicacion","vrServicio",
        "conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"
    ],
    "urgencias": [
        "codPrestador","fechaInicioAtencion","causaMotivoAtencion","codDiagnosticoPrincipal",
        "codDiagnosticoPrincipalE","codDiagnosticoRelacionadoE1","codDiagnosticoRelacionadoE2",
        "codDiagnosticoRelacionadoE3","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte",
        "fechaEgreso","consecutivo"
    ],
    "hospitalizacion": [
        "codPrestador","viaIngresoServicioSalud","fechaInicioAtencion","numAutorizacion",
        "causaMotivoAtencion","codDiagnosticoPrincipal","codDiagnosticoPrincipalE",
        "codDiagnosticoRelacionadoE1","codDiagnosticoRelacionadoE2","codDiagnosticoRelacionadoE3",
        "codComplicacion","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso",
        "consecutivo"
    ],
    "reciennacidos": [
        "codPrestador","tipoDocumentoIdentificacion","numDocumentoIdentificacion","fechaNacimiento",
        "edadGestacional","numConsultasCPrenatal","codSexoBiologico","peso","codDiagnosticoPrincipal",
        "condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso","consecutivo"
    ],
    "medicamentos": [
        "codPrestador","numAutorizacion","idMIPRES","fechaDispensAdmon","codDiagnosticoPrincipal",
        "codDiagnosticoRelacionado","tipoMedicamento","codTecnologiaSalud","nomTecnologiaSalud",
        "concentracionMedicamento","unidadMedida","formaFarmaceutica","unidadMinDispensa",
        "cantidadMedicamento","diasTratamiento","tipoDocumentoIdentificacion",
        "numDocumentoIdentificacion","vrUnitMedicamento","vrServicio","conceptoRecaudo",
        "valorPagoModerador","numFEVPagoModerador","consecutivo"
    ],
    "otrosservicios": [
        "codPrestador","numAutorizacion","idMIPRES","fechaSuministroTecnologia","tipoOS",
        "codTecnologiaSalud","nomTecnologiaSalud","cantidadOS","tipoDocumentoIdentificacion",
        "numDocumentoIdentificacion","vrUnitOS","vrServicio","conceptoRecaudo",
        "valorPagoModerador","numFEVPagoModerador","consecutivo"
    ]
}

def ordenar_campos_servicios(tipo, registros):
    orden = ORDEN_SERVICIOS.get(tipo.lower())
    if not orden:
        return registros

    salida = []
    for reg in registros:
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

# ========================= CONFIG TIPOS =========================

CAMPOS_TEXTO = {...}  # (igual que tu código original)
CAMPOS_NUMERICOS = {...}

# ========================= FUNCIONES ORIGINALES =========================

# (NO las toqué, solo inserté el orden donde corresponde)

# ========================= JSON ➜ EXCEL =========================

def json_to_excel(files, tipo_factura):

    datos = {tipo: [] for tipo in ["usuarios"] + list(set([s.lower() for s in TIPOS_SERVICIOS]))}

    for archivo in files:

        data = json.load(archivo)
        num_factura = _to_str_preserve(data.get("numFactura"))
        archivo_origen = os.path.splitext(getattr(archivo, "name", "archivo"))[0]
        usuarios = data.get("usuarios", [])

        for usuario in usuarios:

            servicios = usuario.get("servicios", {})
            usuario_limpio = usuario.copy()
            usuario_limpio.pop("servicios", None)

            usuario_limpio["archivo_origen"] = archivo_origen
            usuario_limpio["numFactura"] = num_factura

            datos["usuarios"].append(usuario_limpio)

            for tipo, registros in servicios.items():

                tipo_normalizado = tipo.lower()

                if tipo_normalizado in datos:

                    for reg in registros:
                        reg = reg.copy()
                        reg["numFactura"] = num_factura
                        reg["documento_usuario"] = usuario.get("numDocumentoIdentificacion")
                        reg["archivo_origen"] = archivo_origen

                        datos[tipo_normalizado].append(reg)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            if registros:
                registros = ordenar_campos_servicios(tipo, registros)
                df = pd.DataFrame(registros)
                sheet = tipo.capitalize()[:31]
                df.to_excel(writer, sheet_name=sheet, index=False)

    output.seek(0)
    return output

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
                        columns=["numFactura", "documento_usuario", "archivo_origen"],
                        errors="ignore"
                    )

                    registros_limpios = [r.to_dict() for _, r in registros.iterrows()]
                    registros_limpios = ordenar_campos_servicios(tipo, registros_limpios)

                    servicios_dict[tipo] = registros_limpios

            usuario_limpio["servicios"] = servicios_dict
            usuarios_final.append(usuario_limpio)

        salida_json = {
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura_str,
            "usuarios": usuarios_final
        }

        salida_archivos[f"{factura_str}.json"] = json.dumps(salida_json, indent=2, ensure_ascii=False)

    return salida_archivos

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

    if "JSON ➜ Excel" in modo:

    archivos = st.file_uploader(
        "Sube JSON",
        type=["json"],
        accept_multiple_files=True
    )

    if archivos and st.button("Convertir"):

        tipo_factura = "PGP" if "PGP-CAPITA" in modo else "EVENTO"

        excel_data = json_to_excel(archivos, tipo_factura)

        st.download_button(
            "Descargar Excel",
            data=excel_data,
            file_name=f"RIPS_{tipo_factura}.xlsx"
        )

elif "Excel ➜ JSON" in modo:

    archivo_excel = st.file_uploader(
        "Sube Excel",
        type=["xlsx"]
    )

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
