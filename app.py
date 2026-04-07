# -*- coding: utf-8 -*-

import json
import zipfile
from io import BytesIO
import traceback
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Transformador RIPS PGP & EVENTO", layout="centered")

# ================= LOGIN =================

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

# ================= ORDEN =================

ORDEN_SERVICIOS = {
    "consultas": [...],
    "procedimientos": [...],
    "urgencias": [...],
    "hospitalizacion": [...],
    "reciennacidos": [...],
    "medicamentos": [...],
    "otrosservicios": [...]
}

def ordenar_campos(tipo, registros):
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

# ================= TIPOS =================

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

# ================= FECHAS (CORRECTO) =================

def convertir_fecha(k, v):
    if v is None:
        return None

    if "fecha" not in k.lower():
        return v

    try:
        fecha = pd.to_datetime(v, errors="coerce")

        if pd.isna(fecha):
            return None

        if k in ["fechaDispensAdmon", "fechaInicioAtencion", "fechaEgreso"]:
            return fecha.strftime("%Y-%m-%d-%H-%M")

        if k == "fechaNacimiento":
            return fecha.strftime("%Y-%m-%d")

        return fecha.strftime("%Y-%m-%d")

    except:
        return None

def formatear_fechas(data):
    if isinstance(data, dict):
        return {k: formatear_fechas(v) if isinstance(v, (dict, list)) else convertir_fecha(k, v) for k, v in data.items()}
    elif isinstance(data, list):
        return [formatear_fechas(i) for i in data]
    return data

# ================= JSON ➜ EXCEL =================

def json_to_excel(files, tipo_factura):
    datos = {}

    for archivo in files:
        data = json.load(archivo)
        num_factura = data.get("numFactura")

        for usuario in data.get("usuarios", []):
            for tipo, registros in usuario.get("servicios", {}).items():

                tipo = tipo.lower()
                datos.setdefault(tipo, [])

                registros = ordenar_campos(tipo, registros)

                for reg in registros:
                    reg["numFactura"] = num_factura
                    datos[tipo].append(reg)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for tipo, registros in datos.items():
            pd.DataFrame(registros).to_excel(writer, sheet_name=tipo[:31], index=False)

    output.seek(0)
    return output

# ================= EXCEL ➜ JSON =================

def excel_to_json(archivo_excel, tipo_factura, nit):

    try:
        xlsx = pd.read_excel(archivo_excel, sheet_name=None, dtype=str)
    except Exception as e:
        st.error(f"Error leyendo Excel: {e}")
        return None

    dfs = {k.lower(): v.where(pd.notna(v), None) for k, v in xlsx.items()}

    usuarios = dfs.get("usuarios")
    if usuarios is None:
        st.error("Falta hoja 'usuarios'")
        return None

    salida = {}

    for factura in usuarios["numFactura"].dropna().unique():

        usuarios_final = []

        for _, u in usuarios[usuarios["numFactura"] == factura].iterrows():

            u_dict = u.to_dict()
            u_dict.pop("numFactura", None)

            servicios = {}

            for tipo, df in dfs.items():
                if tipo == "usuarios":
                    continue

                reg = df[df["numFactura"] == factura]

                if not reg.empty:
                    lista = [r.to_dict() for _, r in reg.iterrows()]
                    servicios[tipo] = ordenar_campos(tipo, lista)

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

# ================= MAIN =================

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
            excel = json_to_excel(archivos, "PGP")
            st.download_button("Descargar Excel", excel, "rips.xlsx")

    else:
        archivo = st.file_uploader("Sube Excel", type=["xlsx"])

        if archivo:
            resultado = excel_to_json(archivo, "PGP", nit)

            if resultado:
                if resultado["tipo"] == "unico":
                    st.download_button("Descargar JSON", resultado["contenido"], resultado["nombre"])
                else:
                    buffer = BytesIO()
                    with zipfile.ZipFile(buffer, "w") as z:
                        for n, c in resultado["contenido"].items():
                            z.writestr(n, c)

                    buffer.seek(0)
                    st.download_button("Descargar ZIP", buffer, "rips.zip")

# ================= RUN =================

if __name__ == "__main__":
    main()
