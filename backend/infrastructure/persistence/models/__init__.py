"""Modelos ORM. Importarlos aquí garantiza que Base.metadata los conozca."""

from backend.infrastructure.persistence.models.busqueda import (  # noqa: F401
    BusquedaModel,
    CoincidenciaModel,
    PreseleccionModel,
    RecomendacionModel,
)
from backend.infrastructure.persistence.models.cliente import ClienteModel, ProyectoModel  # noqa: F401
from backend.infrastructure.persistence.models.configuracion import (  # noqa: F401
    ParametroRecomendacionModel,
    RegistroBitacoraModel,
)
from backend.infrastructure.persistence.models.hoja_vida import (  # noqa: F401
    CandidatoHabilidadModel,
    CandidatoModel,
    FragmentoCVModel,
    HabilidadModel,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.models.solicitud import CriterioModel, SolicitudModel  # noqa: F401
from backend.infrastructure.persistence.models.usuario import UsuarioModel  # noqa: F401
