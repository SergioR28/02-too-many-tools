"""Pasa cada caso del dataset por las variantes indicadas y guarda cada resultado.

Uso:
    python ejecutar.py --limit 10                       # prueba pequeña
    python ejecutar.py --variantes todas_15 todas_30     # solo estas variantes
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from comprobar import puntuar
from datos import cargar_casos, cargar_herramientas, nombres_objetivo
from informe import imprimir_informe
from variantes import VARIANTES


def ejecutar_caso(nombre_variante, funcion, caso, nombres_obj):
    """Un caso con una variante. Devuelve una fila con todo lo que queremos medir."""
    inicio = time.perf_counter()
    try:
        r = funcion(caso["texto"])
        error = None
    except Exception as e:  # fallo de la API: se anota y se sigue con el siguiente
        r = {
            "herramienta_elegida": None, "args": None, "area_router": None,
            "tin": 0, "tout": 0, "llamadas": 0, "busquedas": 0, "bruto": "", "stop_reason": None,
        }
        error = str(e)
    ms = round((time.perf_counter() - inicio) * 1000)

    p = puntuar(r, caso, nombres_obj)
    return {
        "variante": nombre_variante,
        "id": caso["id"],
        "tipo": caso["tipo"],
        "area": caso["area"],
        "herramienta_esperada": caso["herramienta_esperada"],
        "herramienta_elegida": r["herramienta_elegida"],
        "acierto": p["acierto"],
        "args_ok": p["args_ok"],
        "tipo_fallo": p["tipo_fallo"],
        "area_router": r.get("area_router"),
        "area_ok": p["area_ok"],
        "tin": r["tin"],
        "tout": r["tout"],
        "llamadas": r["llamadas"],
        "busquedas": r["busquedas"],
        "ms": ms,
        "error": error,
        "stop_reason": r.get("stop_reason"),
        "bruto": r["bruto"],
    }


def main():
    ap = argparse.ArgumentParser(description="Mide cómo elige el modelo una herramienta cuando tiene muchas.")
    ap.add_argument("--casos", default="casos.jsonl")
    ap.add_argument("--herramientas", default="herramientas.json")
    ap.add_argument("--limit", type=int, default=0, help="usar solo los N primeros casos")
    ap.add_argument("--variantes", nargs="+", default=list(VARIANTES), help="nombres de variantes a correr")
    args = ap.parse_args()

    casos = cargar_casos(args.casos, args.limit)
    herramientas = cargar_herramientas(args.herramientas)
    nombres_obj = nombres_objetivo(herramientas)

    Path("results").mkdir(exist_ok=True)
    # Si se corre una sola variante, el nombre la incluye; si se corren varias (el caso por
    # defecto), se deja el nombre genérico de siempre para no tocar esa convención.
    sufijo = f"_{args.variantes[0]}" if len(args.variantes) == 1 else ""
    ruta = Path("results") / f"results{sufijo}_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    print(f"{len(casos)} casos x {len(args.variantes)} variantes "
          f"= {len(casos) * len(args.variantes)} llamadas base (más búsquedas y router)")

    filas = []
    with open(ruta, "w", encoding="utf-8") as f:
        for caso in casos:
            for nombre in args.variantes:
                fila = ejecutar_caso(nombre, VARIANTES[nombre], caso, nombres_obj)
                filas.append(fila)
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
                f.flush()  # se guarda al momento: si se corta, no pierdes lo ya pagado

    print(f"Resultados guardados en {ruta}")
    imprimir_informe(filas)


if __name__ == "__main__":
    main()
