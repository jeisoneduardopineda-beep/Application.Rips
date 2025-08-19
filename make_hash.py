import streamlit_authenticator as stauth

# 🔑 Pide la contraseña al usuario
password = input("jeison1411")

# 🛠️ Usa el método correcto de la librería
hashed_passwords = stauth.Hasher().hash(password)

print("\nContraseña encriptada:\n")
print(hashed_passwords)
