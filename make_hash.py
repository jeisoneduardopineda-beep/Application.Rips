import streamlit_authenticator as stauth

# Aquí escribes la clave que quieres usar en texto plano
passwords = ['jeison1411']

# Esto genera los hashes
hashes = stauth.Hasher(passwords).generate()
print(hashes)
