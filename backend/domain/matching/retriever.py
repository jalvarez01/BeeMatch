"""
Etapa 1 del motor: recuperación híbrida.

Combina búsqueda léxica (términos exactos: "Spring Boot", "Temenos T24") con
búsqueda vectorial (equivalencias semánticas: "core bancario"). Los dos rankings
se fusionan con Reciprocal Rank Fusion.

Es la etapa que hace viable el sistema: reduce ~200 hojas de vida a ~20
finalistas antes de invocar al LLM (RNF02).
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import USA_PGVECTOR
from backend.infrastructure.llm.embeddings import deserializar
from backend.infrastructure.persistence.models.hoja_vida import FragmentoCVModel

K_RRF = 60  # constante estándar de Reciprocal Rank Fusion


@dataclass
class FragmentoRecuperado:
    fragmento_id: str
    hoja_de_vida_id: str
    texto: str
    puntaje: float


class RecuperadorHibrido:
    def __init__(self, db: Session):
        self.db = db

    def recuperar(self, consulta: str, embedding: list[float], limite: int = 60) -> list[FragmentoRecuperado]:
        lexico = self._buscar_lexico(consulta, limite)
        vectorial = self._buscar_vectorial(embedding, limite)
        return self._fusionar(lexico, vectorial, limite)

    # --- Búsqueda léxica -----------------------------------------------------

    def _buscar_lexico(self, consulta: str, limite: int) -> list[str]:
        """tsvector + GIN en PostgreSQL; LIKE simple en SQLite para desarrollo."""
        if USA_PGVECTOR:
            filas = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM fragmentos_cv
                    WHERE to_tsvector('spanish', texto) @@ plainto_tsquery('spanish', :q)
                    ORDER BY ts_rank(to_tsvector('spanish', texto),
                                     plainto_tsquery('spanish', :q)) DESC
                    LIMIT :limite
                    """
                ),
                {"q": consulta, "limite": limite},
            ).fetchall()
            return [f[0] for f in filas]

        terminos = [t for t in consulta.split() if len(t) > 3]
        if not terminos:
            return []
        consulta_orm = self.db.query(FragmentoCVModel.id)
        for termino in terminos[:8]:
            consulta_orm = consulta_orm.filter(FragmentoCVModel.texto.ilike(f"%{termino}%"))
        return [f[0] for f in consulta_orm.limit(limite).all()]

    # --- Búsqueda vectorial --------------------------------------------------

    def _buscar_vectorial(self, embedding: list[float], limite: int) -> list[str]:
        """Distancia coseno sobre el índice HNSW de pgvector."""
        if not embedding:
            return []

        if USA_PGVECTOR:
            filas = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM fragmentos_cv
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:vec AS vector)
                    LIMIT :limite
                    """
                ),
                {"vec": str(embedding), "limite": limite},
            ).fetchall()
            return [f[0] for f in filas]

        # Fallback en memoria para desarrollo con SQLite.
        puntajes: list[tuple[str, float]] = []
        for fragmento in self.db.query(FragmentoCVModel).all():
            vector = deserializar(fragmento.embedding)
            if vector:
                puntajes.append((fragmento.id, _coseno(embedding, vector)))
        puntajes.sort(key=lambda p: p[1], reverse=True)
        return [f[0] for f in puntajes[:limite]]

    # --- Fusión --------------------------------------------------------------

    def _fusionar(self, lexico: list[str], vectorial: list[str], limite: int) -> list[FragmentoRecuperado]:
        puntajes: dict[str, float] = {}
        for ranking in (lexico, vectorial):
            for posicion, fragmento_id in enumerate(ranking, start=1):
                puntajes[fragmento_id] = puntajes.get(fragmento_id, 0.0) + 1.0 / (K_RRF + posicion)

        mejores = sorted(puntajes.items(), key=lambda p: p[1], reverse=True)[:limite]
        if not mejores:
            return []

        ids = [m[0] for m in mejores]
        fragmentos = {
            f.id: f
            for f in self.db.query(FragmentoCVModel).filter(FragmentoCVModel.id.in_(ids)).all()
        }

        resultado = []
        for fragmento_id, puntaje in mejores:
            fragmento = fragmentos.get(fragmento_id)
            if fragmento:
                resultado.append(
                    FragmentoRecuperado(
                        fragmento_id=fragmento.id,
                        hoja_de_vida_id=fragmento.hoja_de_vida_id,
                        texto=fragmento.texto,
                        puntaje=puntaje,
                    )
                )
        return resultado


def _coseno(a: list[float], b: list[float]) -> float:
    producto = sum(x * y for x, y in zip(a, b))
    norma_a = sum(x * x for x in a) ** 0.5
    norma_b = sum(y * y for y in b) ** 0.5
    return producto / (norma_a * norma_b) if norma_a and norma_b else 0.0
