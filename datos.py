"""Carga las herramientas y los casos, y construye las listas de tools por variante y por área."""
import json


def cargar_herramientas(ruta="herramientas.json"):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cargar_casos(ruta="casos.jsonl", limite=None):
    with open(ruta, encoding="utf-8") as f:
        casos = [json.loads(linea) for linea in f if linea.strip()]
    return casos[:limite] if limite else casos


def tools_hasta(herramientas, tamano):
    """Definiciones cuyo 'desde' <= tamano. Las variantes están anidadas: 15 ⊆ 30 ⊆ 60."""
    return [h["definicion"] for h in herramientas if h["desde"] <= tamano]


def tools_de_area(herramientas, area):
    """Las 10 definiciones de un área concreta (para la segunda llamada del router)."""
    return [h["definicion"] for h in herramientas if h["area"] == area]


def nombres_objetivo(herramientas):
    """Nombres de las 12 herramientas 'objetivo' (las que algún caso pide de verdad)."""
    return {h["definicion"]["name"] for h in herramientas if h["objetivo"]}
