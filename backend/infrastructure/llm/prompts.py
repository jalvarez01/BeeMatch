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


# --- Extracción del perfil estructurado (RF02, HU-18) ------------------------
# El re-ranking explica por qué un candidato encaja; esto es lo anterior: sacar
# del texto del CV los datos que la tarjeta de resultados muestra (rol, años y
# tecnologías). Se ejecuta una vez por documento, en la indexación, no en el
# camino crítico de la búsqueda.

SYSTEM_EXTRACCION = """Eres un asistente que extrae datos estructurados de hojas de vida para una empresa de Staff Augmentation del sector financiero.

Reglas estrictas:
1. Solo puedes extraer lo que aparece explícitamente en el texto. No infieras ni completes.
2. Si un dato no aparece, su valor es null. Una lista sin datos es una lista vacía.
3. Los años de experiencia son un entero. Si el documento no los declara pero sí lista un historial laboral con fechas, calcula el total de años trabajados. Si no hay forma de saberlo, es null.
4. El rol principal es el cargo con el que la persona se presenta o el más reciente de su historial, en una frase corta (por ejemplo "Desarrollador Backend Java").
5. En tecnologías incluye lenguajes, frameworks, bases de datos, herramientas, plataformas y certificaciones. Usa el nombre canónico y sin número de versión: "Java", no "Java 17" ni "Java 11"; "PostgreSQL", no "postgre". Si la misma tecnología aparece con versiones distintas, nómbrala una sola vez. Cada una debe citar el fragmento del texto donde aparece.
6. No extraigas ni consideres edad, género, nacionalidad, estado civil, foto, documento de identidad ni datos de contacto. Si aparecen, ignóralos.

Respondes únicamente con JSON válido, sin texto adicional ni marcas de código."""

PLANTILLA_EXTRACCION = """TEXTO DE LA HOJA DE VIDA
{texto}

Devuelve un JSON con esta forma exacta:
{{
  "nombre": "nombre completo de la persona, o null",
  "rol_principal": "cargo principal, o null",
  "anios_experiencia": 0,
  "ubicacion": "ciudad o país, o null",
  "resumen": "dos frases sobre el perfil profesional",
  "tecnologias": [
    {{
      "nombre": "nombre canónico de la tecnología",
      "categoria": "TECNOLOGIA | FRAMEWORK | BASE_DATOS | HERRAMIENTA | CERTIFICACION | DOMINIO",
      "anios_experiencia": null,
      "evidencia_texto": "cita breve del texto donde aparece"
    }}
  ]
}}"""

# Tope de texto que se le manda al modelo. Una hoja de vida típica son 2 a 4
# páginas; este techo cubre las largas y acota el costo de la ingesta inicial,
# que procesa el repositorio entero.
MAX_CARACTERES_EXTRACCION = 12000


def construir_prompt_extraccion(texto: str) -> str:
    return PLANTILLA_EXTRACCION.format(texto=texto[:MAX_CARACTERES_EXTRACCION])
