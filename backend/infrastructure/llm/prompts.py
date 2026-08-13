"""
Prompts del motor de matching.

Regla de diseño: el modelo solo puede afirmar lo que aparece en los fragmentos
que se le entregan. Si un requisito no aparece, debe marcarlo NO_EVIDENCIADO y
nunca afirmar que el candidato carece de él (RNF27, RNF28).
"""

SYSTEM_RERANK = """Eres un asistente de preselección de talento para una empresa de Staff Augmentation del sector financiero.

Recibes el perfil solicitado por un cliente y fragmentos textuales extraídos de hojas de vida.

Reglas estrictas:
1. Solo puedes afirmar lo que aparece explícitamente en los fragmentos entregados.
2. Si un requisito solicitado no aparece en los fragmentos, su estado es NO_EVIDENCIADO. Eso significa que el documento no lo menciona, NO que la persona carezca de la habilidad. Nunca afirmes lo segundo.
3. Toda coincidencia con estado ENCONTRADO o PARCIAL debe citar el fragmento que la sustenta.
4. No consideres edad, género, nacionalidad, estado civil ni fotografía. Si aparecen, ignóralos.
5. El puntaje de afinidad es un entero de 0 a 100.

Respondes únicamente con JSON válido, sin texto adicional ni marcas de código."""

PLANTILLA_RERANK = """PERFIL SOLICITADO
{perfil}

REQUISITOS A EVALUAR
{requisitos}

CANDIDATOS
{candidatos}

Devuelve un JSON con esta forma exacta:
{{
  "candidatos": [
    {{
      "candidato_id": "...",
      "puntaje_afinidad": 0,
      "resumen": "una frase sobre por qué encaja",
      "coincidencias": [
        {{
          "requisito": "...",
          "estado": "ENCONTRADO | PARCIAL | NO_EVIDENCIADO",
          "evidencia_texto": "cita breve del fragmento, o null",
          "fragmento_id": "id del fragmento citado, o null"
        }}
      ]
    }}
  ]
}}"""


def construir_prompt_rerank(perfil: str, requisitos: list[str], candidatos: list[dict]) -> str:
    bloques = []
    for c in candidatos:
        fragmentos = "\n".join(f"  [{f['id']}] {f['texto']}" for f in c["fragmentos"])
        bloques.append(f"- candidato_id: {c['candidato_id']}\n  nombre: {c['nombre']}\n{fragmentos}")

    return PLANTILLA_RERANK.format(
        perfil=perfil,
        requisitos="\n".join(f"- {r}" for r in requisitos),
        candidatos="\n\n".join(bloques),
    )
