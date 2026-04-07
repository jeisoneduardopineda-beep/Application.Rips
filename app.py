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
    "consultas": ["codPrestador","fechaInicioAtencion","numAutorizacion","codConsulta","modalidadGrupoServicioTecSal","grupoServicios","codServicio","finalidadTecnologiaSalud","causaMotivoAtencion","codDiagnosticoPrincipal","codDiagnosticoRelacionado1","codDiagnosticoRelacionado2","codDiagnosticoRelacionado3","tipoDiagnosticoPrincipal","tipoDocumentoIdentificacion","numDocumentoIdentificacion","vrServicio","conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"],
    "procedimientos": ["codPrestador","fechaInicioAtencion","idMIPRES","numAutorizacion","codProcedimiento","viaIngresoServicioSalud","modalidadGrupoServicioTecSal","grupoServicios","codServicio","finalidadTecnologiaSalud","tipoDocumentoIdentificacion","numDocumentoIdentificacion","codDiagnosticoPrincipal","codDiagnosticoRelacionado","codComplicacion","vrServicio","conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"],
    "urgencias": ["codPrestador","fechaInicioAtencion","causaMotivoAtencion","codDiagnosticoPrincipal","codDiagnosticoPrincipalE","codDiagnosticoRelacionadoE1","codDiagnosticoRelacionadoE2","codDiagnosticoRelacionadoE3","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso","consecutivo"],
    "hospitalizacion": ["codPrestador","viaIngresoServicioSalud","fechaInicioAtencion","numAutorizacion","causaMotivoAtencion","codDiagnosticoPrincipal","codDiagnosticoPrincipalE","codDiagnosticoRelacionadoE1","codDiagnosticoRelacionadoE2","codDiagnosticoRelacionadoE3","codComplicacion","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso","consecutivo"],
    "reciennacidos": ["codPrestador","tipoDocumentoIdentificacion","numDocumentoIdentificacion","fechaNacimiento","edadGestacional","numConsultasCPrenatal","codSexoBiologico","peso","codDiagnosticoPrincipal","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso","consecutivo"],
    "medicamentos": ["codPrestador","numAutorizacion","idMIPRES","fechaDispensAdmon","codDiagnosticoPrincipal","codDiagnosticoRelacionado","tipoMedicamento","codTecnologiaSalud","nomTecnologiaSalud","concentracionMedicamento","unidadMedida","formaFarmaceutica","unidadMinDispensa","cantidadMedicamento","diasTratamiento","tipoDocumentoIdentificacion","numDocumentoIdentificacion","vrUnitMedicamento","vrServicio","conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"],
    "otrosservicios": ["codPrestador","numAutorizacion","idMIPRES","fechaSuministroTecnologia","tipoOS","codTecnologiaSalud","nomTecnologiaSalud","cantidadOS","tipoDocumentoIdentificacion","numDocumentoIdentificacion","vrUnitOS","vrServicio","conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"]
}

def ordenar_campos(tipo, registros):
    orden = ORDEN_SERVICIOS.get(tipo.lower())
    if not orden:
        return registros

    salida = []
    for reg in registros:
        nuevo = {campo: reg.get(campo) for campo in orden}
        nuevo.update({k:v for k,v in reg.items() if k not in nuevo})
        salida.append(nuevo)
    return salida

# ========================= TIPOS =========================

CAMPOS_NUMERICOS = {"vrServicio","valorPagoModerador","consecutivo","codServicio"}

def convertir(k, v):
    if v in [None, "", "nan", "None"]:
        return None
    if k in CAMPOS_NUMERICOS:
        try:
            return float(v) if "." in str(v) else int(v)
        except:
            return None
    return str(v)

def forzar_tipos(data):
    if isinstance(data, dict):
        return {k: forzar_tipos(v) if isinstance(v,(dict,list)) else convertir(k,v) for k,v in data.items()}
    elif isinstance(data, list):
        return [forzar_tipos(i) for i in data]
    return data

# ========================= FECHAS =========================

def convertir_fecha(k,v):
    if v is None:
        return None
    if "fecha" not in k.lower():
        return v
    try:
        fecha = pd.to_datetime(v, errors="coerce")
        if pd.isna(fecha):
            return None
        if k in ["fechaDispensAdmon","fechaInicioAtencion","fechaEgreso"]:
            return fecha.strftime("%Y-%m-%d-%H-%M")
        if k == "fechaNacimiento":
            return fecha.strftime("%Y-%m-%d")
        return fecha.strftime("%Y-%m-%d")
    except:
        return None

def formatear_fechas(data):
    if isinstance(data, dict):
        return {k: formatear_fechas(v) if isinstance(v,(dict,list)) else convertir_fecha(k,v) for k,v in data.items()}
    elif isinstance(data, list):
        return [formatear_fechas(i) for i in data]
    return data

# ========================= CONVERSIONES =========================

def json_to_excel(files, tipo):
    datos = {}
    for archivo in files:
        data = json.load(archivo)
        factura = data.get("numFactura")

        for usuario in data.get("usuarios", []):
            for tipo_s, regs in usuario.get("servicios", {}).items():
                datos.setdefault(tipo_s.lower(), [])
                for r in ordenar_campos(tipo_s, regs):
                    r["numFactura"] = factura
                    datos[tipo_s.lower()].append(r)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for k,v in datos.items():
            pd.DataFrame(v).to_excel(writer, sheet_name=k[:31], index=False)

    output.seek(0)
    return output


def excel_to_json(archivo, tipo, nit):
    xlsx = pd.read_excel(archivo, sheet_name=None, dtype=str)
    dfs = {k.lower(): v.where(pd.notna(v), None) for k,v in xlsx.items()}

    usuarios = dfs.get("usuarios")
    if usuarios is None:
        st.error("Falta hoja usuarios")
        return None

    salida = {}
    for factura in usuarios["numFactura"].dropna().unique():

        usuarios_final = []
        uf = usuarios[usuarios["numFactura"]==factura]

        for _,u in uf.iterrows():
            u_dict = u.to_dict()
            u_dict.pop("numFactura",None)

            servicios={}
            for tipo_s,df in dfs.items():
                if tipo_s=="usuarios": continue
                reg = df[df["numFactura"]==factura]
                if not reg.empty:
                    servicios[tipo_s] = ordenar_campos(tipo_s,[r.to_dict() for _,r in reg.iterrows()])

            u_dict["servicios"]=servicios
            usuarios_final.append(u_dict)

        salida_json = {
            "numDocumentoIdObligado": nit,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        }

        salida_json = formatear_fechas(forzar_tipos(salida_json))
        salida[f"{factura}.json"] = json.dumps(salida_json, indent=2, ensure_ascii=False)

    if tipo=="PGP":
        return {"tipo":"unico","contenido":list(salida.values())[0]}
    return {"tipo":"zip","contenido":salida}

# ========================= MAIN =========================

def main():

    if "autenticado" not in st.session_state:
        st.session_state["autenticado"]=False

    if not st.session_state["autenticado"]:
        login()
        return

    modo = st.radio("Tipo de conversión",[
        "JSON ➜ Excel (PGP-CAPITA)",
        "Excel ➜ JSON (PGP-CAPITA)",
        "JSON ➜ Excel (Evento)",
        "Excel ➜ JSON (Evento)"
    ])

    nit = st.text_input("NIT obligado", value="900364721")

    archivos=None
    archivo=None

    if "JSON ➜ Excel" in modo:
        archivos = st.file_uploader("Sube JSON", type=["json"], accept_multiple_files=True)

    else:
        archivo = st.file_uploader("Sube Excel", type=["xlsx"])

    if st.button("Convertir"):

        tipo = "PGP" if "PGP-CAPITA" in modo else "EVENTO"

        if archivos:
            excel = json_to_excel(archivos, tipo)
            st.download_button("Descargar Excel", excel, "rips.xlsx")

        elif archivo:
            resultado = excel_to_json(archivo, tipo, nit)

            if resultado:
                if resultado["tipo"]=="unico":
                    st.download_button("Descargar JSON", resultado["contenido"], "rips.json")
                else:
                    buffer = BytesIO()
                    with zipfile.ZipFile(buffer,"w") as z:
                        for n,c in resultado["contenido"].items():
                            z.writestr(n,c)
                    buffer.seek(0)
                    st.download_button("Descargar ZIP", buffer, "rips.zip")

# ========================= RUN =========================

def guard(fn):
    try:
        fn()
    except Exception:
        st.error("Error en ejecución")
        st.code(traceback.format_exc())

guard(main)
