import bcrypt

password_plain = b"jeison1411"  # <- tu clave en texto
stored_hash   = b"$2b$12$PWb1bkGeHYRX2YInizX2P.4.4.fkxCScxAuZzLnz3mTwrFW.qqYEC"  # <- el hash de config.yaml

print("Coincide?:", bcrypt.checkpw(password_plain, stored_hash))
