"""Puntuación de cada caso: ¿acertó la herramienta?, ¿los args?, ¿por qué falló?, ¿acertó el área (router)?"""
import unicodedata


def sin_tildes(valor):
    """Minúsculas y sin tildes, para comparar sin que acentos o mayúsculas cuenten como fallo."""
    texto = unicodedata.normalize("NFD", str(valor).strip().lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def args_ok(args_modelo, args_esperados):
    """Compara cada clave esperada con el argumento del modelo. 'franja' ausente cuenta como 'ninguna'."""
    if not isinstance(args_modelo, dict):
        args_modelo = {}
    for clave, esperado in args_esperados.items():
        valor = args_modelo.get(clave, "ninguna" if clave == "franja" else "")
        if sin_tildes(valor) != sin_tildes(esperado):
            return False
    return True


def tipo_de_fallo(elegida, esperada, nombres_objetivo):
    """Por qué falló el caso. None si acertó la herramienta."""
    if elegida == esperada:
        return None
    if esperada is None:
        return "llamo_cuando_no_debia"
    if elegida is None:
        return "no_llamo_cuando_debia"
    if elegida not in nombres_objetivo:
        return "distractora"
    return "otra_objetivo"


def puntuar(r, caso, nombres_objetivo):
    """Junta las comprobaciones de arriba en los campos que se guardan en la fila de resultados."""
    esperada = caso["herramienta_esperada"]
    elegida = r["herramienta_elegida"]
    acierto = elegida == esperada

    args_esperados = caso.get("args_esperados")
    ok_args = args_ok(r["args"], args_esperados) if (acierto and args_esperados) else None

    area = r.get("area_router")
    area_ok = None
    if area is not None:
        # Si no se esperaba ninguna herramienta, también cuenta como acierto que el router
        # diga "ninguna" aunque el área temática del caso sea otra (p.ej. un "citas" ambiguo).
        area_ok = (area == caso["area"]) or (esperada is None and area == "ninguna")

    return {
        "acierto": acierto,
        "args_ok": ok_args,
        "tipo_fallo": tipo_de_fallo(elegida, esperada, nombres_objetivo),
        "area_ok": area_ok,
    }
