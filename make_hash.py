import streamlit_authenticator as stauth

# Genera el hash para ESTA contraseña (cámbiala si quieres otra)
password = "jeison1411"

# API nueva de la librería local: Hasher().hash(texto)
hashed = stauth.Hasher().hash(password)

print("Hash generado:")
print(hashed)
