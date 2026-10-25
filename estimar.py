"""Estima los tokens de entrada de los 250 casos en cada variante, sin generar ninguna respuesta.

Usa client.messages.count_tokens con el primer caso del dataset. Solo cuenta tokens de
ENTRADA (count_tokens no sabe cuánto va a generar el modelo).

Uso:
    python estimar.py
"""
import anthropic

from config import MODELO, PROMPT_ROUTER, SYSTEM_PROMPT
from datos import cargar_casos, cargar_herramientas, tools_de_area, tools_hasta

N_CASOS = 250
cliente = anthropic.Anthropic()


def contar(system, mensajes, tools=None):
    """Cuenta tokens de entrada de una petición. Devuelve None si el conteo falla."""
    extra = {"tools": tools} if tools else {}
    try:
        return cliente.messages.count_tokens(model=MODELO, system=system, messages=mensajes, **extra).input_tokens
    except Exception as e:
        print(f"  (no se pudo contar: {e})")
        return None


def imprimir_estimacion(nombre, tin):
    if tin is None:
        return 0
    print(f"  tokens_entrada={tin}  x {N_CASOS} casos = {tin * N_CASOS}")
    return tin * N_CASOS


def estimar():
    caso = cargar_casos(limite=1)[0]
    herramientas = cargar_herramientas()
    mensajes = [{"role": "user", "content": caso["texto"]}]

    tools_buscador = [{"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"}] + [
        dict(h["definicion"], defer_loading=True) for h in herramientas
    ]
    variantes_tools = {
        "todas_15": tools_hasta(herramientas, 15),
        "todas_30": tools_hasta(herramientas, 30),
        "todas_60": tools_hasta(herramientas, 60),
        "buscador_60": tools_buscador,
    }

    print(f"Estimación con el caso #{caso['id']} ({len(mensajes[0]['content'])} caracteres):\n")
    total = 0
    for nombre, tools in variantes_tools.items():
        print(f"{nombre}:")
        total += imprimir_estimacion(nombre, contar(SYSTEM_PROMPT, mensajes, tools))

    print("\nrouter_60 (dos llamadas; área 'citas', la más grande):")
    tin1 = contar(PROMPT_ROUTER, mensajes)
    tin2 = contar(SYSTEM_PROMPT, mensajes, tools_de_area(herramientas, "citas"))
    if tin1 is not None and tin2 is not None:
        total += imprimir_estimacion("router_60", tin1 + tin2)

    print(f"\nTotal estimado de tokens de entrada (todas las variantes, {N_CASOS} casos): {total}")


if __name__ == "__main__":
    estimar()
