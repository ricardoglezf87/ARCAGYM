from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import re
import unicodedata
import urllib.error
import urllib.request

from app.config import settings
from app.models import DietEntry


GROUP_ORDER = ["lacteos", "harinas", "frutas", "verduras", "proteinas", "grasas"]
GROUP_LABELS = {
    "lacteos": "Lacteos",
    "harinas": "Harinas",
    "frutas": "Frutas",
    "verduras": "Verduras",
    "proteinas": "Proteinas",
    "grasas": "Grasas",
}
GROUP_SINGULAR = {
    "lacteos": "lacteo",
    "harinas": "harina",
    "frutas": "fruta",
    "verduras": "verdura",
    "proteinas": "proteina",
    "grasas": "grasa",
}
DEFAULT_DAILY_TARGETS = {
    "lacteos": 2.0,
    "harinas": 13.0,
    "frutas": 5.0,
    "verduras": 2.0,
    "proteinas": 10.0,
    "grasas": 2.0,
}


@dataclass(frozen=True)
class FoodEquivalence:
    key: str
    name: str
    group: str
    amount_per_serving: float
    unit: str
    weight_state: str
    aliases: tuple[str, ...]
    unit_singular: str = ""
    unit_plural: str = ""
    default_amount: float | None = None
    default_note: str = ""


@dataclass(frozen=True)
class ParsedDietItem:
    food: FoodEquivalence
    amount: float
    unit: str
    servings: float
    source_text: str
    amount_source: str
    inference_note: str
    parser_source: str = "local"


FOODS = [
    FoodEquivalence(
        "leche",
        "Leche semidesnatada, desnatada, vegetal o sin lactosa",
        "lacteos",
        200,
        "ml",
        "volumen en ml",
        ("leche", "leche semidesnatada", "leche desnatada", "leche de soja", "leche de avena", "leche sin lactosa"),
        default_amount=200,
        default_note="vaso o toma de leche estimada en 200 ml",
    ),
    FoodEquivalence(
        "yogures",
        "Yogures naturales o desnatados 0%",
        "lacteos",
        2,
        "unidades",
        "unidades",
        ("yogures naturales", "yogures desnatados", "yogures 0", "yogur natural", "yogur desnatado", "yogures", "yogur"),
        "yogur",
        "yogures",
        default_amount=1,
        default_note="un yogur indicado sin cantidad se estima como 1 unidad",
    ),
    FoodEquivalence(
        "kefir",
        "Kefir",
        "lacteos",
        250,
        "g",
        "listo para consumir",
        ("kefir",),
        default_amount=250,
        default_note="porcion de kefir estimada en 250 g",
    ),
    FoodEquivalence(
        "queso_fresco_desnatado",
        "Queso fresco desnatado 0%",
        "lacteos",
        150,
        "g",
        "listo para consumir",
        ("queso fresco desnatado", "queso desnatado", "queso fresco 0"),
        default_amount=150,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "queso_fresco_batido",
        "Queso fresco batido",
        "proteinas",
        120,
        "g",
        "listo para consumir",
        ("queso fresco batido",),
        default_amount=120,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "queso_fresco",
        "Queso fresco",
        "lacteos",
        75,
        "g",
        "listo para consumir",
        ("queso fresco",),
        default_amount=75,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "maiz_guisantes",
        "Maiz o guisantes enlatados",
        "harinas",
        60,
        "g",
        "enlatado/listo para consumir",
        ("maiz enlatado", "maiz", "guisantes enlatados", "guisantes"),
        default_amount=60,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "papa_batata_boniato",
        "Papa, batata o boniato",
        "harinas",
        50,
        "g",
        "cocinado/listo para consumir",
        ("papa", "papas", "patata", "patatas", "batata", "batatas", "boniato", "boniatos"),
        default_amount=50,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "legumbres_crudas",
        "Legumbres crudas",
        "harinas",
        20,
        "g",
        "crudo",
        ("legumbres crudas", "lentejas crudas", "garbanzos crudos", "alubias crudas"),
        default_amount=20,
        default_note="porcion cruda estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "legumbres_cocinadas",
        "Legumbres cocinadas",
        "harinas",
        40,
        "g",
        "cocinado",
        ("legumbres cocinadas", "legumbres cocidas", "legumbres", "lentejas", "garbanzos", "alubias", "judias cocidas"),
        default_amount=40,
        default_note="porcion cocinada estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "pan",
        "Pan blanco, integral o de molde",
        "harinas",
        20,
        "g",
        "listo para consumir",
        ("pulguita", "pulga", "bocadillo", "rebanada de pan", "pan de molde", "pan integral", "pan blanco", "pan"),
        default_amount=20,
        default_note="porcion de pan estimada en 20 g si no se reconoce un formato concreto",
    ),
    FoodEquivalence(
        "pan_tostado",
        "Pan tostado",
        "harinas",
        15,
        "g",
        "listo para consumir",
        ("pan tostado", "tostada", "tostadas", "biscote", "biscotes"),
        default_amount=15,
        default_note="pieza de pan tostado estimada en 15 g",
    ),
    FoodEquivalence(
        "arroz_crudo",
        "Arroz crudo",
        "harinas",
        15,
        "g",
        "crudo",
        ("arroz crudo",),
        default_amount=15,
        default_note="porcion cruda estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "arroz_cocinado",
        "Arroz cocinado",
        "harinas",
        45,
        "g",
        "cocinado",
        ("arroz cocinado", "arroz cocido", "arroz"),
        default_amount=45,
        default_note="porcion cocinada estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "pasta_cruda",
        "Pasta cruda",
        "harinas",
        15,
        "g",
        "crudo",
        ("pasta cruda", "macarrones crudos", "espaguetis crudos"),
        default_amount=15,
        default_note="porcion cruda estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "pasta_cocinada",
        "Pasta cocinada",
        "harinas",
        45,
        "g",
        "cocinado",
        ("pasta cocinada", "pasta cocida", "macarrones", "espaguetis", "pasta"),
        default_amount=45,
        default_note="porcion cocinada estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "cuscus_quinoa_crudos",
        "Cuscus o quinoa en crudo",
        "harinas",
        15,
        "g",
        "crudo",
        ("cuscus crudo", "cuscus", "quinoa cruda", "quinoa"),
        default_amount=15,
        default_note="porcion cruda estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "avena_cereales_gofio_muesli",
        "Avena, cereales sin azucar, gofio o muesli",
        "harinas",
        15,
        "g",
        "crudo/listo para consumir",
        ("avena", "cereales sin azucar", "cereales", "gofio", "muesli"),
        default_amount=15,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "tortitas_arroz_maiz",
        "Tortitas de arroz o maiz",
        "harinas",
        15,
        "g",
        "listo para consumir",
        ("tortitas de arroz", "tortita de arroz", "tortitas de maiz", "tortita de maiz", "tortitas"),
        default_amount=15,
        default_note="porcion estimada en 15 g",
    ),
    FoodEquivalence(
        "melon_sandia_pomelo",
        "Melon, sandia o pomelo",
        "frutas",
        150,
        "g",
        "crudo/listo para consumir",
        ("melon", "sandia", "pomelo"),
        default_amount=150,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "frutos_rojos",
        "Frutos rojos",
        "frutas",
        150,
        "g",
        "crudo/listo para consumir",
        ("frutos rojos", "frambuesas", "moras", "arandanos", "fresas"),
        default_amount=150,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "pina",
        "Pina natural o en su jugo",
        "frutas",
        100,
        "g",
        "crudo/listo para consumir",
        ("pina natural", "pina en su jugo", "pina"),
        default_amount=100,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "fruta_60",
        "Manzana, pera, melocoton, kiwi, naranja, nectarina, granada o maracuya",
        "frutas",
        60,
        "g",
        "crudo/listo para consumir",
        (
            "manzana",
            "manzanas",
            "pera",
            "peras",
            "melocoton",
            "melocotones",
            "kiwi",
            "kiwis",
            "naranja",
            "naranjas",
            "nectarina",
            "nectarinas",
            "granada",
            "granadas",
            "maracuya",
        ),
        default_amount=60,
        default_note="pieza o porcion estimada en 60 g",
    ),
    FoodEquivalence(
        "fruta_50",
        "Platano, mango, uvas, cerezas o caqui",
        "frutas",
        50,
        "g",
        "crudo/listo para consumir",
        ("platano", "platanos", "mango", "mangos", "uvas", "cerezas", "caqui", "caquis"),
        default_amount=50,
        default_note="pieza o porcion estimada en 50 g",
    ),
    FoodEquivalence(
        "fiambre_pavo_jamon_cocido",
        "Fiambre de pavo o jamon cocido",
        "proteinas",
        60,
        "g",
        "listo para consumir",
        ("fiambre de pavo", "jamon cocido", "pavo"),
        default_amount=60,
        default_note="porcion de fiambre estimada en 60 g",
    ),
    FoodEquivalence(
        "pescado_blanco_marisco",
        "Pescado blanco o marisco",
        "proteinas",
        75,
        "g",
        "peso del plan; crudo/cocinado no especificado",
        (
            "pescado blanco",
            "merluza",
            "bacalao",
            "lubina",
            "dorada",
            "sepia",
            "pulpo",
            "langostino",
            "langostinos",
            "marisco",
            "mariscos",
        ),
        default_amount=75,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "pescado_graso",
        "Pescado graso",
        "proteinas",
        50,
        "g",
        "peso del plan; crudo/cocinado no especificado",
        ("atun", "salmon", "sardinas", "caballa", "trucha", "bonito", "pescado graso"),
        default_amount=50,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "carnes_magras",
        "Pollo, pavo, ternera, conejo o carne magra",
        "proteinas",
        50,
        "g",
        "peso del plan; crudo/cocinado no especificado",
        ("pollo", "pavo fresco", "carne de pavo", "ternera", "conejo", "carne magra", "carnes magras"),
        default_amount=50,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "jamon_serrano_pata_asada",
        "Jamon serrano o pata asada",
        "proteinas",
        30,
        "g",
        "listo para consumir",
        ("jamon serrano", "pata asada"),
        default_amount=30,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "huevo",
        "Huevo",
        "proteinas",
        1,
        "unidades",
        "unidades",
        ("huevos", "huevo"),
        "huevo",
        "huevos",
        default_amount=1,
        default_note="un huevo indicado sin cantidad se estima como 1 unidad",
    ),
    FoodEquivalence(
        "clara_huevo",
        "Clara de huevo",
        "proteinas",
        90,
        "g",
        "listo para consumir",
        ("clara de huevo", "claras de huevo", "claras", "clara"),
        default_amount=90,
        default_note="porcion estimada en 90 g",
    ),
    FoodEquivalence(
        "tofu",
        "Tofu",
        "proteinas",
        65,
        "g",
        "listo para consumir",
        ("tofu",),
        default_amount=65,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "seitan",
        "Seitan",
        "proteinas",
        40,
        "g",
        "listo para consumir",
        ("seitan",),
        default_amount=40,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "soja",
        "Soja",
        "proteinas",
        30,
        "g",
        "peso del plan; crudo/cocinado no especificado",
        ("soja",),
        default_amount=30,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "frutos_secos_semillas_proteina",
        "Frutos secos o semillas como proteina vegetal",
        "proteinas",
        40,
        "g",
        "listo para consumir",
        ("frutos secos", "semillas"),
        default_amount=40,
        default_note="solo usar si encaja como proteina vegetal segun la tabla",
    ),
    FoodEquivalence(
        "aceite_oliva",
        "Aceite de oliva",
        "grasas",
        10,
        "g",
        "grasa anadida",
        ("aceite de oliva", "aceite"),
        default_amount=10,
        default_note="cucharada sopera o uso de aceite estimado en 10 g",
    ),
    FoodEquivalence(
        "aguacate",
        "Aguacate",
        "grasas",
        70,
        "g",
        "crudo/listo para consumir",
        ("aguacate",),
        default_amount=70,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "aceitunas",
        "Aceitunas",
        "grasas",
        40,
        "g",
        "listo para consumir",
        ("aceitunas",),
        default_amount=40,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "verduras_300",
        "Verduras comunes",
        "verduras",
        300,
        "g",
        "crudo o cocinado segun preparacion",
        (
            "verduras comunes",
            "verduras de hoja",
            "verduras",
            "verdura",
            "ensalada",
            "lechuga",
            "tomate",
            "pepino",
            "calabacin",
            "berenjena",
            "brocoli",
            "coliflor",
            "champinones",
            "espinacas",
            "pimiento",
            "setas",
            "esparragos",
        ),
        default_amount=300,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "verduras_200",
        "Judia verde, puerro, nabo o grelos",
        "verduras",
        200,
        "g",
        "crudo o cocinado segun preparacion",
        ("judia verde", "judias verdes", "puerro", "puerros", "nabo", "nabos", "grelos"),
        default_amount=200,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
    FoodEquivalence(
        "verduras_150",
        "Alcachofa, calabaza, cebolla, zanahoria, remolacha o coles de Bruselas",
        "verduras",
        150,
        "g",
        "crudo o cocinado segun preparacion",
        (
            "alcachofa",
            "alcachofas",
            "calabaza",
            "cebolla",
            "cebollas",
            "zanahoria",
            "zanahorias",
            "remolacha",
            "coles de bruselas",
        ),
        default_amount=150,
        default_note="porcion estimada en 1 racion de la tabla",
    ),
]

FOODS_BY_KEY = {food.key: food for food in FOODS}
ALIAS_DEFAULT_AMOUNTS = {
    ("pan", "pulguita"): (60.0, "pulguita estimada en 60 g"),
    ("pan", "pulga"): (60.0, "pulga estimada en 60 g"),
    ("pan", "bocadillo"): (80.0, "bocadillo estimado en 80 g de pan"),
    ("pan", "rebanada de pan"): (20.0, "rebanada de pan estimada en 20 g"),
    ("pan_tostado", "tostada"): (15.0, "tostada estimada en 15 g"),
    ("pan_tostado", "tostadas"): (15.0, "tostada estimada en 15 g"),
    ("aceite_oliva", "aceite"): (10.0, "uso de aceite estimado en 10 g"),
    ("aceite_oliva", "aceite de oliva"): (10.0, "uso de aceite estimado en 10 g"),
}

UNIT_ALIASES = {
    "g": "g",
    "gr": "g",
    "grs": "g",
    "gramo": "g",
    "gramos": "g",
    "ml": "ml",
    "mililitro": "ml",
    "mililitros": "ml",
    "unidad": "unidades",
    "unidades": "unidades",
    "huevo": "unidades",
    "huevos": "unidades",
    "yogur": "unidades",
    "yogures": "unidades",
    "racion": "raciones",
    "raciones": "raciones",
    "porcion": "raciones",
    "porciones": "raciones",
    "vaso": "vasos",
    "vasos": "vasos",
    "cucharada": "cucharadas",
    "cucharadas": "cucharadas",
    "cda": "cucharadas",
    "cdas": "cucharadas",
    "pieza": "piezas",
    "piezas": "piezas",
}
NUMBER_WORDS = {
    "un": 1.0,
    "una": 1.0,
    "uno": 1.0,
    "dos": 2.0,
    "tres": 3.0,
    "cuatro": 4.0,
    "cinco": 5.0,
    "seis": 6.0,
    "siete": 7.0,
    "ocho": 8.0,
    "nueve": 9.0,
    "diez": 10.0,
}
NUMBER_RE = r"\d+(?:[\.,]\d+)?|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez"
UNIT_RE = "|".join(sorted((re.escape(unit) for unit in UNIT_ALIASES), key=len, reverse=True))


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9,\.]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def format_number(value: float, decimals: int = 2) -> str:
    rounded = round(float(value), decimals)
    if abs(rounded - round(rounded)) < 0.000001:
        return str(int(round(rounded)))
    return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")


def group_serving_label(group_key: str, servings: float) -> str:
    if abs(servings - 1.0) < 0.000001:
        return GROUP_SINGULAR[group_key]
    return GROUP_LABELS[group_key].lower()


def format_amount(amount: float, unit: str, food: FoodEquivalence | None = None) -> str:
    if unit == "unidades":
        singular = food.unit_singular if food and food.unit_singular else "unidad"
        plural = food.unit_plural if food and food.unit_plural else "unidades"
        label = singular if abs(amount - 1.0) < 0.000001 else plural
        return f"{format_number(amount)} {label}"
    return f"{format_number(amount)} {unit}"


def targets_from_plan(plan: Any | None) -> dict[str, float]:
    if plan is None:
        return dict(DEFAULT_DAILY_TARGETS)
    return {
        "lacteos": float(plan.lacteos_target),
        "harinas": float(plan.harinas_target),
        "frutas": float(plan.frutas_target),
        "verduras": float(plan.verduras_target),
        "proteinas": float(plan.proteinas_target),
        "grasas": float(plan.grasas_target),
    }


def grouped_food_options() -> list[dict[str, Any]]:
    return [
        {
            "key": group_key,
            "label": GROUP_LABELS[group_key],
            "foods": [
                {
                    "key": food.key,
                    "name": food.name,
                    "serving": format_amount(food.amount_per_serving, food.unit, food),
                    "weight_state": food.weight_state,
                }
                for food in FOODS
                if food.group == group_key
            ],
        }
        for group_key in GROUP_ORDER
    ]


def entry_from_item(
    item: ParsedDietItem,
    user_id: int,
    entry_date,
    meal_label: str,
    batch_id: str,
    notes: str | None = None,
) -> DietEntry:
    return DietEntry(
        user_id=user_id,
        date=entry_date,
        meal_label=meal_label,
        food_key=item.food.key,
        food_name=item.food.name,
        group_key=item.food.group,
        amount=item.amount,
        unit=item.unit,
        weight_state=item.food.weight_state,
        servings=item.servings,
        amount_source=item.amount_source,
        parser_source=item.parser_source,
        inference_note=item.inference_note,
        source_text=item.source_text or None,
        batch_id=batch_id,
        notes=notes,
    )


def _parse_number(value: str) -> float | None:
    value = value.strip().lower()
    if value in NUMBER_WORDS:
        return NUMBER_WORDS[value]
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    return UNIT_ALIASES.get(unit.strip().lower())


def _amount_before(text: str) -> tuple[float, str] | None:
    pattern = re.compile(
        rf"(?P<number>{NUMBER_RE})\s*(?P<unit>{UNIT_RE})\s*(?:de|del)?\s*$",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    number = _parse_number(match.group("number"))
    unit = _normalize_unit(match.group("unit"))
    if number is None or unit is None:
        return None
    return number, unit


def _amount_after(text: str) -> tuple[float, str] | None:
    pattern = re.compile(
        rf"^\s*(?:de\s+|del\s+)?(?P<number>{NUMBER_RE})\s*(?P<unit>{UNIT_RE})\b",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    number = _parse_number(match.group("number"))
    unit = _normalize_unit(match.group("unit"))
    if number is None or unit is None:
        return None
    return number, unit


def _unit_amount_before(text: str, food: FoodEquivalence) -> tuple[float, str] | None:
    if food.unit != "unidades":
        return None
    pattern = re.compile(rf"(?P<number>{NUMBER_RE})\s*$", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    number = _parse_number(match.group("number"))
    if number is None:
        return None
    return number, "unidades"


def _piece_amount_before(text: str) -> float | None:
    pattern = re.compile(rf"(?P<number>{NUMBER_RE})\s*$", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    return _parse_number(match.group("number"))


def _alias_matches(text: str) -> list[tuple[int, int, FoodEquivalence, str]]:
    matches: list[tuple[int, int, FoodEquivalence, str]] = []
    for food in FOODS:
        for alias in food.aliases:
            alias_text = normalize_text(alias)
            pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias_text)}(?![a-z0-9])")
            for match in pattern.finditer(text):
                matches.append((match.start(), match.end(), food, alias_text))

    selected: list[tuple[int, int, FoodEquivalence, str]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, food, alias in sorted(matches, key=lambda item: (-(item[1] - item[0]), item[0])):
        if any(start < used_end and end > used_start for used_start, used_end in occupied):
            continue
        selected.append((start, end, food, alias))
        occupied.append((start, end))
    return sorted(selected, key=lambda item: item[0])


def _convert_amount(food: FoodEquivalence, amount: float, unit: str) -> tuple[float, str, str] | None:
    if unit == food.unit:
        return amount, food.unit, "cantidad indicada por el usuario"
    if unit == "raciones":
        return amount * food.amount_per_serving, food.unit, "cantidad indicada en raciones"
    if unit == "piezas" and food.default_amount:
        return amount * food.default_amount, food.unit, "piezas estimadas con el tamano de referencia de la tabla"
    if food.key == "leche" and unit == "vasos":
        return amount * 200, "ml", "vaso de leche estimado en 200 ml"
    if food.key == "aceite_oliva" and unit == "cucharadas":
        return amount * 10, "g", "cucharada sopera de aceite estimada en 10 g"
    return None


def _gemini_food_catalog() -> list[dict[str, Any]]:
    return [
        {
            "food_key": food.key,
            "name": food.name,
            "group": food.group,
            "one_serving_amount": food.amount_per_serving,
            "unit": food.unit,
            "weight_state": food.weight_state,
            "aliases": list(food.aliases),
            "default_amount": food.default_amount or food.amount_per_serving,
            "default_note": food.default_note,
        }
        for food in FOODS
    ]


def _gemini_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "food_key": {"type": "string"},
                        "amount": {"type": "number"},
                        "unit": {"type": "string"},
                        "amount_source": {"type": "string"},
                        "inference_note": {"type": "string"},
                    },
                    "required": ["food_key", "amount", "unit", "amount_source", "inference_note"],
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["items", "warnings"],
    }


def _gemini_prompt(value: str) -> str:
    return (
        "Actua como extractor de alimentos para una dieta por raciones prescrita. "
        "No eres medico ni nutricionista. No cambies grupos ni objetivos. "
        "Debes extraer solo alimentos que existan en el catalogo. "
        "Si una cantidad esta escrita, normalizala a la unidad del alimento del catalogo. "
        "Si no hay cantidad, estimala de forma conservadora usando default_amount, formato habitual o 1 racion. "
        "Para pan: pulguita=60 g, bocadillo=80 g si no se indica otra cantidad. "
        "Para aceite: cucharada sopera=10 g. Para vaso de leche=200 ml. "
        "Devuelve JSON valido con items y warnings. "
        "amount_source debe ser 'explicita' o 'estimada'. "
        "unit debe ser exactamente la unidad del alimento: g, ml o unidades. "
        "Catalogo:\n"
        f"{json.dumps(_gemini_food_catalog(), ensure_ascii=False)}\n"
        "Texto del usuario:\n"
        f"{value}"
    )


def _gemini_generated_text(response_data: dict[str, Any]) -> str:
    candidates = response_data.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini no devolvio candidatos.")
    parts = candidates[0].get("content", {}).get("parts") or []
    text_parts = [part.get("text", "") for part in parts if part.get("text")]
    if not text_parts:
        raise ValueError("Gemini no devolvio texto interpretable.")
    return "\n".join(text_parts)


def _request_gemini(value: str) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini no configurado.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": _gemini_prompt(value)}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseJsonSchema": _gemini_response_schema(),
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=settings.gemini_timeout_seconds) as response:
        response_data = json.loads(response.read().decode("utf-8"))
    return json.loads(_gemini_generated_text(response_data))


def _items_from_gemini_payload(value: str, payload: dict[str, Any]) -> tuple[list[ParsedDietItem], list[str]]:
    items: list[ParsedDietItem] = []
    messages = [str(warning) for warning in payload.get("warnings", []) if str(warning).strip()]

    for raw_item in payload.get("items", []):
        food = FOODS_BY_KEY.get(str(raw_item.get("food_key") or ""))
        if not food:
            messages.append(f"Gemini devolvio un alimento fuera de la tabla: {raw_item.get('food_key')}.")
            continue

        try:
            amount = float(raw_item.get("amount"))
        except (TypeError, ValueError):
            messages.append(f"{food.name}: Gemini no devolvio una cantidad numerica.")
            continue

        unit = str(raw_item.get("unit") or "").strip()
        if amount <= 0:
            messages.append(f"{food.name}: Gemini devolvio una cantidad no valida.")
            continue
        if unit != food.unit:
            converted = _convert_amount(food, amount, unit)
            if converted is None:
                messages.append(f"{food.name}: Gemini devolvio unidad incompatible ({unit}).")
                continue
            amount, unit, conversion_note = converted
        else:
            conversion_note = ""

        amount_source = str(raw_item.get("amount_source") or "estimada").strip().lower()
        if amount_source not in {"explicita", "estimada"}:
            amount_source = "estimada"
        inference_note = str(raw_item.get("inference_note") or "").strip()
        if conversion_note and conversion_note not in inference_note:
            inference_note = f"{inference_note} {conversion_note}".strip()
        if not inference_note:
            inference_note = "interpretado por Gemini"

        items.append(
            ParsedDietItem(
                food=food,
                amount=amount,
                unit=unit,
                servings=amount / food.amount_per_serving,
                source_text=value.strip(),
                amount_source=amount_source,
                inference_note=inference_note,
                parser_source="gemini",
            )
        )

    return items, messages


def parse_meal_text_with_gemini(value: str) -> tuple[list[ParsedDietItem], list[str]]:
    return _items_from_gemini_payload(value, _request_gemini(value))


def interpret_meal_text(value: str) -> tuple[list[ParsedDietItem], list[str]]:
    if settings.gemini_api_key:
        try:
            gemini_items, gemini_messages = parse_meal_text_with_gemini(value)
            if gemini_items:
                return gemini_items, gemini_messages
            local_items, local_messages = parse_meal_text(value)
            return local_items, gemini_messages + local_messages
        except (RuntimeError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError, urllib.error.HTTPError) as error:
            local_items, local_messages = parse_meal_text(value)
            notice = f"Gemini no pudo interpretar esta comida; se uso el parser local. Detalle: {error}"
            return local_items, [notice] + local_messages

    return parse_meal_text(value)


def _infer_amount(food: FoodEquivalence, alias: str, before: str, local_text: str) -> tuple[float, str] | None:
    piece_count = _piece_amount_before(before)
    alias_default = ALIAS_DEFAULT_AMOUNTS.get((food.key, alias))
    if piece_count is not None and alias_default:
        amount, note = alias_default
        return piece_count * amount, note
    if piece_count is not None and food.unit == "unidades":
        return piece_count, "unidades indicadas sin unidad escrita"
    if piece_count is not None and food.default_amount:
        return piece_count * food.default_amount, f"{format_number(piece_count)} piezas estimadas con la referencia de la tabla"
    if food.key == "leche" and re.search(r"\bvaso\b", local_text):
        return 200, "vaso de leche estimado en 200 ml"
    if food.key == "aceite_oliva" and re.search(r"\bcucharad", local_text):
        return 10, "cucharada sopera de aceite estimada en 10 g"
    if alias_default:
        return alias_default
    if food.default_amount is not None:
        return food.default_amount, food.default_note or "cantidad estimada en 1 racion de la tabla"
    return food.amount_per_serving, "cantidad estimada en 1 racion de la tabla"


def parse_meal_text(value: str) -> tuple[list[ParsedDietItem], list[str]]:
    text = normalize_text(value)
    if not text:
        return [], ["Escribe los alimentos consumidos."]

    matches = _alias_matches(text)
    if not matches:
        return [], ["No he encontrado alimentos de la tabla. Prueba con nombres como pan, pavo, queso fresco, arroz, pollo o fruta."]

    items: list[ParsedDietItem] = []
    messages: list[str] = []

    for start, end, food, alias in matches:
        before = text[max(0, start - 56) : start]
        after = text[end : min(len(text), end + 56)]
        local_text = f"{before} {text[start:end]} {after}"
        amount = _amount_before(before) or _amount_after(after) or _unit_amount_before(before, food)
        amount_source = "explicita"
        inference_note = "cantidad indicada por el usuario"

        if amount is None:
            inferred = _infer_amount(food, alias, before, local_text)
            if inferred is None:
                messages.append(f"{food.name}: no se pudo estimar una cantidad.")
                continue
            amount_value, inference_note = inferred
            unit = food.unit
            amount_source = "estimada"
        else:
            raw_amount, raw_unit = amount
            converted = _convert_amount(food, raw_amount, raw_unit)
            if converted is None:
                messages.append(
                    f"{food.name}: unidad incompatible ({raw_unit}). Usa {food.unit}, raciones o una medida casera reconocida."
                )
                continue
            amount_value, unit, inference_note = converted

        items.append(
            ParsedDietItem(
                food=food,
                amount=amount_value,
                unit=unit,
                servings=amount_value / food.amount_per_serving,
                source_text=value.strip(),
                amount_source=amount_source,
                inference_note=inference_note,
            )
        )

    return items, messages


def build_daily_state(entries: list[DietEntry], targets: dict[str, float] | None = None) -> dict[str, Any]:
    active_targets = targets or DEFAULT_DAILY_TARGETS
    consumed = {group_key: 0.0 for group_key in GROUP_ORDER}
    for entry in entries:
        if entry.group_key in consumed:
            consumed[entry.group_key] += entry.servings

    rows = []
    remaining_values = {}
    for group_key in GROUP_ORDER:
        target = float(active_targets.get(group_key, DEFAULT_DAILY_TARGETS[group_key]))
        consumed_value = round(consumed[group_key], 4)
        remaining = round(target - consumed_value, 4)
        percent = min(100, round((consumed_value / target) * 100, 1)) if target else (100 if consumed_value else 0)
        remaining_values[group_key] = max(0.0, remaining)
        rows.append(
            {
                "key": group_key,
                "label": GROUP_LABELS[group_key],
                "target": target,
                "target_label": format_number(target),
                "consumed": consumed_value,
                "consumed_label": format_number(consumed_value),
                "remaining": remaining,
                "remaining_label": format_number(remaining),
                "remaining_positive_label": format_number(max(0.0, remaining)),
                "over_label": format_number(max(0.0, -remaining)),
                "percent": percent,
                "is_over": remaining < -0.000001,
            }
        )

    return {"rows": rows, "remaining_values": remaining_values, "consumed": consumed, "targets": active_targets}


def conversion_rows(entries: list[DietEntry]) -> list[dict[str, Any]]:
    rows = []
    for entry in entries:
        food = FOODS_BY_KEY.get(entry.food_key)
        rows.append(
            {
                "food_name": entry.food_name,
                "amount": format_amount(entry.amount, entry.unit, food),
                "servings": format_number(entry.servings),
                "group": GROUP_LABELS.get(entry.group_key, entry.group_key).lower(),
                "group_serving": group_serving_label(entry.group_key, entry.servings),
                "weight_state": entry.weight_state,
                "meal_label": entry.meal_label,
                "amount_source": entry.amount_source or "explicita",
                "parser_source": entry.parser_source or "local",
                "inference_note": entry.inference_note,
                "notes": entry.notes,
            }
        )
    return rows


def entry_rows(entries: list[DietEntry]) -> list[dict[str, Any]]:
    rows = []
    for entry in entries:
        food = FOODS_BY_KEY.get(entry.food_key)
        rows.append(
            {
                "id": entry.id,
                "meal_label": entry.meal_label,
                "food_name": entry.food_name,
                "amount": format_amount(entry.amount, entry.unit, food),
                "servings": format_number(entry.servings),
                "group": GROUP_LABELS.get(entry.group_key, entry.group_key),
                "weight_state": entry.weight_state,
                "amount_source": entry.amount_source or "explicita",
                "parser_source": entry.parser_source or "local",
                "inference_note": entry.inference_note,
                "notes": entry.notes,
                "source_text": entry.source_text,
                "created_at": entry.created_at,
            }
        )
    return rows


def _split(total: float, ratios: tuple[float, float, float]) -> tuple[float, float, float]:
    if total <= 0:
        return 0.0, 0.0, 0.0
    first = round(total * ratios[0], 2)
    second = round(total * ratios[1], 2)
    third = round(total - first - second, 2)
    return first, second, third


def _add_allocation(target: dict[str, dict[str, float]], meal: str, group: str, value: float) -> None:
    if value <= 0.000001:
        return
    target[meal][group] = round(target[meal].get(group, 0.0) + value, 2)


def build_recommendations(remaining_values: dict[str, float]) -> list[dict[str, Any]]:
    if not any(value > 0.000001 for value in remaining_values.values()):
        return []

    allocations = {"Almuerzo": {}, "Merienda": {}, "Cena": {}}
    for group, ratios in {
        "harinas": (0.42, 0.18, 0.40),
        "frutas": (0.25, 0.35, 0.40),
        "proteinas": (0.5, 0.0, 0.5),
        "verduras": (0.5, 0.0, 0.5),
        "grasas": (0.5, 0.0, 0.5),
    }.items():
        lunch, snack, dinner = _split(remaining_values.get(group, 0.0), ratios)
        _add_allocation(allocations, "Almuerzo", group, lunch)
        _add_allocation(allocations, "Merienda", group, snack)
        _add_allocation(allocations, "Cena", group, dinner)

    _add_allocation(allocations, "Merienda", "lacteos", remaining_values.get("lacteos", 0.0))

    meal_foods = {
        "Almuerzo": {
            "harinas": "arroz_cocinado",
            "frutas": "pina",
            "proteinas": "carnes_magras",
            "verduras": "verduras_300",
            "grasas": "aceite_oliva",
        },
        "Merienda": {
            "lacteos": "kefir",
            "harinas": "avena_cereales_gofio_muesli",
            "frutas": "fruta_60",
        },
        "Cena": {
            "harinas": "papa_batata_boniato",
            "frutas": "frutos_rojos",
            "proteinas": "pescado_blanco_marisco",
            "verduras": "verduras_300",
            "grasas": "aceite_oliva",
        },
    }

    recommendations = []
    for meal, groups in allocations.items():
        items = []
        for group in GROUP_ORDER:
            servings = groups.get(group, 0.0)
            if servings <= 0.000001:
                continue
            food = FOODS_BY_KEY[meal_foods[meal][group]]
            amount = servings * food.amount_per_serving
            items.append(
                {
                    "food_name": food.name,
                    "amount": format_amount(amount, food.unit, food),
                    "servings": format_number(servings),
                    "group": GROUP_LABELS[group].lower(),
                    "weight_state": food.weight_state,
                }
            )
        if items:
            recommendations.append({"meal": meal, "food_items": items})

    return recommendations


def equivalence_rows() -> list[dict[str, Any]]:
    rows = []
    for food in FOODS:
        rows.append(
            {
                "group": GROUP_LABELS[food.group],
                "food_name": food.name,
                "serving": format_amount(food.amount_per_serving, food.unit, food),
                "weight_state": food.weight_state,
            }
        )
    return rows
