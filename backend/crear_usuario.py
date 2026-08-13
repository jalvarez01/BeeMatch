"""
Crea usuarios desde la terminal. Necesario al menos una vez: sin un
administrador inicial no hay forma de crear a los demás desde la aplicación.

    python -m backend.crear_usuario

También acepta los datos por argumentos, útil para automatizar:

    python -m backend.crear_usuario --nombre "Dyanna" \
        --correo dyanna@bee.com.co --rol ADMINISTRADOR --password "Bee2026seguro"

La contraseña nunca se guarda en claro: se almacena su hash PBKDF2-SHA256.
"""

import argparse
import getpass
import sys

from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas)
from backend.infrastructure.persistence.database import SessionLocal, init_db
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository
from backend.security import (
    LONGITUD_MINIMA_PASSWORD,
    ROLES_VALIDOS,
    ROL_ADMINISTRADOR,
    hashear_password,
)


def pedir_password() -> str:
    """Solicita la contraseña dos veces sin mostrarla en pantalla."""
    while True:
        password = getpass.getpass("Contraseña: ")
        if len(password) < LONGITUD_MINIMA_PASSWORD:
            print(f"  Debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.")
            continue
        if password.isdigit() or password.isalpha():
            print("  Debe combinar letras y números.")
            continue
        if password != getpass.getpass("Confirmar contraseña: "):
            print("  Las contraseñas no coinciden.")
            continue
        return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea un usuario de BeeMatch.")
    parser.add_argument("--nombre")
    parser.add_argument("--correo")
    parser.add_argument("--rol", choices=sorted(ROLES_VALIDOS))
    parser.add_argument("--password", help="Si se omite, se pide de forma interactiva.")
    argumentos = parser.parse_args()

    init_db()
    db = SessionLocal()

    try:
        repo = UsuarioRepository(db)
        primer_usuario = repo.contar() == 0

        if primer_usuario:
            print("No hay usuarios registrados. Vamos a crear el administrador inicial.\n")

        nombre = argumentos.nombre or input("Nombre: ").strip()
        correo = (argumentos.correo or input("Correo corporativo: ").strip()).lower()

        if not nombre or not correo:
            print("El nombre y el correo son obligatorios.")
            return 1

        if repo.get_by_correo(correo):
            print(f"Ya existe un usuario con el correo {correo}.")
            return 1

        if argumentos.rol:
            rol = argumentos.rol
        elif primer_usuario:
            rol = ROL_ADMINISTRADOR
        else:
            entrada = input(f"Rol {sorted(ROLES_VALIDOS)} [COORDINADOR]: ").strip().upper()
            rol = entrada or "COORDINADOR"

        if rol not in ROLES_VALIDOS:
            print(f"Rol inválido. Debe ser uno de: {', '.join(sorted(ROLES_VALIDOS))}")
            return 1

        password = argumentos.password or pedir_password()

        usuario = repo.crear(
            nombre=nombre,
            correo=correo,
            rol=rol,
            password_hash=hashear_password(password),
            debe_cambiar_password=False,
        )

        print(f"\nUsuario creado: {usuario.nombre} <{usuario.correo}> · {usuario.rol}")
        print("Ya puedes iniciar sesión en la aplicación.")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())