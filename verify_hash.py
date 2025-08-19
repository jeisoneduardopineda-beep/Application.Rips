import bcrypt

password_plain = b"jeison1411"  # <- tu clave en texto
stored_hash   = b"$2b$12$MRbdtEWCTQ3oDNojUjz85uUCD15QOLr1KXy6Zl2NlZDDQbaTxruj"  # <- el hash de config.yaml

print("Coincide?:", bcrypt.checkpw(password_plain, stored_hash))
