"""Resume un archivo de resultados. No llama a la API, así que no gasta nada.

Uso:
    python informe.py results/results_XXXX.jsonl
"""
import json
import statistics
import sys
from collections import Counter

TIPOS_FALLO = ["llamo_cuando_no_debia", "no_llamo_cuando_debia", "distractora", "otra_objetivo"]


def media(filas, clave):
    return sum(f[clave] for f in filas) / len(filas) if filas else 0.0


def tasa(filas, condicion):
    """Fracción de filas que cumplen la condición (0 si no hay filas)."""
    return sum(1 for f in filas if condicion(f)) / len(filas) if filas else 0.0


def pct(valor):
    return f"{valor * 100:.1f}%"


def imprimir_tabla(cabecera, filas):
    """Imprime una tabla con las columnas alineadas."""
    anchos = [max(len(str(x)) for x in columna) for columna in zip(cabecera, *filas)]
    for linea in [cabecera] + filas:
        print("  ".join(str(celda).ljust(ancho) for celda, ancho in zip(linea, anchos)))


def imprimir_resumen_por_variante(filas, variantes):
    print("\n== Resumen por variante (solo filas sin error) ==")
    tabla = []
    for v in variantes:
        fv = [f for f in filas if f["variante"] == v]
        if not fv:
            tabla.append([v, 0, "-", "-", "-", "-", "-", "-", "-", "-", 0])
            continue
        con_tool = [f for f in fv if f["herramienta_esperada"] is not None]
        sin_tool = [f for f in fv if f["herramienta_esperada"] is None]
        con_args = [f for f in fv if f["args_ok"] is not None]
        tabla.append([
            v, len(fv),
            pct(tasa(fv, lambda f: f["acierto"])),
            pct(tasa(con_tool, lambda f: f["acierto"])) if con_tool else "-",
            pct(tasa(sin_tool, lambda f: f["acierto"])) if sin_tool else "-",
            pct(media(con_args, "args_ok")) if con_args else "-",
            pct(tasa(fv, lambda f: f["tipo_fallo"] == "distractora")),
            round(media(fv, "tin")), round(media(fv, "tout")),
            round(statistics.median(f["ms"] for f in fv)),
            sum(f["llamadas"] for f in fv),
        ])
    imprimir_tabla(
        ["variante", "n", "acierto", "acierto_con_tool", "acierto_sin_tool", "args_ok",
         "distractora", "tok_in", "tok_out", "ms_mediana", "llamadas"],
        tabla,
    )


def imprimir_acierto_por_area(filas, variantes, areas):
    print("\n== Acierto por área y variante ==")
    tabla = []
    for v in variantes:
        fila = [v]
        for a in areas:
            fa = [f for f in filas if f["variante"] == v and f["area"] == a]
            fila.append(pct(tasa(fa, lambda f: f["acierto"])) if fa else "-")
        tabla.append(fila)
    imprimir_tabla(["variante"] + areas, tabla)


def imprimir_fallos_por_variante(filas, variantes):
    print("\n== Tipos de fallo por variante ==")
    tabla = []
    for v in variantes:
        fv = [f for f in filas if f["variante"] == v]
        conteo = Counter(f["tipo_fallo"] for f in fv if f["tipo_fallo"])
        tabla.append([v] + [conteo.get(t, 0) for t in TIPOS_FALLO])
    imprimir_tabla(["variante"] + TIPOS_FALLO, tabla)


def imprimir_confusiones(filas, variantes):
    print("\n== Top 10 confusiones (esperada -> elegida) por variante ==")
    for v in variantes:
        fv_variante = [f for f in filas if f["variante"] == v]
        print(f"\n{v}:")
        if not fv_variante:
            print("  (sin filas válidas)")
            continue
        conteo = Counter(
            (f["herramienta_esperada"], f["herramienta_elegida"]) for f in fv_variante if not f["acierto"]
        )
        if not conteo:
            print("  (sin fallos)")
            continue
        for (esperada, elegida), n in conteo.most_common(10):
            print(f"  {esperada} -> {elegida}: {n}")


def imprimir_area_router(filas):
    fr = [f for f in filas if f["area_router"] is not None]
    if not fr:
        return
    print("\n== Router: área correcta ==")
    print(f"{pct(tasa(fr, lambda f: f['area_ok']))} de {len(fr)} casos")


def se_excluye(f):
    """Fila que no se puede puntuar de fiar: falló la API, o la respuesta se cortó por max_tokens."""
    return bool(f["error"]) or f["stop_reason"] == "max_tokens"


def imprimir_informe(filas):
    excluidas = [f for f in filas if se_excluye(f)]
    validas = [f for f in filas if not se_excluye(f)]

    if excluidas:
        por_error = sum(1 for f in excluidas if f["error"])
        por_max_tokens = len(excluidas) - por_error
        print(f"⚠ {len(excluidas)} de {len(filas)} filas excluidas de los porcentajes de abajo "
              f"({por_error} con error de la API, {por_max_tokens} cortadas por max_tokens).\n")

    variantes = list(dict.fromkeys(f["variante"] for f in filas))  # orden de ejecución; incluye las con error
    areas = sorted({f["area"] for f in validas})

    imprimir_resumen_por_variante(validas, variantes)
    imprimir_acierto_por_area(validas, variantes, areas)
    imprimir_fallos_por_variante(validas, variantes)
    imprimir_confusiones(validas, variantes)
    imprimir_area_router(validas)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python informe.py results/results_XXXX.jsonl")
    with open(sys.argv[1], encoding="utf-8") as archivo:
        imprimir_informe([json.loads(linea) for linea in archivo if linea.strip()])
