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

# ========================= CONFIG UI =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "medidatarips_logo.png")
page_icon = LOGO_PATH if os.path.isfile(LOGO_PATH) else None

st.set_page_config(
    page_title="Transformador RIPS PGP & EVENTO",
    layout="centered",
    page_icon=page_icon
)

# ========================= LOGIN =========================

USUARIOS = {
    "jeison": "jeison1411",
    "facturacion1": "rips2024",
    "admin": "rips2026",
    "auditoria": "audit2024"
}

def login():
    st.title("🔐 Inicio de sesión")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        if u in USUARIOS and USUARIOS[u] == p:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

# ========================= UTILS =========================

def _to_str_preserve(v):
    if v is None: return None
    s = str(v)
    return None if s.lower() in {"nan","none",""} else s

def json_friendly(o):
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.strftime("%Y-%m-%d-%H:%M")
    if isinstance(o, date):
        return o.strftime("%Y-%m-%d")
    return o

# ========================= LIMPIAR FECHAS =========================

def limpiar_fechas(dic):
    if isinstance(dic, dict):
        for k, v in dic.items():
            if isinstance(v, dict):
                dic[k] = limpiar_fechas(v)
            elif isinstance(v, list):
                dic[k] = [limpiar_fechas(i) if isinstance(i, dict) else i for i in v]
            else:
                if isinstance(v, str) and "fecha" in k.lower():
                    if len(v) >= 19:
                        v = v[:16]
                    if " " in v:
                        f, h = v.split(" ")
                    else:
                        f, h = v, None

                    if k == "fechaNacimiento":
                        dic[k] = f
                    else:
                        dic[k] = f"{f}-{h[:5]}" if h else f
    return dic

# ========================= ORDEN ESTRUCTURA =========================

ORDEN_SERVICIOS = {
    "consultas":[
        "codPrestador","fechaInicioAtencion","numAutorizacion","codConsulta",
        "modalidadGrupoServicioTecSal","grupoServicios","codServicio",
        "finalidadTecnologiaSalud","causaMotivoAtencion","codDiagnosticoPrincipal",
        "codDiagnosticoRelacionado1","codDiagnosticoRelacionado2","codDiagnosticoRelacionado3",
        "tipoDiagnosticoPrincipal","tipoDocumentoIdentificacion","numDocumentoIdentificacion",
        "vrServicio","conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"
    ],
    "procedimientos":[
        "codPrestador","fechaInicioAtencion","idMIPRES","numAutorizacion","codProcedimiento",
        "viaIngresoServicioSalud","modalidadGrupoServicioTecSal","grupoServicios","codServicio",
        "finalidadTecnologiaSalud","tipoDocumentoIdentificacion","numDocumentoIdentificacion",
        "codDiagnosticoPrincipal","codDiagnosticoRelacionado","codComplicacion","vrServicio",
        "conceptoRecaudo","valorPagoModerador","numFEVPagoModerador","consecutivo"
    ],
    "urgencias":[
        "codPrestador","fechaInicioAtencion","causaMotivoAtencion","codDiagnosticoPrincipal",
        "codDiagnosticoPrincipalE","codDiagnosticoRelacionadoE1","codDiagnosticoRelacionadoE2",
        "codDiagnosticoRelacionadoE3","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte",
        "fechaEgreso","consecutivo"
    ],
    "hospitalizacion":[
        "codPrestador","viaIngresoServicioSalud","fechaInicioAtencion","numAutorizacion",
        "causaMotivoAtencion","codDiagnosticoPrincipal","codDiagnosticoPrincipalE",
        "codDiagnosticoRelacionadoE1","codDiagnosticoRelacionadoE2","codDiagnosticoRelacionadoE3",
        "codComplicacion","condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso",
        "consecutivo"
    ],
    "reciennacidos":[
        "codPrestador","tipoDocumentoIdentificacion","numDocumentoIdentificacion","fechaNacimiento",
        "edadGestacional","numConsultasCPrenatal","codSexoBiologico","peso","codDiagnosticoPrincipal",
        "condicionDestinoUsuarioEgreso","codDiagnosticoCausaMuerte","fechaEgreso","consecutivo"
    ],
    "medicamentos":[
        "codPrestador","numAutorizacion","idMIPRES","fechaDispensAdmon","codDiagnosticoPrincipal",
        "codDiagnosticoRelacionado","tipoMedicamento","codTecnologiaSalud","nomTecnologiaSalud",
        "concentracionMedicamento","unidadMedida","formaFarmaceutica","unidadMinDispensa",
        "cantidadMedicamento","diasTratamiento","tipoDocumentoIdentificacion",
        "numDocumentoIdentificacion","vrUnitMedicamento","vrServicio","conceptoRecaudo",
        "valorPagoModerador","numFEVPagoModerador","consecutivo"
    ],
    "otrosservicios":[
        "codPrestador","numAutorizacion","idMIPRES","fechaSuministroTecnologia","tipoOS",
        "codTecnologiaSalud","nomTecnologiaSalud","cantidadOS","tipoDocumentoIdentificacion",
        "numDocumentoIdentificacion","vrUnitOS","vrServicio","conceptoRecaudo",
        "valorPagoModerador","numFEVPagoModerador","consecutivo"
    ]
}

def ordenar_campos(servicios):
    out = {}
    for t, regs in servicios.items():
        orden = ORDEN_SERVICIOS.get(t.lower(), [])
        out[t] = []
        for r in regs:
            nuevo = {k:r.get(k) for k in orden if k in r}
            for k in r:
                if k not in nuevo:
                    nuevo[k] = r[k]
            out[t].append(nuevo)
    return out

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(file, nit):

    xlsx = pd.read_excel(file, sheet_name=None, dtype=str)
    dfs = {k.lower():v for k,v in xlsx.items()}

    usuarios = dfs["usuarios"]
    servicios = [k for k in dfs if k!="usuarios"]

    salida = {}
    facturas = usuarios["numFactura"].dropna().unique()

    for f in facturas:

        f = _to_str_preserve(f)
        usuarios_final = []

        for _, u in usuarios[usuarios["numFactura"]==f].iterrows():

            doc = u.get("numDocumentoIdentificacion")
            u_dict = u.to_dict()
            u_dict.pop("numFactura", None)

            servicios_dict = {}

            for s in servicios:

                df = dfs[s]
                regs = df[(df["numFactura"]==f)&(df["documento_usuario"]==doc)]

                if not regs.empty:
                    regs = regs.drop(columns=["numFactura","documento_usuario"], errors="ignore")
                    servicios_dict[s] = [r.to_dict() for _,r in regs.iterrows()]

            servicios_dict = ordenar_campos(servicios_dict)

            u_dict["servicios"] = servicios_dict
            usuarios_final.append(u_dict)

        json_out = {
            "numDocumentoIdObligado": nit,
            "numFactura": f,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        }

        json_out = limpiar_fechas(json_out)

        salida[f"{f}.json"] = json.dumps(json_out, indent=2, ensure_ascii=False, default=json_friendly)

    return salida

# ========================= APP =========================

def main():

    if "auth" not in st.session_state:
        st.session_state["auth"] = False

    if not st.session_state["auth"]:
        login()
        return

    file = st.file_uploader("Sube Excel", type=["xlsx"])
    nit = st.text_input("NIT", "900364721")

    if file and st.button("Convertir"):
        res = excel_to_json(file, nit)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            for n,c in res.items():
                z.writestr(n, c)

        buffer.seek(0)
        st.download_button("Descargar ZIP", buffer, "RIPS.zip")

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error(str(e))
        st.stop()

guard(main)
