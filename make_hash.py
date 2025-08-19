import streamlit_authenticator as stauth

# Lista de contraseñas para distintos usuarios
passwords = {
    "jeison": "jeison1411",
    "operador": "operador2025",
    "auditor": "auditorSeg",
    "admin": "Admin123!"
}

print("=== Hashes generados para config.yaml ===\n")
for user, pwd in passwords.items():
    hashed = stauth.Hasher([pwd]).generate()[0]
    print(f"{user}: {hashed}")
