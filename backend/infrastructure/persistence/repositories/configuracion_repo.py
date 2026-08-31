from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.configuracion import (
    ConfiguracionOneDriveModel,
    ParametroRecomendacionModel,
    RegistroBitacoraModel,
)


class OneDriveConfigRepository:
    """
    Acceso a la configuración de conexión con OneDrive (HU-05).

    Solo se mantiene un registro activo. Las escrituras son atómicas: o se
    guarda la configuración completa, o no se toca la anterior.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_activa(self) -> Optional[ConfiguracionOneDriveModel]:
        return (
            self.db.query(ConfiguracionOneDriveModel)
            .filter(ConfiguracionOneDriveModel.activa.is_(True))
            .order_by(ConfiguracionOneDriveModel.updated_at.desc())
            .first()
        )

    def guardar(
        self,
        tenant_id: str,
        client_id: str,
        client_secret_cifrado: str,
        drive_id: str,
        carpeta_cv: str,
        usuario_id: Optional[str] = None,
        documentos_detectados: Optional[int] = None,
    ) -> ConfiguracionOneDriveModel:
        """
        Crea o actualiza la configuración activa.

        Se llama solo después de que la conexión fue validada, de modo que una
        credencial inválida nunca sobrescribe la configuración anterior.
        """
        config = self.get_activa()

        if config is None:
            config = ConfiguracionOneDriveModel(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret_cifrado=client_secret_cifrado,
                drive_id=drive_id,
                carpeta_cv=carpeta_cv,
                actualizado_por=usuario_id,
                ultima_validacion=utcnow(),
                documentos_detectados=documentos_detectados,
            )
            self.db.add(config)
        else:
            cambio_origen = config.drive_id != drive_id or config.carpeta_cv != carpeta_cv

            config.tenant_id = tenant_id
            config.client_id = client_id
            config.client_secret_cifrado = client_secret_cifrado
            config.drive_id = drive_id
            config.carpeta_cv = carpeta_cv
            config.actualizado_por = usuario_id
            config.ultima_validacion = utcnow()
            config.documentos_detectados = documentos_detectados

            # Si cambió la carpeta o el drive, el token delta anterior ya no
            # aplica: la próxima sincronización debe recorrer todo de nuevo.
            if cambio_origen:
                config.delta_link = None

        self.db.commit()
        self.db.refresh(config)
        return config

    def registrar_validacion(self, documentos_detectados: int) -> Optional[ConfiguracionOneDriveModel]:
        config = self.get_activa()
        if not config:
            return None
        config.ultima_validacion = utcnow()
        config.documentos_detectados = documentos_detectados
        self.db.commit()
        self.db.refresh(config)
        return config

    def actualizar_delta(self, delta_link: Optional[str]) -> None:
        config = self.get_activa()
        if config:
            config.delta_link = delta_link
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
