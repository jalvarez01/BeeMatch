from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.configuracion import (
    ConfiguracionRepositorioModel,
    ParametroRecomendacionModel,
    RegistroBitacoraModel,
)


class RepositorioConfigRepository:
    """
    Acceso a la configuración del origen de hojas de vida (HU-05).

    Solo se mantiene un registro activo, sea cual sea el proveedor. Las
    escrituras son atómicas: o se guarda la configuración completa, o no se
    toca la anterior.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_activa(self) -> Optional[ConfiguracionRepositorioModel]:
        return (
            self.db.query(ConfiguracionRepositorioModel)
            .filter(ConfiguracionRepositorioModel.activa.is_(True))
            .order_by(ConfiguracionRepositorioModel.updated_at.desc())
            .first()
        )

    def guardar(
        self,
        tipo: str,
        carpeta: str,
        credenciales_cifradas: str,
        usuario_id: Optional[str] = None,
        documentos_detectados: Optional[int] = None,
        reiniciar_cursor: bool = False,
    ) -> ConfiguracionRepositorioModel:
        """
        Crea o actualiza la configuración activa.

        Se llama solo después de que la conexión fue validada, de modo que una
        credencial inválida nunca sobrescribe la configuración anterior.

        `reiniciar_cursor` lo decide el servicio: si cambió el origen (el
        proveedor o la carpeta), el cursor anterior ya no aplica y la próxima
        sincronización debe recorrer todo de nuevo.
        """
        config = self.get_activa()

        if config is None:
            config = ConfiguracionRepositorioModel(
                tipo=tipo,
                carpeta=carpeta,
                credenciales_cifradas=credenciales_cifradas,
                actualizado_por=usuario_id,
                ultima_validacion=utcnow(),
                documentos_detectados=documentos_detectados,
            )
            self.db.add(config)
        else:
            cambio_origen = reiniciar_cursor or config.tipo != tipo or config.carpeta != carpeta

            config.tipo = tipo
            config.carpeta = carpeta
            config.credenciales_cifradas = credenciales_cifradas
            config.actualizado_por = usuario_id
            config.ultima_validacion = utcnow()
            config.documentos_detectados = documentos_detectados

            if cambio_origen:
                config.cursor_sincronizacion = None

        self.db.commit()
        self.db.refresh(config)
        return config

    def registrar_validacion(self, documentos_detectados: int) -> Optional[ConfiguracionRepositorioModel]:
        config = self.get_activa()
        if not config:
            return None
        config.ultima_validacion = utcnow()
        config.documentos_detectados = documentos_detectados
        self.db.commit()
        self.db.refresh(config)
        return config

    def actualizar_cursor(self, cursor: Optional[str]) -> None:
        config = self.get_activa()
        if config:
            config.cursor_sincronizacion = cursor
            self.db.commit()

    def desactivar(self) -> None:
        config = self.get_activa()
        if config:
            config.activa = False
            self.db.commit()


class ParametroRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, clave: str) -> Optional[ParametroRecomendacionModel]:
        return (
            self.db.query(ParametroRecomendacionModel)
            .filter(ParametroRecomendacionModel.clave == clave)
            .first()
        )

    def listar(self) -> list[ParametroRecomendacionModel]:
        return self.db.query(ParametroRecomendacionModel).order_by(ParametroRecomendacionModel.clave).all()

    def establecer(
        self, clave: str, valor: str, usuario_id: Optional[str] = None
    ) -> ParametroRecomendacionModel:
        parametro = self.get(clave)
        if parametro:
            parametro.valor = valor
            parametro.actualizado_por = usuario_id
        else:
            parametro = ParametroRecomendacionModel(clave=clave, valor=valor, actualizado_por=usuario_id)
            self.db.add(parametro)
        self.db.commit()
        self.db.refresh(parametro)
        return parametro


class BitacoraRepository:
    def __init__(self, db: Session):
        self.db = db

    def registrar(self, **datos) -> RegistroBitacoraModel:
        registro = RegistroBitacoraModel(**datos)
        self.db.add(registro)
        self.db.commit()
        self.db.refresh(registro)
        return registro

    def listar(self, limite: int = 100, desplazamiento: int = 0) -> list[RegistroBitacoraModel]:
        return (
            self.db.query(RegistroBitacoraModel)
            .order_by(RegistroBitacoraModel.created_at.desc())
            .offset(desplazamiento)
            .limit(limite)
            .all()
        )
