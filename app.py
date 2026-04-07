# -*- coding: utf-8 -*-

import os
import json
import zipfile
from io import BytesIO
import traceback
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Transformador RIPS PGP & EVENTO", layout="centered")

@st.cache_data(show_spinner=False)
def leer_excel_cached(file):
    return pd.read_excel(file, sheet_name=None, dtype=str)

# ========================= LOGIN =========================

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

# ========================= ORDEN =========================

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

def ordenar_campos(tipo, registros):
    orden = ORDEN_SERVICIOS.get(tipo.lower())
    if not orden:
        return registros

    salida = []

    for reg in registros:
        if not isinstance(reg, dict):
            continue

        nuevo = {}

        for campo in orden:
            nuevo[campo] = reg.get(campo)

        for k, v in reg.items():
            if k not in nuevo:
                nuevo[k] = v

        salida.append(nuevo)

    return salida

# ========================= TIPOS =========================

CAMPOS_NUMERICOS = {
    "vrServicio","valorPagoModerador","consecutivo","codServicio",
    "cantidadMedicamento","diasTratamiento","vrUnitMedicamento",
    "cantidadOS","vrUnitOS"
}

def convertir(k, v):
    if v is None or str(v).lower() in ["nan", "none", ""]:
        return None

    if k in CAMPOS_NUMERICOS:
        try:
            return float(v) if "." in str(v) else int(v)
        except:
            return None

    return str(v)

def forzar_tipos(data):
    if isinstance(data, dict):
        return {k: forzar_tipos(v) if isinstance(v, (dict, list)) else convertir(k, v) for k, v in data.items()}
    elif isinstance(data, list):
        return [forzar_tipos(i) for i in data]
    return data

# ========================= FECHAS =========================

def convertir_fecha(k, v):

    if v is None:
        return None

    if "fecha" not in k.lower():
        return v

    try:
        v = str(v).strip()

        if v.lower() in ["nan", "none", ""]:
            return None

        fecha = pd.to_datetime(v, errors="coerce")

        if pd.isna(fecha):
            return None

        # 🔴 CAMPOS CON HORA
        if k in ["fechaDispensAdmon", "fechaInicioAtencion", "fechaEgreso"]:
            return fecha.strftime("%Y-%m-%d-%H-%M")

        # 🟢 SOLO FECHA
        if k == "fechaNacimiento":
            return fecha.strftime("%Y-%m-%d")

        # 🔵 OTROS CAMPOS DE FECHA (fallback)
        return fecha.strftime("%Y-%m-%d")

    except:
        return None

def formatear_fechas(data):
    if isinstance(data, dict):
        return {k: formatear_fechas(v) if isinstance(v, (dict, list)) else convertir_fecha(k, v) for k, v in data.items()}
    elif isinstance(data, list):
        return [formatear_fechas(i) for i in data]
    return data

# ========================= JSON ➜ EXCEL =========================

def json_to_excel(files, tipo_factura):

    datos = {}

    for archivo in files:
        data = json.load(archivo)
        num_factura = data.get("numFactura")

        for usuario in data.get("usuarios", []):
            servicios = usuario.get("servicios", {})

            for tipo, registros in servicios.items():

                tipo = tipo.lower()

                if tipo not in datos:
                    datos[tipo] = []

                registros = ordenar_campos(tipo, registros)

                for reg in registros:
                    if isinstance(reg, dict):
                        reg["numFactura"] = num_factura
                        datos[tipo].append(reg)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            df = pd.DataFrame(registros)
            df.to_excel(writer, sheet_name=tipo[:31], index=False)

    output.seek(0)
    return output

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit):

    try:
    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
except Exception as e:
    st.error(f"Error leyendo Excel: {e}")
    return None
    dfs = {k.lower(): v.where(pd.notna(v), None) for k, v in xlsx.items()}

    usuarios = dfs.get("usuarios")

    if usuarios is None:
        st.error("El Excel no tiene hoja 'usuarios'")
        return None

    salida = {}
    facturas = usuarios["numFactura"].dropna().unique()

    for factura in facturas:

        usuarios_final = []

        usuarios_f = usuarios[usuarios["numFactura"] == factura]

        for _, u in usuarios_f.iterrows():

            u_dict = u.to_dict()
            u_dict.pop("numFactura", None)

            servicios = {}

            for tipo, df in dfs.items():

                if tipo == "usuarios":
                    continue

                reg = df[df["numFactura"] == factura]

                if not reg.empty:
                    lista = [r.to_dict() for _, r in reg.iterrows()]
                    lista = ordenar_campos(tipo, lista)
                    servicios[tipo] = lista

            u_dict["servicios"] = servicios
            usuarios_final.append(u_dict)

        salida_json = {
            "numDocumentoIdObligado": nit,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        }

        salida_json = forzar_tipos(salida_json)
        salida_json = formatear_fechas(salida_json)

        salida[f"{factura}.json"] = json.dumps(salida_json, indent=2, ensure_ascii=False)

    if tipo_factura == "PGP":
        return {"tipo": "unico", "contenido": list(salida.values())[0], "nombre": "rips.json"}

    return {"tipo": "zip", "contenido": salida}

def main():
    st.title("APP FUNCIONANDO")
