# smoke_app.py — prueba de vida del entorno
import os, sys, platform, subprocess, json
import streamlit as st
print("BOOT: iniciando app.py")  # se ve en Logs al ejecutar
import sys; print("BOOT: python", sys.version)


st.title("Smoke test ✅")

st.subheader("Entorno")
st.write("Python:", sys.version)
st.write("Platform:", platform.platform())
st.write("CWD:", os.getcwd())

st.subheader("Variables importantes")
st.write("Archivo principal:", os.environ.get("STREAMLIT_SERVER_SCRIPT_PATH", "desconocido"))
st.write("Directorio:", os.listdir("."))

# Mostrar parte del freeze para ver versiones reales instaladas
st.subheader("pip freeze (primeras 60 líneas)")
try:
    out = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True, timeout=30)
    lines = out.strip().splitlines()
    st.code("\n".join(lines[:60]))
except Exception as e:
    st.error("No pude ejecutar pip freeze")
    st.exception(e)

# Probar import crítico
st.subheader("Imports críticos")
try:
    import pandas as pd
    import streamlit_authenticator as stauth
    st.success("✅ pandas y streamlit_authenticator importados")
except Exception as e:
    st.error("❌ Falló un import crítico")
    st.exception(e)

# Probar lectura de Secrets
st.subheader("Lectura de st.secrets")
try:
    have_creds = "credentials" in st.secrets and "cookie" in st.secrets
    st.write("¿Hay credentials y cookie en secrets?:", have_creds)
    if have_creds:
        # no muestres secretos, solo keys
        st.code(json.dumps({"credentials": True, "cookie": True, "preauthorized": "preauthorized" in st.secrets}, indent=2))
    else:
        st.warning("No hay credentials/cookie en st.secrets")
except Exception as e:
    st.error("No pude acceder a st.secrets")
    st.exception(e)

st.info("Si llegaste hasta aquí, el entorno ejecuta. El problema está en tu app principal o en dependencias no declaradas.")
