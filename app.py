## app.py (DIAGNÓSTICO)
import streamlit as st
st.set_page_config(page_title="Diagnóstico Login", layout="centered")

st.title("🩺 Diagnóstico de Autenticación")

import yaml, traceback
from yaml.loader import SafeLoader

# 1) Mostrar ruta actual y listar archivos
import os, glob
st.write("**Working dir:**", os.getcwd())
st.write("**Archivos en raíz:**", sorted([os.path.basename(p) for p in glob.glob("*")]))
st.write("---")

# 2) Intentar leer config.yaml
try:
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=SafeLoader)
    st.success("✅ config.yaml leído")
    st.write("Claves en config:", list(config.keys()))
    st.write("Usernames:", list(config.get("credentials", {}).get("usernames", {}).keys()))
except Exception as e:
    st.error("❌ Error leyendo config.yaml")
    st.exception(e)
    st.stop()

# 3) Mostrar versión de streamlit-authenticator
try:
    import streamlit_authenticator as stauth
    ver = getattr(stauth, "__version__", "desconocida")
    st.write("**streamlit-authenticator versión:**", ver)
except Exception as e:
    st.error("❌ No se pudo importar streamlit_authenticator")
    st.exception(e)
    st.stop()

# 4) Crear authenticator con compat 0.2.x / 0.3.x
try:
    from packaging import version as _v
    if _v.parse(ver) >= _v.parse("0.3.0"):
        authenticator = stauth.Authenticate(
            credentials=config["credentials"],
            cookie_name=config["cookie"]["name"],
            key=config["cookie"]["key"],
            cookie_expiry_days=config["cookie"]["expiry_days"],
        )
        mode = "0.3.x"
    else:
        authenticator = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
            config.get("preauthorized", {}).get("emails", []),
        )
        mode = "0.2.x"
    st.success(f"✅ Authenticator creado (modo {mode})")
except Exception as e:
    st.error("❌ Error creando el authenticator")
    st.exception(e)
    st.stop()

# 5) Formulario de login
try:
    if _v.parse(ver) >= _v.parse("0.3.0"):
        name, auth_status, username = authenticator.login(form_name="🔐 Iniciar sesión", location="main")
    else:
        name, auth_status, username = authenticator.login("🔐 Iniciar sesión", "main")

    st.write("Estado auth_status:", auth_status)

    if auth_status is False:
        st.error("Usuario o contraseña incorrectos.")
    elif auth_status is None:
        st.warning("Ingresa tus credenciales.")
    else:
        st.success(f"Bienvenido, {name} (@{username})")
        authenticator.logout("🚪 Cerrar sesión", "sidebar")
except Exception as e:
    st.error("❌ Error en el login() o logout()")
    st.exception(e)


