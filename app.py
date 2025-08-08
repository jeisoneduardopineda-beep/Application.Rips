import streamlit as st
import os
import json
import pandas as pd
from io import BytesIO
import zipfile
import yaml
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
# ------------------- CARGAR CONFIGURACIÓN -------------------
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# ------------------- AUTENTICACIÓN -------------------
authenticator = stauth.Authenticate(
    credentials=config['credentials'],
    cookie_name=config['cookie']['name'],
    key=config['cookie']['key'],
    expiry_days=config['cookie']['expiry_days']
)

# Barra lateral: Generador de hash
st.sidebar.title("🔑 Herramientas")
if st.sidebar.button("Abrir generador de hash"):
    st.session_state["show_hash_gen"] = True

if st.session_state.get("show_hash_gen", False):
    st.sidebar.subheader("Generar hash de contraseña")
    new_password = st.sidebar.text_input("Introduce la contraseña", type="password")
    if st.sidebar.button("Generar hash"):
        if new_password:
            hashed = stauth.Hasher().generate([new_password])
            st.sidebar.code(hashed[0], language="text")
        else:
            st.sidebar.warning("Introduce una contraseña primero.")

# ------------------- FORMULARIO LOGIN -------------------
name, authentication_status, username = authenticator.login("Iniciar sesión", "main")

if authentication_status is False:
    st.error("❌ Usuario o contraseña incorrectos.")
    st.stop()
elif authentication_status is None:
    st.warning("Por favor ingresa tus credenciales.")
    st.stop()
else:
    st.success(f"Bienvenido {name} 👋")

# ------------------- TU APP PRINCIPAL -------------------
st.set_page_config(page_title="Transformador RIPS PGP & EVENTO", layout="centered")
st.title(f"🔄 Bienvenido {st.session_state['name']}")

# ------------------- FUNCIONES -------------------
TIPOS_SERVICIOS = [
    "consultas", "procedimientos", "hospitalizacion", "hospitalizaciones",
    "urgencias", "reciennacidos", "medicamentos", "otrosservicios", "otrosServicios"
]

CAMPOS_NUMERICOS = [
    "consecutivo", "codServicio", "vrServicio", "valorPagoModerador",
    "concentracionMedicamento", "unidadMedida", "unidadMinDispensa",
    "cantidadMedicamento", "diasTratamiento", "vrUnitMedicamento",
    "idMIPRES", "cantidadOS", "vrUnitOS"
]

CAMPOS_CODIGOS = [
    "tipoUsuario", "viaIngresoServicioSalud", "modalidadGrupoServicioTecSal",
    "grupoServicios", "finalidadTecnologiaSalud", "conceptoRecaudo",
    "tipoMedicamento", "tipoOS", "codZonaTerritorialResidencia",
    "codPaisResidencia", "codPaisOrigen"
]

def limpiar_valores(d):
    limpio = {}
    for k, v in d.items():
        if pd.isna(v):
            limpio[k] = None
        elif k in CAMPOS_NUMERICOS:
            try:
                limpio[k] = int(v) if float(v) == int(v) else float(v)
            except:
                limpio[k] = None
        elif k in CAMPOS_CODIGOS:
            limpio[k] = str(v).zfill(2)
        else:
            limpio[k] = str(v).strip() if not isinstance(v, str) else v.strip()
    return limpio

def json_to_excel(files, tipo_factura):
    datos = {tipo: [] for tipo in ["usuarios"] + list(set([s.lower() for s in TIPOS_SERVICIOS]))}

    for archivo in files:
        data = json.load(archivo)
        num_factura = data.get("numFactura", "SIN_FACTURA")
        archivo_origen = os.path.splitext(archivo.name)[0]
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
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for tipo, registros in datos.items():
            if registros:
                df = pd.DataFrame(registros)
                df.to_excel(writer, sheet_name=tipo.capitalize(), index=False)
    output.seek(0)
    return output

def excel_to_json(archivo_excel, tipo_factura, nit_obligado):
    xlsx = pd.read_excel(archivo_excel, sheet_name=None)
    dataframes = {k.lower(): v for k, v in xlsx.items()}

    if "usuarios" not in dataframes:
        st.error("❌ El archivo no contiene una hoja llamada 'usuarios'.")
        return None

    usuarios_df = dataframes["usuarios"]
    tipos_servicios = [k for k in dataframes if k != "usuarios"]

    if tipo_factura == "PGP":
        facturas = usuarios_df['numFactura'].dropna().unique()
        if len(facturas) != 1:
            st.error("❌ Para PGP solo se permite una única factura.")
            return None

        factura = facturas[0]
        usuarios_final = []

        for _, usuario in usuarios_df.iterrows():
            usuario_dict = usuario.to_dict()
            doc = usuario_dict.get("numDocumentoIdentificacion") or usuario_dict.get("documento_usuario")
            usuario_limpio = limpiar_valores(usuario_dict)
            usuario_limpio.pop("archivo_origen", None)
            usuario_limpio.pop("numFactura", None)

            servicios_dict = {}
            for tipo in tipos_servicios:
                df_tipo = dataframes[tipo]
                registros = df_tipo[df_tipo["documento_usuario"] == doc]
                if not registros.empty:
                    registros = registros.drop(columns=["numFactura", "documento_usuario", "archivo_origen"], errors='ignore')
                    registros_limpios = [limpiar_valores(r) for _, r in registros.iterrows()]
                    servicios_dict[tipo] = registros_limpios

            usuario_limpio["servicios"] = servicios_dict
            usuarios_final.append(usuario_limpio)

        salida_json = {
            "numDocumentoIdObligado": nit_obligado,
            "numFactura": factura,
            "tipoNota": None,
            "numNota": None,
            "usuarios": usuarios_final
        }

        return {
            "tipo": "único",
            "contenido": json.dumps(salida_json, ensure_ascii=False, indent=2),
            "nombre": f"Factura_RIPS_{tipo_factura}.json"
        }

    else:
        salida_archivos = {}
        for factura in usuarios_df['numFactura'].dropna().unique():
            usuarios_factura = usuarios_df[usuarios_df['numFactura'] == factura]
            usuarios_final = []

            for _, usuario in usuarios_factura.iterrows():
                usuario_dict = usuario.to_dict()
                doc = usuario_dict.get("numDocumentoIdentificacion") or usuario_dict.get("documento_usuario")
                usuario_limpio = limpiar_valores(usuario_dict)
                usuario_limpio.pop("archivo_origen", None)
                usuario_limpio.pop("numFactura", None)

                servicios_dict = {}
                for tipo in tipos_servicios:
                    df_tipo = dataframes[tipo]
                    registros = df_tipo[
                        (df_tipo["numFactura"] == factura) &
                        (df_tipo["documento_usuario"] == doc)
                    ]
                    if not registros.empty:
                        registros = registros.drop(columns=["numFactura", "documento_usuario", "archivo_origen"], errors='ignore')
                        registros_limpios = [limpiar_valores(r) for _, r in registros.iterrows()]
                        servicios_dict[tipo] = registros_limpios

                usuario_limpio["servicios"] = servicios_dict
                usuarios_final.append(usuario_limpio)

            salida_json = {
                "numDocumentoIdObligado": nit_obligado,
                "numFactura": factura,
                "tipoNota": None,
                "numNota": None,
                "usuarios": usuarios_final
            }

            salida_archivos[f"{factura}_RIPS.json"] = json.dumps(salida_json, ensure_ascii=False, indent=2)

        return {
            "tipo": "zip",
            "contenido": salida_archivos
        }

# ------------------- INTERFAZ DE USUARIO -------------------

st.title("📄 Transformador RIPS: PGP y EVENTO")

modo = st.radio("Selecciona el tipo de conversión:", [
    "📥 JSON ➜ Excel (PGP)", "📤 Excel ➜ JSON (PGP)",
    "📥 JSON ➜ Excel (Evento)", "📤 Excel ➜ JSON (Evento)"
])

nit_obligado = st.text_input("🔢 NIT del Obligado a Facturar", value="900364721")

if "JSON ➜ Excel" in modo:
    archivos = st.file_uploader("📂 Selecciona uno o varios archivos JSON", type=["json"], accept_multiple_files=True)
    if archivos and st.button("🚀 Convertir a Excel"):
        tipo_factura = "PGP" if "PGP" in modo else "EVENTO"
        excel_data = json_to_excel(archivos, tipo_factura)
        st.download_button("⬇️ Descargar Excel", data=excel_data, file_name=f"RIPS_Consolidado_{tipo_factura}.xlsx")

elif "Excel ➜ JSON" in modo:
    archivo_excel = st.file_uploader("📂 Selecciona archivo Excel", type=["xlsx"])
    if archivo_excel and st.button("🚀 Convertir a JSON"):
        tipo_factura = "PGP" if "PGP" in modo else "EVENTO"
        resultado = excel_to_json(archivo_excel, tipo_factura, nit_obligado)

        if resultado:
            if resultado["tipo"] == "único":
                st.download_button("⬇️ Descargar JSON", data=resultado["contenido"].encode("utf-8"), file_name=resultado["nombre"])
            elif resultado["tipo"] == "zip":
                buffer = BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for nombre, contenido in resultado["contenido"].items():
                        zipf.writestr(nombre, contenido)
                buffer.seek(0)
                st.download_button("⬇️ Descargar ZIP de JSONs", data=buffer, file_name="RIPS_Evento_JSONs.zip")

# ------------------- LOGOUT -------------------
st.sidebar.title("👤 Usuario")
st.sidebar.write(f"Bienvenido, {st.session_state['name']}")
authenticator.logout("🚪 Cerrar sesión", "sidebar")


