# -*- coding: utf-8 -*-

import os
import json
import zipfile
from io import BytesIO
import time
import traceback
import pandas as pd
import streamlit as st

# ========================= CONFIG =========================

st.set_page_config(page_title="Transformador RIPS PGP & EVENTO", layout="centered")

USUARIOS = {
    "jeison": "jeison1411",
    "facturacion1": "rips2024",
    "admin": "rips2026",
    "auditoria": "audit2024"
}

# ========================= LOGIN =========================

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

ORDEN_SERVICIOS = {...}  # (déjalo igual que ya lo tienes completo)

def ordenar_campos_servicios(tipo, registros):
    orden = ORDEN_SERVICIOS.get(tipo.lower())
    if not orden:
        return registros
    salida = []
    for reg in registros:
        nuevo = {campo: reg.get(campo) for campo in orden}
        for k, v in reg.items():
            if k not in nuevo:
                nuevo[k] = v
        salida.append(nuevo)
    return salida

# ========================= AUX =========================

def _to_str_preserve(v):
    if v is None:
        return None
    s = str(v)
    if s.lower() in {"nan","none",""}:
        return None
    return s

TIPOS_SERVICIOS = [
    "consultas","procedimientos","hospitalizacion","urgencias",
    "reciennacidos","medicamentos","otrosservicios"
]

# ========================= JSON ➜ EXCEL =========================

def json_to_excel(files, tipo_factura):

    datos = {tipo: [] for tipo in ["usuarios"] + TIPOS_SERVICIOS}

    for archivo in files:
        data = json.load(archivo)
        num_factura = _to_str_preserve(data.get("numFactura"))

        for usuario in data.get("usuarios", []):
            servicios = usuario.get("servicios", {})

            for tipo, registros in servicios.items():
                tipo = tipo.lower()
                if tipo in datos:
                    for reg in registros:
                        reg["numFactura"] = num_factura
                        datos[tipo].append(reg)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            if registros:
                registros = ordenar_campos_servicios(tipo, registros)
                pd.DataFrame(registros).to_excel(writer, sheet_name=tipo[:31], index=False)

    output.seek(0)
    return output

# ========================= EXCEL ➜ JSON =========================

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):

    xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    dataframes = {k.lower(): v for k, v in xlsx.items()}

    usuarios_df = dataframes.get("usuarios")
    if usuarios_df is None:
        return None

    salida_archivos = {}
    facturas = usuarios_df["numFactura"].dropna().unique()

    for factura in facturas:

        factura_str = _to_str_preserve(factura)
        usuarios_final = []

        usuarios_factura = usuarios_df[usuarios_df["numFactura"] == factura_str]

        for _, usuario in usuarios_factura.iterrows():

            usuario_dict = usuario.to_dict()
            usuario_dict.pop("numFactura", None)

            servicios_dict = {}

            for tipo, df in dataframes.items():
                if tipo == "usuarios":
                    continue

                registros = df[df["numFactura"] == factura_str]

                if not registros.empty:
                    lista = [r.to_dict() for _, r in registros.iterrows()]
                    lista = ordenar_campos_servicios(tipo, lista)
                    servicios_dict[tipo] = lista

            usuario_dict["servicios"] = servicios_dict
            usuarios_final.append(usuario_dict)

        salida_json = {
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura_str,
            "usuarios": usuarios_final
        }

        salida_archivos[f"{factura_str}.json"] = json.dumps(salida_json, indent=2, ensure_ascii=False)

    if tipo_factura == "PGP":
        return {
            "tipo": "unico",
            "contenido": list(salida_archivos.values())[0],
            "nombre": "rips.json"
        }

    return {
        "tipo": "zip",
        "contenido": salida_archivos
    }

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

    modo = st.radio("Tipo de conversión", [
        "JSON ➜ Excel (PGP-CAPITA)",
        "Excel ➜ JSON (PGP-CAPITA)",
        "JSON ➜ Excel (Evento)",
        "Excel ➜ JSON (Evento)"
    ])

    nit = st.text_input("NIT obligado", value="900364721")

    if "JSON ➜ Excel" in modo:

        archivos = st.file_uploader("Sube JSON", type=["json"], accept_multiple_files=True)

        if archivos:
            tipo = "PGP" if "PGP-CAPITA" in modo else "EVENTO"
            excel = json_to_excel(archivos, tipo)
            st.download_button("Descargar Excel", excel, "rips.xlsx")

    elif "Excel ➜ JSON" in modo:

        archivo = st.file_uploader("Sube Excel", type=["xlsx"])

        if archivo:
            tipo = "PGP" if "PGP-CAPITA" in modo else "EVENTO"
            resultado = excel_to_json(archivo, tipo, nit)

            if resultado["tipo"] == "unico":
                st.download_button("Descargar JSON", resultado["contenido"], resultado["nombre"])

            else:
                buffer = BytesIO()
                with zipfile.ZipFile(buffer, "w") as zipf:
                    for nombre, contenido in resultado["contenido"].items():
                        zipf.writestr(nombre, contenido)

                buffer.seek(0)

                st.download_button("Descargar ZIP", buffer, "rips.zip")

# ========================= RUN =========================

def guard(fn):
    try:
        fn()
    except Exception as e:
        st.error("Error en ejecución")
        st.code(str(e))

guard(main)
