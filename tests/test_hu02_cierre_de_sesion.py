"""
HU-02 — pruebas del lado servidor.

La opción visible en todas las pantallas, la redirección y el temporizador de
inactividad viven en el frontend (`Sidebar`, `Layout`, `useInactividad`); aquí
se prueba lo que el servidor garantiza: el cierre queda en bitácora y el token
vence a los 30 minutos si no se renueva.
"""

from datetime import UTC, datetime, timedelta

import jwt

from backend.config import JWT_ALGORITHM, JWT_EXPIRACION_MINUTOS, JWT_SECRET
from backend.infrastructure.persistence.models.configuracion import RegistroBitacoraModel


def test_hu02_el_cierre_de_sesion_queda_en_la_bitacora(cliente, crear_usuario, entrar, db):
    crear_usuario("ana@bee.com.co")
    cabeceras = entrar("ana@bee.com.co")

    assert cliente.post("/auth/logout", headers=cabeceras).status_code == 204

    acciones = [r.accion for r in db.query(RegistroBitacoraModel).all()]
    assert "LOGOUT" in acciones


def test_hu02_criterio4_la_sesion_dura_treinta_minutos(cliente, crear_usuario, entrar):
    crear_usuario("ana@bee.com.co")
    token = entrar("ana@bee.com.co")["Authorization"].split()[1]

    datos = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    duracion = datetime.fromtimestamp(datos["exp"], UTC) - datetime.fromtimestamp(datos["iat"], UTC)

    assert JWT_EXPIRACION_MINUTOS == 30
    assert duracion == timedelta(minutes=30)


def test_hu02_criterio4_un_token_inactivo_mas_de_treinta_minutos_se_rechaza(
    cliente, crear_usuario
):
    usuario = crear_usuario("ana@bee.com.co")
    hace_una_hora = datetime.now(UTC) - timedelta(hours=1)
    vencido = jwt.encode(
        {
            "sub": usuario.id,
            "iat": hace_una_hora,
            "exp": hace_una_hora + timedelta(minutes=30),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    respuesta = cliente.get("/auth/yo", headers={"Authorization": f"Bearer {vencido}"})

    assert respuesta.status_code == 401
    assert "expiró" in respuesta.json()["detail"]


def test_hu02_criterio4_renovar_entrega_un_token_valido_y_alarga_la_sesion(
    cliente, crear_usuario, entrar
):
    crear_usuario("ana@bee.com.co")
    cabeceras = entrar("ana@bee.com.co")

    respuesta = cliente.post("/auth/renovar", headers=cabeceras)

    assert respuesta.status_code == 200
    nuevas = {"Authorization": f"Bearer {respuesta.json()['access_token']}"}
    assert cliente.get("/auth/yo", headers=nuevas).status_code == 200


def test_hu02_renovar_exige_sesion(cliente):
    assert cliente.post("/auth/renovar").status_code == 401


def test_hu02_una_cuenta_inactivada_no_puede_renovar(cliente, crear_usuario, entrar, db):
    usuario = crear_usuario("ana@bee.com.co")
    cabeceras = entrar("ana@bee.com.co")
    usuario.activo = False
    db.commit()

    assert cliente.post("/auth/renovar", headers=cabeceras).status_code == 401
