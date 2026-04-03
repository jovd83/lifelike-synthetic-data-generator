#!/usr/bin/env python

import argparse
import copy
import json
import re
from pathlib import Path

import generate_data


ROOT_DIR = Path(__file__).resolve().parent.parent
BASE_PERSONA_EXAMPLE = ROOT_DIR / "examples" / "persona-belgium.json"
SUPPORTED_BELGIAN_TRANSLATION_LOCALES = {"nl_BE", "fr_BE"}

WORD_NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}

MULTILINGUAL_NUMBER_HINTS = {
    "geen": 0,
    "nul": 0,
    "zero": 0,
    "one": 1,
    "een": 1,
    "un": 1,
    "une": 1,
    "two": 2,
    "twee": 2,
    "deux": 2,
    "three": 3,
    "drie": 3,
    "trois": 3,
    "four": 4,
    "vier": 4,
    "quatre": 4,
    "five": 5,
    "vijf": 5,
    "cinq": 5,
}

INDUSTRY_HINTS = {
    "healthcare": ("Healthcare", "Healthcare Operations Lead", "Healthcare Services"),
    "zorg": ("Healthcare", "Healthcare Operations Lead", "Healthcare Services"),
    "soins de sante": ("Healthcare", "Healthcare Operations Lead", "Healthcare Services"),
    "cybersecurity": ("Cybersecurity", "Security Program Manager", "Cybersecurity"),
    "cyberbeveiliging": ("Cybersecurity", "Security Program Manager", "Cybersecurity"),
    "cybersecurite": ("Cybersecurity", "Security Program Manager", "Cybersecurity"),
    "public sector": ("Public Administration", "Policy Program Lead", "Public Administration"),
    "publieke sector": ("Public Administration", "Policy Program Lead", "Public Administration"),
    "secteur public": ("Public Administration", "Policy Program Lead", "Public Administration"),
    "education": ("Education", "Education Program Coordinator", "Education"),
    "onderwijs": ("Education", "Education Program Coordinator", "Education"),
    "enseignement": ("Education", "Education Program Coordinator", "Education"),
    "finance": ("Financial Services", "Risk and Operations Lead", "Financial Services"),
    "financien": ("Financial Services", "Risk and Operations Lead", "Financial Services"),
    "finance bancaire": ("Financial Services", "Risk and Operations Lead", "Financial Services"),
}

PRIVACY_HINTS = ["privacy-conscious", "privacybewust", "soucieux de la vie privee", "respectueux de la vie privee"]
URBAN_HINTS = ["urban", "city", "large city", "stedelijk", "stad", "urbain", "grande ville"]
PARENT_HINTS = ["parent", "children", "ouder", "ouders", "kinderen", "parents", "enfants"]
BUDGET_HINTS = ["budget-conscious", "budgetbewust", "attentif au budget", "sensible au budget"]
COMMUTER_HINTS = ["commuter", "pendelaar", "navetteur", "forens", "pendelt", "doet de navette"]
NO_CHILDREN_HINTS = ["no children", "without children", "geen kinderen", "sans enfants"]
SINGLE_HINTS = ["single", "alleenstaand", "celibataire", "solo", "single en", "vit seul"]
MARRIED_HINTS = ["married", "getrouwd", "marie", "mariee", "gehuwd"]
URBAN_NEIGHBORHOOD_HINTS = ["urban", "large city", "city", "stedelijk", "stad", "urbain", "ville", "in de stad", "en ville"]
SUBURBAN_HINTS = ["suburban", "voorstedelijk", "banlieue", "periurbain", "rand van de stad"]
RURAL_HINTS = ["rural", "landelijk", "campagne", "op den buiten", "a la campagne"]
NO_CAR_HINTS = ["no car", "without a car", "geen auto", "sans voiture"]
HAS_CAR_HINTS = ["owns a car", "has a car", "heeft een auto", "avec une voiture", "possede une voiture"]
BIKE_HINTS = ["bike", "bicycle", "fiets", "velo", "cycl", "rijdt met de fiets", "se deplace a velo"]
DOG_HINTS = ["dog", "hond", "chien"]
CAT_HINTS = ["cat", "kat", "chat"]
LOW_INCOME_HINTS = ["low income", "low-income", "laag inkomen", "faible revenu"]
HIGH_INCOME_HINTS = ["high income", "affluent", "hoog inkomen", "revenu eleve", "aise"]
REMOTE_WORK_HINTS = ["remote", "remote worker", "works remotely", "telework", "thuiswerk", "werkt van thuis", "a distance", "travail a distance", "van thuis uit", "en teletravail"]
HYBRID_WORK_HINTS = ["hybrid", "hybride", "hybrid work", "hybride werk", "travail hybride", "deels thuis", "partiellement a distance"]
SHIFT_WORK_HINTS = ["shift work", "shift worker", "ploegen", "ploegendienst", "travail en equipes", "travaille en horaires decales", "wisselende uren"]
SELF_EMPLOYED_HINTS = ["self-employed", "freelancer", "independent", "zelfstandig", "freelance", "independant", "eigen zaak", "a son compte"]
PART_TIME_HINTS = ["part-time", "part time", "deeltijds", "mi-temps", "temps partiel"]
CIVIL_SERVICE_HINTS = ["civil servant", "ambtenaar", "fonctionnaire", "public service employee", "werkt voor de overheid", "travaille pour l'administration"]
PUBLIC_SECTOR_HINTS = ["publieke sector", "secteur public", "government", "overheid", "administration publique"]
DEVELOPER_HINTS = ["developer", "software engineer", "ontwikkelaar", "dev", "developpeur"]
DESIGNER_HINTS = ["designer", "ux designer", "ontwerper", "designer freelance"]
MARKETING_HINTS = ["marketing", "marketeer", "marketing manager", "marketing digital"]
LEGAL_HINTS = ["lawyer", "legal", "advocaat", "juriste", "juridique"]
LOGISTICS_HINTS = ["logistics", "supply chain", "logistiek", "supply chain", "logistique"]
RETAIL_HINTS = ["retail", "winkel", "store manager", "commerce de detail"]
UTILITIES_HINTS = ["utilities", "energy sector", "nutsbedrijf", "secteur de l'energie"]
STUDENT_HINTS = ["student", "universiteitsstudent", "etudiant", "etudiante"]
STARTER_HINTS = ["starter", "young professional", "career starter", "jonge professional", "debut de carriere"]
MID_CAREER_HINTS = ["mid-career", "mid career", "midden in haar carriere", "midden in zijn carriere", "milieu de carriere"]
PRE_RETIREMENT_HINTS = ["near retirement", "approaching retirement", "bijna met pensioen", "bientot a la retraite"]
RETIRED_HINTS = ["retired", "retiree", "gepensioneerd", "met pensioen", "retraite"]
OWNER_HINTS = ["owner", "homeowner", "eigenaar", "huiseigenaar", "proprietaire"]
RENTER_HINTS = ["renter", "tenant", "huurder", "huurt", "gehuurd", "locataire", "loue"]
APARTMENT_HINTS = ["apartment", "flat", "appartement", "flatgebouw"]
HOUSE_HINTS = ["house", "home", "huis", "maison"]
ROW_HOUSE_HINTS = ["row house", "rowhouse", "rijwoning", "rijhuis", "maison mitoyenne", "maison en rangee"]
LIVES_ALONE_HINTS = ["living alone", "lives alone", "woont alleen", "vit seul", "vit seule"]
COUPLE_HINTS = ["with partner", "met partner", "avec partenaire", "couple", "samenwonend", "cohabite"]
MULTIGENERATIONAL_HINTS = [
    "multigenerational",
    "multi-generational",
    "meergeneratiewoning",
    "plusieurs generations",
    "extended family household",
]
SINGLE_PARENT_HINTS = [
    "single parent",
    "single mother",
    "single father",
    "alleenstaande ouder",
    "alleenstaande moeder",
    "alleenstaande vader",
    "parent seul",
    "mere celibataire",
    "pere celibataire",
]
DIVORCED_HINTS = ["divorced", "gescheiden", "divorce", "divorcee"]
CO_PARENTING_HINTS = [
    "co-parent",
    "co parenting",
    "co-parenting",
    "co-ouder",
    "co-ouderschap",
    "coparentalite",
]
BLENDED_FAMILY_HINTS = [
    "blended family",
    "samengesteld gezin",
    "nieuw samengesteld gezin",
    "famille recomposee",
]
TOWNHOUSE_HINTS = ["townhouse", "rijhuis", "maison de ville"]
DUPLEX_HINTS = ["duplex", "dubbelwoonst"]
ASSISTED_LIVING_HINTS = ["assisted living", "serviceflat", "residentie", "residence services"]
BRUSSELS_APARTMENT_HINTS = [
    "brussels apartment",
    "brussels flat",
    "brussels-style apartment",
    "appartement bruxellois",
    "appartement de style bruxellois",
    "appartement a bruxelles",
    "appartement in brussel",
    "herenhuisappartement",
    "appartement in een herenhuis",
    "appartement dans une maison de maitre",
]

CITY_HINTS = {
    "brussels": "Brussel",
    "bruxelles": "Brussel",
    "brussel": "Brussel",
    "antwerp": "Antwerp",
    "anvers": "Antwerp",
    "antwerpen": "Antwerp",
    "ghent": "Ghent",
    "gent": "Ghent",
    "liege": "Liege",
    "bruges": "Bruges",
    "brugge": "Bruges",
    "namur": "Namur",
    "leuven": "Leuven",
    "mechelen": "Mechelen",
    "malines": "Mechelen",
}

REGION_HINTS = {
    "flanders": {"city": "Ghent", "neighborhood_type": "suburban"},
    "vlaanderen": {"city": "Ghent", "neighborhood_type": "suburban"},
    "wallonia": {"city": "Namur", "neighborhood_type": "suburban"},
    "wallonie": {"city": "Namur", "neighborhood_type": "suburban"},
    "brussels-capital": {"city": "Brussel", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "brussels capital": {"city": "Brussel", "province": "Brussels-Capital", "neighborhood_type": "urban"},
}
PROVINCE_HINTS = {
    "antwerp province": {"province": "Antwerp"},
    "provincie antwerpen": {"province": "Antwerp"},
    "province d'anvers": {"province": "Antwerp"},
    "east flanders": {"province": "East Flanders"},
    "oost-vlaanderen": {"province": "East Flanders"},
    "flanders orientale": {"province": "East Flanders"},
    "west flanders": {"province": "West Flanders"},
    "west-vlaanderen": {"province": "West Flanders"},
    "flanders occidentale": {"province": "West Flanders"},
    "limburg": {"province": "Limburg"},
    "flemish brabant": {"province": "Flemish Brabant"},
    "vlaams-brabant": {"province": "Flemish Brabant"},
    "hainaut": {"province": "Hainaut"},
    "liege province": {"province": "Liege"},
    "province de liege": {"province": "Liege"},
    "luxembourg province": {"province": "Luxembourg"},
    "province du luxembourg": {"province": "Luxembourg"},
    "namur province": {"province": "Namur"},
    "province de namur": {"province": "Namur"},
    "walloon brabant": {"province": "Walloon Brabant"},
    "brabant wallon": {"province": "Walloon Brabant"},
    "brussels province": {"province": "Brussels-Capital"},
    "region bruxelloise": {"province": "Brussels-Capital", "city": "Brussel", "neighborhood_type": "urban"},
}
BRUSSELS_COMMUNE_HINTS = {
    "ixelles": {"city": "Elsene", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "elsene": {"city": "Elsene", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "anderlecht": {"city": "Anderlecht", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "schaerbeek": {"city": "Schaarbeek", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "schaarbeek": {"city": "Schaarbeek", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "uccle": {"city": "Ukkel", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "ukkel": {"city": "Ukkel", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "etterbeek": {"city": "Etterbeek", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "saint-gilles": {"city": "Sint-Gillis", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "st-gilles": {"city": "Sint-Gillis", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "sint-gillis": {"city": "Sint-Gillis", "province": "Brussels-Capital", "neighborhood_type": "urban"},
    "molenbeek": {"city": "Sint-Jans-Molenbeek", "province": "Brussels-Capital", "neighborhood_type": "urban"},
}

TRAIN_COMMUTE_HINTS = [
    "train commuter",
    "commutes by train",
    "met de trein",
    "pendelt met de trein",
    "navette en train",
    "prend le train",
]
BIKE_COMMUTE_HINTS = [
    "bike commuter",
    "commutes by bike",
    "met de fiets",
    "fietsforens",
    "a velo",
    "se deplace a velo",
]
CAR_COMMUTE_HINTS = [
    "commutes by car",
    "met de auto",
    "met de wagen",
    "en voiture",
    "voiture pour le travail",
]
TRANSIT_HINTS = ["public transport", "openbaar vervoer", "transports en commun", "metro", "tram"]
METRO_HINTS = ["metro", "subway", "met de metro", "en metro"]
TRAM_HINTS = ["tram", "met de tram", "en tram"]
BUS_HINTS = ["bus", "met de bus", "en bus"]
EV_HINTS = ["electric car", "electric vehicle", "elektrische auto", "elektrische wagen", "voiture electrique", "vehicule electrique"]
COMPANY_CAR_HINTS = ["company car", "bedrijfswagen", "voiture de societe"]
CARGO_BIKE_HINTS = ["cargo bike", "bakfiets", "velo cargo"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: str) -> str:
    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "à": "a",
        "â": "a",
        "ä": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ö": "o",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ç": "c",
    }
    normalized = value.lower()
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def collect_request_text(request: dict) -> str:
    parts = []
    for key in ["prompt", "freeform"]:
        value = request.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    wishes = request.get("wishes", [])
    if isinstance(wishes, list):
        parts.extend(str(item).strip() for item in wishes if str(item).strip())
    return normalize_text(" | ".join(parts))


def find_field(fields: list[dict], path: str) -> dict:
    current_fields = fields
    parts = path.split(".")
    for index, part in enumerate(parts):
        match = next((field for field in current_fields if field["name"] == part), None)
        if match is None:
            raise generate_data.SkillError(f"Could not find field path {path!r}.")
        if index == len(parts) - 1:
            return match
        if match["type"] != "object":
            raise generate_data.SkillError(f"Field path {path!r} expected {part!r} to be an object.")
        current_fields = match["params"]["fields"]
    raise generate_data.SkillError(f"Could not resolve field path {path!r}.")


def set_literal(config: dict, path: str, value) -> None:
    parts = path.split(".")
    current_fields = config["fields"]
    for index, part in enumerate(parts):
        field = next((item for item in current_fields if item["name"] == part), None)
        is_last = index == len(parts) - 1
        if field is None:
            if is_last:
                current_fields.append({"name": part, "type": "literal", "params": {"value": value}})
                return
            new_field = {"name": part, "type": "object", "params": {"fields": []}}
            current_fields.append(new_field)
            field = new_field
        if is_last:
            field["type"] = "literal"
            field["params"] = {"value": value}
            return
        if field["type"] != "object":
            field["type"] = "object"
            field["params"] = {"fields": []}
        current_fields = field["params"]["fields"]


def get_literal(config: dict, path: str):
    try:
        field = find_field(config["fields"], path)
    except generate_data.SkillError:
        return None
    if field.get("params") and "value" in field["params"]:
        return field["params"]["value"]
    return None


def update_field_params(config: dict, path: str, updates: dict) -> None:
    try:
        field = find_field(config["fields"], path)
    except generate_data.SkillError:
        return
    params = field.setdefault("params", {})
    params.update(updates)


def apply_contact_address_filters(config: dict, *, city: str | None = None, province: str | None = None) -> None:
    updates = {}
    if city:
        updates["city"] = city
    if province:
        updates["province"] = province
    if not updates:
        return
    for path in ["contact.address", "contact.city", "contact.postal_code"]:
        update_field_params(config, path, updates)


def append_unique(items: list, value) -> None:
    if value not in items:
        items.append(value)


def contains_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def first_matching_value(text: str, mapping: dict[str, str | dict]) -> str | dict | None:
    for phrase, value in mapping.items():
        if phrase in text:
            return value
    return None


def set_population_age_band(config: dict, age_band: str) -> None:
    population_model = config.get("population_model")
    if not isinstance(population_model, dict):
        return

    segments = population_model.get("segments")
    if isinstance(segments, list):
        for segment in segments:
            values = segment.get("values")
            if isinstance(values, dict):
                values["age_band"] = age_band

    try:
        birth_date_field = find_field(config["fields"], "identity.birth_date")
    except generate_data.SkillError:
        return

    if birth_date_field.get("type") != "birth_date_from_age_band":
        return

    params = birth_date_field.setdefault("params", {})
    bands = params.setdefault("bands", {})
    default_bands = {
        "Y18T24": {"min_age": 18, "max_age": 24},
        "Y25T34": {"min_age": 25, "max_age": 34},
        "Y35T44": {"min_age": 35, "max_age": 44},
        "Y45T54": {"min_age": 45, "max_age": 54},
        "Y55T64": {"min_age": 55, "max_age": 64},
        "Y65PL": {"min_age": 65, "max_age": 92},
    }
    if age_band in default_bands and age_band not in bands:
        bands[age_band] = default_bands[age_band]


def extract_children_count(text: str) -> int | None:
    if contains_any(text, NO_CHILDREN_HINTS):
        return 0

    for pattern in [r"\b(\d+)\s+children?\b", r"\b(\d+)\s+(kinderen|enfants)\b"]:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    for word, value in {**WORD_NUMBERS, **MULTILINGUAL_NUMBER_HINTS}.items():
        if re.search(rf"\b{re.escape(word)}\s+(children?|kinderen|enfants)\b", text):
            return value
    return None


def collect_ambiguities(text: str) -> list[str]:
    ambiguities = []
    if contains_any(text, SINGLE_HINTS) and contains_any(text, MARRIED_HINTS):
        ambiguities.append("Request mentions both single and married relationship status.")
    if contains_any(text, NO_CAR_HINTS) and (contains_any(text, HAS_CAR_HINTS) or contains_any(text, EV_HINTS) or contains_any(text, COMPANY_CAR_HINTS)):
        ambiguities.append("Request mentions both car ownership and no-car preferences.")
    if contains_any(text, LIVES_ALONE_HINTS) and contains_any(text, PARENT_HINTS):
        ambiguities.append("Request suggests both living alone and having a parent-style household.")
    return ambiguities


def collect_matched_signals(text: str) -> list[str]:
    signal_map = {
        "privacy": PRIVACY_HINTS,
        "urban": URBAN_HINTS,
        "parent": PARENT_HINTS,
        "budget": BUDGET_HINTS,
        "commuter": COMMUTER_HINTS,
        "housing": OWNER_HINTS + RENTER_HINTS + APARTMENT_HINTS + HOUSE_HINTS + ROW_HOUSE_HINTS + TOWNHOUSE_HINTS + DUPLEX_HINTS + BRUSSELS_APARTMENT_HINTS,
        "work_mode": REMOTE_WORK_HINTS + HYBRID_WORK_HINTS + SHIFT_WORK_HINTS + PART_TIME_HINTS,
        "self_employed": SELF_EMPLOYED_HINTS,
        "public_sector": CIVIL_SERVICE_HINTS + PUBLIC_SECTOR_HINTS,
        "mobility": TRAIN_COMMUTE_HINTS + BIKE_COMMUTE_HINTS + CAR_COMMUTE_HINTS + METRO_HINTS + TRAM_HINTS + BUS_HINTS + CARGO_BIKE_HINTS + EV_HINTS + COMPANY_CAR_HINTS,
        "geography": list(CITY_HINTS.keys()) + list(REGION_HINTS.keys()) + list(PROVINCE_HINTS.keys()) + list(BRUSSELS_COMMUNE_HINTS.keys()),
    }
    return [label for label, phrases in signal_map.items() if contains_any(text, phrases)]


def build_translation_metadata(text: str, *, locale: str, country: str) -> dict:
    matched_signals = collect_matched_signals(text)
    ambiguities = collect_ambiguities(text)
    base_score = min(0.45 + (0.08 * len(matched_signals)), 0.95)
    confidence = round(max(0.2, base_score - (0.15 * len(ambiguities))), 2)
    return {
        "locale_resolution": {"locale": locale, "country": country},
        "matched_signals": matched_signals,
        "ambiguities": ambiguities,
        "confidence": confidence,
    }


def infer_archetypes(text: str) -> list[str]:
    archetypes = []
    if contains_any(text, PRIVACY_HINTS) and contains_any(text, URBAN_HINTS) and contains_any(text, PARENT_HINTS):
        append_unique(archetypes, "privacy-conscious-urban-parent")
    if contains_any(text, BUDGET_HINTS) and contains_any(text, COMMUTER_HINTS):
        append_unique(archetypes, "budget-conscious-commuter")
    return archetypes


def resolve_belgian_translation_locale(request_locale: str | None, country: str | None) -> tuple[str, str]:
    country = (country or "BE").upper()
    if country != "BE":
        raise generate_data.SkillError(
            "translate_persona_request.py remains Belgium-focused. Non-Belgian target countries are not supported yet."
        )

    locale = str(request_locale or "").strip()
    if not locale:
        return "nl_BE", country

    if locale in SUPPORTED_BELGIAN_TRANSLATION_LOCALES:
        return locale, country

    language = locale.split("_", 1)[0].lower()
    if language == "fr":
        return "fr_BE", country
    return "nl_BE", country


def apply_geography_hints(config: dict, text: str) -> None:
    if contains_any(text, URBAN_NEIGHBORHOOD_HINTS):
        set_literal(config, "household_context.neighborhood_type", "urban")
    elif contains_any(text, SUBURBAN_HINTS):
        set_literal(config, "household_context.neighborhood_type", "suburban")
    elif contains_any(text, RURAL_HINTS):
        set_literal(config, "household_context.neighborhood_type", "rural")

    city_hint = first_matching_value(text, CITY_HINTS)
    if isinstance(city_hint, str):
        apply_contact_address_filters(config, city=city_hint)
        if city_hint == "Brussel":
            set_literal(config, "household_context.neighborhood_type", "urban")

    province_hint = first_matching_value(text, PROVINCE_HINTS)
    if isinstance(province_hint, dict):
        apply_contact_address_filters(config, city=province_hint.get("city"), province=province_hint.get("province"))
        if "neighborhood_type" in province_hint:
            set_literal(config, "household_context.neighborhood_type", province_hint["neighborhood_type"])

    brussels_commune_hint = first_matching_value(text, BRUSSELS_COMMUNE_HINTS)
    if isinstance(brussels_commune_hint, dict):
        apply_contact_address_filters(
            config,
            city=brussels_commune_hint.get("city"),
            province=brussels_commune_hint.get("province"),
        )
        if "neighborhood_type" in brussels_commune_hint:
            set_literal(config, "household_context.neighborhood_type", brussels_commune_hint["neighborhood_type"])

    region_hint = first_matching_value(text, REGION_HINTS)
    if isinstance(region_hint, dict):
        apply_contact_address_filters(config, city=region_hint.get("city"), province=region_hint.get("province"))
        if "neighborhood_type" in region_hint:
            set_literal(config, "household_context.neighborhood_type", region_hint["neighborhood_type"])


def apply_commute_hints(config: dict, text: str) -> None:
    if contains_any(text, TRAIN_COMMUTE_HINTS):
        set_literal(config, "mobility.primary_commute_mode", "train")
        set_literal(config, "mobility.public_transport_use", "frequent")
        set_literal(config, "household_context.commute_style", "train-based commuter routine")
    elif contains_any(text, METRO_HINTS):
        set_literal(config, "mobility.primary_commute_mode", "metro")
        set_literal(config, "mobility.public_transport_use", "frequent")
        set_literal(config, "household_context.commute_style", "metro-first urban commute")
    elif contains_any(text, TRAM_HINTS):
        set_literal(config, "mobility.primary_commute_mode", "tram")
        set_literal(config, "mobility.public_transport_use", "frequent")
        set_literal(config, "household_context.commute_style", "tram-based urban commute")
    elif contains_any(text, BUS_HINTS):
        set_literal(config, "mobility.primary_commute_mode", "bus")
        set_literal(config, "mobility.public_transport_use", "frequent")
        set_literal(config, "household_context.commute_style", "bus-first commuter routine")
    elif contains_any(text, BIKE_COMMUTE_HINTS):
        set_literal(config, "mobility.primary_commute_mode", "bike")
        set_literal(config, "mobility.public_transport_use", "occasional")
        set_literal(config, "household_context.commute_style", "bike-first commuter routine")
    elif contains_any(text, CAR_COMMUTE_HINTS):
        set_literal(config, "mobility.primary_commute_mode", "car")
        set_literal(config, "mobility.public_transport_use", "rare")
        set_literal(config, "household_context.commute_style", "car-based commuter routine")
    elif contains_any(text, TRANSIT_HINTS):
        set_literal(config, "mobility.public_transport_use", "frequent")

    if contains_any(text, EV_HINTS):
        set_literal(config, "lifestyle.car_model", "Tesla Model 3")
        set_literal(config, "mobility.driving_frequency", "most weekdays")

    if contains_any(text, COMPANY_CAR_HINTS):
        set_literal(config, "lifestyle.car_model", "BMW iX1 company car")
        set_literal(config, "mobility.driving_frequency", "most weekdays")

    if contains_any(text, CARGO_BIKE_HINTS):
        set_literal(config, "lifestyle.bike_model", "Urban Arrow Family")
        if get_literal(config, "mobility.primary_commute_mode") is None:
            set_literal(config, "mobility.primary_commute_mode", "cargo bike")
        set_literal(config, "household_context.commute_style", "cargo-bike household routine")


def apply_housing_and_household_hints(config: dict, text: str) -> None:
    if contains_any(text, OWNER_HINTS):
        set_literal(config, "household_context.ownership_status", "owner")
    elif contains_any(text, RENTER_HINTS):
        set_literal(config, "household_context.ownership_status", "renter")

    if contains_any(text, BRUSSELS_APARTMENT_HINTS):
        set_literal(config, "household_context.housing_type", "brussels apartment")
        set_literal(config, "household_context.neighborhood_type", "urban")
        apply_contact_address_filters(config, city="Brussel", province="Brussels-Capital")
    elif contains_any(text, APARTMENT_HINTS):
        set_literal(config, "household_context.housing_type", "apartment")
    elif contains_any(text, ROW_HOUSE_HINTS):
        set_literal(config, "household_context.housing_type", "row house")
    elif contains_any(text, DUPLEX_HINTS):
        set_literal(config, "household_context.housing_type", "duplex")
    elif contains_any(text, TOWNHOUSE_HINTS):
        set_literal(config, "household_context.housing_type", "townhouse")
    elif contains_any(text, ASSISTED_LIVING_HINTS):
        set_literal(config, "household_context.housing_type", "assisted living residence")
    elif contains_any(text, HOUSE_HINTS):
        set_literal(config, "household_context.housing_type", "house")

    if contains_any(text, SINGLE_PARENT_HINTS):
        set_literal(config, "identity.marital_status", "single")
        existing_children = get_literal(config, "identity.num_children")
        if existing_children in (None, 0):
            set_literal(config, "identity.num_children", 1)

    if contains_any(text, LIVES_ALONE_HINTS):
        set_literal(config, "identity.marital_status", "single")
        set_literal(config, "identity.num_children", 0)
        set_literal(config, "household_context.household_size", 1)
        return

    if contains_any(text, DIVORCED_HINTS):
        set_literal(config, "identity.marital_status", "divorced")

    if contains_any(text, CO_PARENTING_HINTS):
        set_literal(config, "identity.marital_status", "divorced")
        if extract_children_count(text) is None:
            set_literal(config, "identity.num_children", 1)

    if contains_any(text, BLENDED_FAMILY_HINTS):
        set_literal(config, "identity.marital_status", "married")
        existing_children = get_literal(config, "identity.num_children")
        if existing_children in (None, 0, 1):
            set_literal(config, "identity.num_children", 2)

    marital_status = get_literal(config, "identity.marital_status")
    num_children = get_literal(config, "identity.num_children")
    if not isinstance(num_children, int):
        num_children = 0

    if contains_any(text, MULTIGENERATIONAL_HINTS):
        base_size = 2 if marital_status == "married" or contains_any(text, COUPLE_HINTS) else 1
        set_literal(config, "household_context.household_size", base_size + num_children + 1)
        return

    if contains_any(text, COUPLE_HINTS) and marital_status in {None, "single"}:
        set_literal(config, "identity.marital_status", "married")
        marital_status = "married"

    if marital_status == "married":
        set_literal(config, "household_context.household_size", 2 + num_children)
    elif marital_status == "divorced":
        set_literal(config, "household_context.household_size", max(1, 1 + num_children))
    elif marital_status == "single":
        set_literal(config, "household_context.household_size", max(1, 1 + num_children))


def apply_work_hints(config: dict, text: str) -> None:
    if contains_any(text, REMOTE_WORK_HINTS):
        set_literal(config, "daily_routine.work_pattern", "mostly remote schedule")
        set_literal(config, "household_context.commute_style", "mostly remote work routine")
    elif contains_any(text, HYBRID_WORK_HINTS):
        set_literal(config, "daily_routine.work_pattern", "hybrid office schedule")
        set_literal(config, "household_context.commute_style", "structured hybrid commute")
    elif contains_any(text, SHIFT_WORK_HINTS):
        set_literal(config, "daily_routine.work_pattern", "shift-based schedule")
        set_literal(config, "household_context.commute_style", "shift-based commute pattern")
    elif contains_any(text, PART_TIME_HINTS):
        set_literal(config, "daily_routine.work_pattern", "part-time schedule")
        set_literal(config, "household_context.commute_style", "part-time weekly commute")

    if contains_any(text, SELF_EMPLOYED_HINTS):
        set_literal(config, "professional.company", "Self-employed")
        if get_literal(config, "professional.job_title") is None:
            set_literal(config, "professional.job_title", "Independent Consultant")
        if get_literal(config, "professional.profession") is None:
            set_literal(config, "professional.profession", "Independent Consultant")

    if contains_any(text, DEVELOPER_HINTS):
        set_literal(config, "professional.industry", "Software")
        set_literal(config, "professional.job_title", "Software Engineer")
        set_literal(config, "professional.profession", "Software Engineer")
    elif contains_any(text, DESIGNER_HINTS):
        set_literal(config, "professional.industry", "Design")
        set_literal(config, "professional.job_title", "UX Designer")
        set_literal(config, "professional.profession", "UX Designer")
    elif contains_any(text, MARKETING_HINTS):
        set_literal(config, "professional.industry", "Marketing")
        set_literal(config, "professional.job_title", "Digital Marketing Manager")
        set_literal(config, "professional.profession", "Digital Marketing Manager")
    elif contains_any(text, LEGAL_HINTS):
        set_literal(config, "professional.industry", "Legal Services")
        set_literal(config, "professional.job_title", "Legal Advisor")
        set_literal(config, "professional.profession", "Legal Advisor")
    elif contains_any(text, LOGISTICS_HINTS):
        set_literal(config, "professional.industry", "Logistics")
        set_literal(config, "professional.job_title", "Supply Chain Coordinator")
        set_literal(config, "professional.profession", "Supply Chain Coordinator")
    elif contains_any(text, RETAIL_HINTS):
        set_literal(config, "professional.industry", "Retail")
        set_literal(config, "professional.job_title", "Store Operations Manager")
        set_literal(config, "professional.profession", "Store Operations Manager")
    elif contains_any(text, UTILITIES_HINTS):
        set_literal(config, "professional.industry", "Utilities")
        set_literal(config, "professional.job_title", "Customer Operations Lead")
        set_literal(config, "professional.profession", "Customer Operations Lead")

    if contains_any(text, CIVIL_SERVICE_HINTS):
        set_literal(config, "professional.company", "Belgian Public Administration")
        set_literal(config, "professional.industry", "Public Administration")
        set_literal(config, "professional.job_title", "Civil Service Coordinator")
        set_literal(config, "professional.profession", "Public Administration")
    elif contains_any(text, PUBLIC_SECTOR_HINTS):
        set_literal(config, "professional.company", "Local Public Service")
        set_literal(config, "professional.industry", "Public Administration")
        if get_literal(config, "professional.job_title") is None:
            set_literal(config, "professional.job_title", "Public Service Program Officer")
        if get_literal(config, "professional.profession") is None:
            set_literal(config, "professional.profession", "Public Administration")


def apply_life_stage_hints(config: dict, text: str) -> None:
    if contains_any(text, STUDENT_HINTS):
        set_population_age_band(config, "Y18T24")
        set_literal(config, "professional.profession", "Student")
        set_literal(config, "professional.job_title", "Higher Education Student")
        set_literal(config, "professional.company", "Higher Education")
        set_literal(config, "professional.education_level", "Secondary school or bachelor's in progress")
        set_literal(config, "professional.income_bracket", "low")
        set_literal(config, "daily_routine.work_pattern", "study-centered schedule")
        return

    if contains_any(text, STARTER_HINTS):
        set_population_age_band(config, "Y25T34")
        set_literal(config, "professional.education_level", "Bachelor's degree")
        if get_literal(config, "professional.income_bracket") is None:
            set_literal(config, "professional.income_bracket", "middle")
        return

    if contains_any(text, MID_CAREER_HINTS):
        set_population_age_band(config, "Y35T44")
        return

    if contains_any(text, PRE_RETIREMENT_HINTS):
        set_population_age_band(config, "Y55T64")
        set_literal(config, "daily_routine.work_pattern", "senior professional schedule")
        return

    if contains_any(text, RETIRED_HINTS):
        set_population_age_band(config, "Y65PL")
        set_literal(config, "professional.profession", "Retired")
        set_literal(config, "professional.job_title", "Retired")
        set_literal(config, "professional.company", "Retired")
        set_literal(config, "daily_routine.work_pattern", "retired routine")
        set_literal(config, "household_context.commute_style", "local, low-commute routine")
        return


def build_persona_config_from_request(request: dict) -> dict:
    locale, country = resolve_belgian_translation_locale(
        request.get("locale"),
        request.get("country", "BE"),
    )

    config = copy.deepcopy(load_json(BASE_PERSONA_EXAMPLE))
    config["locale"] = locale
    config["records"] = int(request.get("count", 1))
    if "seed" in request:
        config["seed"] = request["seed"]

    text = collect_request_text(request)
    config["archetypes"] = infer_archetypes(text)
    config["translation_metadata"] = build_translation_metadata(text, locale=locale, country=country)

    children_count = extract_children_count(text)
    if children_count is not None:
        set_literal(config, "identity.num_children", children_count)
        if children_count == 0:
            set_literal(config, "identity.marital_status", "single")

    if contains_any(text, SINGLE_HINTS):
        set_literal(config, "identity.marital_status", "single")
    elif contains_any(text, MARRIED_HINTS):
        set_literal(config, "identity.marital_status", "married")

    apply_geography_hints(config, text)

    if contains_any(text, NO_CAR_HINTS):
        set_literal(config, "lifestyle.car_model", None)
    elif contains_any(text, HAS_CAR_HINTS):
        set_literal(config, "lifestyle.car_model", "Volvo XC40")

    if contains_any(text, BIKE_HINTS):
        set_literal(config, "lifestyle.bike_model", "Gazelle Ultimate")

    if contains_any(text, DOG_HINTS):
        set_literal(config, "lifestyle.pet", "dog")
    elif contains_any(text, CAT_HINTS):
        set_literal(config, "lifestyle.pet", "cat")

    for hint, values in INDUSTRY_HINTS.items():
        if hint in text:
            industry, job_title, profession = values
            set_literal(config, "professional.industry", industry)
            set_literal(config, "professional.job_title", job_title)
            set_literal(config, "professional.profession", profession)
            break

    if contains_any(text, LOW_INCOME_HINTS):
        set_literal(config, "professional.income_bracket", "low")
    elif contains_any(text, HIGH_INCOME_HINTS):
        set_literal(config, "professional.income_bracket", "high")

    apply_life_stage_hints(config, text)
    apply_housing_and_household_hints(config, text)
    apply_work_hints(config, text)
    apply_commute_hints(config, text)

    output_path = request.get("output_path", "artifacts/persona-request-generated.json")
    config["output"]["path"] = output_path
    return config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate a natural-language persona request into a runnable config.")
    parser.add_argument("--request", required=True, help="Path to a persona request JSON file.")
    parser.add_argument("--output", help="Path to write the generated persona config JSON.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the generated config instead of writing it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = load_json(Path(args.request))
    config = build_persona_config_from_request(request)
    generate_data.normalize_config(config)

    if args.validate_only:
        print(
            json.dumps(
                {"status": "validated", "records": config["records"], "archetypes": config.get("archetypes", [])},
                indent=2,
            )
        )
        return 0

    output_path = Path(args.output) if args.output else Path(config["output"]["path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": "written", "output": str(output_path), "archetypes": config.get("archetypes", [])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
