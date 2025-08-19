import streamlit_authenticator as stauth

# Diccionario: usuario → contraseña en texto plano
passwords = {
    "jeison": "jeison1411",
    "operador": "operador2025",
    "auditor": "auditorSeg",
    "admin": "Admin123!"
}

print("=== Hashes generados para config.yaml ===\n")
for user, pwd in passwords.items():
    hashed = stauth.Hasher().hash(pwd)
    print(f"{user}: {hashed}")
