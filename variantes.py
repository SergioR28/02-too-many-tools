"""Las 6 variantes para medir cómo elige el modelo una herramienta entre muchas.

Todas reciben el texto del usuario y devuelven un diccionario con:
  herramienta_elegida  nombre de la tool que llamó (None si no llamó a ninguna)
  args                 argumentos con los que la llamó (None si no llamó)
  area_router          área que eligió el router (None salvo en router_60)
  tin, tout            tokens de entrada y de salida, sumados de todas las llamadas
  llamadas             número de llamadas a la API hechas para este caso
  busquedas            número de búsquedas del buscador (0 salvo en buscador_60)
  bruto                resumen en texto de los bloques de la respuesta
  stop_reason          el de la última respuesta (en el router, el de la 2ª llamada si la hubo)
"""
import json

import anthropic

from config import (
    ESQUEMA_ROUTER,
    MAX_TOKENS,
    MODELO,
    PROMPT_EXTRA_BUSCADOR,
    PROMPT_EXTRA_NOCONF,
    PROMPT_ROUTER,
    SYSTEM_PROMPT,
    TEMPERATURA,
)
from datos import cargar_herramientas, tools_de_area, tools_hasta

MAX_PAUSE_TURN = 3  # límite de reintentos si el buscador agota las iteraciones del servidor
cliente = anthropic.Anthropic()

HERRAMIENTAS = cargar_herramientas()
TOOLS_15 = tools_hasta(HERRAMIENTAS, 15)
TOOLS_30 = tools_hasta(HERRAMIENTAS, 30)
TOOLS_60 = tools_hasta(HERRAMIENTAS, 60)

# El buscador necesita las 60 definiciones con defer_loading=True (no entran en el contexto
# hasta que el modelo las busca). La propia tool de búsqueda NUNCA se marca como diferida:
# así queda como la única "no diferida" y la API no se queja de "todas las tools diferidas".
TOOLS_BUSCADOR = [{"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"}] + [
    dict(definicion, defer_loading=True) for definicion in TOOLS_60
]

TOOLS_POR_AREA = {area: tools_de_area(HERRAMIENTAS, area) for area in {h["area"] for h in HERRAMIENTAS}}

# Mismo system prompt que las demás variantes, más el aviso de que hay que buscar. Es la
# única diferencia de buscador_60 respecto al resto: se guarda aparte para que se vea claro.
SYSTEM_BUSCADOR = f"{SYSTEM_PROMPT} {PROMPT_EXTRA_BUSCADOR}"

# El de buscador_60 + el bloque contra pedir confirmación de más. Es la ÚNICA diferencia
# entre buscador_60 y buscador_60_noconf: mismas 60 tools, mismo mecanismo de búsqueda,
# mismo modelo y parámetros.
SYSTEM_BUSCADOR_NOCONF = f"{SYSTEM_BUSCADOR}\n\n{PROMPT_EXTRA_NOCONF}"


# ---------------------------------------------------------------- ayudas
def llamar(mensajes, system=SYSTEM_PROMPT, **extra):
    """Una llamada a la API. Devuelve (respuesta, tokens_entrada, tokens_salida)."""
    parametros = dict(model=MODELO, max_tokens=MAX_TOKENS, system=system, messages=mensajes, **extra)
    if TEMPERATURA is not None:
        parametros["temperature"] = TEMPERATURA
    respuesta = cliente.messages.create(**parametros)
    return respuesta, respuesta.usage.input_tokens, respuesta.usage.output_tokens


def texto_de(respuesta):
    """Une los bloques de texto de la respuesta."""
    return "".join(b.text for b in respuesta.content if b.type == "text")


def primer_tool_use(bloques):
    """El primer tool_use real (ignora los server_tool_use del buscador). (nombre, args) o (None, None)."""
    for b in bloques:
        if b.type == "tool_use":
            return b.name, b.input
    return None, None


def resumen_bloques(bloques):
    """Resumen corto de los bloques de la respuesta, para depurar sin guardar la respuesta entera."""
    partes = []
    for b in bloques:
        if b.type == "text":
            partes.append(f"text:{b.text[:80]!r}")
        elif b.type == "tool_use":
            partes.append(f"tool_use:{b.name}({json.dumps(b.input, ensure_ascii=False)})")
        elif b.type == "server_tool_use":
            partes.append(f"server_tool_use:{b.name}({json.dumps(b.input, ensure_ascii=False)})")
        elif b.type == "tool_search_tool_result":
            contenido = b.content
            if getattr(contenido, "type", None) == "tool_search_tool_result_error":
                partes.append(f"tool_search_tool_result:error={contenido.error_code}")
            else:
                nombres = [r.tool_name for r in getattr(contenido, "tool_references", [])]
                partes.append(f"tool_search_tool_result:{nombres}")
        else:
            partes.append(b.type)
    return " | ".join(partes)


def resultado(herramienta_elegida, args, tin, tout, llamadas=1, busquedas=0, area_router=None, bruto="",
              stop_reason=None):
    return {
        "herramienta_elegida": herramienta_elegida,
        "args": args,
        "area_router": area_router,
        "tin": tin,
        "tout": tout,
        "llamadas": llamadas,
        "busquedas": busquedas,
        "bruto": bruto,
        "stop_reason": stop_reason,
    }


def leer_area(texto_json):
    """Saca el área del JSON del router. 'ninguna' si no se puede leer (caso defensivo)."""
    try:
        return json.loads(texto_json)["area"]
    except (ValueError, KeyError, TypeError):
        return "ninguna"


# ---------------------------------------------------------------- las 5 variantes
def _con_tools(texto, tools):
    """Una sola llamada con una lista fija de tools y tool_choice automático."""
    respuesta, tin, tout = llamar(
        [{"role": "user", "content": texto}],
        tools=tools,
        tool_choice={"type": "auto"},
    )
    nombre, args = primer_tool_use(respuesta.content)
    return resultado(nombre, args, tin, tout, bruto=resumen_bloques(respuesta.content),
                      stop_reason=respuesta.stop_reason)


def todas_15(texto):
    """1. Solo las 15 herramientas de la variante más pequeña."""
    return _con_tools(texto, TOOLS_15)


def todas_30(texto):
    """2. Las 30 herramientas de la variante intermedia."""
    return _con_tools(texto, TOOLS_30)


def todas_60(texto):
    """3. Las 60 herramientas, todas visibles a la vez."""
    return _con_tools(texto, TOOLS_60)


def _buscador(texto, system):
    """Mecanismo común del buscador: las 60 tools diferidas, el modelo busca antes de llamar.
    Compartido por buscador_60 y buscador_60_noconf — lo único que varía entre ellas es `system`.
    """
    mensajes = [{"role": "user", "content": texto}]
    tin_total = tout_total = 0
    llamadas = busquedas = 0
    bloques = []

    respuesta, tin, tout = llamar(mensajes, system=system, tools=TOOLS_BUSCADOR, tool_choice={"type": "auto"})
    tin_total += tin
    tout_total += tout
    llamadas += 1
    bloques += list(respuesta.content)
    busquedas += sum(1 for b in respuesta.content if b.type == "server_tool_use")

    # El buscador del servidor tiene un límite de iteraciones; si lo agota, la respuesta
    # llega con pause_turn y hay que repetir la petición (con el contenido del asistente
    # añadido) para que el modelo siga donde lo dejó.
    intentos = 0
    while respuesta.stop_reason == "pause_turn" and intentos < MAX_PAUSE_TURN:
        mensajes = [
            {"role": "user", "content": texto},
            {"role": "assistant", "content": respuesta.content},
        ]
        respuesta, tin, tout = llamar(mensajes, system=system, tools=TOOLS_BUSCADOR, tool_choice={"type": "auto"})
        tin_total += tin
        tout_total += tout
        llamadas += 1
        intentos += 1
        bloques += list(respuesta.content)
        busquedas += sum(1 for b in respuesta.content if b.type == "server_tool_use")

    nombre, args = primer_tool_use(bloques)
    return resultado(
        nombre, args, tin_total, tout_total, llamadas=llamadas, busquedas=busquedas,
        bruto=resumen_bloques(bloques), stop_reason=respuesta.stop_reason,
    )


def buscador_60(texto):
    """4. Las 60, todas diferidas: el modelo tiene que buscar antes de poder llamar a ninguna."""
    return _buscador(texto, SYSTEM_BUSCADOR)


def buscador_60_noconf(texto):
    """4b. Igual que buscador_60 (mismas tools, mismo mecanismo), con una instrucción extra
    en el system prompt contra pedir confirmación de más. Para aislar si los fallos de
    buscador_60 son por confirmar en exceso o por no encontrar la herramienta correcta."""
    return _buscador(texto, SYSTEM_BUSCADOR_NOCONF)


def router_60(texto):
    """5. Primero clasifica el área (sin tools), luego decide con las 10 tools de esa área."""
    mensajes = [{"role": "user", "content": texto}]
    respuesta1, tin1, tout1 = llamar(
        mensajes,
        system=PROMPT_ROUTER,
        output_config={"format": {"type": "json_schema", "schema": ESQUEMA_ROUTER}},
    )
    texto1 = texto_de(respuesta1)
    area = leer_area(texto1)

    if area == "ninguna":
        return resultado(None, None, tin1, tout1, area_router=area, bruto=f"router:{texto1!r}",
                          stop_reason=respuesta1.stop_reason)

    respuesta2, tin2, tout2 = llamar(mensajes, tools=TOOLS_POR_AREA[area], tool_choice={"type": "auto"})
    nombre, args = primer_tool_use(respuesta2.content)
    return resultado(
        nombre, args, tin1 + tin2, tout1 + tout2, llamadas=2, area_router=area,
        bruto=f"router:{texto1!r} | {resumen_bloques(respuesta2.content)}",
        stop_reason=respuesta2.stop_reason,
    )


VARIANTES = {
    "todas_15": todas_15,
    "todas_30": todas_30,
    "todas_60": todas_60,
    "buscador_60": buscador_60,
    "buscador_60_noconf": buscador_60_noconf,
    "router_60": router_60,
}
