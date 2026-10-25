"""Compara buscador_60 y buscador_60_noconf, para ver si los fallos de buscador_60 son por
pedir confirmación de más o por no encontrar la herramienta correcta. No llama a la API.

Acepta uno o varios archivos de resultados (p.ej. uno con buscador_60 y otro con
buscador_60_noconf) y agrupa por el campo "variante" de cada fila.

Uso:
    python comparar_buscador.py results/results_buscador_60_XXXX.jsonl results/results_buscador_60_noconf_XXXX.jsonl
"""
import json
import statistics
import sys

from informe import imprimir_tabla, media, pct, se_excluye, tasa

TIPOS = ["claro", "rebuscado", "ambiguo", "malicioso", "fuera_de_ambito"]


def cargar(rutas):
    filas = []
    for ruta in rutas:
        with open(ruta, encoding="utf-8") as f:
            filas += [json.loads(linea) for linea in f if linea.strip()]

    excluidas = [f for f in filas if se_excluye(f)]
    if excluidas:
        print(f"⚠ {len(excluidas)} de {len(filas)} filas excluidas (error de la API o max_tokens).\n")
    return [f for f in filas if not se_excluye(f)]


def imprimir_acierto(filas, variantes):
    print("== Acierto global y por tipo de caso ==")
    tabla = []
    for v in variantes:
        fv = [f for f in filas if f["variante"] == v]
        fila = [v, len(fv), pct(tasa(fv, lambda f: f["acierto"]))]
        for t in TIPOS:
            ft = [f for f in fv if f["tipo"] == t]
            fila.append(pct(tasa(ft, lambda f: f["acierto"])) if ft else "-")
        tabla.append(fila)
    imprimir_tabla(["variante", "n", "acierto"] + TIPOS, tabla)


def imprimir_fallos_por_tipo(filas, variantes):
    print("\n== llamo_cuando_no_debia / no_llamo_cuando_debia, por tipo de caso ==")
    for v in variantes:
        print(f"\n{v}:")
        tabla = []
        for t in TIPOS:
            ft = [f for f in filas if f["variante"] == v and f["tipo"] == t]
            llamo_de_mas = sum(1 for f in ft if f["tipo_fallo"] == "llamo_cuando_no_debia")
            no_llamo = sum(1 for f in ft if f["tipo_fallo"] == "no_llamo_cuando_debia")
            tabla.append([t, len(ft), llamo_de_mas, no_llamo])
        imprimir_tabla(["tipo", "n", "llamo_cuando_no_debia", "no_llamo_cuando_debia"], tabla)


def imprimir_busquedas_y_latencia(filas, variantes):
    print("\n== Búsquedas medias por caso y latencia mediana ==")
    tabla = []
    for v in variantes:
        fv = [f for f in filas if f["variante"] == v]
        tabla.append([
            v,
            round(media(fv, "busquedas"), 2) if fv else "-",
            round(statistics.median(f["ms"] for f in fv)) if fv else "-",
        ])
    imprimir_tabla(["variante", "busquedas_media", "ms_mediana"], tabla)


def comparar(filas):
    variantes = list(dict.fromkeys(f["variante"] for f in filas))
    imprimir_acierto(filas, variantes)
    imprimir_fallos_por_tipo(filas, variantes)
    imprimir_busquedas_y_latencia(filas, variantes)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python comparar_buscador.py results/archivo1.jsonl [results/archivo2.jsonl ...]")
    comparar(cargar(sys.argv[1:]))
