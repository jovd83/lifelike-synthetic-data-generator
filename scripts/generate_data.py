#!/usr/bin/env python
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "faker>=24.4.0,<25",
#   "rstr>=3.2.2,<4",
# ]
# ///

import argparse
import csv
import html
import json
import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from faker import Faker
import rstr


SUPPORTED_OUTPUT_FORMATS = {"csv", "json", "ndjson", "sql", "html", "markdown"}
POPULATION_AWARE_FIELD_TYPES = {"segment_value", "birth_date_from_age_band", "faker_from_segment"}
DEFAULT_OUTPUT_NAME = {
    "csv": "synthetic_data.csv",
    "json": "synthetic_data.json",
    "ndjson": "synthetic_data.ndjson",
    "sql": "synthetic_data.sql",
    "html": "synthetic_personas_html",
    "markdown": "synthetic_personas_markdown",
}
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CUSTOM_FORMATS_PATH = ROOT_DIR / "references" / "custom_formats.json"
DEFAULT_OPEN_DATA_SOURCES_PATH = ROOT_DIR / "references" / "open_data_sources.json"
DEFAULT_BELGIAN_ADDRESS_CATALOG_PATH = ROOT_DIR / "references" / "belgian_address_catalog.json"
DEFAULT_BELGIAN_BANK_CATALOG_PATH = ROOT_DIR / "references" / "belgian_bank_catalog.json"
DEFAULT_PERSONA_CATALOGS_PATH = ROOT_DIR / "references" / "persona_catalogs.json"
DEFAULT_PERSONA_PROFILE_BUNDLES_PATH = ROOT_DIR / "references" / "persona_profile_bundles.json"
DEFAULT_PERSONA_ARCHETYPES_PATH = ROOT_DIR / "references" / "persona_archetypes.json"
BELGIAN_COMPANY_LEGAL_FORMS = {
    "VLG": {"BV": 58, "NV": 22, "CommV": 12, "VOF": 8},
    "WAL": {"SRL": 58, "SA": 22, "SNC": 12, "SC": 8},
    "BXL": {"SRL": 34, "BV": 18, "SA": 18, "NV": 12, "SNC": 10, "VOF": 8},
    "default": {"BV": 24, "SRL": 24, "NV": 16, "SA": 16, "VOF": 10, "SNC": 10},
}
BELGIAN_NONPROFIT_LEGAL_FORMS = {
    "VLG": {"vzw": 100},
    "WAL": {"ASBL": 100},
    "BXL": {"ASBL": 70, "vzw": 20, "AISBL": 10},
    "default": {"ASBL": 60, "vzw": 40},
}
BELGIAN_COMPANY_SURNAMES = {
    "VLG": [
        "De Smet",
        "Peeters",
        "Janssens",
        "Maes",
        "Willems",
        "Claes",
        "Vermeulen",
        "Goossens",
        "Van den Broeck",
        "Michiels",
    ],
    "WAL": [
        "Dubois",
        "Lambert",
        "Leclercq",
        "Remy",
        "Dumont",
        "Denis",
        "Piron",
        "Simon",
        "Renard",
        "Toussaint",
    ],
    "BXL": [
        "Jacobs",
        "Smets",
        "Diallo",
        "Benali",
        "Martens",
        "Dubois",
        "El Khattabi",
        "Lopez",
        "Kaya",
        "Mertens",
    ],
}
BELGIAN_COMPANY_INDUSTRY_TOKENS = {
    "business services": {
        "VLG": ["Office Services", "Support", "Administratie", "Business Services", "Diensten"],
        "WAL": ["Services", "Support", "Bureau Services", "Administration", "Conseil"],
        "BXL": ["Services", "Office Support", "Business Services", "Advisory", "Support"],
    },
    "wholesale and retail": {
        "VLG": ["Handel", "Retail", "Distributie", "Trade", "Market"],
        "WAL": ["Commerce", "Distribution", "Retail", "Trade", "Marche"],
        "BXL": ["Retail", "Trade", "Distribution", "Market", "Commerce"],
    },
    "retail": {
        "VLG": ["Retail", "Handel", "Market", "Shop Services", "Trade"],
        "WAL": ["Retail", "Commerce", "Marche", "Trade", "Distribution"],
        "BXL": ["Retail", "Market", "Trade", "Shop Services", "Commerce"],
    },
    "home services": {
        "VLG": ["Home Services", "Schoonmaak", "Huiszorg", "Cleaning", "Woonservice"],
        "WAL": ["Services a domicile", "Cleaning", "Home Services", "Menage", "Assistance"],
        "BXL": ["Home Services", "Cleaning", "Household Support", "Living Services", "Domestic Services"],
    },
    "facilities and hospitality": {
        "VLG": ["Facility Services", "Site Support", "Gebouwservice", "Hospitality", "Onderhoud"],
        "WAL": ["Facility Services", "Support de site", "Maintenance", "Hospitalite", "Services"],
        "BXL": ["Facility Services", "Site Support", "Maintenance", "Hospitality Services", "Building Support"],
    },
    "education": {
        "VLG": ["Leercentrum", "Onderwijsdiensten", "Training", "Campus Services", "Studiebegeleiding"],
        "WAL": ["Formation", "Education Services", "Campus", "Apprentissage", "Soutien scolaire"],
        "BXL": ["Learning Hub", "Education Services", "Training", "Campus", "Study Support"],
    },
    "healthcare": {
        "VLG": ["Zorg", "Care Services", "Gezondheid", "Medisch Support", "Thuiszorg"],
        "WAL": ["Sante", "Care Services", "Medical Support", "Soins", "Assistance"],
        "BXL": ["Care Services", "Health Partners", "Medical Support", "Wellbeing", "Sante"],
    },
    "logistics": {
        "VLG": ["Logistiek", "Supply", "Cargo", "Distribution", "Warehousing"],
        "WAL": ["Logistique", "Supply", "Cargo", "Distribution", "Entrepot"],
        "BXL": ["Logistics", "Supply", "Cargo", "Distribution", "Warehousing"],
    },
    "social services": {
        "VLG": ["Sociale Zorg", "Community Support", "Welzijn", "Buurtzorg", "Care Services"],
        "WAL": ["Services sociaux", "Community Support", "Solidarite", "Accompagnement", "Care Services"],
        "BXL": ["Community Support", "Social Care", "Wellbeing", "Solidarity", "Care Services"],
    },
    "professional services": {
        "VLG": ["Advies", "Consult", "Business Services", "Partners", "Projecten"],
        "WAL": ["Conseil", "Services", "Consulting", "Projet", "Partenaires"],
        "BXL": ["Advisory", "Consulting", "Services", "Partners", "Projects"],
    },
    "finance": {
        "VLG": ["Accountancy", "Finadvies", "Audit", "Kapitaal", "Boekhouding"],
        "WAL": ["Finance", "Compta", "Audit", "Patrimoine", "Conseil"],
        "BXL": ["Finance", "Advisory", "Capital", "Audit", "Ledger"],
    },
    "transport and logistics": {
        "VLG": ["Transport", "Logistiek", "Cargo", "Supply", "Distributie"],
        "WAL": ["Transport", "Logistique", "Cargo", "Distribution", "Freight"],
        "BXL": ["Transport", "Logistics", "Cargo", "Mobility", "Supply"],
    },
    "hospitality": {
        "VLG": ["Hospitality", "Catering", "Brasserie Services", "Event Services", "Food House"],
        "WAL": ["Hospitalite", "Restauration", "Brasserie", "Food Services", "Evenements"],
        "BXL": ["Hospitality", "Food Services", "Brasserie", "Events", "Guest Services"],
    },
    "information technology": {
        "VLG": ["Data Systems", "Digital", "Software", "Cloud", "IT Solutions"],
        "WAL": ["Digital", "Logiciels", "Donnees", "Systemes", "IT Services"],
        "BXL": ["Digital", "Software", "Data", "Cloud", "Tech"],
    },
    "childcare": {
        "VLG": ["Kinderzorg", "Childcare", "Gezinszorg", "Kids Care", "Daycare"],
        "WAL": ["Petite enfance", "Childcare", "Family Services", "Kids Care", "Creche Services"],
        "BXL": ["Childcare", "Family Services", "Kids Care", "Early Years", "Daycare"],
    },
    "construction": {
        "VLG": ["Bouw", "Construct", "Projecten", "Aanneming", "Werken"],
        "WAL": ["Construction", "Travaux", "Batiment", "Chantiers", "Projets"],
        "BXL": ["Construct", "Building Services", "Projects", "Works", "Urban Build"],
    },
    "default": {
        "VLG": ["Advies", "Technics", "Projecten", "Diensten", "Groep"],
        "WAL": ["Services", "Conseil", "Projets", "Tech", "Solutions"],
        "BXL": ["Advisory", "Services", "Solutions", "Partners", "Projects"],
    },
}
DEFAULT_NETWORK_TIMEOUT_SEC = 30
SUPPORTED_SOURCE_FILTER_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "in"}
NUMERIC_AGE_BAND_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
NUMERIC_AGE_PLUS_PATTERN = re.compile(r"^\s*(\d+)\s*\+\s*$")
STATBEL_AGE_BAND_PATTERN = re.compile(r"^Y(\d+)T(\d+)$")
STATBEL_AGE_PLUS_PATTERN = re.compile(r"^Y(\d+)PL$")
STATBEL_AGE_GE_PATTERN = re.compile(r"^Y_GE(\d+)$")
STATBEL_AGE_LT_PATTERN = re.compile(r"^Y_LT(\d+)$")
MISSING = object()
SQL_CONSTRAINT_KEYWORDS = {
    "not",
    "null",
    "default",
    "primary",
    "references",
    "unique",
    "check",
    "constraint",
    "collate",
    "generated",
}
PERSONA_BUNDLE_SENSITIVE_PATH_PATTERNS = {
    ("identity", "unique_id"),
    ("identity", "national_id_type"),
    ("identity", "national_id_number"),
    ("contact", "email"),
    ("contact", "phone_number"),
    ("contact", "address"),
    ("contact", "postal_code"),
    ("finance", "iban"),
    ("finance", "swift_bic"),
    ("family", "spouse", "birth_date"),
    ("family", "spouse", "national_id_type"),
    ("family", "spouse", "national_id_number"),
    ("family", "children", "*", "birth_date"),
}
PERSONA_BUNDLE_UI_TEXT = {
    "en": {
        "generated_personas_title": "Generated Personas",
        "browse_personas": "Browse the generated personas below.",
        "back_to_index": "Back to index",
        "name": "Name",
        "role": "Role",
        "city": "City",
        "summary": "Summary",
        "none": "None",
    },
    "nl": {
        "generated_personas_title": "Gegenereerde Persona's",
        "browse_personas": "Blader hieronder door de gegenereerde persona's.",
        "back_to_index": "Terug naar overzicht",
        "name": "Naam",
        "role": "Rol",
        "city": "Woonplaats",
        "summary": "Samenvatting",
        "none": "Geen",
    },
    "fr": {
        "generated_personas_title": "Personas Generes",
        "browse_personas": "Parcourez ci-dessous les personas generes.",
        "back_to_index": "Retour a l'index",
        "name": "Nom",
        "role": "Role",
        "city": "Ville",
        "summary": "Resume",
        "none": "Aucun",
    },
}
PERSONA_BUNDLE_LABELS = {
    "nl": {
        "identity": "Identiteit",
        "daily_routine": "Dagelijks Ritme",
        "mobility": "Mobiliteit",
        "contact": "Contact",
        "professional": "Professioneel",
        "household_context": "Huishoudcontext",
        "lifestyle": "Leefstijl",
        "shopping_and_brand_preferences": "Winkel- En Merkvoorkeuren",
        "digital": "Digitaal",
        "finance": "Financien",
        "family": "Gezin",
        "introduction": "Introductie",
        "life_timeline": "Levenslijn",
        "biography": "Biografie",
        "date": "Datum",
        "category": "Categorie",
        "title": "Titel",
        "description": "Beschrijving",
        "first_name": "Voornaam",
        "last_name": "Achternaam",
        "full_name": "Volledige Naam",
        "gender": "Geslacht",
        "birth_date": "Geboortedatum",
        "age": "Leeftijd",
        "nationality": "Nationaliteit",
        "marital_status": "Burgerlijke Staat",
        "num_children": "Aantal Kinderen",
        "preferred_pronouns": "Voornaamwoorden",
        "pet": "Huisdier",
        "household_size": "Huishoudgrootte",
        "driving_frequency": "Rijfrequentie",
        "travel_frequency": "Reisfrequentie",
        "region": "Regio",
        "city": "Stad",
        "province": "Provincie",
        "country": "Land",
        "job_title": "Functie",
        "profession": "Beroep",
        "industry": "Sector",
        "collar_type": "Arbeidsprofiel",
        "work_pattern": "Werkpatroon",
        "company": "Werkgever",
        "organization_type": "Organisatietype",
        "sector_type": "Sectortype",
        "employer_scale": "Werkgeversschaal",
        "education_profile": "Opleidingsprofiel",
        "level": "Niveau",
        "institution_type": "Instellingstype",
        "instruction_language": "Onderwijstaal",
        "education_level": "Opleidingsniveau",
        "income_bracket": "Inkomensgroep",
        "primary_commute_mode": "Vervoersmiddel Woon-Werk",
        "public_transport_use": "Gebruik Openbaar Vervoer",
        "travel_style": "Reisstijl",
        "weekday_rhythm": "Weekritme",
        "evening_habits": "Avondgewoonten",
        "weekend_rhythm": "Weekendritme",
        "wake_time": "Opstaantijd",
        "housing_type": "Woningtype",
        "ownership_status": "Woonstatus",
        "neighborhood_type": "Buurtprofiel",
        "commute_style": "Pendelprofiel",
        "hobbies": "Hobby's",
        "languages_spoken": "Gesproken Talen",
        "values": "Waarden",
        "personality_type": "Persoonlijkheidstype",
        "computer_model": "Computermodel",
        "smartphone_model": "Smartphonemodel",
        "tablet_model": "Tabletmodel",
        "car_model": "Automodel",
        "bike_model": "Fietsmodel",
        "tv_brand": "Tv-Merk",
        "favorite_tv_show": "Favoriete Tv-Show",
        "favorite_movie": "Favoriete Film",
        "favorite_documentary": "Favoriete Documentaire",
        "favorite_vacation_destinations": "Favoriete Reisbestemmingen",
        "bank_name": "Bank",
        "income_level": "Inkomen",
        "preferred_payment_methods": "Betaalvoorkeuren",
        "favorite_supermarket": "Favoriete Supermarkt",
        "preferred_insurer": "Voorkeursverzekeraar",
        "preferred_transit_operator": "Voorkeursvervoerder",
        "preferred_news_brand": "Voorkeursnieuwsbron",
        "mobile_provider": "Mobiele Provider",
        "streaming_platform": "Streamingplatform",
        "device_use": "Apparaatgebruik",
        "privacy_awareness": "Privacybewustzijn",
        "posting_frequency": "Postfrequentie",
        "spouse": "Partner",
        "children": "Kinderen",
    },
    "fr": {
        "identity": "Identite",
        "daily_routine": "Routine Quotidienne",
        "mobility": "Mobilite",
        "contact": "Contact",
        "professional": "Professionnel",
        "household_context": "Contexte Du Menage",
        "lifestyle": "Style De Vie",
        "shopping_and_brand_preferences": "Preferences D'achat Et De Marque",
        "digital": "Numerique",
        "finance": "Finances",
        "family": "Famille",
        "introduction": "Introduction",
        "life_timeline": "Chronologie De Vie",
        "biography": "Biographie",
        "date": "Date",
        "category": "Categorie",
        "title": "Titre",
        "description": "Description",
        "first_name": "Prenom",
        "last_name": "Nom",
        "full_name": "Nom Complet",
        "gender": "Genre",
        "birth_date": "Date De Naissance",
        "age": "Age",
        "nationality": "Nationalite",
        "marital_status": "Etat Civil",
        "num_children": "Nombre D'enfants",
        "preferred_pronouns": "Pronoms",
        "pet": "Animal De Compagnie",
        "household_size": "Taille Du Menage",
        "driving_frequency": "Frequence De Conduite",
        "travel_frequency": "Frequence De Voyage",
        "region": "Region",
        "city": "Ville",
        "province": "Province",
        "country": "Pays",
        "job_title": "Fonction",
        "profession": "Profession",
        "industry": "Secteur",
        "collar_type": "Type D'emploi",
        "work_pattern": "Organisation Du Travail",
        "company": "Employeur",
        "organization_type": "Type D'organisation",
        "sector_type": "Type De Secteur",
        "employer_scale": "Taille De L'employeur",
        "education_profile": "Profil D'etudes",
        "level": "Niveau",
        "institution_type": "Type D'etablissement",
        "instruction_language": "Langue D'enseignement",
        "education_level": "Niveau D'etudes",
        "income_bracket": "Tranche De Revenu",
        "primary_commute_mode": "Mode De Trajet",
        "public_transport_use": "Usage Des Transports Publics",
        "travel_style": "Style De Voyage",
        "weekday_rhythm": "Rythme En Semaine",
        "evening_habits": "Habitudes Du Soir",
        "weekend_rhythm": "Rythme Du Week-end",
        "wake_time": "Heure De Lever",
        "housing_type": "Type De Logement",
        "ownership_status": "Statut D'occupation",
        "neighborhood_type": "Cadre De Quartier",
        "commute_style": "Profil De Trajet",
        "hobbies": "Loisirs",
        "languages_spoken": "Langues Parlees",
        "values": "Valeurs",
        "personality_type": "Type De Personnalite",
        "computer_model": "Modele D'ordinateur",
        "smartphone_model": "Modele De Smartphone",
        "tablet_model": "Modele De Tablette",
        "car_model": "Modele De Voiture",
        "bike_model": "Modele De Velo",
        "tv_brand": "Marque De Television",
        "favorite_tv_show": "Serie Preferee",
        "favorite_movie": "Film Prefere",
        "favorite_documentary": "Documentaire Prefere",
        "favorite_vacation_destinations": "Destinations Preferees",
        "bank_name": "Banque",
        "income_level": "Niveau De Revenu",
        "preferred_payment_methods": "Moyens De Paiement Preferes",
        "favorite_supermarket": "Supermarche Prefere",
        "preferred_insurer": "Assureur Prefere",
        "preferred_transit_operator": "Operateur De Transport Prefere",
        "preferred_news_brand": "Marque D'information Preferee",
        "mobile_provider": "Operateur Mobile",
        "streaming_platform": "Plateforme De Streaming",
        "device_use": "Usage Numerique",
        "privacy_awareness": "Sensibilite A La Vie Privee",
        "posting_frequency": "Frequence De Publication",
        "spouse": "Partenaire",
        "children": "Enfants",
    },
}
PERSONA_BUNDLE_VALUE_LOCALIZATION = {
    "nl": {
        ("life_timeline", "*", "title"): {
            "Birth": "Geboorte",
            "Completed secondary education": "Secundair onderwijs afgerond",
            "Started higher education or training": "Hoger onderwijs of opleiding gestart",
            "Completed a bachelor's degree": "Bacheloropleiding afgerond",
            "Completed a master's degree": "Masteropleiding afgerond",
            "Completed vocational training": "Beroepsopleiding afgerond",
            "Completed doctoral studies": "Doctoraatsopleiding afgerond",
            "Career start": "Start van de loopbaan",
            "Expanded responsibilities": "Meer verantwoordelijkheden",
            "Current role": "Huidige functie",
            "Child born": "Geboorte van een kind",
            "Marriage or long-term partnership": "Huwelijk of duurzame partnerrelatie",
            "Established an independent household": "Zelfstandig huishouden opgebouwd",
            "Settled in current city": "Gevestigd in de huidige woonplaats",
            "Household routine changed": "Huishoudroutine veranderde",
        },
        ("professional", "work_pattern"): {
            "hybrid office schedule": "hybride kantoorregeling",
            "structured daytime schedule": "gestructureerd dagschema",
            "shift-based schedule": "ploegenschema",
            "field-based service schedule": "dienstschema op locatie",
            "on-site service schedule": "dienstschema op de werkvloer",
            "remote work routine": "thuiswerkritme",
            "part-time schedule": "deeltijds schema",
            "retired routine": "ritme na pensionering",
        },
        ("daily_routine", "work_pattern"): {
            "hybrid office schedule": "hybride kantoorregeling",
            "structured daytime schedule": "gestructureerd dagschema",
            "shift-based schedule": "ploegenschema",
            "on-site schedule": "schema op locatie",
            "remote work routine": "thuiswerkritme",
            "part-time schedule": "deeltijds schema",
            "retired routine": "ritme na pensionering",
        },
        ("mobility", "primary_commute_mode"): {
            "train": "trein",
            "car": "auto",
            "bike": "fiets",
            "public transport": "openbaar vervoer",
            "metro": "metro",
            "cargo bike": "bakfiets",
        },
        ("mobility", "public_transport_use"): {
            "frequent": "frequent",
            "occasional": "af en toe",
        },
        ("mobility", "travel_style"): {
            "well-planned, family-friendly trips": "goed geplande, gezinsvriendelijke reizen",
            "spontaneous weekends": "spontane weekends",
        },
        ("professional", "income_bracket"): {
            "low": "laag",
            "lower-middle": "lager midden",
            "middle": "midden",
            "upper-middle": "hoger midden",
        },
        ("professional", "sector_type"): {
            "public sector": "publieke sector",
            "private sector": "privésector",
            "nonprofit or community sector": "non-profit- of gemeenschapssector",
        },
        ("professional", "organization_type"): {
            "office-based firm": "kantoororganisatie",
            "operating company": "operationeel bedrijf",
            "service firm": "dienstverlenend bedrijf",
            "school network": "scholennetwerk",
            "public service office": "overheidsdienst",
            "community service organization": "gemeenschapsorganisatie",
            "care network": "zorgnetwerk",
            "care services group": "zorggroep",
        },
        ("professional", "employer_scale"): {
            "regional mid-sized employer": "regionale middelgrote werkgever",
            "local or regional firm": "lokaal of regionaal bedrijf",
            "national or regional operator": "nationale of regionale speler",
            "local SME": "lokale kmo",
            "municipal or regional institution": "gemeentelijke of regionale instelling",
            "local community organization": "lokale gemeenschapsorganisatie",
            "regional support network": "regionaal ondersteuningsnetwerk",
            "regional care network": "regionaal zorgnetwerk",
        },
        ("professional", "collar_type"): {
            "white-collar": "bediende",
            "blue-collar": "arbeider",
            "civil-service": "ambtenarenprofiel",
        },
        ("household_context", "housing_type"): {
            "apartment": "appartement",
            "row house": "rijwoning",
            "semi-detached house": "halfopen bebouwing",
            "detached house": "vrijstaande woning",
            "house": "woning",
            "brussels apartment": "Brussels appartement",
        },
        ("household_context", "ownership_status"): {
            "owner": "eigenaar",
            "renter": "huurder",
        },
        ("household_context", "neighborhood_type"): {
            "urban": "stedelijk",
            "suburban": "voorstedelijk",
            "small-town": "kleinstedelijk",
        },
        ("household_context", "commute_style"): {
            "train-based family logistics": "gezinslogistiek rond de trein",
            "train-based commuter routine": "pendelroutine met de trein",
            "car-based family commute": "gezinspendel met de auto",
            "car-led commute routine": "pendelroutine met de auto",
            "bike-first family routine": "gezinsroutine met de fiets op de eerste plaats",
            "bike-first local routine": "lokale routine met de fiets op de eerste plaats",
        },
        ("lifestyle", "languages_spoken"): {
            "Dutch": "Nederlands",
            "French": "Frans",
            "English": "Engels",
        },
    },
    "fr": {
        ("life_timeline", "*", "title"): {
            "Birth": "Naissance",
            "Completed secondary education": "Etudes secondaires terminees",
            "Started higher education or training": "Debut des etudes superieures ou d'une formation",
            "Completed a bachelor's degree": "Bachelier termine",
            "Completed a master's degree": "Master termine",
            "Completed vocational training": "Formation professionnelle terminee",
            "Completed doctoral studies": "Doctorat termine",
            "Career start": "Debut de carriere",
            "Expanded responsibilities": "Responsabilites elargies",
            "Current role": "Fonction actuelle",
            "Child born": "Naissance d'un enfant",
            "Marriage or long-term partnership": "Mariage ou relation durable",
            "Established an independent household": "Foyer autonome etabli",
            "Settled in current city": "Installation dans la ville actuelle",
            "Household routine changed": "Routine du foyer modifiee",
        },
        ("professional", "work_pattern"): {
            "hybrid office schedule": "organisation hybride bureau-domicile",
            "structured daytime schedule": "horaire de jour structure",
            "shift-based schedule": "horaire en equipes",
            "field-based service schedule": "horaire de service sur le terrain",
            "on-site service schedule": "horaire de service sur site",
            "remote work routine": "routine de teletravail",
            "part-time schedule": "horaire a temps partiel",
            "retired routine": "rythme de retraite",
        },
        ("daily_routine", "work_pattern"): {
            "hybrid office schedule": "organisation hybride bureau-domicile",
            "structured daytime schedule": "horaire de jour structure",
            "shift-based schedule": "horaire en equipes",
            "on-site schedule": "horaire sur site",
            "remote work routine": "routine de teletravail",
            "part-time schedule": "horaire a temps partiel",
            "retired routine": "rythme de retraite",
        },
        ("mobility", "primary_commute_mode"): {
            "train": "train",
            "car": "voiture",
            "bike": "velo",
            "public transport": "transports publics",
            "metro": "metro",
            "cargo bike": "velo cargo",
        },
        ("mobility", "public_transport_use"): {
            "frequent": "frequent",
            "occasional": "occasionnel",
        },
        ("mobility", "travel_style"): {
            "well-planned, family-friendly trips": "voyages bien planifies et adaptes a la famille",
            "spontaneous weekends": "week-ends spontanes",
        },
        ("professional", "income_bracket"): {
            "low": "faible",
            "lower-middle": "moyen inferieur",
            "middle": "moyen",
            "upper-middle": "moyen superieur",
        },
        ("professional", "sector_type"): {
            "public sector": "secteur public",
            "private sector": "secteur prive",
            "nonprofit or community sector": "secteur associatif ou communautaire",
        },
        ("professional", "organization_type"): {
            "office-based firm": "entreprise de bureau",
            "operating company": "entreprise operationnelle",
            "service firm": "entreprise de services",
            "school network": "reseau scolaire",
            "public service office": "service public",
            "community service organization": "organisation de service communautaire",
            "care network": "reseau de soins",
            "care services group": "groupe de services de soins",
        },
        ("professional", "employer_scale"): {
            "regional mid-sized employer": "employeur regional de taille moyenne",
            "local or regional firm": "entreprise locale ou regionale",
            "national or regional operator": "acteur national ou regional",
            "local SME": "PME locale",
            "municipal or regional institution": "institution communale ou regionale",
            "local community organization": "organisation communautaire locale",
            "regional support network": "reseau regional de soutien",
            "regional care network": "reseau regional de soins",
        },
        ("professional", "collar_type"): {
            "white-collar": "emploi de bureau",
            "blue-collar": "emploi manuel",
            "civil-service": "fonction publique",
        },
        ("household_context", "housing_type"): {
            "apartment": "appartement",
            "row house": "maison mitoyenne",
            "semi-detached house": "maison semi-detachee",
            "detached house": "maison individuelle",
            "house": "maison",
            "brussels apartment": "appartement bruxellois",
        },
        ("household_context", "ownership_status"): {
            "owner": "proprietaire",
            "renter": "locataire",
        },
        ("household_context", "neighborhood_type"): {
            "urban": "urbain",
            "suburban": "periurbain",
            "small-town": "petite ville",
        },
        ("household_context", "commute_style"): {
            "train-based family logistics": "logistique familiale autour du train",
            "train-based commuter routine": "routine de trajet en train",
            "car-based family commute": "trajet familial en voiture",
            "car-led commute routine": "routine de trajet en voiture",
            "bike-first family routine": "routine familiale centree sur le velo",
            "bike-first local routine": "routine locale centree sur le velo",
        },
        ("lifestyle", "languages_spoken"): {
            "Dutch": "Neerlandais",
            "French": "Francais",
            "English": "Anglais",
        },
    },
}
PERSONA_BUNDLE_VALUE_LOCALIZATION_BY_KEY = {
    "nl": {
        "category": {
            "identity": "identiteit",
            "education": "onderwijs",
            "career": "carriere",
            "family": "gezin",
            "location": "locatie",
        },
        "gender": {
            "M": "man",
            "F": "vrouw",
            "X": "x",
        },
        "nationality": {
            "Belgian": "Belgisch",
        },
        "marital_status": {
            "single": "alleenstaand",
            "married": "getrouwd",
            "partnered": "partnerrelatie",
            "divorced": "gescheiden",
            "widowed": "weduwe of weduwnaar",
        },
        "preferred_pronouns": {
            "he/him": "hij/hem",
            "she/her": "zij/haar",
            "they/them": "die/hen",
        },
        "pet": {
            "cat": "kat",
            "dog": "hond",
        },
        "level": {
            "Master's degree": "masteropleiding",
            "Bachelor's degree": "bacheloropleiding",
            "Vocational training": "beroepsopleiding",
            "Upper secondary education": "opleiding in het secundair onderwijs",
            "Secondary education": "secundair onderwijs",
            "Doctoral degree": "doctoraatsopleiding",
        },
        "institution_type": {
            "university": "universiteit",
            "university college": "hogeschool",
            "secondary school": "secundaire school",
            "vocational school or adult training": "beroepsschool of volwassenenopleiding",
        },
        "instruction_language": {
            "Dutch": "Nederlands",
            "French": "Frans",
            "Dutch or French": "Nederlands of Frans",
            "German": "Duits",
        },
        "values": {
            "stability": "stabiliteit",
            "family time": "gezinstijd",
            "practicality": "praktisch denken",
            "learning": "leren",
            "reliability": "betrouwbaarheid",
            "comfort": "comfort",
            "independence": "onafhankelijkheid",
            "fairness": "eerlijkheid",
            "planning": "planning",
            "balance": "balans",
            "curiosity": "nieuwsgierigheid",
            "convenience": "gemak",
            "friendship": "vriendschap",
            "routine": "routine",
            "family loyalty": "familiale loyaliteit",
            "rest": "rust",
            "self-reliance": "zelfredzaamheid",
            "loyalty": "loyaliteit",
            "plain speaking": "rechtuit spreken",
            "community": "gemeenschapszin",
            "security": "zekerheid",
            "care": "zorgzaamheid",
            "patience": "geduld",
            "service": "dienstbaarheid",
            "predictability": "voorspelbaarheid",
        },
        "personality_type": {
            "organized and warm": "georganiseerd en warm",
            "thoughtful and steady": "bedachtzaam en standvastig",
            "pragmatic and calm": "pragmatisch en kalm",
            "social and organized": "sociaal en georganiseerd",
            "steady and sociable": "standvastig en sociaal",
            "straightforward and dependable": "rechtuit en betrouwbaar",
            "reserved and steady": "gereserveerd en standvastig",
            "direct and practical": "direct en praktisch",
            "grounded and friendly": "nuchter en vriendelijk",
            "patient and structured": "geduldig en gestructureerd",
            "warm and grounded": "warm en nuchter",
            "measured and dependable": "weloverwogen en betrouwbaar",
        },
        "country": {
            "Belgium": "Belgie",
        },
        "favorite_vacation_destinations": {
            "Ardennes": "Ardennen",
            "Brittany": "Bretagne",
            "Tuscany": "Toscane",
            "Zeeland": "Zeeland",
            "Copenhagen": "Kopenhagen",
            "Alsace": "Elzas",
            "Black Forest": "Zwarte Woud",
            "Lake Constance": "Bodenmeer",
            "Lisbon": "Lissabon",
            "Ghent": "Gent",
            "Valencia": "Valencia",
            "Amsterdam": "Amsterdam",
            "Antwerp": "Antwerpen",
            "Mallorca": "Mallorca",
            "Belgian coast": "Belgische kust",
            "Eifel": "Eifel",
            "Limburg": "Limburg",
            "Luxembourg province": "provincie Luxemburg",
            "North Sea coast": "Noordzeekust",
            "Ostend": "Oostende",
            "Paris": "Parijs",
            "Normandy": "Normandie",
            "Bruges": "Brugge",
            "Jura": "Jura",
        },
        "province": {
            "Brussels-Capital": "Brussels Hoofdstedelijk Gewest",
            "East Flanders": "Oost-Vlaanderen",
            "West Flanders": "West-Vlaanderen",
            "Flemish Brabant": "Vlaams-Brabant",
            "Liege": "Luik",
        },
        "income_level": {
            "stable middle-income household": "stabiel middeninkomenshuishouden",
            "stable but budget-aware household": "stabiel maar prijsbewust huishouden",
            "carefully budgeted household": "zorgvuldig gebudgetteerd huishouden",
            "comfortable upper-middle-income household": "comfortabel hoger middeninkomenshuishouden",
            "stable middle-income household with predictable pay": "stabiel middeninkomenshuishouden met voorspelbaar loon",
            "comfortable upper-middle-income household with predictable pay": "comfortabel hoger middeninkomenshuishouden met voorspelbaar loon",
            "stable middle-income household with careful planning": "stabiel middeninkomenshuishouden met zorgvuldige planning",
            "comfortable upper-middle-income household with careful planning": "comfortabel hoger middeninkomenshuishouden met zorgvuldige planning",
            "carefully budgeted household with close monthly planning": "zorgvuldig gebudgetteerd huishouden met nauwe maandplanning",
            "stable household income": "stabiel huishoudinkomen",
        },
        "preferred_payment_methods": {
            "debit card": "betaalkaart",
            "credit card": "kredietkaart",
            "mobile payment": "mobiel betalen",
        },
        "driving_frequency": {
            "most weekdays": "meeste weekdagen",
            "rare": "zelden",
            "weekends and occasional errands": "weekends en af en toe boodschappen",
            "weekends and occasional school runs": "weekends en af en toe schoolritten",
            "varies by workday": "varieert per werkdag",
        },
        "travel_frequency": {
            "mostly day trips and one budget-friendly holiday": "vooral daguitstappen en een budgetvriendelijke vakantie",
            "one leisure trip or a few short breaks per year": "een vakantiereis of enkele korte uitstappen per jaar",
            "one or two leisure trips per year": "een of twee vakantiereizen per jaar",
            "two or three leisure trips per year": "twee of drie vakantiereizen per jaar",
        },
        "device_use": {
            "shared family planning, streaming, banking, and work communication": "gedeelde gezinsplanning, streaming, bankzaken en werkcommunicatie",
            "practical household coordination, media, and mobile-first browsing": "praktische huishoudafstemming, media en mobielgericht browsen",
            "connected TV use, local content, catch-up viewing, and practical family coordination": "slimme tv-gewoonten, lokale content, uitgesteld kijken en praktische gezinsafstemming",
            "value-conscious mobile use, messaging, catch-up TV, and one main streaming subscription": "prijsbewust mobiel gebruik, berichten, uitgesteld tv-kijken en een hoofdstreamingabonnement",
            "budget-conscious shopping, messaging, and one value-focused streaming subscription": "prijsbewust winkelen, berichten en een voordelig streamingabonnement",
            "mobile-centric browsing, messaging, and selective streaming on a tighter budget": "mobielgericht browsen, berichten en selectief streamen met een krapper budget",
            "connected-home routines, streaming, work communication, and shared family logistics": "slimme thuisroutines, streaming, werkcommunicatie en gedeelde gezinslogistiek",
            "practical household planning, work communication, public-service tools, and streaming in moderation": "praktische huishoudplanning, werkcommunicatie, overheidsdiensten en gematigd streamen",
            "work communication, household planning, public-service admin tools, and steady streaming habits": "werkcommunicatie, huishoudplanning, overheidsadministratie en stabiele streaminggewoonten",
            "messaging, household coordination, work communication, and one or two main streaming habits": "berichten, huishoudafstemming, werkcommunicatie en een of twee vaste streaminggewoonten",
            "messaging, practical household admin, catch-up TV, and careful online shopping": "berichten, praktische huishoudadministratie, uitgesteld tv-kijken en voorzichtig online winkelen",
        },
        "privacy_awareness": {
            "moderate": "matig",
            "moderate-to-high": "matig tot hoog",
            "high": "hoog",
        },
        "posting_frequency": {
            "low": "laag",
            "low-to-moderate": "laag tot matig",
            "occasional": "af en toe",
        },
    },
    "fr": {
        "category": {
            "identity": "identite",
            "education": "education",
            "career": "carriere",
            "family": "famille",
            "location": "lieu",
        },
        "gender": {
            "M": "homme",
            "F": "femme",
            "X": "x",
        },
        "nationality": {
            "Belgian": "Belge",
        },
        "marital_status": {
            "single": "celibataire",
            "married": "marie",
            "partnered": "en couple",
            "divorced": "divorce",
            "widowed": "veuf ou veuve",
        },
        "preferred_pronouns": {
            "he/him": "il/lui",
            "she/her": "elle",
            "they/them": "iel/eux",
        },
        "pet": {
            "cat": "chat",
            "dog": "chien",
        },
        "level": {
            "Master's degree": "master",
            "Bachelor's degree": "bachelier",
            "Vocational training": "formation professionnelle",
            "Upper secondary education": "etudes secondaires superieures",
            "Secondary education": "etudes secondaires",
            "Doctoral degree": "doctorat",
        },
        "institution_type": {
            "university": "universite",
            "university college": "haute ecole",
            "secondary school": "ecole secondaire",
            "vocational school or adult training": "ecole professionnelle ou formation pour adultes",
        },
        "instruction_language": {
            "Dutch": "neerlandais",
            "French": "francais",
            "Dutch or French": "neerlandais ou francais",
            "German": "allemand",
        },
        "values": {
            "stability": "stabilite",
            "family time": "temps en famille",
            "practicality": "sens pratique",
            "learning": "apprentissage",
            "reliability": "fiabilite",
            "comfort": "confort",
            "independence": "independance",
            "fairness": "equite",
            "planning": "planification",
            "balance": "equilibre",
            "curiosity": "curiosite",
            "convenience": "praticite",
            "friendship": "amitie",
            "routine": "routine",
            "family loyalty": "loyaute familiale",
            "rest": "repos",
            "self-reliance": "autonomie",
            "loyalty": "loyaute",
            "plain speaking": "franchise",
            "community": "esprit de communaute",
            "security": "securite",
            "care": "attention aux autres",
            "patience": "patience",
            "service": "service",
            "predictability": "previsibilite",
        },
        "personality_type": {
            "organized and warm": "organise et chaleureux",
            "thoughtful and steady": "reflechi et stable",
            "pragmatic and calm": "pragmatique et calme",
            "social and organized": "sociable et organise",
            "steady and sociable": "stable et sociable",
            "straightforward and dependable": "direct et fiable",
            "reserved and steady": "reserve et stable",
            "direct and practical": "direct et pratique",
            "grounded and friendly": "ancre et amical",
            "patient and structured": "patient et structure",
            "warm and grounded": "chaleureux et ancre",
            "measured and dependable": "mesure et fiable",
        },
        "country": {
            "Belgium": "Belgique",
        },
        "favorite_vacation_destinations": {
            "Ardennes": "Ardennes",
            "Brittany": "Bretagne",
            "Tuscany": "Toscane",
            "Zeeland": "Zelande",
            "Copenhagen": "Copenhague",
            "Alsace": "Alsace",
            "Black Forest": "Foret-Noire",
            "Lake Constance": "Lac de Constance",
            "Lisbon": "Lisbonne",
            "Ghent": "Gand",
            "Valencia": "Valence",
            "Amsterdam": "Amsterdam",
            "Antwerp": "Anvers",
            "Mallorca": "Majorque",
            "Belgian coast": "cote belge",
            "Eifel": "Eifel",
            "Limburg": "Limbourg",
            "Luxembourg province": "province de Luxembourg",
            "North Sea coast": "cote de la mer du Nord",
            "Ostend": "Ostende",
            "Paris": "Paris",
            "Normandy": "Normandie",
            "Bruges": "Bruges",
            "Jura": "Jura",
        },
        "province": {
            "Brussels-Capital": "Bruxelles-Capitale",
            "East Flanders": "Flandre-Orientale",
            "West Flanders": "Flandre-Occidentale",
            "Flemish Brabant": "Brabant flamand",
            "Liege": "Liege",
        },
        "income_level": {
            "stable middle-income household": "menage stable a revenu moyen",
            "stable but budget-aware household": "menage stable mais attentif au budget",
            "carefully budgeted household": "menage au budget soigneusement gere",
            "comfortable upper-middle-income household": "menage confortable a revenu moyen superieur",
            "stable middle-income household with predictable pay": "menage stable a revenu moyen avec remuneration previsible",
            "comfortable upper-middle-income household with predictable pay": "menage confortable a revenu moyen superieur avec remuneration previsible",
            "stable middle-income household with careful planning": "menage stable a revenu moyen avec planification attentive",
            "comfortable upper-middle-income household with careful planning": "menage confortable a revenu moyen superieur avec planification attentive",
            "carefully budgeted household with close monthly planning": "menage au budget soigneusement gere avec planification mensuelle serree",
            "stable household income": "revenu du menage stable",
        },
        "preferred_payment_methods": {
            "debit card": "carte de debit",
            "credit card": "carte de credit",
            "mobile payment": "paiement mobile",
        },
        "driving_frequency": {
            "most weekdays": "la plupart des jours de semaine",
            "rare": "rare",
            "weekends and occasional errands": "les week-ends et pour quelques courses",
            "weekends and occasional school runs": "les week-ends et pour quelques trajets scolaires",
            "varies by workday": "varie selon la journee de travail",
        },
        "travel_frequency": {
            "mostly day trips and one budget-friendly holiday": "surtout des excursions d'un jour et un sejour abordable",
            "one leisure trip or a few short breaks per year": "un voyage de loisirs ou quelques courts sejours par an",
            "one or two leisure trips per year": "un ou deux voyages de loisirs par an",
            "two or three leisure trips per year": "deux ou trois voyages de loisirs par an",
        },
        "device_use": {
            "shared family planning, streaming, banking, and work communication": "planification familiale partagee, streaming, banque et communication de travail",
            "practical household coordination, media, and mobile-first browsing": "coordination pratique du foyer, medias et navigation principalement mobile",
            "connected TV use, local content, catch-up viewing, and practical family coordination": "usage de la television connectee, contenus locaux, replay et coordination familiale pratique",
            "value-conscious mobile use, messaging, catch-up TV, and one main streaming subscription": "usage mobile attentif au prix, messagerie, replay et un abonnement principal de streaming",
            "budget-conscious shopping, messaging, and one value-focused streaming subscription": "achats attentifs au budget, messagerie et un abonnement de streaming economique",
            "mobile-centric browsing, messaging, and selective streaming on a tighter budget": "navigation surtout mobile, messagerie et streaming selectif avec un budget plus serre",
            "connected-home routines, streaming, work communication, and shared family logistics": "routines de maison connectee, streaming, communication de travail et logistique familiale partagee",
            "practical household planning, work communication, public-service tools, and streaming in moderation": "planification pratique du foyer, communication de travail, outils publics et streaming modere",
            "work communication, household planning, public-service admin tools, and steady streaming habits": "communication de travail, planification du foyer, outils administratifs publics et habitudes de streaming stables",
            "messaging, household coordination, work communication, and one or two main streaming habits": "messagerie, coordination du foyer, communication de travail et une ou deux habitudes principales de streaming",
            "messaging, practical household admin, catch-up TV, and careful online shopping": "messagerie, administration pratique du foyer, replay et achats en ligne prudents",
        },
        "privacy_awareness": {
            "moderate": "moderee",
            "moderate-to-high": "moderee a elevee",
            "high": "elevee",
        },
        "posting_frequency": {
            "low": "faible",
            "low-to-moderate": "faible a moderee",
            "occasional": "occasionnelle",
        },
    },
}


class SkillError(Exception):
    """Raised when the config or generation workflow is invalid."""


def resolve_bundle_language(locale: str | None) -> str:
    if not locale:
        return "en"
    normalized = str(locale).replace("-", "_").split("_", 1)[0].strip().lower()
    if normalized in {"nl", "fr", "en"}:
        return normalized
    return "en"


def resolve_html_lang(locale: str | None) -> str:
    if not locale:
        return "en"
    normalized = str(locale).strip().replace("_", "-")
    return normalized or "en"


def get_bundle_text(locale: str | None, key: str) -> str:
    language = resolve_bundle_language(locale)
    return PERSONA_BUNDLE_UI_TEXT.get(language, PERSONA_BUNDLE_UI_TEXT["en"]).get(
        key,
        PERSONA_BUNDLE_UI_TEXT["en"][key],
    )


def format_bundle_label(key: str, locale: str | None) -> str:
    language = resolve_bundle_language(locale)
    translated = PERSONA_BUNDLE_LABELS.get(language, {}).get(key)
    if translated:
        return translated
    return key.replace("_", " ").title()


def english_indefinite_article(phrase: str) -> str:
    cleaned = re.sub(r"^[^A-Za-z]+", "", phrase or "").strip()
    if not cleaned:
        return "a"
    lowered = cleaned.lower()
    silent_h_prefixes = ("honest", "honor", "hour", "heir")
    if lowered.startswith(silent_h_prefixes):
        return "an"
    if lowered.startswith(("uni", "use", "user", "euro", "one", "once")):
        return "a"
    return "an" if lowered[0] in {"a", "e", "i", "o", "u"} else "a"


def with_english_indefinite_article(phrase: str) -> str:
    return f"{english_indefinite_article(phrase)} {phrase}"


def persona_bundle_path_is_sensitive(path: tuple[str, ...]) -> bool:
    for pattern in PERSONA_BUNDLE_SENSITIVE_PATH_PATTERNS:
        if len(path) != len(pattern):
            continue
        if all(expected == actual or expected == "*" for expected, actual in zip(pattern, path)):
            return True
    return False


def sanitize_persona_bundle_value(value, *, path: tuple[str, ...], include_sensitive_fields: bool):
    if not include_sensitive_fields and persona_bundle_path_is_sensitive(path):
        return MISSING
    if value is None:
        return MISSING
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            cleaned = sanitize_persona_bundle_value(
                item,
                path=path + (key,),
                include_sensitive_fields=include_sensitive_fields,
            )
            if cleaned is not MISSING:
                sanitized[key] = cleaned
        return sanitized or MISSING
    if isinstance(value, list):
        sanitized = []
        for item in value:
            cleaned = sanitize_persona_bundle_value(
                item,
                path=path + ("*",),
                include_sensitive_fields=include_sensitive_fields,
            )
            if cleaned is not MISSING:
                sanitized.append(cleaned)
        return sanitized or MISSING
    return value


def sanitize_persona_bundle_row(row: dict, *, include_sensitive_fields: bool) -> dict:
    sanitized = sanitize_persona_bundle_value(
        row,
        path=(),
        include_sensitive_fields=include_sensitive_fields,
    )
    if sanitized is MISSING:
        return {}
    return sanitized


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SkillError(f"Config file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SkillError(f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}") from exc


def load_custom_formats(path: Path = DEFAULT_CUSTOM_FORMATS_PATH) -> dict:
    if not path.exists():
        return {}

    data = load_json(path)
    formats = data.get("formats", {})
    if not isinstance(formats, dict):
        raise SkillError(f"Expected 'formats' to be an object in {path}")
    return formats


def load_open_data_sources(path: Path = DEFAULT_OPEN_DATA_SOURCES_PATH) -> dict:
    data = load_json(path)
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        raise SkillError(f"Expected 'sources' to be an array in {path}")
    return data


def load_persona_catalogs(path: Path = DEFAULT_PERSONA_CATALOGS_PATH) -> dict:
    data = load_json(path)
    catalogs = data.get("catalogs", {})
    if not isinstance(catalogs, dict):
        raise SkillError(f"Expected 'catalogs' to be an object in {path}")
    return data


def load_persona_profile_bundles(path: Path = DEFAULT_PERSONA_PROFILE_BUNDLES_PATH) -> dict:
    data = load_json(path)
    bundles = data.get("bundles", {})
    if not isinstance(bundles, dict):
        raise SkillError(f"Expected 'bundles' to be an object in {path}")
    return data


def load_persona_archetypes(path: Path = DEFAULT_PERSONA_ARCHETYPES_PATH) -> dict:
    data = load_json(path)
    archetypes = data.get("archetypes", {})
    if not isinstance(archetypes, dict):
        raise SkillError(f"Expected 'archetypes' to be an object in {path}")
    return data


def load_belgian_address_catalog(path: Path = DEFAULT_BELGIAN_ADDRESS_CATALOG_PATH) -> list[dict]:
    data = load_json(path)
    addresses = data.get("addresses", [])
    if not isinstance(addresses, list) or not addresses:
        raise SkillError(f"Expected 'addresses' to be a non-empty array in {path}")
    required_keys = {"region", "province", "postcode", "city", "street_address"}
    for index, address in enumerate(addresses, start=1):
        if not isinstance(address, dict):
            raise SkillError(f"Address catalog entry {index} in {path} must be an object.")
        missing = sorted(required_keys - set(address))
        if missing:
            raise SkillError(f"Address catalog entry {index} in {path} is missing keys: {', '.join(missing)}.")
    return addresses


def load_belgian_bank_catalog(path: Path = DEFAULT_BELGIAN_BANK_CATALOG_PATH) -> list[dict]:
    data = load_json(path)
    banks = data.get("banks", [])
    if not isinstance(banks, list) or not banks:
        raise SkillError(f"Expected 'banks' to be a non-empty array in {path}")
    required_keys = {"bank_name", "bank_code", "swift_bic"}
    for index, bank in enumerate(banks, start=1):
        if not isinstance(bank, dict):
            raise SkillError(f"Bank catalog entry {index} in {path} must be an object.")
        missing = sorted(required_keys - set(bank))
        if missing:
            raise SkillError(f"Bank catalog entry {index} in {path} is missing keys: {', '.join(missing)}.")
    return banks


def split_sql_definitions(definition_block: str) -> list[str]:
    parts = []
    current = []
    depth = 0
    for char in definition_block:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                parts.append(item)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def normalize_identifier(raw_name: str) -> str:
    name = raw_name.strip()
    if (name.startswith('"') and name.endswith('"')) or (name.startswith("`") and name.endswith("`")):
        return name[1:-1]
    if name.startswith("[") and name.endswith("]"):
        return name[1:-1]
    return name


def parse_sql_type(definition_tail: str) -> str:
    tokens = []
    current = []
    depth = 0
    for raw_token in definition_tail.split():
        lower_token = raw_token.lower()
        depth += raw_token.count("(")
        depth -= raw_token.count(")")
        if depth <= 0 and lower_token in SQL_CONSTRAINT_KEYWORDS:
            break
        tokens.append(raw_token)
    sql_type = " ".join(tokens).strip()
    if not sql_type:
        raise SkillError(f"Could not infer SQL column type from definition: {definition_tail!r}")
    return sql_type


def parse_create_table_ddl(ddl: str) -> dict:
    if not isinstance(ddl, str) or not ddl.strip():
        raise SkillError("'sql_schema.ddl' must be a non-empty string.")
    match = re.search(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?P<table>[^\s(]+)\s*\((?P<body>.*)\)\s*;?\s*$",
        ddl.strip(),
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise SkillError("Only simple CREATE TABLE statements are supported in 'sql_schema.ddl'.")

    raw_table_name = match.group("table")
    body = match.group("body")
    columns = []
    for definition in split_sql_definitions(body):
        stripped = definition.strip()
        if not stripped:
            continue
        leading = stripped.split(None, 1)[0].lower()
        if leading in {"primary", "foreign", "unique", "constraint", "check"}:
            continue

        column_match = re.match(r'(?P<name>"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][\w$]*)\s+(?P<tail>.+)$', stripped, re.DOTALL)
        if not column_match:
            raise SkillError(f"Unsupported column definition in SQL schema: {definition!r}")

        column_name = normalize_identifier(column_match.group("name"))
        sql_type = parse_sql_type(column_match.group("tail"))
        columns.append({"name": column_name, "sql_type": sql_type})

    if not columns:
        raise SkillError("The provided CREATE TABLE statement does not contain any supported column definitions.")

    return {
        "table_name": normalize_identifier(raw_table_name.split(".")[-1]),
        "columns": columns,
    }


def infer_field_from_sql_column(column_name: str, sql_type: str, *, locale: str) -> dict:
    normalized_name = column_name.lower()
    normalized_type = sql_type.lower()

    if normalized_name in {"first_name", "firstname", "given_name"}:
        return {"name": column_name, "type": "first_name", "params": {}}
    if normalized_name in {"last_name", "lastname", "family_name", "surname"}:
        return {"name": column_name, "type": "last_name", "params": {}}
    if normalized_name in {"full_name", "name"}:
        return {"name": column_name, "type": "name", "params": {}}
    if "email" in normalized_name:
        return {"name": column_name, "type": "email", "params": {}}
    if normalized_name in {"city", "town"}:
        return {"name": column_name, "type": "city", "params": {}}
    if "street" in normalized_name or "address" in normalized_name:
        return {"name": column_name, "type": "street_address", "params": {}}
    if "postcode" in normalized_name or "postal_code" in normalized_name or "zip" in normalized_name:
        field_type = "belgian_postal_code" if locale.endswith("_BE") else "postcode"
        return {"name": column_name, "type": field_type, "params": {}}
    if "mobile" in normalized_name:
        field_type = "belgian_mobile_phone" if locale.endswith("_BE") else "phone_number"
        return {"name": column_name, "type": field_type, "params": {}}
    if "phone" in normalized_name:
        return {"name": column_name, "type": "phone_number", "params": {}}
    if normalized_name == "iban":
        return {"name": column_name, "type": "iban", "params": {}}
    if "insz" in normalized_name:
        return {"name": column_name, "type": "belgian_insz", "params": {}}
    if "eid" in normalized_name:
        return {"name": column_name, "type": "belgian_eid", "params": {}}
    if "license_plate" in normalized_name or "licence_plate" in normalized_name:
        field_type = "belgian_license_plate" if locale.endswith("_BE") else "license_plate"
        return {"name": column_name, "type": field_type, "params": {}}
    if any(token in normalized_type for token in {"date", "time"}):
        return {"name": column_name, "type": "date_between", "params": {}}
    if normalized_name in {"birth_date", "date_of_birth"}:
        return {"name": column_name, "type": "date_between", "params": {"start_date": "-90y", "end_date": "-18y"}}
    if "date" in normalized_name or "timestamp" in normalized_name:
        return {"name": column_name, "type": "date_between", "params": {}}
    if normalized_name.startswith("is_") or normalized_type == "boolean":
        return {"name": column_name, "type": "choice", "params": {"values": [True, False]}}
    if any(token in normalized_type for token in {"int", "serial"}):
        return {"name": column_name, "type": "number_int", "params": {"min": 1, "max": 1000000}}
    if any(token in normalized_type for token in {"numeric", "decimal", "real", "double", "float"}):
        return {"name": column_name, "type": "number_float", "params": {"min": 0, "max": 100000, "precision": 2}}
    return {"name": column_name, "type": "word", "params": {}}


def normalize_sql_schema(raw_sql_schema, *, locale: str) -> dict | None:
    if raw_sql_schema is None:
        return None
    if not isinstance(raw_sql_schema, dict):
        raise SkillError("'sql_schema' must be an object when provided.")

    ddl = raw_sql_schema.get("ddl")
    ddl_path = raw_sql_schema.get("ddl_path")
    if ddl is None and ddl_path is None:
        raise SkillError("'sql_schema' requires either 'ddl' or 'ddl_path'.")
    if ddl is not None and ddl_path is not None:
        raise SkillError("'sql_schema' must not define both 'ddl' and 'ddl_path' at the same time.")
    if ddl_path is not None:
        try:
            ddl = Path(ddl_path).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SkillError(f"SQL schema file not found: {ddl_path}") from exc

    parsed = parse_create_table_ddl(ddl)
    return {
        "table_name": parsed["table_name"],
        "columns": parsed["columns"],
        "derived_fields": [infer_field_from_sql_column(column["name"], column["sql_type"], locale=locale) for column in parsed["columns"]],
    }


def is_scalar(value) -> bool:
    return isinstance(value, (str, int, float, bool)) and not isinstance(value, complex)


def unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def slugify_text(value: str) -> str:
    normalized = str(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", "", normalized)
    return normalized


def flatten_context(prefix: str, value, target: dict) -> None:
    if not prefix:
        return
    target[prefix] = value
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            if isinstance(child_key, str) and child_key:
                flatten_context(f"{prefix}.{child_key}", child_value, target)


def build_template_context(row_context: dict | None) -> dict:
    context = {}
    if not row_context:
        return context
    current = row_context.get("__current__", {})
    root = row_context.get("__root__", {})
    if isinstance(current, dict):
        for key, value in current.items():
            if isinstance(key, str) and key:
                flatten_context(key, value, context)
    if isinstance(root, dict):
        for key, value in root.items():
            if isinstance(key, str) and key and key not in context:
                flatten_context(key, value, context)
    return context


def resolve_row_locale(row_context: dict | None, *, default: str = "en_US") -> str:
    if not isinstance(row_context, dict):
        return default
    locale_value = row_context.get("__locale__")
    if isinstance(locale_value, str) and locale_value.strip():
        return locale_value.strip()
    return default


def locale_family(locale: str | None) -> str:
    normalized = str(locale or "").strip().lower()
    if normalized.startswith("nl"):
        return "nl"
    if normalized.startswith("fr"):
        return "fr"
    return "en"


NARRATIVE_LOCALIZATION = {
    "nl": {
        "profession": {
            "designer": "ontwerper",
            "productdesigner": "productontwerper",
            "officeclerk": "administratief medewerker",
            "storesalesperson": "winkelmedewerker",
            "homecarecleaner": "poetshulp aan huis",
            "facilitycleaner": "schoonmaker",
            "secondaryschoolteacher": "leraar secundair onderwijs",
            "primaryschoolteacher": "leraar lager onderwijs",
            "practicalnurse": "zorgkundige",
            "registerednurse": "verpleegkundige",
            "stockclerk": "voorraadmedewerker",
            "careassistant": "zorgassistent",
            "warehousehandler": "magazijnmedewerker",
            "socialworker": "maatschappelijk werker",
            "businessanalyst": "businessanalist",
            "salesmanager": "salesmanager",
            "accountant": "accountant",
            "truckdriver": "vrachtwagenchauffeur",
            "waiter": "ober",
            "systemsanalyst": "systeemanalist",
            "bookkeeper": "boekhouder",
            "softwaredeveloper": "softwareontwikkelaar",
            "officesupervisor": "teamleider administratie",
            "childcareworker": "kinderbegeleider",
            "accountingtechnician": "boekhoudkundig medewerker",
            "constructionworker": "bouwvakker",
            "salesrepresentative": "vertegenwoordiger",
            "cashier": "kassamedewerker",
            "generalmanager": "algemeen directeur",
            "financialservicesclerk": "medewerker financiele diensten",
            "industrialmachinerymechanic": "industrieel onderhoudsmecanicien",
            "buildingelectrician": "elektricien",
        },
        "industry": {
            "businessservices": "zakelijke dienstverlening",
            "retail": "detailhandel",
            "homeservices": "huishoudelijke diensten",
            "facilitiesandhospitality": "facilitaire diensten en hospitality",
            "education": "onderwijs",
            "healthcare": "gezondheidszorg",
            "logistics": "logistiek",
            "socialservices": "sociale dienstverlening",
            "professionalservices": "professionele dienstverlening",
            "wholesaleandretail": "groothandel en detailhandel",
            "finance": "financien",
            "transportandlogistics": "transport en logistiek",
            "hospitality": "horeca",
            "informationtechnology": "informatietechnologie",
            "childcare": "kinderopvang",
            "construction": "bouw",
            "wholesaleanddistribution": "groothandel en distributie",
            "generalmanagement": "algemeen management",
            "manufacturing": "maakindustrie",
            "creativeandmedia": "creatieve sector en media",
            "legalservices": "juridische dienstverlening",
            "engineeringandtechnology": "engineering en technologie",
            "salesandmarketing": "sales en marketing",
        },
        "education": {
            "mastersdegree": "masteropleiding",
            "bachelorsdegree": "bacheloropleiding",
            "vocationaltraining": "beroepsopleiding",
            "uppersecondaryeducation": "opleiding in het secundair onderwijs",
            "secondaryeducation": "secundair onderwijs",
            "doctoraldegree": "doctoraatsopleiding",
            "phd": "doctoraat",
        },
        "hobby": {
            "cycling": "fietsen",
            "homecooking": "thuis koken",
            "podcasts": "podcasts",
            "weekendrunning": "weekend hardlopen",
            "museumvisits": "museumbezoeken",
            "recipeexperimenting": "experimenteren met recepten",
            "hiking": "wandelen",
            "diyprojects": "doe-het-zelfprojecten",
            "radioshows": "radioprogramma's",
            "padel": "padel",
            "weekendcitytrips": "stedentrips in het weekend",
            "foodpodcasts": "foodpodcasts",
            "fitnessclasses": "fitnesslessen",
            "boardgames": "bordspellen",
            "brunchwithfriends": "brunchen met vrienden",
            "localfootball": "lokaal voetbal",
            "barbecuing": "barbecueen",
            "recreationalcycling": "recreatief fietsen",
            "gardening": "tuinieren",
            "angling": "hengelsport",
            "motocrossontv": "motocross op tv",
            "smallrepairs": "kleine herstellingen",
            "terraceevenings": "avonden op het terras",
            "darts": "darts",
            "weekendmarkets": "weekendmarkten",
            "choir": "koor",
            "bookclub": "leesclub",
            "walkingclubs": "wandelclubs",
            "baking": "bakken",
            "communityevents": "activiteiten in de buurt",
            "amateurtheatre": "amateurtheater",
            "libraryvisits": "bibliotheekbezoeken",
            "choosingfamilyoutings": "gezinsuitstappen plannen",
        },
    },
    "fr": {
        "profession": {
            "designer": "designer",
            "productdesigner": "designer produit",
            "officeclerk": "employe administratif",
            "storesalesperson": "vendeur en magasin",
            "homecarecleaner": "aide-menagere a domicile",
            "facilitycleaner": "agent d'entretien",
            "secondaryschoolteacher": "enseignant du secondaire",
            "primaryschoolteacher": "instituteur primaire",
            "practicalnurse": "aide-soignant",
            "registerednurse": "infirmier",
            "stockclerk": "magasinier",
            "careassistant": "assistant de soins",
            "warehousehandler": "manutentionnaire d'entrepot",
            "socialworker": "assistant social",
            "businessanalyst": "analyste d'affaires",
            "salesmanager": "responsable commercial",
            "accountant": "comptable",
            "truckdriver": "chauffeur routier",
            "waiter": "serveur",
            "systemsanalyst": "analyste systemes",
            "bookkeeper": "comptable",
            "softwaredeveloper": "developpeur logiciel",
            "officesupervisor": "superviseur administratif",
            "childcareworker": "auxiliaire de petite enfance",
            "accountingtechnician": "technicien comptable",
            "constructionworker": "ouvrier du batiment",
            "salesrepresentative": "representant commercial",
            "cashier": "caissier",
            "generalmanager": "directeur general",
            "financialservicesclerk": "agent des services financiers",
            "industrialmachinerymechanic": "mecanicien en machines industrielles",
            "buildingelectrician": "electricien du batiment",
        },
        "industry": {
            "businessservices": "services aux entreprises",
            "retail": "commerce de detail",
            "homeservices": "services a domicile",
            "facilitiesandhospitality": "services aux batiments et hospitalite",
            "education": "enseignement",
            "healthcare": "sante",
            "logistics": "logistique",
            "socialservices": "services sociaux",
            "professionalservices": "services professionnels",
            "wholesaleandretail": "commerce de gros et de detail",
            "finance": "finance",
            "transportandlogistics": "transport et logistique",
            "hospitality": "horeca",
            "informationtechnology": "technologies de l'information",
            "childcare": "petite enfance",
            "construction": "construction",
            "wholesaleanddistribution": "commerce de gros et distribution",
            "generalmanagement": "direction generale",
            "manufacturing": "industrie manufacturiere",
            "creativeandmedia": "creation et medias",
            "legalservices": "services juridiques",
            "engineeringandtechnology": "ingenierie et technologie",
            "salesandmarketing": "vente et marketing",
        },
        "education": {
            "mastersdegree": "un master",
            "bachelorsdegree": "un bachelier",
            "vocationaltraining": "une formation professionnelle",
            "uppersecondaryeducation": "des etudes secondaires superieures",
            "secondaryeducation": "des etudes secondaires",
            "doctoraldegree": "un doctorat",
            "phd": "un doctorat",
        },
        "hobby": {
            "cycling": "cyclisme",
            "homecooking": "cuisine maison",
            "podcasts": "podcasts",
            "weekendrunning": "course a pied le week-end",
            "museumvisits": "visites de musees",
            "recipeexperimenting": "experimentation culinaire",
            "hiking": "randonnee",
            "diyprojects": "bricolage",
            "radioshows": "emissions de radio",
            "padel": "padel",
            "weekendcitytrips": "escapades urbaines le week-end",
            "foodpodcasts": "podcasts culinaires",
            "fitnessclasses": "cours de fitness",
            "boardgames": "jeux de societe",
            "brunchwithfriends": "brunch entre amis",
            "localfootball": "football local",
            "barbecuing": "barbecues",
            "recreationalcycling": "cyclisme de loisir",
            "gardening": "jardinage",
            "angling": "peche",
            "motocrossontv": "motocross a la television",
            "smallrepairs": "petites reparations",
            "terraceevenings": "soirees en terrasse",
            "darts": "flechettes",
            "weekendmarkets": "marches du week-end",
            "choir": "chorale",
            "bookclub": "club de lecture",
            "walkingclubs": "clubs de marche",
            "baking": "patisserie",
            "communityevents": "evenements de quartier",
            "amateurtheatre": "theatre amateur",
            "libraryvisits": "visites a la bibliotheque",
            "choosingfamilyoutings": "planification des sorties en famille",
        },
    },
}


def localize_narrative_term(value, *, locale_kind: str, category: str):
    if locale_kind == "en":
        return value
    if not isinstance(value, str):
        return value
    localized_values = NARRATIVE_LOCALIZATION.get(locale_kind, {}).get(category, {})
    return localized_values.get(slugify_text(value.strip()), value)


def format_narrative_list(value, *, locale_kind: str, category: str | None = None) -> str | None:
    conjunction_map = {"en": "and", "nl": "en", "fr": "et"}
    conjunction = conjunction_map.get(locale_kind, "and")
    oxford_comma = locale_kind == "en"
    if isinstance(value, list):
        cleaned = []
        for item in value:
            item_text = str(item).strip()
            if not item_text:
                continue
            if category:
                item_text = localize_narrative_term(item_text, locale_kind=locale_kind, category=category)
            cleaned.append(str(item_text))
        if not cleaned:
            return None
        if len(cleaned) == 1:
            return cleaned[0]
        if len(cleaned) == 2:
            return f"{cleaned[0]} {conjunction} {cleaned[1]}"
        separator = f", {conjunction} " if oxford_comma else f" {conjunction} "
        return ", ".join(cleaned[:-1]) + separator + cleaned[-1]
    if isinstance(value, str) and value.strip():
        localized_value = (
            localize_narrative_term(value.strip(), locale_kind=locale_kind, category=category)
            if category
            else value.strip()
        )
        return str(localized_value)
    return None


def get_generation_state(row_context: dict | None) -> dict:
    if row_context is None:
        return {}
    state = row_context.get("__state__")
    if state is None:
        state = {}
        row_context["__state__"] = state
    return state


def resolve_context_value(row_context: dict | None, key: str, *, field_name: str, purpose: str):
    context = build_template_context(row_context)
    if key not in context:
        raise SkillError(f"Field {field_name!r} could not resolve {purpose} from unknown key {key!r}.")
    return context[key]


TEMPLATE_TOKEN_PATTERN = re.compile(r"\{([^{}]+)\}")


def render_template_string(template: str, context: dict, *, field_name: str) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1).strip()
        if key not in context:
            raise SkillError(f"Field {field_name!r} template references unknown key {key!r}.")
        return str(context[key])

    return TEMPLATE_TOKEN_PATTERN.sub(replace, template)


def education_timeline_defaults(education_level: str | None) -> tuple[int, int, str] | None:
    if not education_level:
        return None
    normalized = education_level.strip().lower()
    if "phd" in normalized or "doctor" in normalized:
        return (18, 30, "Completed doctoral studies")
    if "master" in normalized:
        return (18, 24, "Completed a master's degree")
    if "bachelor" in normalized:
        return (18, 22, "Completed a bachelor's degree")
    if "secondary" in normalized or "high school" in normalized:
        return (12, 18, "Completed secondary education")
    if "vocational" in normalized:
        return (16, 20, "Completed vocational training")
    return None


def normalize_belgian_region_label(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().upper()
    aliases = {
        "VLG": "VLG",
        "FLANDERS": "VLG",
        "FLEMISH": "VLG",
        "WAL": "WAL",
        "WALLONIA": "WAL",
        "BXL": "BXL",
        "BRUSSELS": "BXL",
        "BRUSSELS-CAPITAL": "BXL",
    }
    return aliases.get(normalized, normalized if normalized in {"VLG", "WAL", "BXL"} else None)


def build_belgian_language_profile(*, row_context: dict | None, params: dict, field_name: str) -> list[str]:
    region_value = None
    if params.get("region_field"):
        value = get_context_value_or_missing(row_context, params["region_field"])
        if value is not MISSING:
            region_value = value

    city_value = None
    if params.get("city_field"):
        value = get_context_value_or_missing(row_context, params["city_field"])
        if value is not MISSING:
            city_value = value

    region = normalize_belgian_region_label(region_value if isinstance(region_value, str) else None)
    city = str(city_value).strip().lower() if isinstance(city_value, str) else ""

    if city in {"brussel", "bruxelles", "anderlecht", "etterbeek", "ukkel", "uccle", "elsene", "ixelles", "schaarbeek", "schaerbeek", "sint-gillis"} or region == "BXL":
        return ["French", "Dutch", "English"]
    if region == "WAL":
        return ["French", "English"]
    return ["Dutch", "French", "English"]


def build_belgian_education_profile(*, row_context: dict | None, params: dict, field_name: str) -> dict:
    age_value = resolve_context_value(
        row_context,
        params["age_field"],
        field_name=field_name,
        purpose="age",
    )
    if not isinstance(age_value, int) or isinstance(age_value, bool) or age_value < 0:
        raise SkillError(f"Field {field_name!r} expected a non-negative integer age, received {age_value!r}.")

    region_value = None
    if params.get("region_field"):
        value = get_context_value_or_missing(row_context, params["region_field"])
        if value is not MISSING:
            region_value = value
    region = normalize_belgian_region_label(region_value if isinstance(region_value, str) else None)

    profession_value = None
    if params.get("profession_field"):
        value = get_context_value_or_missing(row_context, params["profession_field"])
        if value is not MISSING:
            profession_value = value
    normalized_profession = str(profession_value).strip().lower() if isinstance(profession_value, str) else ""

    vocational_keywords = {
        "bricklayer",
        "carpenter",
        "cashier",
        "cleaner",
        "cook",
        "driver",
        "electrician",
        "handler",
        "kitchen",
        "mechanic",
        "plumber",
        "roofer",
        "server",
        "stock",
        "warehouse",
        "waiter",
    }
    secondary_keywords = {
        "assistant",
        "childcare worker",
        "clerk",
        "home care",
        "salesperson",
        "secretary",
        "service clerk",
        "store",
        "taxi",
    }
    bachelor_keywords = {
        "accountant",
        "bookkeeper",
        "childcare educator",
        "nurse",
        "primary school teacher",
        "practical nurse",
        "social worker",
        "teacher",
    }
    master_keywords = {
        "analyst",
        "developer",
        "director",
        "general manager",
        "manager",
        "physician",
        "professor",
        "software",
        "specialist",
        "systems",
    }

    if any(keyword in normalized_profession for keyword in vocational_keywords):
        level = "Vocational training"
        institution_type = "vocational school or adult training"
    elif any(keyword in normalized_profession for keyword in secondary_keywords):
        level = "Upper secondary education"
        institution_type = "secondary school"
    elif any(keyword in normalized_profession for keyword in master_keywords):
        level = "Master's degree"
        institution_type = "university"
    elif any(keyword in normalized_profession for keyword in bachelor_keywords):
        level = "Bachelor's degree"
        institution_type = "university college"
    elif age_value < 23:
        level = "Bachelor's degree"
        institution_type = "university college"
    elif age_value < 30:
        level = "Master's degree"
        institution_type = "university"
    elif age_value < 55:
        level = "Master's degree"
        institution_type = "university"
    else:
        level = "Bachelor's degree"
        institution_type = "university college"

    if region == "WAL":
        instruction_language = "French"
    elif region == "BXL":
        instruction_language = "Dutch or French"
    else:
        instruction_language = "Dutch"

    return {
        "level": level,
        "institution_type": institution_type,
        "instruction_language": instruction_language,
    }


def build_life_timeline(
    rng: random.Random,
    *,
    row_context: dict | None,
    params: dict,
    field_name: str,
) -> list[dict]:
    birth_date_value = resolve_context_value(
        row_context,
        params["birth_date_field"],
        field_name=field_name,
        purpose="birth date",
    )
    if not isinstance(birth_date_value, str):
        raise SkillError(f"Field {field_name!r} expected a string ISO birth date, received {birth_date_value!r}.")

    birth_date = parse_iso_date(birth_date_value, field_label=f"Field {field_name!r} source birth date")
    reference_date = parse_iso_date(
        params.get("reference_date", date.today().isoformat()),
        field_label=f"Field {field_name!r} params.reference_date",
    )
    if reference_date < birth_date:
        raise SkillError(f"Field {field_name!r} received a reference date earlier than the birth date.")

    row_locale = resolve_row_locale(row_context)
    locale_kind = locale_family(row_locale)

    full_name = None
    if params.get("full_name_field"):
        full_name = get_context_value_or_missing(row_context, params["full_name_field"])
        if full_name is MISSING:
            full_name = None

    subject = (
        str(full_name)
        if full_name
        else {"nl": "Het profiel", "fr": "Le profil"}.get(locale_kind, "The persona")
    )

    def event(event_date: date, category: str, title: str, description: str) -> dict:
        return {
            "date": event_date.isoformat(),
            "category": category,
            "title": title,
            "description": description,
        }

    timeline = [
        event(
            birth_date,
            "identity",
            "Birth",
            (
                f"{subject} werd geboren op {birth_date.isoformat()}."
                if locale_kind == "nl"
                else f"{subject} est ne le {birth_date.isoformat()}."
                if locale_kind == "fr"
                else f"{subject} was born on {birth_date.isoformat()}."
            ),
        )
    ]

    age = reference_date.year - birth_date.year - (
        (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day)
    )

    secondary_completion_date = None
    if age >= 18:
        secondary_completion_date = shift_years_safe(birth_date, 18)
        timeline.append(
            event(
                secondary_completion_date,
                "education",
                "Completed secondary education",
                (
                    f"{subject} voltooide het secundair onderwijs en begon zich voor te bereiden op een zelfstandiger volwassen leven."
                    if locale_kind == "nl"
                    else f"{subject} a termine l'enseignement secondaire et a commence a se preparer a une vie adulte plus autonome."
                    if locale_kind == "fr"
                    else f"{subject} completed secondary education and started preparing for a more independent adult path."
                ),
            )
        )

    education_level = None
    if params.get("education_level_field"):
        education_level = get_context_value_or_missing(row_context, params["education_level_field"])
        if education_level is MISSING:
            education_level = None
    localized_education_level = localize_narrative_term(education_level, locale_kind=locale_kind, category="education")
    education_defaults = education_timeline_defaults(education_level if isinstance(education_level, str) else None)
    career_start_date = None
    education_end_date = None

    if education_defaults is not None and age >= education_defaults[1]:
        start_age, end_age, title = education_defaults
        if start_age >= 18:
            education_start_date = shift_years_safe(birth_date, start_age)
            timeline.append(
                event(
                    education_start_date,
                    "education",
                    "Started higher education or training",
                    (
                        f"{subject} begon rond de leeftijd van {start_age} aan een meer gespecialiseerde opleiding of training."
                        if locale_kind == "nl"
                        else f"{subject} a entame vers l'age de {start_age} une formation ou un parcours plus specialise."
                        if locale_kind == "fr"
                        else f"{subject} began a more specialized education path around age {start_age}."
                    ),
                )
            )
        education_end_date = shift_years_safe(birth_date, end_age)
        timeline.append(
            event(
                education_end_date,
                "education",
                title,
                (
                    f"{subject} bereikte rond de leeftijd van {end_age} het niveau van {localized_education_level}."
                    if locale_kind == "nl"
                    else f"{subject} a atteint vers l'age de {end_age} le niveau de {localized_education_level}."
                    if locale_kind == "fr"
                    else f"{subject} reached the {education_level} milestone around age {end_age}."
                ),
            )
        )
        career_start_date = shift_years_safe(birth_date, end_age)

    profession = None
    if params.get("profession_field"):
        profession = get_context_value_or_missing(row_context, params["profession_field"])
        if profession is MISSING:
            profession = None
    localized_profession = localize_narrative_term(profession, locale_kind=locale_kind, category="profession")
    company = None
    if params.get("company_field"):
        company = get_context_value_or_missing(row_context, params["company_field"])
        if company is MISSING:
            company = None

    if profession:
        if career_start_date is None:
            start_age = min(max(age - 8, 18), max(age - 1, 18))
            career_start_date = shift_years_safe(birth_date, start_age)
        timeline.append(
            event(
                career_start_date,
                "career",
                "Career start",
                (
                    f"{subject} stapte het beroepsleven in als {localized_profession}."
                    if locale_kind == "nl"
                    else f"{subject} est entre dans la vie professionnelle comme {localized_profession}."
                    if locale_kind == "fr"
                    else f"{subject} entered professional work in {profession}."
                ),
            )
        )

        current_role_min = max(career_start_date, shift_years_safe(reference_date, -8))
        current_role_max = max(current_role_min, shift_years_safe(reference_date, -1))
        current_role_date = random_date_between(rng, current_role_min, current_role_max)
        if (current_role_date - career_start_date).days >= 365 * 4:
            promotion_min = career_start_date + timedelta(days=365 * 2)
            promotion_max = current_role_date - timedelta(days=365)
            if promotion_min <= promotion_max:
                promotion_date = random_date_between(rng, promotion_min, promotion_max)
                timeline.append(
                    event(
                        promotion_date,
                        "career",
                        "Expanded responsibilities",
                        (
                            f"{subject} groeide door naar een bredere verantwoordelijkheid naarmate ervaring en vertrouwen toenamen."
                            if locale_kind == "nl"
                            else f"{subject} a evolue vers un champ de responsabilites plus large a mesure que l'experience et la confiance augmentaient."
                            if locale_kind == "fr"
                            else f"{subject} moved into a broader scope of work as experience and trust accumulated."
                        ),
                    )
                )
        if locale_kind == "nl":
            company_fragment = f" bij {company}" if company else ""
        elif locale_kind == "fr":
            company_fragment = f" chez {company}" if company else ""
        else:
            company_fragment = f" at {company}" if company else ""
        timeline.append(
            event(
                current_role_date,
                "career",
                "Current role",
                (
                    f"{subject} nam de huidige rol als {localized_profession} op{company_fragment}."
                    if locale_kind == "nl"
                    else f"{subject} a pris la fonction actuelle de {localized_profession}{company_fragment}."
                    if locale_kind == "fr"
                    else f"{subject} moved into the current {profession} role{company_fragment}."
                ),
            )
        )

    marital_status = None
    if params.get("marital_status_field"):
        marital_status = get_context_value_or_missing(row_context, params["marital_status_field"])
        if marital_status is MISSING:
            marital_status = None
    spouse = None
    if params.get("spouse_field"):
        spouse = get_context_value_or_missing(row_context, params["spouse_field"])
        if spouse is MISSING:
            spouse = None

    children = None
    if params.get("children_field"):
        children = get_context_value_or_missing(row_context, params["children_field"])
        if children is MISSING:
            children = None
    child_birth_dates = []
    if isinstance(children, list):
        for child in children:
            if not isinstance(child, dict):
                continue
            child_birth_date = child.get("birth_date")
            if not isinstance(child_birth_date, str):
                continue
            child_name = child.get("full_name", "a child")
            parsed_child_birth_date = parse_iso_date(child_birth_date, field_label=f"Field {field_name!r} child birth date")
            child_birth_dates.append(parsed_child_birth_date)
            timeline.append(
                event(
                    parsed_child_birth_date,
                    "family",
                    "Child born",
                    (
                        f"{subject} verwelkomde {child_name} in het huishouden."
                        if locale_kind == "nl"
                        else f"{subject} a accueilli {child_name} dans le foyer."
                        if locale_kind == "fr"
                        else f"{subject} welcomed {child_name} into the household."
                    ),
                )
            )

    marriage_date = None
    if marital_status in {"married", "partnered"}:
        min_marriage_date = shift_years_safe(birth_date, 22)
        if education_end_date is not None:
            min_marriage_date = max(min_marriage_date, education_end_date)
        if career_start_date is not None:
            min_marriage_date = max(min_marriage_date, career_start_date)

        max_marriage_date = shift_years_safe(reference_date, -1)
        if child_birth_dates:
            max_marriage_date = min(max_marriage_date, min(child_birth_dates) - timedelta(days=30))

        if min_marriage_date <= max_marriage_date:
            marriage_date = random_date_between(rng, min_marriage_date, max_marriage_date)
            spouse_name = spouse.get("full_name") if isinstance(spouse, dict) else None
            if locale_kind == "nl":
                spouse_fragment = f" met {spouse_name}" if spouse_name else ""
            elif locale_kind == "fr":
                spouse_fragment = f" avec {spouse_name}" if spouse_name else ""
            else:
                spouse_fragment = f" with {spouse_name}" if spouse_name else ""
            timeline.append(
                event(
                    marriage_date,
                    "family",
                    "Marriage or long-term partnership",
                    (
                        f"{subject} formaliseerde een duurzame partnerrelatie{spouse_fragment}."
                        if locale_kind == "nl"
                        else f"{subject} a officialise une relation durable{spouse_fragment}."
                        if locale_kind == "fr"
                        else f"{subject} formalized a long-term partnership{spouse_fragment}."
                    ),
                )
            )

    independent_household_date = None
    if age >= 22:
        household_min = shift_years_safe(birth_date, 20)
        if education_end_date is not None:
            household_min = max(household_min, education_end_date)
        household_max = shift_years_safe(reference_date, -3)
        if marriage_date is not None:
            household_max = min(household_max, marriage_date)
        if child_birth_dates:
            household_max = min(household_max, min(child_birth_dates) - timedelta(days=120))
        if household_min <= household_max:
            independent_household_date = random_date_between(rng, household_min, household_max)
            timeline.append(
                event(
                    independent_household_date,
                    "family",
                    "Established an independent household",
                    (
                        f"{subject} bouwde een meer zelfstandige huishoudroutine en langdurigere verantwoordelijkheden op."
                        if locale_kind == "nl"
                        else f"{subject} a construit un rythme de foyer plus autonome et des responsabilites plus durables."
                        if locale_kind == "fr"
                        else f"{subject} settled into a more self-directed household rhythm and longer-term responsibilities."
                    ),
                )
            )

    city = None
    if params.get("city_field"):
        city = get_context_value_or_missing(row_context, params["city_field"])
        if city is MISSING:
            city = None
    if isinstance(city, str) and city.strip() and age >= 20:
        move_start = career_start_date or independent_household_date or shift_years_safe(birth_date, 18)
        move_min = max(move_start, shift_years_safe(reference_date, -12))
        move_max = max(move_min, shift_years_safe(reference_date, -1))
        move_date = random_date_between(rng, move_min, move_max)
        timeline.append(
            event(
                move_date,
                "location",
                "Settled in current city",
                (
                    f"{subject} bouwde het dagelijkse leven uit in {city}."
                    if locale_kind == "nl"
                    else f"{subject} a etabli son quotidien a {city}."
                    if locale_kind == "fr"
                    else f"{subject} established daily life in {city}."
                ),
            )
        )

    if child_birth_dates:
        household_change_date = min(min(child_birth_dates) + timedelta(days=90), reference_date)
        timeline.append(
            event(
                household_change_date,
                "family",
                "Household routine changed",
                (
                    f"{subject} herorganiseerde de dagelijkse routine rond zorg, logistiek en een voller huishouden."
                    if locale_kind == "nl"
                    else f"{subject} a reconfigure les routines quotidiennes autour des soins, de la logistique et d'un foyer plus charge."
                    if locale_kind == "fr"
                    else f"{subject} reorganized daily routines around care, logistics, and a fuller household schedule."
                ),
            )
        )

    timeline.sort(key=lambda item: item["date"])
    return timeline


def build_biography_from_timeline(*, row_context: dict | None, params: dict, field_name: str) -> str:
    timeline = resolve_context_value(
        row_context,
        params["timeline_field"],
        field_name=field_name,
        purpose="life timeline",
    )
    if not isinstance(timeline, list):
        raise SkillError(f"Field {field_name!r} expected timeline_field to resolve to an array.")

    row_locale = resolve_row_locale(row_context)
    locale_kind = locale_family(row_locale)

    full_name = None
    if params.get("full_name_field"):
        value = get_context_value_or_missing(row_context, params["full_name_field"])
        if value is not MISSING:
            full_name = value

    city = None
    if params.get("city_field"):
        value = get_context_value_or_missing(row_context, params["city_field"])
        if value is not MISSING:
            city = value

    education_level = None
    if params.get("education_level_field"):
        value = get_context_value_or_missing(row_context, params["education_level_field"])
        if value is not MISSING:
            education_level = value

    profession = None
    if params.get("profession_field"):
        value = get_context_value_or_missing(row_context, params["profession_field"])
        if value is not MISSING:
            profession = value

    hobbies = None
    if params.get("hobbies_field"):
        value = get_context_value_or_missing(row_context, params["hobbies_field"])
        if value is not MISSING:
            hobbies = value

    income_level = None
    if params.get("income_level_field"):
        value = get_context_value_or_missing(row_context, params["income_level_field"])
        if value is not MISSING:
            income_level = value

    marital_status = None
    if params.get("marital_status_field"):
        value = get_context_value_or_missing(row_context, params["marital_status_field"])
        if value is not MISSING:
            marital_status = value

    spouse = None
    if params.get("spouse_field"):
        value = get_context_value_or_missing(row_context, params["spouse_field"])
        if value is not MISSING:
            spouse = value

    children = None
    if params.get("children_field"):
        value = get_context_value_or_missing(row_context, params["children_field"])
        if value is not MISSING:
            children = value

    def first_event(category: str, title: str | None = None):
        for event in timeline:
            if not isinstance(event, dict):
                continue
            if event.get("category") != category:
                continue
            if title is not None and event.get("title") != title:
                continue
            return event
        return None

    def format_child_count_phrase(count: int) -> str:
        if locale_kind == "nl":
            return f"{count} kind" if count == 1 else f"{count} kinderen"
        if locale_kind == "fr":
            return f"{count} enfant" if count == 1 else f"{count} enfants"
        return f"{count} child" if count == 1 else f"{count} children"

    def build_income_sentence(income_level_value, *, style_name: str) -> str | None:
        if not isinstance(income_level_value, str) or not income_level_value.strip():
            return None
        income_text = income_level_value.strip()
        if locale_kind == "nl":
            localized_income_text = {
                "carefully budgeted household": "een zorgvuldig gebudgetteerd huishouden",
                "stable but budget-aware household": "een stabiel maar prijsbewust huishouden",
                "stable middle-income household": "een stabiel middeninkomenshuishouden",
                "comfortable upper-middle-income household": "een comfortabel hoger-middeninkomenshuishouden",
                "carefully budgeted household with close monthly planning": "een zorgvuldig gebudgetteerd huishouden met strakke maandplanning",
                "stable middle-income household with careful planning": "een stabiel middeninkomenshuishouden met zorgvuldige planning",
                "comfortable upper-middle-income household with careful planning": "een comfortabel hoger-middeninkomenshuishouden met zorgvuldige planning",
            }.get(income_text, income_text)
            if style_name == "direct":
                return f"Uitgaven passen bij {localized_income_text}."
            if style_name == "narrative":
                return f"De levensstijl sluit daardoor aan bij {localized_income_text}, waarbij comfort en praktische afwegingen in evenwicht blijven."
            return f"Het algemene profiel wijst op {localized_income_text}, met keuzes die betrouwbaarheid, comfort en realistische afwegingen benadrukken."
        if locale_kind == "fr":
            localized_income_text = {
                "carefully budgeted household": "un menage gere avec un budget serre",
                "stable but budget-aware household": "un menage stable mais attentif au budget",
                "stable middle-income household": "un menage stable a revenu moyen",
                "comfortable upper-middle-income household": "un menage aise de classe moyenne superieure",
                "carefully budgeted household with close monthly planning": "un menage gere avec un budget serre et une planification mensuelle rigoureuse",
                "stable middle-income household with careful planning": "un menage stable a revenu moyen avec une planification soignee",
                "comfortable upper-middle-income household with careful planning": "un menage aise de classe moyenne superieure avec une planification soignee",
            }.get(income_text, income_text)
            if style_name == "direct":
                return f"Les depenses correspondent a {localized_income_text}."
            if style_name == "narrative":
                return f"Le mode de vie correspond ainsi a {localized_income_text}, ou le confort reste equilibre par des arbitrages pratiques."
            return f"Le profil general evoque {localized_income_text}, avec des choix qui privilegient la fiabilite, le confort et des compromis realistes."
        normalized_income = income_text.lower()
        refers_to_existing_profile = any(
            marker in normalized_income
            for marker in ["household", "profile", "pattern", "lifestyle"]
        )
        income_phrase = (
            with_english_indefinite_article(income_text)
            if refers_to_existing_profile
            else f"a {income_text} profile"
        )

        if style_name == "direct":
            return f"Spending patterns fit {income_phrase}."
        if style_name == "narrative":
            if refers_to_existing_profile:
                return f"The resulting lifestyle fits {income_phrase}, where comfort is balanced against practical tradeoffs."
            return f"The resulting lifestyle fits a {income_text} pattern, where comfort is balanced against practical tradeoffs."
        if refers_to_existing_profile:
            return f"The overall profile suggests {income_phrase}, with decisions that favor reliability, comfort, and realistic tradeoffs."
        return f"The overall profile suggests a {income_text} pattern, with decisions that favor reliability, comfort, and realistic tradeoffs."

    def build_housing_context_phrase(
        housing_type_value,
        ownership_status_value,
        neighborhood_type_value,
    ) -> str | None:
        housing_type_text = str(housing_type_value).strip() if isinstance(housing_type_value, str) and housing_type_value.strip() else None
        ownership_status_text = (
            str(ownership_status_value).strip().lower()
            if isinstance(ownership_status_value, str) and ownership_status_value.strip()
            else None
        )
        neighborhood_type_text = (
            str(neighborhood_type_value).strip()
            if isinstance(neighborhood_type_value, str) and neighborhood_type_value.strip()
            else None
        )

        if locale_kind == "nl":
            generic_home = {
                "apartment": "een appartement",
                "row house": "een rijwoning",
                "semi-detached house": "een halfopen woning",
                "detached house": "een vrijstaande woning",
                "house": "een woning",
                "brussels apartment": "een Brussels appartement",
            }
            owned_home = {
                "apartment": "een appartement in eigendom",
                "row house": "een rijwoning in eigendom",
                "semi-detached house": "een halfopen woning in eigendom",
                "detached house": "een vrijstaande woning in eigendom",
                "house": "een woning in eigendom",
                "brussels apartment": "een Brussels appartement in eigendom",
            }
            rented_home = {
                "apartment": "een huurappartement",
                "row house": "een huurwoning",
                "semi-detached house": "een gehuurde halfopen woning",
                "detached house": "een gehuurde vrijstaande woning",
                "house": "een huurwoning",
                "brussels apartment": "een huurappartement in Brussel",
            }
            setting_map = {
                "urban": "een stedelijke omgeving",
                "suburban": "een voorstedelijke omgeving",
                "small-town": "een kleinstedelijke omgeving",
            }
            if ownership_status_text == "owner":
                home_phrase = owned_home.get(housing_type_text)
            elif ownership_status_text == "renter":
                home_phrase = rented_home.get(housing_type_text)
            else:
                home_phrase = generic_home.get(housing_type_text)
            neighborhood_phrase = setting_map.get(neighborhood_type_text)
            if home_phrase and neighborhood_phrase:
                return f"{home_phrase} in {neighborhood_phrase}"
            return home_phrase or neighborhood_phrase

        if locale_kind == "fr":
            generic_home = {
                "apartment": "un appartement",
                "row house": "une maison mitoyenne",
                "semi-detached house": "une maison semi-detachee",
                "detached house": "une maison individuelle",
                "house": "une maison",
                "brussels apartment": "un appartement bruxellois",
            }
            owned_home = {
                "apartment": "un appartement en propriete",
                "row house": "une maison mitoyenne en propriete",
                "semi-detached house": "une maison semi-detachee en propriete",
                "detached house": "une maison individuelle en propriete",
                "house": "une maison en propriete",
                "brussels apartment": "un appartement bruxellois en propriete",
            }
            rented_home = {
                "apartment": "un appartement loue",
                "row house": "une maison mitoyenne louee",
                "semi-detached house": "une maison semi-detachee louee",
                "detached house": "une maison individuelle louee",
                "house": "une maison louee",
                "brussels apartment": "un appartement bruxellois loue",
            }
            setting_map = {
                "urban": "un cadre urbain",
                "suburban": "un cadre periurbain",
                "small-town": "une petite ville",
            }
            if ownership_status_text == "owner":
                home_phrase = owned_home.get(housing_type_text)
            elif ownership_status_text == "renter":
                home_phrase = rented_home.get(housing_type_text)
            else:
                home_phrase = generic_home.get(housing_type_text)
            neighborhood_phrase = setting_map.get(neighborhood_type_text)
            if home_phrase and neighborhood_phrase:
                return f"{home_phrase} dans {neighborhood_phrase}"
            return home_phrase or neighborhood_phrase

        housing_descriptor = None
        if ownership_status_text == "owner":
            housing_descriptor = "owner-occupied"
        elif ownership_status_text == "renter":
            housing_descriptor = "rented"

        if housing_type_text:
            home_phrase = f"{housing_descriptor} {housing_type_text}" if housing_descriptor else housing_type_text
        elif housing_descriptor:
            home_phrase = f"{housing_descriptor} home"
        else:
            home_phrase = None

        neighborhood_phrase = (
            with_english_indefinite_article(f"{neighborhood_type_text} setting")
            if neighborhood_type_text
            else None
        )

        if home_phrase and neighborhood_phrase:
            return f"{with_english_indefinite_article(home_phrase)} in {neighborhood_phrase}"
        if home_phrase:
            return with_english_indefinite_article(home_phrase)
        if neighborhood_phrase:
            return f"a home in {neighborhood_phrase}"
        return None

    localized_education_level = localize_narrative_term(education_level, locale_kind=locale_kind, category="education")
    localized_profession = localize_narrative_term(profession, locale_kind=locale_kind, category="profession")
    localized_industry = None
    if params.get("industry_field"):
        value = get_context_value_or_missing(row_context, params["industry_field"])
        if value is not MISSING:
            localized_industry = localize_narrative_term(value, locale_kind=locale_kind, category="industry")
    hobbies_text = format_narrative_list(hobbies, locale_kind=locale_kind, category="hobby")

    explicit_style = params.get("style")
    if explicit_style is not None:
        style = str(explicit_style).strip().lower()
    else:
        style_options = params.get("styles", [])
        if isinstance(style_options, list) and style_options:
            anchor = "|".join(str(part or "") for part in [full_name, profession, city, education_level])
            style = str(style_options[sum(ord(char) for char in anchor) % len(style_options)]).strip().lower()
        else:
            style = "reflective"

    subject = str(full_name) if full_name else "This persona"
    education_event = first_event("education")
    career_event = first_event("career", "Current role")
    family_events = [event for event in timeline if isinstance(event, dict) and event.get("category") == "family"]
    partnership_event = first_event("family", "Marriage or long-term partnership")
    location_event = first_event("location")
    child_count = len(children) if isinstance(children, list) else 0
    has_partner_context = partnership_event is not None or isinstance(spouse, dict) or marital_status in {"married", "partnered"}
    housing_type = None
    if params.get("housing_type_field"):
        value = get_context_value_or_missing(row_context, params["housing_type_field"])
        if value is not MISSING:
            housing_type = value
    ownership_status = None
    if params.get("ownership_status_field"):
        value = get_context_value_or_missing(row_context, params["ownership_status_field"])
        if value is not MISSING:
            ownership_status = value
    neighborhood_type = None
    if params.get("neighborhood_type_field"):
        value = get_context_value_or_missing(row_context, params["neighborhood_type_field"])
        if value is not MISSING:
            neighborhood_type = value
    housing_context_phrase = build_housing_context_phrase(housing_type, ownership_status, neighborhood_type)

    variation_anchor = "|".join(
        str(part or "")
        for part in [
            full_name,
            city,
            localized_education_level,
            localized_profession,
            localized_industry,
            income_level,
            marital_status,
            child_count,
            housing_type,
            ownership_status,
            neighborhood_type,
        ]
    )

    def choose_sentence_variant(label: str, options: list[str]) -> str:
        cleaned = [option for option in options if isinstance(option, str) and option.strip()]
        if not cleaned:
            raise SkillError(f"Field {field_name!r} could not build a sentence variant for {label}.")
        anchor = f"{variation_anchor}|{label}"
        return cleaned[sum(ord(char) for char in anchor) % len(cleaned)]

    if locale_kind == "nl":
        role_clause = f" als {localized_profession}" if localized_profession else ""
        city_clause = f" in {city}" if city else ""
        if style == "direct":
            sentences = [
                choose_sentence_variant(
                    "direct_intro_nl",
                    [
                        f"{subject} is vandaag gevestigd{role_clause}{city_clause}.",
                        f"Vandaag leeft {subject}{role_clause}{city_clause}.",
                        f"{subject} heeft vandaag een stabiele plek{role_clause}{city_clause}.",
                    ],
                )
            ]
            if education_event is not None and education_level:
                sentences.append(
                    choose_sentence_variant(
                        "direct_education_nl",
                        [
                            f"{localized_education_level.capitalize()} vormde een belangrijke basis voor het huidige werk.",
                            f"De {localized_education_level} legde veel van de basis voor de huidige rol.",
                            f"Met {localized_education_level} ontstond een groot deel van de basis voor het werkritme van vandaag.",
                        ],
                    )
                )
            if career_event is not None and localized_profession:
                sentences.append(
                    choose_sentence_variant(
                        "direct_career_nl",
                        [
                            f"De loopbaan bouwde geleidelijk op naar de huidige rol als {localized_profession}.",
                            f"Professionele stappen leidden gaandeweg naar de huidige functie als {localized_profession}.",
                            f"Werkervaring groeide uit tot de huidige positie als {localized_profession}.",
                        ],
                    )
                )
            if child_count > 0:
                sentences.append(
                    choose_sentence_variant(
                        "direct_family_children_nl",
                        [
                            f"Het huishouden draait rond {format_child_count_phrase(child_count)} en een voorspelbare dagelijkse organisatie.",
                            f"Een routine rond {format_child_count_phrase(child_count)} bepaalt hoe tijd, zorg en planning worden georganiseerd.",
                            f"Dagelijkse keuzes worden duidelijk gevormd door {format_child_count_phrase(child_count)} en een vaste huishoudelijke cadans.",
                        ],
                    )
                )
            elif has_partner_context:
                sentences.append(
                    choose_sentence_variant(
                        "direct_family_partner_nl",
                        [
                            "Een duurzame relatie blijft zichtbaar in prioriteiten en planning.",
                            "Keuzes binnen de relatie blijven doorwerken in de dagelijkse organisatie.",
                            "Een stabiele partnercontext speelt nog altijd een rol in de manier waarop tijd en verantwoordelijkheden worden verdeeld.",
                        ],
                    )
                )
            if location_event is not None and city:
                sentences.append(
                    choose_sentence_variant(
                        "direct_location_nl",
                        [
                            f"Het leven in {city} kleurt de wekelijkse gewoonten en lokale voorkeuren.",
                            f"Dagelijkse gewoonten worden duidelijk gevormd door het leven in {city}.",
                            f"{city} geeft het lokale kader voor wekelijkse routines en voorkeuren.",
                        ],
                    )
                )
            if housing_context_phrase:
                sentences.append(
                    choose_sentence_variant(
                        "direct_housing_nl",
                        [
                            f"Het thuisleven is verankerd in {housing_context_phrase}.",
                            f"Het huishouden is gecentreerd rond {housing_context_phrase}.",
                            f"Het dagelijks leven wordt mee gedragen door {housing_context_phrase}.",
                        ],
                    )
                )
            if hobbies_text:
                sentences.append(
                    choose_sentence_variant(
                        "direct_hobbies_nl",
                        [
                            f"Vrije tijd gaat meestal naar {hobbies_text}.",
                            f"Buiten verplichtingen gaat tijd vaak naar {hobbies_text}.",
                            f"De meeste vrije tijd vloeit naar {hobbies_text}.",
                        ],
                    )
                )
            income_sentence = build_income_sentence(income_level, style_name="direct")
            if income_sentence:
                sentences.append(income_sentence)
            return " ".join(sentences)

        if style == "narrative":
            city_clause = f" die nu samenkomen in {city}" if city else ""
            sentences = [
                choose_sentence_variant(
                    "narrative_intro_nl",
                    [
                        f"{subject} is door een reeks nuchtere levensveranderingen gegaan{city_clause}.",
                        f"Het verhaal van {subject} wordt gevormd door een reeks gestage overgangen{city_clause}.",
                        f"In de loop van de tijd groeide {subject} uit tot een profiel met duidelijke praktische mijlpalen{city_clause}.",
                    ],
                )
            ]
            if education_event is not None and education_level:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_education_nl",
                        [
                            f"De opleiding mondde uit in {localized_education_level}, wat de weg opende naar meer gespecialiseerde verantwoordelijkheden.",
                            f"Het bereiken van {localized_education_level} schiep de voorwaarden voor meer gespecialiseerd werk en stabielere verantwoordelijkheden.",
                            f"{localized_education_level.capitalize()} vormde een belangrijk keerpunt richting een duidelijker professioneel pad.",
                        ],
                    )
                )
            if career_event is not None and localized_profession:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_career_nl",
                        [
                            f"Het werkleven ontwikkelde zich daarna richting de huidige positie als {localized_profession}, waar ervaring en betrouwbaarheid zichtbaarder werden.",
                            f"Het professionele leven vernauwde geleidelijk naar de huidige rol als {localized_profession}, waarbij ervaring uitgroeide tot duidelijkere verantwoordelijkheid.",
                            f"Loopbaanontwikkeling leidde uiteindelijk naar de huidige functie als {localized_profession}, waar consistentie en ervaring sterker zichtbaar werden.",
                        ],
                    )
                )
            if child_count > 0:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_family_children_nl",
                        [
                            f"Gezinsmijlpalen hertekenden het huishouden, waarbij {format_child_count_phrase(child_count)} planning, zorg en stabiliteit centraler maakten.",
                            f"Gezinsleven kreeg gaandeweg meer gewicht, en {format_child_count_phrase(child_count)} maakten zorg, structuur en planning belangrijker.",
                            f"Het huishoudverhaal veranderde merkbaar rond {format_child_count_phrase(child_count)}, waardoor langdurige coordinatie en betrouwbaarheid belangrijker werden.",
                        ],
                    )
                )
            elif has_partner_context:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_family_partner_nl",
                        [
                            "Relatiemijlpalen voegden een extra laag van continuiteit toe aan het levensverhaal.",
                            "Ontwikkelingen in de partnerrelatie brachten een extra lijn van continuiteit in het profiel.",
                            "Een duurzame relatie werd deel van het bredere patroon dat vandaag de prioriteiten mee bepaalt.",
                        ],
                    )
                )
            if housing_context_phrase:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_housing_nl",
                        [
                            f"Het dagelijkse leven wordt verder gegrond in {housing_context_phrase}, wat het profiel een duidelijker thuiscentrum geeft.",
                            f"Het huishoudelijke beeld wordt concreter door {housing_context_phrase}, wat het dagelijkse ritme beter verankert.",
                            f"{housing_context_phrase.capitalize()} geeft het bredere verhaal een tastbaardere thuisbasis.",
                        ],
                    )
                )
            if hobbies_text:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_hobbies_nl",
                        [
                            f"Buiten formele verantwoordelijkheden zorgen {hobbies_text} voor continuiteit en verklaren ze mee het persoonlijke ritme.",
                            f"Los van werk en verplichtingen geven {hobbies_text} continuiteit en een duidelijker persoonlijk tempo.",
                            f"Weg van werk en logistiek zorgen {hobbies_text} voor het rustigere ritme dat het profiel afrondt.",
                        ],
                    )
                )
            income_sentence = build_income_sentence(income_level, style_name="narrative")
            if income_sentence:
                sentences.append(income_sentence)
            return " ".join(sentences)

        sentences = [
            choose_sentence_variant(
                "reflective_intro_nl",
                [
                    f"{subject} heeft een leven opgebouwd met gestage mijlpalen{role_clause}{city_clause}.",
                    f"Het huidige profiel van {subject} weerspiegelt een reeks stabiele mijlpalen{role_clause}{city_clause}.",
                    f"{subject} bevindt zich vandaag in een gegronde levensfase{role_clause}{city_clause}.",
                ],
            )
        ]
        if education_event is not None and education_level:
            sentences.append(
                choose_sentence_variant(
                    "reflective_education_nl",
                    [
                        f"Na {localized_education_level} verschoof het pad naar een duidelijker professionele richting.",
                        f"{localized_education_level.capitalize()} markeerde de overgang naar een meer afgebakende werkroute.",
                        f"Het afronden van {localized_education_level} zette de stap naar een stabieler werkpad in gang.",
                    ],
                )
            )
        if career_event is not None and localized_profession:
            sentences.append(
                choose_sentence_variant(
                    "reflective_career_nl",
                    [
                        f"De loopbaanlijn wijst op een geleidelijke doorgroei naar de huidige rol als {localized_profession}.",
                        f"In de loop van de tijd groeiden werkverantwoordelijkheden uit tot de huidige functie als {localized_profession}.",
                        f"Het bredere loopbaanpad vernauwde stap voor stap naar de huidige positie als {localized_profession}.",
                    ],
                )
            )
        if child_count > 0:
            sentences.append(
                choose_sentence_variant(
                    "reflective_family_children_nl",
                    [
                        f"Gezinsleven werd gaandeweg centraler en mondde uit in een huishouden met {format_child_count_phrase(child_count)} en routines rond zorg, planning en betrouwbaarheid.",
                        f"Na verloop van tijd draaide het huishouden duidelijker rond {format_child_count_phrase(child_count)}, waarbij zorg en planning meer gewicht kregen.",
                        f"Een gezinsroutine rond {format_child_count_phrase(child_count)} bepaalt nu veel van de planning en dagelijkse betrouwbaarheid.",
                    ],
                )
            )
        elif has_partner_context:
            sentences.append(
                choose_sentence_variant(
                    "reflective_family_partner_nl",
                    [
                        "Relatiemijlpalen spelen zichtbaar mee in de huidige prioriteiten van het profiel.",
                        "Een stabiele partnercontext blijft belangrijk voor de huidige prioriteiten en afwegingen.",
                        "Keuzes binnen de relatie helpen nog steeds verklaren hoe verantwoordelijkheden vandaag worden afgewogen.",
                    ],
                )
            )
        if location_event is not None and city:
            sentences.append(
                choose_sentence_variant(
                    "reflective_location_nl",
                    [
                        f"Zich vestigen in {city} verankert het dagelijkse ritme, lokale voorkeuren en een langdurig gevoel van plaats.",
                        f"Het leven in {city} biedt nu het lokale kader dat dagelijkse ritmes en praktische voorkeuren vormgeeft.",
                        f"{city} verbindt het alledaagse ritme, lokale gewoonten en een gevoel van langere termijn stabiliteit.",
                    ],
                )
            )
        if housing_context_phrase:
            sentences.append(
                choose_sentence_variant(
                    "reflective_housing_nl",
                    [
                        f"Het thuisleven is verankerd in {housing_context_phrase}, wat het wekelijkse ritme verder versterkt.",
                        f"De huiselijke context draait om {housing_context_phrase}, wat het beschreven weekritme verder ondersteunt.",
                        f"{housing_context_phrase.capitalize()} geeft het bredere weekpatroon van het profiel een concrete thuisbasis.",
                    ],
                )
            )
        if hobbies_text:
            sentences.append(
                choose_sentence_variant(
                    "reflective_hobbies_nl",
                    [
                        f"Buiten het werk gaat tijd vaak naar {hobbies_text}, wat het profiel een gegrond en persoonlijk consistent ritme geeft.",
                        f"Naast werk helpen {hobbies_text} een levensstijl uittekenen die stabiel en persoonlijk samenhangend aanvoelt.",
                        f"In persoonlijke tijd geven {hobbies_text} het profiel een herkenbaar en rustig tempo.",
                    ],
                )
            )
        income_sentence = build_income_sentence(income_level, style_name="reflective")
        if income_sentence:
            sentences.append(income_sentence)
        return " ".join(sentences)

    if locale_kind == "fr":
        role_clause = f" comme {localized_profession}" if localized_profession else ""
        city_clause = f" a {city}" if city else ""
        if style == "direct":
            sentences = [
                choose_sentence_variant(
                    "direct_intro_fr",
                    [
                        f"{subject} est aujourd'hui installe{role_clause}{city_clause}.",
                        f"Aujourd'hui, {subject} vit{role_clause}{city_clause}.",
                        f"{subject} a aujourd'hui une situation stable{role_clause}{city_clause}.",
                    ],
                )
            ]
            if education_event is not None and education_level:
                sentences.append(
                    choose_sentence_variant(
                        "direct_education_fr",
                        [
                            f"{localized_education_level.capitalize()} a constitue une base importante pour le travail actuel.",
                            f"La formation jusqu'a {localized_education_level} a pose une grande partie des bases du role actuel.",
                            f"{localized_education_level.capitalize()} a fourni une part essentielle du socle du rythme professionnel d'aujourd'hui.",
                        ],
                    )
                )
            if career_event is not None and localized_profession:
                sentences.append(
                    choose_sentence_variant(
                        "direct_career_fr",
                        [
                            f"Le parcours professionnel a progressivement mene au role actuel de {localized_profession}.",
                            f"Les etapes de carriere ont conduit peu a peu a la fonction actuelle de {localized_profession}.",
                            f"L'experience de travail s'est accumulee jusqu'a la position actuelle de {localized_profession}.",
                        ],
                    )
                )
            if child_count > 0:
                sentences.append(
                    choose_sentence_variant(
                        "direct_family_children_fr",
                        [
                            f"Le foyer s'organise autour de {format_child_count_phrase(child_count)} et d'une routine quotidienne previsible.",
                            f"Une routine construite autour de {format_child_count_phrase(child_count)} structure le temps, les soins et la planification.",
                            f"Les choix quotidiens sont clairement formes par {format_child_count_phrase(child_count)} et une cadence domestique stable.",
                        ],
                    )
                )
            elif has_partner_context:
                sentences.append(
                    choose_sentence_variant(
                        "direct_family_partner_fr",
                        [
                            "Une relation durable continue de peser dans les priorites et l'organisation du temps.",
                            "Les choix du couple restent visibles dans la facon de planifier le quotidien.",
                            "Un contexte de couple stable joue encore un role dans la repartition du temps et des responsabilites.",
                        ],
                    )
                )
            if location_event is not None and city:
                sentences.append(
                    choose_sentence_variant(
                        "direct_location_fr",
                        [
                            f"La vie a {city} influence nettement les habitudes hebdomadaires et les preferences locales.",
                            f"Les habitudes quotidiennes sont clairement faconnees par la vie a {city}.",
                            f"{city} fournit le cadre local des routines hebdomadaires et des preferences.",
                        ],
                    )
                )
            if housing_context_phrase:
                sentences.append(
                    choose_sentence_variant(
                        "direct_housing_fr",
                        [
                            f"La vie domestique s'ancre dans {housing_context_phrase}.",
                            f"Le foyer s'organise autour de {housing_context_phrase}.",
                            f"Le quotidien prend appui sur {housing_context_phrase}.",
                        ],
                    )
                )
            if hobbies_text:
                sentences.append(
                    choose_sentence_variant(
                        "direct_hobbies_fr",
                        [
                            f"Le temps libre va le plus souvent vers {hobbies_text}.",
                            f"En dehors des obligations, le temps se tourne souvent vers {hobbies_text}.",
                            f"L'essentiel du temps libre s'oriente vers {hobbies_text}.",
                        ],
                    )
                )
            income_sentence = build_income_sentence(income_level, style_name="direct")
            if income_sentence:
                sentences.append(income_sentence)
            return " ".join(sentences)

        if style == "narrative":
            city_clause = f" qui convergent aujourd'hui vers {city}" if city else ""
            sentences = [
                choose_sentence_variant(
                    "narrative_intro_fr",
                    [
                        f"{subject} a traverse une serie de changements de vie tres concrets{city_clause}.",
                        f"L'histoire de {subject} se compose d'une serie de transitions regulieres{city_clause}.",
                        f"Avec le temps, {subject} a evolue vers un profil marque par des jalons tres concrets{city_clause}.",
                    ],
                )
            ]
            if education_event is not None and education_level:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_education_fr",
                        [
                            f"La formation a abouti a {localized_education_level}, ouvrant la voie a des responsabilites plus specialisees.",
                            f"Atteindre {localized_education_level} a cree les conditions d'un travail plus specialise et plus stable.",
                            f"{localized_education_level.capitalize()} a marque un tournant important vers une direction professionnelle plus nette.",
                        ],
                    )
                )
            if career_event is not None and localized_profession:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_career_fr",
                        [
                            f"La vie professionnelle s'est ensuite orientee vers la position actuelle de {localized_profession}, ou l'experience et la fiabilite sont devenues plus visibles.",
                            f"Le parcours professionnel s'est progressivement resserre vers le role actuel de {localized_profession}, avec une experience transformee en responsabilites plus nettes.",
                            f"L'evolution de carriere a finalement conduit a la fonction actuelle de {localized_profession}, ou la constance et l'experience apparaissent davantage.",
                        ],
                    )
                )
            if child_count > 0:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_family_children_fr",
                        [
                            f"Les jalons familiaux ont reconfigure le foyer, {format_child_count_phrase(child_count)} rendant la planification, les soins et la stabilite plus centraux.",
                            f"La vie familiale a pris plus de poids avec le temps, et {format_child_count_phrase(child_count)} ont rendu les soins, la structure et la planification plus importants.",
                            f"L'histoire du foyer a change de facon nette autour de {format_child_count_phrase(child_count)}, rendant la coordination de long terme plus importante.",
                        ],
                    )
                )
            elif has_partner_context:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_family_partner_fr",
                        [
                            "Les etapes de la relation ont ajoute une autre couche de continuite a l'histoire de vie.",
                            "Les evolutions du couple ont apporte un fil supplementaire de continuite au profil.",
                            "Une relation durable est devenue une partie du schema plus large qui structure aujourd'hui les priorites.",
                        ],
                    )
                )
            if housing_context_phrase:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_housing_fr",
                        [
                            f"Le quotidien est davantage ancre dans {housing_context_phrase}, ce qui donne au profil un centre domestique plus net.",
                            f"L'image du foyer devient plus concrete avec {housing_context_phrase}, ce qui aide a centrer le rythme quotidien.",
                            f"{housing_context_phrase.capitalize()} donne a l'ensemble de l'histoire un point d'ancrage residentiel plus tangible.",
                        ],
                    )
                )
            if hobbies_text:
                sentences.append(
                    choose_sentence_variant(
                        "narrative_hobbies_fr",
                        [
                            f"En dehors des responsabilites formelles, {hobbies_text} apportent de la continuite et aident a expliquer le rythme personnel.",
                            f"Au-dela du travail et des obligations, {hobbies_text} donnent de la continuite et un tempo personnel plus clair.",
                            f"Loin du travail et de la logistique, {hobbies_text} creent le rythme plus calme qui complete le profil.",
                        ],
                    )
                )
            income_sentence = build_income_sentence(income_level, style_name="narrative")
            if income_sentence:
                sentences.append(income_sentence)
            return " ".join(sentences)

        sentences = [
            choose_sentence_variant(
                "reflective_intro_fr",
                [
                    f"{subject} a construit une vie faite de jalons reguliers{role_clause}{city_clause}.",
                    f"Le profil actuel de {subject} reflete une serie de jalons stables{role_clause}{city_clause}.",
                    f"{subject} se trouve aujourd'hui dans une phase de vie bien ancree{role_clause}{city_clause}.",
                ],
            )
        ]
        if education_event is not None and education_level:
            sentences.append(
                choose_sentence_variant(
                    "reflective_education_fr",
                    [
                        f"Apres {localized_education_level}, la trajectoire s'est orientee vers une direction professionnelle plus claire.",
                        f"{localized_education_level.capitalize()} a marque la transition vers un parcours de travail plus defini.",
                        f"L'achevement de {localized_education_level} a enclenche le passage vers un chemin professionnel plus stable.",
                    ],
                )
            )
        if career_event is not None and localized_profession:
            sentences.append(
                choose_sentence_variant(
                    "reflective_career_fr",
                    [
                        f"Le fil de carriere montre une progression graduelle vers le role actuel de {localized_profession}.",
                        f"Avec le temps, les responsabilites professionnelles se sont accumulees jusqu'a la fonction actuelle de {localized_profession}.",
                        f"Le parcours de carriere s'est resserre pas a pas vers la position actuelle de {localized_profession}.",
                    ],
                )
            )
        if child_count > 0:
            sentences.append(
                choose_sentence_variant(
                    "reflective_family_children_fr",
                    [
                        f"La vie familiale a progressivement pris plus de place, pour aboutir a un foyer avec {format_child_count_phrase(child_count)} et des routines marquees par les soins, la planification et la fiabilite.",
                        f"Avec le temps, le foyer s'est organise plus clairement autour de {format_child_count_phrase(child_count)}, donnant plus de poids aux soins et a la planification.",
                        f"Une routine familiale construite autour de {format_child_count_phrase(child_count)} structure aujourd'hui une grande partie de la planification et de la fiabilite quotidienne.",
                    ],
                )
            )
        elif has_partner_context:
            sentences.append(
                choose_sentence_variant(
                    "reflective_family_partner_fr",
                    [
                        "Les etapes de la relation jouent encore un role visible dans les priorites actuelles du profil.",
                        "Un contexte de couple stable reste important pour comprendre les priorites et les arbitrages actuels.",
                        "Les choix de la relation continuent d'expliquer la facon dont les responsabilites sont aujourd'hui equilibrees.",
                    ],
                )
            )
        if location_event is not None and city:
            sentences.append(
                choose_sentence_variant(
                    "reflective_location_fr",
                    [
                        f"S'installer a {city} ancre le rythme quotidien, les preferences locales et un sentiment durable d'appartenance.",
                        f"La vie a {city} fournit aujourd'hui le cadre local qui structure les rythmes du quotidien et les preferences pratiques.",
                        f"{city} relie le rythme ordinaire, les habitudes locales et une forme de stabilite a plus long terme.",
                    ],
                )
            )
        if housing_context_phrase:
            sentences.append(
                choose_sentence_variant(
                    "reflective_housing_fr",
                    [
                        f"La vie domestique s'ancre dans {housing_context_phrase}, ce qui renforce encore le rythme hebdomadaire.",
                        f"Le cadre du foyer repose sur {housing_context_phrase}, ce qui soutient le rythme de semaine decrit ailleurs dans le profil.",
                        f"{housing_context_phrase.capitalize()} donne au schema hebdomadaire du profil un point d'appui residentiel concret.",
                    ],
                )
            )
        if hobbies_text:
            sentences.append(
                choose_sentence_variant(
                    "reflective_hobbies_fr",
                    [
                        f"En dehors du travail, le temps va souvent vers {hobbies_text}, ce qui donne au profil un rythme personnel stable et coherent.",
                        f"En plus du travail, {hobbies_text} contribuent a dessiner un mode de vie qui semble stable et personnellement coherent.",
                        f"Dans le temps personnel, {hobbies_text} donnent au profil un tempo reconnaissable et plus calme.",
                    ],
                )
            )
        income_sentence = build_income_sentence(income_level, style_name="reflective")
        if income_sentence:
            sentences.append(income_sentence)
        return " ".join(sentences)

    if style == "direct":
        role_clause = f" as {with_english_indefinite_article(profession)}" if profession else ""
        working_role_clause = f" working as {with_english_indefinite_article(profession)}" if profession else ""
        city_clause = f" in {city}" if city else ""
        sentences = [
            choose_sentence_variant(
                "direct_intro",
                [
                    f"{subject} is now established{role_clause}{city_clause}.",
                    f"Today, {subject} is settled{role_clause}{city_clause}.",
                    f"{subject} is at a stage of life that feels steady{working_role_clause}{city_clause}.",
                ],
            )
        ]
        if education_event is not None and education_level:
            sentences.append(
                choose_sentence_variant(
                    "direct_education",
                    [
                        f"{education_level} helped shape the base for the current work profile.",
                        f"Training through {education_level} laid the groundwork for the current role.",
                        f"{education_level} provided much of the foundation for today's work routine.",
                    ],
                )
            )
        if career_event is not None and profession:
            sentences.append(
                choose_sentence_variant(
                    "direct_career",
                    [
                        f"The timeline shows a steady progression toward the current {profession} role.",
                        f"Career steps gradually led toward the current {profession} position.",
                        f"Work experience accumulated into the current {profession} role over time.",
                    ],
                )
            )
        if child_count > 0:
            sentences.append(
                choose_sentence_variant(
                    "direct_family_children",
                    [
                        f"Family decisions are organized around {format_child_count_phrase(child_count)} and a predictable household routine.",
                        f"Household planning now revolves around {format_child_count_phrase(child_count)} and dependable day-to-day coordination.",
                        f"A routine built around {format_child_count_phrase(child_count)} shapes how time, care, and planning are organized.",
                    ],
                )
            )
        elif has_partner_context:
            sentences.append(
                choose_sentence_variant(
                    "direct_family_partner",
                    [
                        "Partnership milestones still shape priorities and scheduling.",
                        "Long-term partnership choices continue to influence priorities and daily planning.",
                        "A stable partnership still plays a visible role in the way time and responsibilities are managed.",
                    ],
                )
            )
        if location_event is not None and city:
            sentences.append(
                choose_sentence_variant(
                    "direct_location",
                    [
                        f"Living in {city} strongly influences local preferences and weekly rhythm.",
                        f"Day-to-day habits are clearly shaped by life in {city}.",
                        f"{city} provides the local frame for weekly routines and preferences.",
                    ],
                )
            )
        if housing_context_phrase:
            sentences.append(
                choose_sentence_variant(
                    "direct_housing",
                    [
                        f"Home life is anchored in {housing_context_phrase}.",
                        f"The household is centered around {housing_context_phrase}.",
                        f"Daily life is grounded in {housing_context_phrase}.",
                    ],
                )
            )
        if hobbies_text:
            sentences.append(
                choose_sentence_variant(
                    "direct_hobbies",
                    [
                        f"Free time is mostly directed toward {hobbies_text}.",
                        f"Outside obligations, time usually goes toward {hobbies_text}.",
                        f"Most discretionary time tends to flow toward {hobbies_text}.",
                    ],
                )
            )
        income_sentence = build_income_sentence(income_level, style_name="direct")
        if income_sentence:
            sentences.append(income_sentence)
        return " ".join(sentences)

    if style == "narrative":
        city_clause = f" that now converge in {city}" if city else ""
        sentences = [
            choose_sentence_variant(
                "narrative_intro",
                [
                    f"{subject} has moved through a sequence of grounded life changes{city_clause}.",
                    f"{subject}'s story is shaped by a series of steady transitions{city_clause}.",
                    f"Over time, {subject} has grown into a profile defined by practical milestones{city_clause}.",
                ],
            )
        ]
        if education_event is not None and education_level:
            sentences.append(
                choose_sentence_variant(
                    "narrative_education",
                    [
                        f"Education culminated in {education_level}, which opened the path toward more specialized responsibilities.",
                        f"Reaching {education_level} created the conditions for more specialized work and steadier responsibilities.",
                        f"{education_level} marked an important turning point toward a more defined professional direction.",
                    ],
                )
            )
        if career_event is not None and profession:
            sentences.append(
                choose_sentence_variant(
                    "narrative_career",
                    [
                        f"Work life then developed toward the current {profession} position, where accumulated experience and reliability became more visible.",
                        f"Professional life gradually narrowed toward the current {profession} role, with experience building into clearer responsibility.",
                        f"Career progress eventually led to the current {profession} position, where consistency and experience became more apparent.",
                    ],
                )
            )
        if child_count > 0:
            sentences.append(
                choose_sentence_variant(
                    "narrative_family_children",
                    [
                        f"Family milestones reshaped the household over time, with {format_child_count_phrase(child_count)} making planning, care, and stability more central.",
                        f"Family life took on greater weight over time, and {format_child_count_phrase(child_count)} made care, structure, and planning more central.",
                        f"The household story changed notably around {format_child_count_phrase(child_count)}, making long-term coordination and dependability more important.",
                    ],
                )
            )
        elif has_partner_context:
            sentences.append(
                choose_sentence_variant(
                    "narrative_family_partner",
                    [
                        "Relationship milestones added another layer of continuity to the overall life story.",
                        "Partnership developments introduced another thread of continuity into the persona's life story.",
                        "A durable partnership became part of the broader pattern that now defines daily priorities.",
                    ],
                )
            )
        if housing_context_phrase:
            sentences.append(
                choose_sentence_variant(
                    "narrative_housing",
                    [
                        f"Daily life is further grounded by {housing_context_phrase}, giving the profile a clearer domestic center.",
                        f"The domestic picture is made more concrete by {housing_context_phrase}, which helps center the persona's day-to-day rhythm.",
                        f"{housing_context_phrase.capitalize()} gives the wider story a more tangible home base.",
                    ],
                )
            )
        if hobbies_text:
            sentences.append(
                choose_sentence_variant(
                    "narrative_hobbies",
                    [
                        f"Outside formal responsibilities, {hobbies_text} provide continuity and help explain the persona's personal rhythm.",
                        f"Beyond formal obligations, {hobbies_text} add continuity and help define the persona's personal tempo.",
                        f"Away from work and logistics, {hobbies_text} create the steadier rhythm that rounds out the profile.",
                    ],
                )
            )
        income_sentence = build_income_sentence(income_level, style_name="narrative")
        if income_sentence:
            sentences.append(income_sentence)
        return " ".join(sentences)

    role_clause = f" as {with_english_indefinite_article(profession)}" if profession else ""
    city_clause = f" in {city}" if city else ""
    sentences = [
        choose_sentence_variant(
            "reflective_intro",
            [
                f"{subject} has built a life shaped by steady milestones{role_clause}{city_clause}.",
                f"{subject}'s current profile reflects a series of steady milestones{role_clause}{city_clause}.",
                f"{subject} has arrived at a grounded stage of life{role_clause}{city_clause}.",
            ],
        )
    ]

    if education_event is not None and education_level:
        sentences.append(
            choose_sentence_variant(
                "reflective_education",
                [
                    f"After completing {education_level}, {subject if full_name else 'they'} moved into a more defined professional path.",
                    f"{education_level} helped mark the shift toward a clearer professional direction.",
                    f"Completing {education_level} set the stage for a more settled work path.",
                ],
            )
        )

    if career_event is not None and profession:
        sentences.append(
            choose_sentence_variant(
                "reflective_career",
                [
                    f"The career timeline points to a progression into the current {profession} role as responsibilities and stability increased.",
                    f"Over time, work responsibilities accumulated into the current {profession} role.",
                    f"The broader career path gradually narrowed into the current {profession} position as experience deepened.",
                ],
            )
        )

    if child_count > 0:
        sentences.append(
            choose_sentence_variant(
                "reflective_family_children",
                [
                    f"Family life became more central over time, culminating in a household with {format_child_count_phrase(child_count)} and routines shaped around care, planning, and dependability.",
                    f"Over time, the household came to revolve more clearly around {format_child_count_phrase(child_count)}, with care and planning taking on greater weight.",
                    f"A family routine organized around {format_child_count_phrase(child_count)} now shapes much of the persona's planning and dependability.",
                ],
            )
        )
    elif has_partner_context:
        sentences.append(
            choose_sentence_variant(
                "reflective_family_partner",
                [
                    "Relationship milestones play a visible role in the profile and help explain the persona's current priorities.",
                    "A stable partnership remains an important part of the profile's current priorities and tradeoffs.",
                    "Partnership decisions still help explain how present-day responsibilities are balanced.",
                ],
            )
        )

    if location_event is not None and city:
        sentences.append(
            choose_sentence_variant(
                "reflective_location",
                [
                    f"Settling in {city} anchors the persona's daily rhythm, local preferences, and long-term sense of place.",
                    f"Life in {city} now provides the local context that shapes daily rhythm and practical preferences.",
                    f"{city} serves as the place that ties together everyday rhythm, local habits, and longer-term stability.",
                ],
            )
        )

    if housing_context_phrase:
        sentences.append(
            choose_sentence_variant(
                "reflective_housing",
                [
                    f"Home life is anchored in {housing_context_phrase}, reinforcing the persona's overall weekly rhythm.",
                    f"The domestic setting centers on {housing_context_phrase}, which reinforces the weekly rhythm described elsewhere in the profile.",
                    f"{housing_context_phrase.capitalize()} adds a concrete home base to the persona's broader weekly pattern.",
                ],
            )
        )

    if hobbies_text:
        sentences.append(
            choose_sentence_variant(
                "reflective_hobbies",
                [
                    f"Outside work, time tends to flow toward {hobbies_text}, reinforcing a lifestyle that feels grounded and personally consistent.",
                    f"Beyond work, {hobbies_text} help round out a lifestyle that feels stable and personally coherent.",
                    f"In personal time, {hobbies_text} help give the profile a steady and recognizable rhythm.",
                ],
            )
        )

    income_sentence = build_income_sentence(income_level, style_name="reflective")
    if income_sentence:
        sentences.append(income_sentence)

    return " ".join(sentences)


def build_persona_introduction(*, row_context: dict | None, params: dict, field_name: str) -> str:
    full_name = resolve_context_value(row_context, params["full_name_field"], field_name=field_name, purpose="full name")
    age = resolve_context_value(row_context, params["age_field"], field_name=field_name, purpose="age")
    profession = resolve_context_value(row_context, params["profession_field"], field_name=field_name, purpose="profession")

    city = None
    if params.get("city_field"):
        value = get_context_value_or_missing(row_context, params["city_field"])
        if value is not MISSING:
            city = value

    industry = None
    if params.get("industry_field"):
        value = get_context_value_or_missing(row_context, params["industry_field"])
        if value is not MISSING:
            industry = value

    neighborhood_type = None
    if params.get("neighborhood_type_field"):
        value = get_context_value_or_missing(row_context, params["neighborhood_type_field"])
        if value is not MISSING:
            neighborhood_type = value

    locale_kind = locale_family(resolve_row_locale(row_context))
    localized_profession = localize_narrative_term(profession, locale_kind=locale_kind, category="profession")
    localized_industry = localize_narrative_term(industry, locale_kind=locale_kind, category="industry")
    neighborhood_base = {
        "en": {
            "urban": "urban",
            "suburban": "suburban",
            "small-town": "small-town",
        },
        "nl": {
            "urban": "stedelijke",
            "suburban": "voorstedelijke",
            "small-town": "kleinstedelijke",
        },
        "fr": {
            "urban": "urbain",
            "suburban": "periurbain",
            "small-town": "de petite ville",
        },
    }.get(locale_kind, {}).get(str(neighborhood_type or "").strip(), str(neighborhood_type or "").strip())

    if locale_kind == "nl":
        city_clause = f" in {city}" if city else ""
        industry_clause = f" door werk in {localized_industry}" if localized_industry else ""
        neighborhood_clause = f", een {neighborhood_base} thuisbasis" if neighborhood_base else ""
        return (
            f"{full_name} is {age} jaar en werkt als {localized_profession}{city_clause}. "
            f"Het dagelijks leven wordt gevormd{industry_clause}{neighborhood_clause}, en door voorkeuren die passen bij een geloofwaardig Belgisch dagelijks leven."
        )

    if locale_kind == "fr":
        city_clause = f" a {city}" if city else ""
        industry_clause = f" par le travail dans {localized_industry}" if localized_industry else ""
        neighborhood_clause = f", un ancrage {neighborhood_base}" if neighborhood_base else ""
        return (
            f"{full_name} a {age} ans et travaille comme {localized_profession}{city_clause}. "
            f"Le quotidien est faconne{industry_clause}{neighborhood_clause}, et par des preferences qui correspondent a une vie belge credible au jour le jour."
        )

    city_clause = f" living in {city}" if city else ""
    industry_clause = f" by work in {industry}" if industry else ""
    neighborhood_clause = f", their {neighborhood_base} home base" if neighborhood_base else ""
    return (
        f"{full_name} is a {age}-year-old {profession}{city_clause}. "
        f"Their routine is shaped{industry_clause}{neighborhood_clause}, and preferences that fit a believable day-to-day life."
    )


def infer_life_stage(age: int) -> str:
    if age >= 65:
        return "retired"
    if age < 25:
        return "early_adult"
    if age < 40:
        return "mid_career"
    return "established_adult"


def normalize_income_bracket_label(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"low", "lower-middle", "middle", "upper-middle"}:
        return normalized
    return None


def build_routine_coordination_phrase(
    *,
    profession: str | None,
    sector_type: str | None,
    employer_scale: str | None,
    locale_kind: str = "en",
) -> str:
    if locale_kind == "nl":
        if sector_type == "public sector":
            return "agenda-gestuurde vergaderingen, publiekgerichte afstemming en dossieropvolging"
        if sector_type == "nonprofit or community sector":
            return "mensgerichte afstemming, praktische opvolging en een dienstgerichte dagstructuur"
        if employer_scale == "local SME":
            return "praktische afstemming in een kleiner team en veel schakelen tussen taken"
        if employer_scale == "national or regional operator":
            return "afstemming tussen teams en gestructureerde overdrachten binnen een grotere organisatie"
        if employer_scale == "regional mid-sized employer":
            return "vaste overlegmomenten, gerichte werkblokken en afstemming in een middelgroot team"
        if profession:
            return "gerichte werkblokken en praktische afstemming rond de functie"
        return "gerichte werkblokken"
    if locale_kind == "fr":
        if sector_type == "public sector":
            return "reunions calees sur l'agenda, coordination avec le public et suivi de dossiers"
        if sector_type == "nonprofit or community sector":
            return "coordination tres humaine, suivi pratique et rythme de jour oriente vers le service"
        if employer_scale == "local SME":
            return "coordination tres concrete dans une petite equipe et nombreux changements de tache"
        if employer_scale == "national or regional operator":
            return "coordination entre equipes et relais structures dans une organisation plus large"
        if employer_scale == "regional mid-sized employer":
            return "reunions regulieres, plages de travail ciblees et coordination dans une equipe de taille moyenne"
        if profession:
            return "plages de travail ciblees et coordination pratique autour de la fonction"
        return "plages de travail ciblees"
    if sector_type == "public sector":
        return "calendar-driven meetings, public-facing coordination, and document-heavy follow-up"
    if sector_type == "nonprofit or community sector":
        return "people-facing coordination, practical follow-up, and a service-oriented daytime rhythm"
    if employer_scale == "local SME":
        return "hands-on coordination across a smaller team and practical task switching"
    if employer_scale == "national or regional operator":
        return "cross-team coordination and structured handoffs across a larger operation"
    if employer_scale == "regional mid-sized employer":
        return "steady meetings, focused work blocks, and coordination across a mid-sized team"
    if profession:
        return "focused work periods and practical coordination around the role"
    return "focused work periods"


def build_income_sensitive_weekend_rhythm(
    *,
    income_bracket: str | None,
    default_weekend: str,
    locale_kind: str = "en",
) -> str:
    if income_bracket in {"low", "lower-middle"}:
        if locale_kind == "nl":
            return "praktische boodschappen, prijsbewust winkelen en wat lokale ontspanning"
        if locale_kind == "fr":
            return "courses pratiques, achats attentifs au budget et un peu de temps libre a proximite"
        return "practical errands, budget-aware shopping, and some local downtime"
    if income_bracket == "upper-middle":
        if locale_kind == "nl":
            return "beweging, boodschappen en nog een extra sociaal of recreatief plan"
        if locale_kind == "fr":
            return "activite physique, courses et un plan social ou de loisir supplementaire"
        return "exercise, errands, and one more discretionary social or leisure plan"
    return default_weekend


def build_daily_routine_profile(*, row_context: dict | None, params: dict, field_name: str) -> dict:
    age_value = resolve_context_value(
        row_context,
        params["age_field"],
        field_name=field_name,
        purpose="age",
    )
    if not isinstance(age_value, int) or isinstance(age_value, bool) or age_value < 0:
        raise SkillError(f"Field {field_name!r} expected a non-negative integer age, received {age_value!r}.")

    profession = None
    if params.get("profession_field"):
        value = get_context_value_or_missing(row_context, params["profession_field"])
        if value is not MISSING:
            profession = str(value)

    work_pattern_value = None
    if params.get("work_pattern_field"):
        value = get_context_value_or_missing(row_context, params["work_pattern_field"])
        if value is not MISSING:
            work_pattern_value = str(value)

    commute_mode = None
    if params.get("primary_commute_mode_field"):
        value = get_context_value_or_missing(row_context, params["primary_commute_mode_field"])
        if value is not MISSING:
            commute_mode = str(value)

    child_count = 0
    if params.get("children_count_field"):
        value = get_context_value_or_missing(row_context, params["children_count_field"])
        if value is not MISSING and isinstance(value, int) and not isinstance(value, bool):
            child_count = value

    sector_type = None
    if params.get("sector_type_field"):
        value = get_context_value_or_missing(row_context, params["sector_type_field"])
        if value is not MISSING:
            sector_type = str(value)

    employer_scale = None
    if params.get("employer_scale_field"):
        value = get_context_value_or_missing(row_context, params["employer_scale_field"])
        if value is not MISSING:
            employer_scale = str(value)

    income_bracket = None
    if params.get("income_bracket_field"):
        value = get_context_value_or_missing(row_context, params["income_bracket_field"])
        if value is not MISSING:
            income_bracket = normalize_income_bracket_label(str(value))

    row_locale = resolve_row_locale(row_context)
    locale_kind = locale_family(row_locale)
    localized_profession = localize_narrative_term(profession, locale_kind=locale_kind, category="profession")
    life_stage = infer_life_stage(age_value)
    normalized_work = (work_pattern_value or "").strip().lower()
    coordination_phrase = build_routine_coordination_phrase(
        profession=profession,
        sector_type=sector_type,
        employer_scale=employer_scale,
        locale_kind=locale_kind,
    )

    if life_stage == "retired" or "retired" in normalized_work:
        if locale_kind == "nl":
            return {
                "wake_time": "07:30",
                "work_pattern": "retired routine",
                "weekday_rhythm": "een rustigere ochtend, afspraken of boodschappen, en tijd voor persoonlijke interesses",
                "evening_habits": "een rustige maaltijd, lokale televisie en een vroegere avond",
                "weekend_rhythm": "familiebezoeken, lokale uitstappen en een lichter huishoudritme",
            }
        if locale_kind == "fr":
            return {
                "wake_time": "07:30",
                "work_pattern": "retired routine",
                "weekday_rhythm": "une matinee plus lente, quelques rendez-vous ou courses, et du temps pour des centres d'interet personnels",
                "evening_habits": "un repas calme, la television locale et une soiree plus tot",
                "weekend_rhythm": "visites a la famille, sorties de proximite et rythme domestique plus leger",
            }
        return {
            "wake_time": "07:30",
            "work_pattern": "retired routine",
            "weekday_rhythm": "a slower morning, appointments or errands, and time for personal interests",
            "evening_habits": "a calm meal, local television, and an earlier night",
            "weekend_rhythm": "family visits, local outings, and a lighter household schedule",
        }

    if "shift" in normalized_work:
        if locale_kind == "nl":
            weekday = "wisselende starturen, strakke logistiek en herstel tussen veeleisende werkblokken"
            if child_count > 0:
                weekday = "wisselende starturen, afstemming rond kinderzorg en herstel tussen veeleisende werkblokken"
            return {
                "wake_time": "05:30",
                "work_pattern": "shift-based schedule",
                "weekday_rhythm": weekday,
                "evening_habits": "afstemming rond maaltijden, decompressie en een vroeger herstelmoment",
                "weekend_rhythm": "rust, praktische boodschappen en een gepland sociaal of familiaal moment",
            }
        if locale_kind == "fr":
            weekday = "horaires de debut variables, logistique tres serree et recuperation entre des blocs de travail exigeants"
            if child_count > 0:
                weekday = "horaires de debut variables, coordination autour de la garde des enfants et recuperation entre des blocs de travail exigeants"
            return {
                "wake_time": "05:30",
                "work_pattern": "shift-based schedule",
                "weekday_rhythm": weekday,
                "evening_habits": "coordination des repas, decompression et fenetre de recuperation plus precoce",
                "weekend_rhythm": "repos, courses pratiques et un moment social ou familial planifie",
            }
        weekday = "variable start times, tightly managed logistics, and recovery between demanding work blocks"
        if child_count > 0:
            weekday = "variable start times, childcare coordination, and recovery between demanding work blocks"
        return {
            "wake_time": "05:30",
            "work_pattern": "shift-based schedule",
            "weekday_rhythm": weekday,
            "evening_habits": "meal coordination, decompression, and an earlier recovery window",
            "weekend_rhythm": "rest, practical errands, and one planned social or family moment",
        }

    if "part-time" in normalized_work:
        if locale_kind == "nl":
            return {
                "wake_time": "06:45" if child_count > 0 else "07:00",
                "work_pattern": "part-time schedule",
                "weekday_rhythm": "compacte werkblokken in balans met huishoudtaken en lokale boodschappen",
                "evening_habits": "gedeelde maaltijden, praktische planning en lichtere schermtijd",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="gezinsactiviteiten, boodschappen en ruimte voor een trager tempo",
                    locale_kind=locale_kind,
                ),
            }
        if locale_kind == "fr":
            return {
                "wake_time": "06:45" if child_count > 0 else "07:00",
                "work_pattern": "part-time schedule",
                "weekday_rhythm": "blocs de travail compresses en equilibre avec les taches domestiques et les courses de proximite",
                "evening_habits": "repas partages, planification pratique et temps d'ecran plus leger",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="activites familiales, courses et place pour un rythme plus lent",
                    locale_kind=locale_kind,
                ),
            }
        return {
            "wake_time": "06:45" if child_count > 0 else "07:00",
            "work_pattern": "part-time schedule",
            "weekday_rhythm": "compressed work blocks balanced with household tasks and local errands",
            "evening_habits": "shared meals, practical planning, and lighter screen time",
            "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                income_bracket=income_bracket,
                default_weekend="family activities, errands, and room for a slower pace",
                locale_kind=locale_kind,
            ),
        }

    if "remote" in normalized_work:
        if locale_kind == "nl":
            return {
                "wake_time": "07:00" if child_count == 0 else "06:40",
                "work_pattern": "remote work routine",
                "weekday_rhythm": "thuis gebaseerde werkblokken afgewisseld met huishoudtaken en korte resetmomenten",
                "evening_habits": "een duidelijke schermpauze, avondeten thuis en rustigere ontspanning",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="lokale plannen, sociale bijpraatmomenten en een praktische reset voor de volgende week",
                    locale_kind=locale_kind,
                ),
            }
        if locale_kind == "fr":
            return {
                "wake_time": "07:00" if child_count == 0 else "06:40",
                "work_pattern": "remote work routine",
                "weekday_rhythm": "blocs de travail a domicile ponctues de taches domestiques et de courts moments de respiration",
                "evening_habits": "une vraie coupure avec les ecrans, le diner a la maison et un temps plus calme",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="plans de proximite, retrouvailles sociales et remise en ordre pratique pour la semaine suivante",
                    locale_kind=locale_kind,
                ),
            }
        return {
            "wake_time": "07:00" if child_count == 0 else "06:40",
            "work_pattern": "remote work routine",
            "weekday_rhythm": "home-based focused work blocks separated by household tasks and short reset moments",
            "evening_habits": "a clear break from screens, dinner at home, and quieter downtime",
            "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                income_bracket=income_bracket,
                default_weekend="local plans, social catch-ups, and a practical reset for the week ahead",
                locale_kind=locale_kind,
            ),
        }

    if "field" in normalized_work or "on-site" in normalized_work or "onsite" in normalized_work:
        if locale_kind == "nl":
            weekday = "verplaatsingen naar werkplekken, praktische afstemming en een fysieker dagritme"
            if child_count > 0:
                weekday = "vroege vertrekken, praktische afstemming en een strak geregelde gezinsoverdracht na het werk op locatie"
            elif employer_scale == "local SME":
                weekday = "verplaatsingen naar werkplekken, praktische afstemming in een kleiner team en een fysieker dagritme"
            elif sector_type == "public sector":
                weekday = "verplaatsingen naar publiekgerichte locaties, ingeplande afstemming en een strak gestructureerd dagritme"
            return {
                "wake_time": "05:50" if child_count > 0 else "06:05",
                "work_pattern": "on-site schedule",
                "weekday_rhythm": weekday,
                "evening_habits": "avondeten, decompressie en een rustiger herstelmoment na een actievere dag",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="klusjes in huis, boodschappen en een sociaal of familiaal bezoek",
                    locale_kind=locale_kind,
                ),
            }
        if locale_kind == "fr":
            weekday = "deplacements vers les lieux de travail, coordination pratique et rythme de jour plus physique"
            if child_count > 0:
                weekday = "departs matinaux, coordination pratique et relais familial tres serre apres le travail sur site"
            elif employer_scale == "local SME":
                weekday = "deplacements vers les lieux de travail, coordination tres concrete dans une petite equipe et rythme plus physique"
            elif sector_type == "public sector":
                weekday = "deplacements vers des sites au contact du public, coordination planifiee et rythme de jour tres structure"
            return {
                "wake_time": "05:50" if child_count > 0 else "06:05",
                "work_pattern": "on-site schedule",
                "weekday_rhythm": weekday,
                "evening_habits": "diner, decompression et fenetre de recuperation plus calme apres une journee plus active",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="entretien du logement, courses et une visite sociale ou familiale",
                    locale_kind=locale_kind,
                ),
            }
        weekday = "travel to work sites, practical coordination, and a more physical daytime rhythm"
        if child_count > 0:
            weekday = "early departures, practical coordination, and a tightly managed family handoff after on-site work"
        elif employer_scale == "local SME":
            weekday = "travel to work sites, hands-on coordination across a smaller team, and a more physical daytime rhythm"
        elif sector_type == "public sector":
            weekday = "travel to public-facing sites, scheduled coordination, and a tightly structured daytime rhythm"
        return {
            "wake_time": "05:50" if child_count > 0 else "06:05",
            "work_pattern": "on-site schedule",
            "weekday_rhythm": weekday,
            "evening_habits": "dinner, decompression, and a quieter recovery window after a more active day",
            "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                income_bracket=income_bracket,
                default_weekend="home maintenance, errands, and one social or family visit",
                locale_kind=locale_kind,
            ),
        }

    if "hybrid" in normalized_work or (not normalized_work and life_stage in {"mid_career", "established_adult"}):
        if locale_kind == "nl":
            commute_fragment = "een mix van kantoor- en thuiswerkblokken"
            if commute_mode == "train":
                commute_fragment = (
                    "school- of huishoudafstemming rond een treinrit" if child_count > 0 else "een treinrit met vaste kantoordagen"
                )
            elif commute_mode == "car":
                commute_fragment = "verplaatsingen en planning rond een werkdag met de auto"
            elif commute_mode == "bike":
                commute_fragment = "korte actieve verplaatsingen en lokaal gestructureerde werkblokken"
            return {
                "wake_time": "06:30" if child_count > 0 else "06:50",
                "work_pattern": "hybrid office schedule",
                "weekday_rhythm": f"{commute_fragment}, {coordination_phrase}, en een voorspelbare avondoverdracht",
                "evening_habits": "avondeten, planning voor de volgende dag en licht streamen of lezen",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="sport, boodschappen en familiebezoeken" if child_count > 0 else "boodschappen, beweging en een flexibeler sociaal ritme",
                    locale_kind=locale_kind,
                ),
            }
        if locale_kind == "fr":
            commute_fragment = "une alternance de blocs de travail au bureau et a domicile"
            if commute_mode == "train":
                commute_fragment = (
                    "coordination scolaire ou domestique autour d'un trajet en train" if child_count > 0 else "un trajet en train avec des jours de bureau bien cadres"
                )
            elif commute_mode == "car":
                commute_fragment = "deplacements et planification autour d'une journee de travail en voiture"
            elif commute_mode == "bike":
                commute_fragment = "courts trajets actifs et blocs de travail structures a proximite"
            return {
                "wake_time": "06:30" if child_count > 0 else "06:50",
                "work_pattern": "hybrid office schedule",
                "weekday_rhythm": f"{commute_fragment}, {coordination_phrase}, et un relais du soir previsible",
                "evening_habits": "diner, planification du lendemain et un peu de streaming ou de lecture",
                "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                    income_bracket=income_bracket,
                    default_weekend="sport, courses et visites a la famille" if child_count > 0 else "courses, activite physique et rythme social plus souple",
                    locale_kind=locale_kind,
                ),
            }
        commute_fragment = "mixed office and home-based work blocks"
        if commute_mode == "train":
            commute_fragment = "school or household coordination around a train-led commute" if child_count > 0 else "a train-led commute with structured office days"
        elif commute_mode == "car":
            commute_fragment = "commuting and planning around a car-led workday"
        elif commute_mode == "bike":
            commute_fragment = "short active commutes and locally structured work blocks"
        return {
            "wake_time": "06:30" if child_count > 0 else "06:50",
            "work_pattern": "hybrid office schedule",
            "weekday_rhythm": f"{commute_fragment}, {coordination_phrase}, and a predictable evening handoff",
            "evening_habits": "dinner, planning for the next day, and light streaming or reading",
            "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                income_bracket=income_bracket,
                default_weekend="sports, errands, and visits with relatives" if child_count > 0 else "errands, exercise, and a more flexible social rhythm",
                locale_kind=locale_kind,
            ),
        }

    if locale_kind == "nl":
        profession_fragment = f" rond {localized_profession}" if localized_profession else ""
        commute_fragment = ""
        if commute_mode == "train":
            commute_fragment = "een treinrit, " if child_count == 0 else "afstemming rond een treinrit, "
        elif commute_mode == "car":
            commute_fragment = "verplaatsingen rond een werkdag met de auto, "
        elif commute_mode == "bike":
            commute_fragment = "korte actieve verplaatsingen, "
        return {
            "wake_time": "07:10",
            "work_pattern": "structured daytime schedule",
            "weekday_rhythm": f"{commute_fragment}vaste dagverplichtingen{profession_fragment}, {coordination_phrase}, en een regelmatige avondreset",
            "evening_habits": "een maaltijd thuis, lichtere administratie en bescheiden ontspanning",
            "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                income_bracket=income_bracket,
                default_weekend="praktische taken, een sociaal plan en wat ongestructureerde rust",
                locale_kind=locale_kind,
            ),
        }
    if locale_kind == "fr":
        profession_fragment = f" autour du role de {localized_profession}" if localized_profession else ""
        commute_fragment = ""
        if commute_mode == "train":
            commute_fragment = "un trajet en train, " if child_count == 0 else "de la coordination autour d'un trajet en train, "
        elif commute_mode == "car":
            commute_fragment = "des deplacements autour d'une journee de travail en voiture, "
        elif commute_mode == "bike":
            commute_fragment = "de courts trajets actifs, "
        return {
            "wake_time": "07:10",
            "work_pattern": "structured daytime schedule",
            "weekday_rhythm": f"{commute_fragment}des engagements reguliers en journee{profession_fragment}, {coordination_phrase}, et une remise a plat du soir assez reguliere",
            "evening_habits": "un repas a la maison, un peu d'administratif leger et des loisirs modestes",
            "weekend_rhythm": build_income_sensitive_weekend_rhythm(
                income_bracket=income_bracket,
                default_weekend="taches pratiques, un plan social et un peu de temps moins structure",
                locale_kind=locale_kind,
            ),
        }
    profession_fragment = f" around {profession}" if profession else ""
    commute_fragment = ""
    if commute_mode == "train":
        commute_fragment = "a train-led commute, " if child_count == 0 else "coordination around a train-led commute, "
    elif commute_mode == "car":
        commute_fragment = "commuting around a car-led workday, "
    elif commute_mode == "bike":
        commute_fragment = "short active commutes, "
    return {
        "wake_time": "07:10",
        "work_pattern": "structured daytime schedule",
        "weekday_rhythm": f"{commute_fragment}steady daytime commitments{profession_fragment}, {coordination_phrase}, and a regular evening reset",
        "evening_habits": "a home meal, lighter administration, and modest entertainment",
        "weekend_rhythm": build_income_sensitive_weekend_rhythm(
            income_bracket=income_bracket,
            default_weekend="practical tasks, one social plan, and some unstructured downtime",
            locale_kind=locale_kind,
        ),
    }


SUPPORTED_CONDITION_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "exists", "truthy", "falsy"}


def normalize_condition(raw_condition, *, field_label: str) -> dict | None:
    if raw_condition is None:
        return None
    if not isinstance(raw_condition, dict):
        raise SkillError(f"{field_label} must be an object when provided.")

    if "all" in raw_condition:
        items = raw_condition["all"]
        if not isinstance(items, list) or not items:
            raise SkillError(f"{field_label}.all must be a non-empty array.")
        return {"all": [normalize_condition(item, field_label=f"{field_label}.all[{index}]") for index, item in enumerate(items)]}

    if "any" in raw_condition:
        items = raw_condition["any"]
        if not isinstance(items, list) or not items:
            raise SkillError(f"{field_label}.any must be a non-empty array.")
        return {"any": [normalize_condition(item, field_label=f"{field_label}.any[{index}]") for index, item in enumerate(items)]}

    if "not" in raw_condition:
        return {"not": normalize_condition(raw_condition["not"], field_label=f"{field_label}.not")}

    path = raw_condition.get("path")
    op = raw_condition.get("op", "eq")
    if not isinstance(path, str) or not path.strip():
        raise SkillError(f"{field_label} requires a non-empty 'path' unless it uses all/any/not.")
    if op not in SUPPORTED_CONDITION_OPS:
        allowed = ", ".join(sorted(SUPPORTED_CONDITION_OPS))
        raise SkillError(f"{field_label} uses unsupported op {op!r}. Allowed: {allowed}.")

    normalized = {"path": path, "op": op}
    if op not in {"exists", "truthy", "falsy"}:
        if "value" not in raw_condition:
            raise SkillError(f"{field_label} with op {op!r} requires 'value'.")
        normalized["value"] = raw_condition["value"]
    return normalized


def normalize_correlation_assignment(raw_assignment, *, rule_label: str, index: int) -> dict:
    if not isinstance(raw_assignment, dict):
        raise SkillError(f"{rule_label} assignment #{index} must be an object.")
    path = raw_assignment.get("path")
    if not isinstance(path, str) or not path.strip():
        raise SkillError(f"{rule_label} assignment #{index} requires a non-empty path.")

    has_value = "value" in raw_assignment
    has_choices = "choices" in raw_assignment
    if has_value == has_choices:
        raise SkillError(f"{rule_label} assignment #{index} must define exactly one of 'value' or 'choices'.")

    assignment = {"path": path}
    if has_value:
        assignment["value"] = raw_assignment["value"]
        return assignment

    choices = raw_assignment["choices"]
    if not isinstance(choices, list) or not choices:
        raise SkillError(f"{rule_label} assignment #{index} choices must be a non-empty array.")
    assignment["choices"] = choices
    weights = raw_assignment.get("weights")
    if weights is not None:
        if not isinstance(weights, list) or len(weights) != len(choices):
            raise SkillError(f"{rule_label} assignment #{index} weights must match the number of choices.")
        if any((not isinstance(weight, (int, float)) or weight <= 0) for weight in weights):
            raise SkillError(f"{rule_label} assignment #{index} weights must contain positive numbers.")
        assignment["weights"] = weights
    return assignment


def normalize_source_backed_match(raw_match, *, rule_label: str, index: int) -> dict:
    if not isinstance(raw_match, dict):
        raise SkillError(f"{rule_label} source_model.match_on entry #{index} must be an object.")
    path = raw_match.get("path")
    segment_key = raw_match.get("segment_key")
    if not isinstance(path, str) or not path.strip():
        raise SkillError(f"{rule_label} source_model.match_on entry #{index} requires a non-empty path.")
    if not isinstance(segment_key, str) or not segment_key.strip():
        raise SkillError(f"{rule_label} source_model.match_on entry #{index} requires a non-empty segment_key.")
    return {"path": path, "segment_key": segment_key}


def normalize_source_backed_assignment(raw_assignment, *, rule_label: str, index: int) -> dict:
    if not isinstance(raw_assignment, dict):
        raise SkillError(f"{rule_label} source_model.assign_from_segment entry #{index} must be an object.")
    path = raw_assignment.get("path")
    segment_key = raw_assignment.get("segment_key")
    if not isinstance(path, str) or not path.strip():
        raise SkillError(f"{rule_label} source_model.assign_from_segment entry #{index} requires a non-empty path.")
    if not isinstance(segment_key, str) or not segment_key.strip():
        raise SkillError(
            f"{rule_label} source_model.assign_from_segment entry #{index} requires a non-empty segment_key."
        )
    return {"path": path, "segment_key": segment_key}


def normalize_correlation_source_model(raw_source_model, *, rule_label: str) -> dict:
    if not isinstance(raw_source_model, dict):
        raise SkillError(f"{rule_label} source_model must be an object.")

    raw_segments = raw_source_model.get("segments")
    raw_source_query = raw_source_model.get("source_query")
    if raw_segments is not None and raw_source_query is not None:
        raise SkillError(f"{rule_label} source_model must define either segments or source_query, not both.")
    if raw_segments is None and raw_source_query is None:
        raise SkillError(f"{rule_label} source_model must define either segments or source_query.")

    if raw_source_query is not None:
        source_query = normalize_population_source_query(raw_source_query)
        raw_segments = build_segments_from_source_query(source_query)
        segment_origin = "source_query"
    else:
        source_query = None
        raw_segments = normalize_population_segments(raw_segments)
        segment_origin = "explicit_segments"

    filters = normalize_population_filters(raw_source_model.get("filters", {}))
    filtered_segments = apply_population_filters(raw_segments, filters)
    match_on = raw_source_model.get("match_on", [])
    assign_from_segment = raw_source_model.get("assign_from_segment")
    if not isinstance(match_on, list):
        raise SkillError(f"{rule_label} source_model.match_on must be an array when provided.")
    if not isinstance(assign_from_segment, list) or not assign_from_segment:
        raise SkillError(f"{rule_label} source_model.assign_from_segment must be a non-empty array.")

    return {
        "segment_origin": segment_origin,
        "source_query": source_query,
        "filters": filters,
        "segments": filtered_segments,
        "match_on": [
            normalize_source_backed_match(item, rule_label=rule_label, index=index)
            for index, item in enumerate(match_on, start=1)
        ],
        "assign_from_segment": [
            normalize_source_backed_assignment(item, rule_label=rule_label, index=index)
            for index, item in enumerate(assign_from_segment, start=1)
        ],
    }


def normalize_correlation_rules(raw_rules) -> list[dict]:
    if raw_rules is None:
        return []
    if not isinstance(raw_rules, list):
        raise SkillError("'correlation_rules' must be an array when provided.")

    normalized = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, dict):
            raise SkillError(f"Correlation rule #{index} must be an object.")
        rule_label = f"Correlation rule #{index}"
        assignments = raw_rule.get("assignments")
        source_model = raw_rule.get("source_model")
        if assignments is None and source_model is None:
            raise SkillError(f"{rule_label} requires either assignments or source_model.")
        if assignments is not None and source_model is not None:
            raise SkillError(f"{rule_label} must not define both assignments and source_model.")

        normalized_rule = {
            "name": raw_rule.get("name", f"rule_{index}"),
            "when": normalize_condition(raw_rule.get("when"), field_label=f"{rule_label} when"),
        }
        if assignments is not None:
            if not isinstance(assignments, list) or not assignments:
                raise SkillError(f"{rule_label} requires a non-empty assignments array.")
            normalized_rule["assignments"] = [
                normalize_correlation_assignment(item, rule_label=rule_label, index=assignment_index)
                for assignment_index, item in enumerate(assignments, start=1)
            ]
        else:
            normalized_rule["source_model"] = normalize_correlation_source_model(source_model, rule_label=rule_label)
        normalized.append(normalized_rule)
    return normalized


def normalize_contradiction_checks(raw_checks) -> list[dict]:
    if raw_checks is None:
        return []
    if not isinstance(raw_checks, list):
        raise SkillError("'contradiction_checks' must be an array when provided.")

    normalized = []
    for index, raw_check in enumerate(raw_checks, start=1):
        if not isinstance(raw_check, dict):
            raise SkillError(f"Contradiction check #{index} must be an object.")
        message = raw_check.get("message")
        if not isinstance(message, str) or not message.strip():
            raise SkillError(f"Contradiction check #{index} requires a non-empty message.")
        timeline_assertions = normalize_timeline_assertions(
            raw_check.get("timeline_assertions", []),
            check_label=f"Contradiction check #{index}",
        )
        normalized.append(
            {
                "name": raw_check.get("name", f"contradiction_{index}"),
                "when": normalize_condition(raw_check.get("when"), field_label=f"Contradiction check #{index} when"),
                "timeline_assertions": timeline_assertions,
                "message": message,
            }
        )
    return normalized


def normalize_archetype_requests(raw_archetypes) -> list[dict]:
    if raw_archetypes is None:
        return []
    if not isinstance(raw_archetypes, list):
        raise SkillError("'archetypes' must be an array when provided.")

    normalized = []
    for index, raw_archetype in enumerate(raw_archetypes, start=1):
        if isinstance(raw_archetype, str):
            name = raw_archetype
            when = None
        elif isinstance(raw_archetype, dict):
            name = raw_archetype.get("name")
            when = normalize_condition(raw_archetype.get("when"), field_label=f"Archetype #{index} when")
        else:
            raise SkillError(f"Archetype #{index} must be a string or object.")

        if not isinstance(name, str) or not name.strip():
            raise SkillError(f"Archetype #{index} requires a non-empty name.")
        normalized.append({"name": name, "when": when})
    return normalized


def normalize_timeline_event_selector(raw_selector, *, label: str) -> dict:
    if not isinstance(raw_selector, dict):
        raise SkillError(f"{label} must be an object.")
    category = raw_selector.get("category")
    title = raw_selector.get("title")
    if category is None and title is None:
        raise SkillError(f"{label} requires at least 'category' or 'title'.")
    if category is not None and (not isinstance(category, str) or not category.strip()):
        raise SkillError(f"{label}.category must be a non-empty string when provided.")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise SkillError(f"{label}.title must be a non-empty string when provided.")
    normalized = {}
    if category is not None:
        normalized["category"] = category
    if title is not None:
        normalized["title"] = title
    return normalized


def normalize_timeline_assertions(raw_assertions, *, check_label: str) -> list[dict]:
    if raw_assertions is None:
        return []
    if not isinstance(raw_assertions, list):
        raise SkillError(f"{check_label} timeline_assertions must be an array when provided.")

    normalized = []
    for index, raw_assertion in enumerate(raw_assertions, start=1):
        if not isinstance(raw_assertion, dict):
            raise SkillError(f"{check_label} timeline assertion #{index} must be an object.")
        assertion_type = raw_assertion.get("type")
        if assertion_type not in {"event_exists", "ordered_events", "minimum_age_at_event", "maximum_age_at_event", "minimum_gap_between_events"}:
            raise SkillError(
                f"{check_label} timeline assertion #{index} uses unsupported type {assertion_type!r}."
            )

        timeline_field = raw_assertion.get("timeline_field", "life_timeline")
        if not isinstance(timeline_field, str) or not timeline_field.strip():
            raise SkillError(f"{check_label} timeline assertion #{index} requires a non-empty timeline_field.")

        normalized_assertion = {
            "type": assertion_type,
            "timeline_field": timeline_field,
        }

        if assertion_type == "event_exists":
            normalized_assertion["event"] = normalize_timeline_event_selector(
                raw_assertion.get("event"),
                label=f"{check_label} timeline assertion #{index} event",
            )
        elif assertion_type == "ordered_events":
            first_event = normalize_timeline_event_selector(
                raw_assertion.get("first_event"),
                label=f"{check_label} timeline assertion #{index} first_event",
            )
            second_event = normalize_timeline_event_selector(
                raw_assertion.get("second_event"),
                label=f"{check_label} timeline assertion #{index} second_event",
            )
            allow_same_day = raw_assertion.get("allow_same_day", True)
            if not isinstance(allow_same_day, bool):
                raise SkillError(f"{check_label} timeline assertion #{index} allow_same_day must be a boolean.")
            normalized_assertion["first_event"] = first_event
            normalized_assertion["second_event"] = second_event
            normalized_assertion["allow_same_day"] = allow_same_day
        elif assertion_type == "minimum_age_at_event":
            event = normalize_timeline_event_selector(
                raw_assertion.get("event"),
                label=f"{check_label} timeline assertion #{index} event",
            )
            birth_date_field = raw_assertion.get("birth_date_field", "identity.birth_date")
            min_age = raw_assertion.get("min_age")
            if not isinstance(birth_date_field, str) or not birth_date_field.strip():
                raise SkillError(f"{check_label} timeline assertion #{index} requires a non-empty birth_date_field.")
            if not isinstance(min_age, int) or isinstance(min_age, bool) or min_age < 0:
                raise SkillError(f"{check_label} timeline assertion #{index} requires a non-negative integer min_age.")
            normalized_assertion["event"] = event
            normalized_assertion["birth_date_field"] = birth_date_field
            normalized_assertion["min_age"] = min_age
        elif assertion_type == "maximum_age_at_event":
            event = normalize_timeline_event_selector(
                raw_assertion.get("event"),
                label=f"{check_label} timeline assertion #{index} event",
            )
            birth_date_field = raw_assertion.get("birth_date_field", "identity.birth_date")
            max_age = raw_assertion.get("max_age")
            if not isinstance(birth_date_field, str) or not birth_date_field.strip():
                raise SkillError(f"{check_label} timeline assertion #{index} requires a non-empty birth_date_field.")
            if not isinstance(max_age, int) or isinstance(max_age, bool) or max_age < 0:
                raise SkillError(f"{check_label} timeline assertion #{index} requires a non-negative integer max_age.")
            normalized_assertion["event"] = event
            normalized_assertion["birth_date_field"] = birth_date_field
            normalized_assertion["max_age"] = max_age
        elif assertion_type == "minimum_gap_between_events":
            first_event = normalize_timeline_event_selector(
                raw_assertion.get("first_event"),
                label=f"{check_label} timeline assertion #{index} first_event",
            )
            second_event = normalize_timeline_event_selector(
                raw_assertion.get("second_event"),
                label=f"{check_label} timeline assertion #{index} second_event",
            )
            min_gap_days = raw_assertion.get("min_gap_days")
            if not isinstance(min_gap_days, int) or isinstance(min_gap_days, bool) or min_gap_days < 0:
                raise SkillError(f"{check_label} timeline assertion #{index} requires a non-negative integer min_gap_days.")
            normalized_assertion["first_event"] = first_event
            normalized_assertion["second_event"] = second_event
            normalized_assertion["min_gap_days"] = min_gap_days

        normalized.append(normalized_assertion)
    return normalized


def normalize_source_query_filters(raw_filters) -> dict:
    if raw_filters is None:
        return {}
    if not isinstance(raw_filters, dict):
        raise SkillError("'population_model.source_query.filters' must be an object when provided.")

    normalized = {}
    for column_name, raw_spec in raw_filters.items():
        if not isinstance(column_name, str) or not column_name.strip():
            raise SkillError("Each source-query filter key must be a non-empty string.")

        if isinstance(raw_spec, dict):
            op = raw_spec.get("op", "eq")
            value = raw_spec.get("value")
        elif isinstance(raw_spec, list):
            op = "in"
            value = raw_spec
        else:
            op = "eq"
            value = raw_spec

        if op not in SUPPORTED_SOURCE_FILTER_OPS:
            allowed = ", ".join(sorted(SUPPORTED_SOURCE_FILTER_OPS))
            raise SkillError(f"Source-query filter {column_name!r} uses unsupported op {op!r}. Allowed: {allowed}.")

        if op == "in":
            if not isinstance(value, list) or not value:
                raise SkillError(f"Source-query filter {column_name!r} with op 'in' requires a non-empty array value.")
            normalized_values = []
            for item in value:
                if not is_scalar(item):
                    raise SkillError(
                        f"Source-query filter {column_name!r} only supports string, number, or boolean values."
                    )
                normalized_values.append(item)
            normalized[column_name] = {"op": op, "value": normalized_values}
            continue

        if not is_scalar(value):
            raise SkillError(f"Source-query filter {column_name!r} must use a string, number, or boolean value.")
        normalized[column_name] = {"op": op, "value": value}

    return normalized


def normalize_population_source_query(raw_source_query) -> dict:
    if not isinstance(raw_source_query, dict):
        raise SkillError("'population_model.source_query' must be an object when provided.")

    catalog_id = raw_source_query.get("catalog_id")
    base_url = raw_source_query.get("base_url")
    if catalog_id is None and base_url is None:
        raise SkillError("'population_model.source_query' requires either 'catalog_id' or 'base_url'.")
    if catalog_id is not None and (not isinstance(catalog_id, str) or not catalog_id.strip()):
        raise SkillError("'population_model.source_query.catalog_id' must be a non-empty string when provided.")
    if base_url is not None and (not isinstance(base_url, str) or not base_url.strip()):
        raise SkillError("'population_model.source_query.base_url' must be a non-empty string when provided.")

    dataset = raw_source_query.get("dataset")
    if not isinstance(dataset, str) or not dataset.strip():
        raise SkillError("'population_model.source_query.dataset' must be a non-empty string.")

    weight_column = raw_source_query.get("weight_column", "MS_VALUE")
    if not isinstance(weight_column, str) or not weight_column.strip():
        raise SkillError("'population_model.source_query.weight_column' must be a non-empty string when provided.")

    dimension_columns = raw_source_query.get("dimension_columns")
    if not isinstance(dimension_columns, dict) or not dimension_columns:
        raise SkillError("'population_model.source_query.dimension_columns' must be a non-empty object.")

    normalized_dimension_columns = {}
    for dimension_name, column_name in dimension_columns.items():
        if not isinstance(dimension_name, str) or not dimension_name.strip():
            raise SkillError("Each source-query dimension name must be a non-empty string.")
        if not isinstance(column_name, str) or not column_name.strip():
            raise SkillError(f"Source-query dimension {dimension_name!r} must map to a non-empty column name.")
        normalized_dimension_columns[dimension_name] = column_name

    raw_value_maps = raw_source_query.get("dimension_value_maps", {})
    if raw_value_maps is None:
        raw_value_maps = {}
    if not isinstance(raw_value_maps, dict):
        raise SkillError("'population_model.source_query.dimension_value_maps' must be an object when provided.")

    normalized_value_maps = {}
    for dimension_name, raw_mapping in raw_value_maps.items():
        if dimension_name not in normalized_dimension_columns:
            raise SkillError(
                f"Source-query value map {dimension_name!r} does not match any configured source-query dimension."
            )
        if not isinstance(raw_mapping, dict) or not raw_mapping:
            raise SkillError(f"Source-query value map for {dimension_name!r} must be a non-empty object.")

        normalized_mapping = {}
        for raw_value, mapped_value in raw_mapping.items():
            if not is_scalar(mapped_value):
                raise SkillError(
                    f"Source-query value map for {dimension_name!r} only supports string, number, or boolean outputs."
                )
            normalized_mapping[str(raw_value)] = mapped_value
        normalized_value_maps[dimension_name] = normalized_mapping

    timeout_sec = raw_source_query.get("timeout_sec", DEFAULT_NETWORK_TIMEOUT_SEC)
    if not isinstance(timeout_sec, int) or isinstance(timeout_sec, bool) or timeout_sec < 1:
        raise SkillError("'population_model.source_query.timeout_sec' must be a positive integer when provided.")

    return {
        "catalog_id": catalog_id,
        "base_url": base_url,
        "dataset": dataset,
        "weight_column": weight_column,
        "dimension_columns": normalized_dimension_columns,
        "dimension_value_maps": normalized_value_maps,
        "filters": normalize_source_query_filters(raw_source_query.get("filters", {})),
        "timeout_sec": timeout_sec,
    }


def get_open_data_source_by_id(source_id: str, open_data_sources: dict | None = None) -> dict:
    open_data_sources = open_data_sources or load_open_data_sources()
    for source in open_data_sources.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise SkillError(f"Open-data source {source_id!r} is not present in references/open_data_sources.json.")


def resolve_source_query_base_url(source_query: dict, open_data_sources: dict | None = None) -> str:
    if source_query.get("base_url"):
        return source_query["base_url"].rstrip("/")

    source = get_open_data_source_by_id(source_query["catalog_id"], open_data_sources=open_data_sources)
    source_url = source.get("url")
    if not isinstance(source_url, str) or not source_url.strip():
        raise SkillError(f"Open-data source {source_query['catalog_id']!r} is missing a usable 'url'.")
    return source_url.rstrip("/")


def format_source_filter_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_source_filter_expression(filter_spec: dict) -> str:
    op = filter_spec["op"]
    if op == "in":
        values = ",".join(format_source_filter_value(item) for item in filter_spec["value"])
        return f"in.({values})"
    return f"{op}.{format_source_filter_value(filter_spec['value'])}"


def fetch_json_url(url: str, *, timeout_sec: int = DEFAULT_NETWORK_TIMEOUT_SEC):
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise SkillError(f"Failed to fetch remote JSON from {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SkillError(f"Timed out while fetching remote JSON from {url}.") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SkillError(f"Remote endpoint {url} did not return valid JSON.") from exc


def build_source_query_url(source_query: dict, *, open_data_sources: dict | None = None) -> str:
    base_url = resolve_source_query_base_url(source_query, open_data_sources=open_data_sources)
    dataset_path = source_query["dataset"]
    if not dataset_path.startswith("/"):
        dataset_path = f"/{dataset_path}"

    select_columns = unique_preserving_order(
        list(source_query["dimension_columns"].values()) + [source_query["weight_column"]]
    )
    params = {
        "select": ",".join(select_columns),
    }
    for column_name, filter_spec in source_query["filters"].items():
        params[column_name] = build_source_filter_expression(filter_spec)

    query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"{base_url}{dataset_path}?{query_string}"


def coerce_numeric_weight(value, *, label: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise SkillError(f"{label} must be numeric; received {value!r}.") from exc
    raise SkillError(f"{label} must be numeric; received {value!r}.")


def build_segments_from_source_query(source_query: dict, *, open_data_sources: dict | None = None) -> list[dict]:
    source_url = build_source_query_url(source_query, open_data_sources=open_data_sources)
    rows = fetch_json_url(source_url, timeout_sec=source_query["timeout_sec"])

    if not isinstance(rows, list):
        raise SkillError(f"Source query {source_url} did not return a JSON array.")

    dimension_names = list(source_query["dimension_columns"].keys())
    aggregated = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SkillError(f"Source query row #{index} is not an object.")

        values = {}
        for dimension_name, column_name in source_query["dimension_columns"].items():
            if column_name not in row:
                raise SkillError(
                    f"Source query row #{index} is missing required column {column_name!r} for dimension {dimension_name!r}."
                )
            raw_value = row[column_name]
            mapped_value = source_query["dimension_value_maps"].get(dimension_name, {}).get(str(raw_value), raw_value)
            if not is_scalar(mapped_value):
                raise SkillError(
                    f"Source query dimension {dimension_name!r} produced unsupported mapped value {mapped_value!r}."
                )
            values[dimension_name] = mapped_value

        if source_query["weight_column"] not in row:
            raise SkillError(
                f"Source query row #{index} is missing weight column {source_query['weight_column']!r}."
            )
        weight = coerce_numeric_weight(
            row[source_query["weight_column"]],
            label=f"Source query weight column {source_query['weight_column']!r}",
        )
        if weight <= 0:
            continue

        key = tuple((dimension_name, values[dimension_name]) for dimension_name in dimension_names)
        if key not in aggregated:
            aggregated[key] = {
                "weight": 0.0,
                "values": values,
            }
        aggregated[key]["weight"] += weight

    if not aggregated:
        raise SkillError("Source query produced no positive-weight segments.")

    normalized_segments = []
    for aggregated_segment in aggregated.values():
        normalized_segments.append(
            {
                "weight": aggregated_segment["weight"],
                "values": aggregated_segment["values"],
                "source": {
                    "catalog_id": source_query.get("catalog_id"),
                    "dataset": source_query["dataset"],
                    "query_url": source_url,
                },
            }
        )

    return normalize_population_segments(normalized_segments)


def parse_iso_date(value: str, *, field_label: str) -> date:
    if not isinstance(value, str):
        raise SkillError(f"{field_label} must be an ISO date string.")

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SkillError(f"{field_label} must be a valid ISO date in YYYY-MM-DD format.") from exc


def normalize_population_filters(raw_filters) -> dict:
    if raw_filters is None:
        return {}
    if not isinstance(raw_filters, dict):
        raise SkillError("'population_model.filters' must be an object when provided.")

    normalized = {}
    for key, raw_value in raw_filters.items():
        if not isinstance(key, str) or not key.strip():
            raise SkillError("Each population filter key must be a non-empty string.")

        if isinstance(raw_value, list):
            if not raw_value:
                raise SkillError(f"Population filter {key!r} must not be an empty array.")
            values = raw_value
        else:
            values = [raw_value]

        normalized_values = []
        for value in values:
            if not is_scalar(value):
                raise SkillError(
                    f"Population filter {key!r} only supports string, number, or boolean values."
                )
            normalized_values.append(value)
        normalized[key] = normalized_values

    return normalized


def normalize_population_dimensions(raw_dimensions) -> list[dict]:
    if raw_dimensions is None:
        return []
    if not isinstance(raw_dimensions, list):
        raise SkillError("'population_model.dimensions' must be an array when provided.")

    normalized = []
    seen = set()
    for index, dimension in enumerate(raw_dimensions, start=1):
        if not isinstance(dimension, dict):
            raise SkillError(f"Population dimension #{index} must be an object.")

        name = dimension.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SkillError(f"Population dimension #{index} is missing a valid 'name'.")
        if name in seen:
            raise SkillError(f"Duplicate population dimension name: {name!r}")

        represented = dimension.get("represented", True)
        if not isinstance(represented, bool):
            raise SkillError(f"Population dimension {name!r} has invalid 'represented'; expected boolean.")

        source = dimension.get("source")
        if source is not None and not isinstance(source, dict):
            raise SkillError(f"Population dimension {name!r} has invalid 'source'; expected an object.")

        description = dimension.get("description")
        if description is not None and not isinstance(description, str):
            raise SkillError(f"Population dimension {name!r} has invalid 'description'; expected a string.")

        normalized_dimension = {
            "name": name,
            "represented": represented,
        }
        if source is not None:
            normalized_dimension["source"] = source
        if description is not None:
            normalized_dimension["description"] = description

        normalized.append(normalized_dimension)
        seen.add(name)

    return normalized


def normalize_population_segments(raw_segments) -> list[dict]:
    if not isinstance(raw_segments, list) or not raw_segments:
        raise SkillError("'population_model.segments' must be a non-empty array.")

    normalized = []
    for index, segment in enumerate(raw_segments, start=1):
        if not isinstance(segment, dict):
            raise SkillError(f"Population segment #{index} must be an object.")

        weight = segment.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight <= 0:
            raise SkillError(f"Population segment #{index} must define a positive numeric 'weight'.")

        values = segment.get("values")
        if not isinstance(values, dict) or not values:
            raise SkillError(f"Population segment #{index} must define a non-empty 'values' object.")

        normalized_values = {}
        for key, value in values.items():
            if not isinstance(key, str) or not key.strip():
                raise SkillError(f"Population segment #{index} contains an invalid value key.")
            if not is_scalar(value):
                raise SkillError(
                    f"Population segment #{index} value {key!r} must be a string, number, or boolean."
                )
            normalized_values[key] = value

        normalized_segment = {
            "weight": float(weight),
            "values": normalized_values,
        }

        label = segment.get("label")
        if label is not None:
            if not isinstance(label, str):
                raise SkillError(f"Population segment #{index} has invalid 'label'; expected a string.")
            normalized_segment["label"] = label

        source = segment.get("source")
        if source is not None:
            if not isinstance(source, dict):
                raise SkillError(f"Population segment #{index} has invalid 'source'; expected an object.")
            normalized_segment["source"] = source

        normalized.append(normalized_segment)

    return normalized


def segment_matches_filters(values: dict, filters: dict) -> bool:
    for key, allowed_values in filters.items():
        if key not in values or values[key] not in allowed_values:
            return False
    return True


def apply_population_filters(segments: list[dict], filters: dict) -> list[dict]:
    filtered = [segment for segment in segments if segment_matches_filters(segment["values"], filters)]
    if not filtered:
        raise SkillError("Population filters removed all population segments.")

    total_weight = sum(segment["weight"] for segment in filtered)
    normalized = []
    for segment in filtered:
        normalized_segment = dict(segment)
        normalized_segment["normalized_weight"] = segment["weight"] / total_weight
        normalized.append(normalized_segment)
    return normalized


def normalize_population_model(raw_population_model) -> dict | None:
    if raw_population_model is None:
        return None
    if not isinstance(raw_population_model, dict):
        raise SkillError("'population_model' must be an object when provided.")

    scope = raw_population_model.get("scope", {})
    if scope is None:
        scope = {}
    if not isinstance(scope, dict):
        raise SkillError("'population_model.scope' must be an object when provided.")

    filters = normalize_population_filters(raw_population_model.get("filters", {}))
    dimensions = normalize_population_dimensions(raw_population_model.get("dimensions", []))
    raw_segments = raw_population_model.get("segments")
    raw_source_query = raw_population_model.get("source_query")
    if raw_segments is not None and raw_source_query is not None:
        raise SkillError("'population_model' must define either 'segments' or 'source_query', not both.")
    if raw_segments is None and raw_source_query is None:
        raise SkillError("'population_model' must define either 'segments' or 'source_query'.")

    source_query = None
    if raw_source_query is not None:
        source_query = normalize_population_source_query(raw_source_query)
        raw_segments = build_segments_from_source_query(source_query)
        segment_origin = "source_query"
    else:
        raw_segments = normalize_population_segments(raw_segments)
        segment_origin = "explicit"
    filtered_segments = apply_population_filters(raw_segments, filters)

    return {
        "scope": scope,
        "filters": filters,
        "dimensions": dimensions,
        "source_query": source_query,
        "segment_origin": segment_origin,
        "segments": filtered_segments,
        "segment_count_before_filters": len(raw_segments),
        "segment_count_after_filters": len(filtered_segments),
    }


def normalize_config(raw_config: dict) -> dict:
    if not isinstance(raw_config, dict):
        raise SkillError("Config must be a JSON object.")

    locale = raw_config.get("locale", "en_US")
    if not isinstance(locale, str) or not locale.strip():
        raise SkillError("'locale' must be a string when provided.")

    records = raw_config.get("records")
    if not isinstance(records, int) or records < 1:
        raise SkillError("'records' must be an integer greater than or equal to 1.")

    fields = raw_config.get("fields")
    sql_schema = normalize_sql_schema(raw_config.get("sql_schema"), locale=locale)
    if fields is None:
        if sql_schema is None:
            raise SkillError("'fields' must be a non-empty array unless 'sql_schema' is provided.")
        fields = sql_schema["derived_fields"]
    if not isinstance(fields, list) or not fields:
        raise SkillError("'fields' must be a non-empty array.")

    output = raw_config.get("output")
    legacy_format = raw_config.get("output_format")
    legacy_file = raw_config.get("output_file")

    if output is not None and not isinstance(output, dict):
        raise SkillError("'output' must be an object when provided.")

    output_format = None
    output_path = None
    if output:
        output_format = output.get("format")
        output_path = output.get("path")

    output_format = output_format or legacy_format or "csv"
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        allowed = ", ".join(sorted(SUPPORTED_OUTPUT_FORMATS))
        raise SkillError(f"'output.format' must be one of: {allowed}. Received: {output_format!r}")

    output_path = output_path or legacy_file or DEFAULT_OUTPUT_NAME[output_format]
    output_table_name = None
    output_title = None
    output_include_sensitive_fields = None
    if output:
        output_table_name = output.get("table_name")
        output_title = output.get("title")
        output_include_sensitive_fields = output.get("include_sensitive_fields")
    if output_title is not None and (not isinstance(output_title, str) or not output_title.strip()):
        raise SkillError("'output.title' must be a non-empty string when provided.")
    if output_include_sensitive_fields is not None and not isinstance(output_include_sensitive_fields, bool):
        raise SkillError("'output.include_sensitive_fields' must be a boolean when provided.")
    if output_table_name is None and sql_schema is not None:
        output_table_name = sql_schema["table_name"]
    if output_format == "sql" and (not isinstance(output_table_name, str) or not output_table_name.strip()):
        raise SkillError("'output.table_name' is required for SQL output unless it can be derived from 'sql_schema'.")
    population_model = normalize_population_model(raw_config.get("population_model"))
    correlation_rules = normalize_correlation_rules(raw_config.get("correlation_rules", []))
    contradiction_checks = normalize_contradiction_checks(raw_config.get("contradiction_checks", []))
    archetypes = normalize_archetype_requests(raw_config.get("archetypes", []))

    normalized_fields = []
    seen_names = set()
    for index, field in enumerate(fields, start=1):
        if not isinstance(field, dict):
            raise SkillError(f"Field #{index} must be an object.")

        name = field.get("name")
        field_type = field.get("type")
        params = field.get("params", {})

        if not isinstance(name, str) or not name.strip():
            raise SkillError(f"Field #{index} is missing a valid 'name'.")
        if name in seen_names:
            raise SkillError(f"Duplicate field name: {name!r}")
        if not isinstance(field_type, str) or not field_type.strip():
            raise SkillError(f"Field {name!r} is missing a valid 'type'.")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise SkillError(f"Field {name!r} has invalid 'params'; expected an object.")

        normalized_fields.append(
            {
                "name": name,
                "type": field_type,
                "params": params,
                "when": normalize_condition(field.get("when"), field_label=f"Field {name!r} when"),
            }
        )
        seen_names.add(name)

    return {
        "version": raw_config.get("version", "1.0"),
        "locale": locale,
        "seed": raw_config.get("seed"),
        "records": records,
        "population_model": population_model,
        "correlation_rules": correlation_rules,
        "contradiction_checks": contradiction_checks,
        "archetypes": archetypes,
        "sql_schema": sql_schema,
        "output": {
            "format": output_format,
            "path": output_path,
            "table_name": output_table_name,
            "title": output_title.strip() if isinstance(output_title, str) else None,
            "include_sensitive_fields": output_include_sensitive_fields if output_include_sensitive_fields is not None else False,
        },
        "fields": normalized_fields,
    }


def validate_nested_field_definition(raw_field: dict, *, container_label: str) -> dict:
    if not isinstance(raw_field, dict):
        raise SkillError(f"{container_label} must be an object.")

    field_name = raw_field.get("name", "_value")
    field_type = raw_field.get("type")
    params = raw_field.get("params", {})
    if not isinstance(field_name, str) or not field_name.strip():
        raise SkillError(f"{container_label} is missing a valid 'name'.")
    if not isinstance(field_type, str) or not field_type.strip():
        raise SkillError(f"{container_label} is missing a valid 'type'.")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise SkillError(f"{container_label} has invalid 'params'; expected an object.")
    return {
        "name": field_name,
        "type": field_type,
        "params": params,
        "when": normalize_condition(raw_field.get("when"), field_label=f"{container_label} when"),
    }


def derive_catalog_locales(config_locale: str) -> list[str]:
    locales = []
    if isinstance(config_locale, str) and config_locale.strip():
        locales.append(config_locale)
        if "_" in config_locale:
            locales.append(config_locale.split("_", 1)[1])
    return locales


def validate_faker_provider(fake: Faker, provider_name: str, *, field_name: str) -> None:
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise SkillError(f"Field {field_name!r} must reference a valid Faker provider name.")

    provider = getattr(fake, provider_name, None)
    if provider is None or not callable(provider):
        raise SkillError(f"Field {field_name!r} references unsupported Faker provider {provider_name!r}.")


def validate_age_band_mapping(field_name: str, band_name: str, band_definition: dict) -> None:
    if not isinstance(band_definition, dict):
        raise SkillError(
            f"Field {field_name!r} has invalid custom age-band mapping for {band_name!r}; expected an object."
        )

    min_age = band_definition.get("min_age")
    max_age = band_definition.get("max_age")
    if (
        not isinstance(min_age, int)
        or isinstance(min_age, bool)
        or not isinstance(max_age, int)
        or isinstance(max_age, bool)
        or min_age < 0
        or max_age < min_age
    ):
        raise SkillError(
            f"Field {field_name!r} custom age-band {band_name!r} must define integer min_age/max_age with min_age <= max_age."
        )


def validate_field(fake: Faker, field: dict, custom_formats: dict, population_model: dict | None) -> None:
    field_type = field["type"]
    params = field["params"]
    name = field["name"]

    if field_type == "literal":
        if "value" not in params:
            raise SkillError(f"Field {name!r} of type 'literal' requires params.value.")
        return

    if field_type == "choice":
        values = params.get("values")
        if not isinstance(values, list) or not values:
            raise SkillError(f"Field {name!r} of type 'choice' requires a non-empty params.values array.")
        weights = params.get("weights")
        if weights is not None:
            if not isinstance(weights, list) or len(weights) != len(values):
                raise SkillError(f"Field {name!r} of type 'choice' requires params.weights to match params.values length.")
            if any((not isinstance(weight, (int, float)) or weight <= 0) for weight in weights):
                raise SkillError(f"Field {name!r} of type 'choice' requires params.weights to contain positive numbers.")
        return

    if field_type == "number_int":
        min_value = params.get("min", 0)
        max_value = params.get("max", 100)
        if not isinstance(min_value, int) or not isinstance(max_value, int) or min_value > max_value:
            raise SkillError(f"Field {name!r} has an invalid integer range.")
        return

    if field_type == "number_float":
        min_value = params.get("min", 0)
        max_value = params.get("max", 100)
        precision = params.get("precision", 2)
        if not isinstance(min_value, (int, float)) or not isinstance(max_value, (int, float)) or min_value > max_value:
            raise SkillError(f"Field {name!r} has an invalid float range.")
        if not isinstance(precision, int) or precision < 0:
            raise SkillError(f"Field {name!r} has an invalid precision.")
        return

    if field_type == "date_between":
        return

    if field_type == "child_birth_date_from_parent":
        parent_birth_date_field = params.get("parent_birth_date_field")
        if not isinstance(parent_birth_date_field, str) or not parent_birth_date_field.strip():
            raise SkillError(f"Field {name!r} of type 'child_birth_date_from_parent' requires params.parent_birth_date_field.")
        for key, default in [("min_child_age", 0), ("max_child_age", 25), ("min_parent_age_at_birth", 16), ("max_parent_age_at_birth", 60)]:
            value = params.get(key, default)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected a non-negative integer.")
        if params.get("min_child_age", 0) > params.get("max_child_age", 25):
            raise SkillError(f"Field {name!r} has min_child_age greater than max_child_age.")
        if params.get("min_parent_age_at_birth", 16) > params.get("max_parent_age_at_birth", 60):
            raise SkillError(f"Field {name!r} has min_parent_age_at_birth greater than max_parent_age_at_birth.")
        profile = params.get("profile")
        if profile is not None and (not isinstance(profile, str) or not profile.strip()):
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        for key, default in [("min_spacing_days", 0), ("max_spacing_years_between_siblings", 10)]:
            value = params.get(key, default)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected a non-negative integer.")
        reference_date = params.get("reference_date")
        if reference_date is not None:
            parse_iso_date(reference_date, field_label=f"Field {name!r} params.reference_date")
        return

    if field_type == "catalog_choice":
        catalog_name = params.get("catalog")
        return_key = params.get("return", "value")
        profile = params.get("profile")
        if not isinstance(catalog_name, str) or not catalog_name.strip():
            raise SkillError(f"Field {name!r} of type 'catalog_choice' requires params.catalog.")
        if not isinstance(return_key, str) or not return_key.strip():
            raise SkillError(f"Field {name!r} of type 'catalog_choice' requires a non-empty params.return when provided.")
        if profile is not None and (not isinstance(profile, str) or not profile.strip()):
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        filters = params.get("filters", {})
        if filters is None:
            filters = {}
        if not isinstance(filters, dict):
            raise SkillError(f"Field {name!r} has invalid params.filters; expected an object.")
        filter_from_fields = params.get("filter_from_fields", {})
        if filter_from_fields is None:
            filter_from_fields = {}
        if not isinstance(filter_from_fields, dict):
            raise SkillError(f"Field {name!r} has invalid params.filter_from_fields; expected an object.")
        for key, value in filter_from_fields.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
                raise SkillError(
                    f"Field {name!r} params.filter_from_fields must map non-empty catalog keys to non-empty field paths."
                )
        return

    if field_type == "profile_bundle":
        bundle_name = params.get("bundle")
        if not isinstance(bundle_name, str) or not bundle_name.strip():
            raise SkillError(f"Field {name!r} of type 'profile_bundle' requires params.bundle.")
        filters = params.get("filters", {})
        if filters is None:
            filters = {}
        if not isinstance(filters, dict):
            raise SkillError(f"Field {name!r} has invalid params.filters; expected an object.")
        filter_from_fields = params.get("filter_from_fields", {})
        if filter_from_fields is None:
            filter_from_fields = {}
        if not isinstance(filter_from_fields, dict):
            raise SkillError(f"Field {name!r} has invalid params.filter_from_fields; expected an object.")
        for key, value in filter_from_fields.items():
            if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
                raise SkillError(
                    f"Field {name!r} params.filter_from_fields must map non-empty bundle keys to non-empty field paths."
                )
        return

    if field_type == "age_from_birth_date":
        source_field = params.get("field")
        if not isinstance(source_field, str) or not source_field.strip():
            raise SkillError(f"Field {name!r} of type 'age_from_birth_date' requires params.field.")
        reference_date = params.get("reference_date")
        if reference_date is not None:
            parse_iso_date(reference_date, field_label=f"Field {name!r} params.reference_date")
        return

    if field_type == "pronouns_from_gender":
        gender_field = params.get("field")
        if not isinstance(gender_field, str) or not gender_field.strip():
            raise SkillError(f"Field {name!r} of type 'pronouns_from_gender' requires params.field.")
        return

    if field_type == "complementary_gender":
        gender_field = params.get("field")
        if not isinstance(gender_field, str) or not gender_field.strip():
            raise SkillError(f"Field {name!r} of type 'complementary_gender' requires params.field.")
        return

    if field_type == "birth_date_relative_to_field":
        anchor_field = params.get("anchor_birth_date_field")
        if not isinstance(anchor_field, str) or not anchor_field.strip():
            raise SkillError(f"Field {name!r} of type 'birth_date_relative_to_field' requires params.anchor_birth_date_field.")
        for key, default in [("min_years_offset", -5), ("max_years_offset", 5), ("min_age", 18), ("max_age", 92)]:
            value = params.get(key, default)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 and key in {"min_age", "max_age"}:
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected an integer.")
        if params.get("min_years_offset", -5) > params.get("max_years_offset", 5):
            raise SkillError(f"Field {name!r} has min_years_offset greater than max_years_offset.")
        if params.get("min_age", 18) > params.get("max_age", 92):
            raise SkillError(f"Field {name!r} has min_age greater than max_age.")
        reference_date = params.get("reference_date")
        if reference_date is not None:
            parse_iso_date(reference_date, field_label=f"Field {name!r} params.reference_date")
        return

    if field_type == "life_timeline":
        birth_date_field = params.get("birth_date_field")
        if not isinstance(birth_date_field, str) or not birth_date_field.strip():
            raise SkillError(f"Field {name!r} of type 'life_timeline' requires params.birth_date_field.")
        reference_date = params.get("reference_date")
        if reference_date is not None:
            parse_iso_date(reference_date, field_label=f"Field {name!r} params.reference_date")
        for optional_key in [
            "full_name_field",
            "education_level_field",
            "profession_field",
            "company_field",
            "marital_status_field",
            "spouse_field",
            "children_field",
            "city_field",
        ]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "persona_introduction":
        for required_key in ["full_name_field", "age_field", "profession_field"]:
            required_value = params.get(required_key)
            if not isinstance(required_value, str) or not required_value.strip():
                raise SkillError(f"Field {name!r} of type 'persona_introduction' requires params.{required_key}.")
        for optional_key in ["city_field", "industry_field", "neighborhood_type_field"]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "biography_from_timeline":
        timeline_field = params.get("timeline_field")
        if not isinstance(timeline_field, str) or not timeline_field.strip():
            raise SkillError(f"Field {name!r} of type 'biography_from_timeline' requires params.timeline_field.")
        style = params.get("style")
        if style is not None and (not isinstance(style, str) or not style.strip()):
            raise SkillError(f"Field {name!r} has invalid params.style; expected a non-empty string.")
        styles = params.get("styles")
        if styles is not None:
            if not isinstance(styles, list) or not styles or any(not isinstance(item, str) or not item.strip() for item in styles):
                raise SkillError(f"Field {name!r} has invalid params.styles; expected a non-empty string array.")
        for optional_key in [
            "full_name_field",
            "city_field",
            "education_level_field",
            "profession_field",
            "hobbies_field",
            "income_level_field",
            "housing_type_field",
            "ownership_status_field",
            "neighborhood_type_field",
            "marital_status_field",
            "spouse_field",
            "children_field",
        ]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "daily_routine_profile":
        age_field = params.get("age_field")
        if not isinstance(age_field, str) or not age_field.strip():
            raise SkillError(f"Field {name!r} of type 'daily_routine_profile' requires params.age_field.")
        for optional_key in [
            "profession_field",
            "work_pattern_field",
            "primary_commute_mode_field",
            "children_count_field",
            "income_bracket_field",
            "sector_type_field",
            "employer_scale_field",
        ]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "belgian_language_profile":
        for optional_key in ["region_field", "city_field"]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "belgian_education_profile":
        age_field = params.get("age_field")
        if not isinstance(age_field, str) or not age_field.strip():
            raise SkillError(f"Field {name!r} of type 'belgian_education_profile' requires params.age_field.")
        region_field = params.get("region_field")
        if region_field is not None and (not isinstance(region_field, str) or not region_field.strip()):
            raise SkillError(f"Field {name!r} has invalid params.region_field; expected a non-empty string.")
        profession_field = params.get("profession_field")
        if profession_field is not None and (not isinstance(profession_field, str) or not profession_field.strip()):
            raise SkillError(f"Field {name!r} has invalid params.profession_field; expected a non-empty string.")
        return

    if field_type == "belgian_company_name":
        profile = params.get("profile", "default")
        if not isinstance(profile, str) or not profile.strip():
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        for optional_key in [
            "industry_field",
            "region_field",
            "city_field",
            "collar_type_field",
            "work_pattern_field",
            "industry",
            "region",
            "city",
            "collar_type",
            "work_pattern",
        ]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "belgian_employer_component":
        component = params.get("component")
        if component not in {"company_name", "legal_form", "organization_type", "sector_type", "employer_scale"}:
            raise SkillError(
                f"Field {name!r} of type 'belgian_employer_component' requires params.component to be one of company_name, legal_form, organization_type, sector_type, or employer_scale."
            )
        profile = params.get("profile", "default")
        if not isinstance(profile, str) or not profile.strip():
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        for optional_key in [
            "industry_field",
            "region_field",
            "city_field",
            "collar_type_field",
            "work_pattern_field",
            "industry",
            "region",
            "city",
            "collar_type",
            "work_pattern",
        ]:
            optional_value = params.get(optional_key)
            if optional_value is not None and (not isinstance(optional_value, str) or not optional_value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{optional_key}; expected a non-empty string.")
        return

    if field_type == "template":
        template = params.get("template")
        if not isinstance(template, str) or not template:
            raise SkillError(f"Field {name!r} of type 'template' requires a non-empty params.template string.")
        return

    if field_type == "object":
        nested_fields = params.get("fields")
        if not isinstance(nested_fields, list) or not nested_fields:
            raise SkillError(f"Field {name!r} of type 'object' requires a non-empty params.fields array.")
        seen_nested_names = set()
        for index, nested_field in enumerate(nested_fields, start=1):
            normalized_nested = validate_nested_field_definition(
                nested_field,
                container_label=f"Field {name!r} nested field #{index}",
            )
            nested_name = normalized_nested["name"]
            if nested_name in seen_nested_names:
                raise SkillError(f"Field {name!r} has duplicate nested field name {nested_name!r}.")
            seen_nested_names.add(nested_name)
            validate_field(fake, normalized_nested, custom_formats, population_model)
        return

    if field_type == "array":
        count = params.get("count")
        count_from_field = params.get("count_from_field")
        if count is None and count_from_field is None:
            raise SkillError(f"Field {name!r} of type 'array' requires params.count or params.count_from_field.")
        if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 0):
            raise SkillError(f"Field {name!r} has invalid params.count; expected a non-negative integer.")
        if count_from_field is not None and (not isinstance(count_from_field, str) or not count_from_field.strip()):
            raise SkillError(f"Field {name!r} has invalid params.count_from_field; expected a non-empty string.")
        item_definition = params.get("item")
        normalized_item = validate_nested_field_definition(
            item_definition,
            container_label=f"Field {name!r} params.item",
        )
        validate_field(fake, normalized_item, custom_formats, population_model)
        return

    if field_type == "segment_value":
        key = params.get("key")
        if not isinstance(key, str) or not key.strip():
            raise SkillError(f"Field {name!r} of type 'segment_value' requires params.key.")
        if population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled segment value.")
        return

    if field_type == "birth_date_from_age_band":
        segment_key = params.get("segment_key")
        if not isinstance(segment_key, str) or not segment_key.strip():
            raise SkillError(f"Field {name!r} of type 'birth_date_from_age_band' requires params.segment_key.")

        bands = params.get("bands", {})
        if bands is None:
            bands = {}
        if not isinstance(bands, dict):
            raise SkillError(f"Field {name!r} has invalid params.bands; expected an object.")
        for band_name, band_definition in bands.items():
            validate_age_band_mapping(name, str(band_name), band_definition)

        default_max_age = params.get("default_max_age", 100)
        if not isinstance(default_max_age, int) or isinstance(default_max_age, bool) or default_max_age < 0:
            raise SkillError(f"Field {name!r} has invalid params.default_max_age; expected a non-negative integer.")

        reference_date = params.get("reference_date")
        if reference_date is not None:
            parse_iso_date(reference_date, field_label=f"Field {name!r} params.reference_date")

        if population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled age band.")
        return

    if field_type == "faker_from_segment":
        segment_key = params.get("segment_key")
        if not isinstance(segment_key, str) or not segment_key.strip():
            raise SkillError(f"Field {name!r} of type 'faker_from_segment' requires params.segment_key.")

        providers = params.get("providers")
        if not isinstance(providers, dict) or not providers:
            raise SkillError(f"Field {name!r} of type 'faker_from_segment' requires a non-empty params.providers object.")
        for provider_name in providers.values():
            validate_faker_provider(fake, provider_name, field_name=name)

        fallback_provider = params.get("fallback_provider")
        if fallback_provider is not None:
            validate_faker_provider(fake, fallback_provider, field_name=name)

        provider_params = params.get("provider_params", {})
        if not isinstance(provider_params, dict):
            raise SkillError(f"Field {name!r} has invalid params.provider_params; expected an object.")

        if population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled segment value.")
        return

    if field_type == "faker_from_field":
        source_field = params.get("field")
        if not isinstance(source_field, str) or not source_field.strip():
            raise SkillError(f"Field {name!r} of type 'faker_from_field' requires params.field.")

        providers = params.get("providers")
        if not isinstance(providers, dict) or not providers:
            raise SkillError(f"Field {name!r} of type 'faker_from_field' requires a non-empty params.providers object.")
        for provider_name in providers.values():
            validate_faker_provider(fake, provider_name, field_name=name)

        fallback_provider = params.get("fallback_provider")
        if fallback_provider is not None:
            validate_faker_provider(fake, fallback_provider, field_name=name)

        provider_params = params.get("provider_params", {})
        if not isinstance(provider_params, dict):
            raise SkillError(f"Field {name!r} has invalid params.provider_params; expected an object.")
        return

    if field_type == "faker_from_field":
        field_key = params.get("field")
        if not isinstance(field_key, str) or not field_key.strip():
            raise SkillError(f"Field {name!r} of type 'faker_from_field' requires params.field.")

        providers = params.get("providers")
        if not isinstance(providers, dict) or not providers:
            raise SkillError(f"Field {name!r} of type 'faker_from_field' requires a non-empty params.providers object.")
        for provider_name in providers.values():
            validate_faker_provider(fake, provider_name, field_name=name)

        fallback_provider = params.get("fallback_provider")
        if fallback_provider is not None:
            validate_faker_provider(fake, fallback_provider, field_name=name)

        provider_params = params.get("provider_params", {})
        if not isinstance(provider_params, dict):
            raise SkillError(f"Field {name!r} has invalid params.provider_params; expected an object.")
        return

    if field_type == "belgian_address_component":
        component = params.get("component")
        if component not in {"street_address", "postcode", "city", "province", "region", "locality_size"}:
            raise SkillError(
                f"Field {name!r} of type 'belgian_address_component' requires params.component to be one of street_address, postcode, city, province, region, or locality_size."
            )
        profile = params.get("profile", "default")
        if not isinstance(profile, str) or not profile.strip():
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        region_segment_key = params.get("region_segment_key")
        if region_segment_key is not None and (not isinstance(region_segment_key, str) or not region_segment_key.strip()):
            raise SkillError(f"Field {name!r} has invalid params.region_segment_key; expected a non-empty string.")
        for key in {"region", "province", "postcode_prefix", "city"}:
            value = params.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected a non-empty string.")
        for key in {"locality_min_size", "locality_max_size"}:
            value = params.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected a non-negative integer.")
        if region_segment_key is not None and population_model is None:
            raise SkillError(f"Field {name!r} requires 'population_model' because it reads a sampled region segment value.")
        load_belgian_address_catalog()
        return

    if field_type == "belgian_bank_account_component":
        component = params.get("component")
        if component not in {"bank_name", "bank_code", "swift_bic", "iban"}:
            raise SkillError(
                f"Field {name!r} of type 'belgian_bank_account_component' requires params.component to be one of bank_name, bank_code, swift_bic, or iban."
            )
        profile = params.get("profile", "default")
        if not isinstance(profile, str) or not profile.strip():
            raise SkillError(f"Field {name!r} has invalid params.profile; expected a non-empty string.")
        load_belgian_bank_catalog()
        return

    if field_type == "belgian_insz":
        for key in ("birth_date_field", "gender_field"):
            value = params.get(key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise SkillError(f"Field {name!r} has invalid params.{key}; expected a non-empty string when provided.")
        return

    if field_type == "belgian_eid":
        return

    if field_type in custom_formats:
        format_definition = custom_formats[field_type]
        if format_definition.get("type") != "regex" or "pattern" not in format_definition:
            raise SkillError(f"Custom format {field_type!r} must declare type='regex' and a pattern.")
        return

    if hasattr(fake, field_type):
        provider = getattr(fake, field_type)
        if not callable(provider):
            raise SkillError(f"Faker attribute {field_type!r} exists but is not callable.")
        return

    raise SkillError(f"Unsupported field type: {field_type!r}")


def build_fake(locale: str, seed: int | None) -> Faker:
    try:
        fake = Faker(locale)
    except Exception as exc:  # noqa: BLE001
        raise SkillError(f"Unsupported Faker locale: {locale!r}") from exc

    if seed is not None:
        if not isinstance(seed, int):
            raise SkillError("'seed' must be an integer when provided.")
        Faker.seed(seed)
        fake.seed_instance(seed)

    return fake


def random_birth_date(rng: random.Random, start_year: int = 1950, end_year: int = 2010) -> date:
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    offset = rng.randint(0, (end - start).days)
    return start + timedelta(days=offset)


def random_date_between(rng: random.Random, start: date, end: date) -> date:
    if start > end:
        raise SkillError("Date range is invalid because the start date is after the end date.")
    offset = rng.randint(0, (end - start).days)
    return start + timedelta(days=offset)


def shift_years_safe(value: date, years: int) -> date:
    target_year = value.year + years
    try:
        return value.replace(year=target_year)
    except ValueError:
        # Handle leap-day overflow by clamping to February 28.
        return value.replace(month=2, day=28, year=target_year)


def resolve_age_range_from_band(age_band, params: dict, field_name: str) -> tuple[int, int]:
    custom_bands = params.get("bands", {})
    age_band_key = str(age_band)
    if age_band_key in custom_bands:
        band_definition = custom_bands[age_band_key]
        return band_definition["min_age"], band_definition["max_age"]

    if not isinstance(age_band, str):
        raise SkillError(
            f"Field {field_name!r} expected a string age band in the sampled segment but received {age_band!r}."
        )

    normalized_age_band = age_band.strip().upper()
    if normalized_age_band == "TOTAL":
        raise SkillError(f"Field {field_name!r} cannot generate a birth date from the non-specific age band 'TOTAL'.")

    match = NUMERIC_AGE_BAND_PATTERN.match(normalized_age_band)
    if match:
        min_age, max_age = int(match.group(1)), int(match.group(2))
        if min_age > max_age:
            raise SkillError(f"Field {field_name!r} received an invalid age band {age_band!r}.")
        return min_age, max_age

    match = NUMERIC_AGE_PLUS_PATTERN.match(normalized_age_band)
    if match:
        min_age = int(match.group(1))
        max_age = params.get("default_max_age", 100)
        if max_age < min_age:
            raise SkillError(f"Field {field_name!r} has default_max_age smaller than the lower age bound in {age_band!r}.")
        return min_age, max_age

    match = STATBEL_AGE_BAND_PATTERN.match(normalized_age_band)
    if match:
        min_age, max_age = int(match.group(1)), int(match.group(2))
        return min_age, max_age

    match = STATBEL_AGE_PLUS_PATTERN.match(normalized_age_band)
    if match:
        min_age = int(match.group(1))
        max_age = params.get("default_max_age", 100)
        if max_age < min_age:
            raise SkillError(f"Field {field_name!r} has default_max_age smaller than the lower age bound in {age_band!r}.")
        return min_age, max_age

    match = STATBEL_AGE_GE_PATTERN.match(normalized_age_band)
    if match:
        min_age = int(match.group(1))
        max_age = params.get("default_max_age", max(min_age, 100))
        if max_age < min_age:
            raise SkillError(f"Field {field_name!r} has default_max_age smaller than the lower age bound in {age_band!r}.")
        return min_age, max_age

    match = STATBEL_AGE_LT_PATTERN.match(normalized_age_band)
    if match:
        upper_bound = int(match.group(1))
        if upper_bound <= 0:
            raise SkillError(f"Field {field_name!r} received an invalid age band {age_band!r}.")
        return 0, upper_bound - 1

    raise SkillError(
        f"Field {field_name!r} could not parse age band {age_band!r}. Provide params.bands for custom labels."
    )


def birth_date_for_age_range(
    rng: random.Random,
    *,
    min_age: int,
    max_age: int,
    reference_date: date,
) -> date:
    earliest_birth_date = shift_years_safe(reference_date, -(max_age + 1)) + timedelta(days=1)
    latest_birth_date = shift_years_safe(reference_date, -min_age)
    return random_date_between(rng, earliest_birth_date, latest_birth_date)


def infer_belgian_insz_sequence_parity(gender_value) -> int | None:
    if gender_value is MISSING or gender_value is None:
        return None
    normalized = str(gender_value).strip().lower()
    female_values = {"f", "female", "vrouw", "femme", "woman"}
    male_values = {"m", "male", "man", "homme"}
    if normalized in female_values:
        return 0
    if normalized in male_values:
        return 1
    return None


def compute_belgian_insz_checksum(birth_date: date, sequence_number: int) -> int:
    date_part = birth_date.strftime("%y%m%d")
    seq_part = f"{sequence_number:03d}"
    base_number_str = date_part + seq_part
    calc_base = int(("2" if birth_date.year >= 2000 else "") + base_number_str)
    checksum = 97 - (calc_base % 97)
    return checksum or 97


def generate_belgian_insz(
    rng: random.Random,
    *,
    birth_date: date | None = None,
    gender_value=None,
) -> str:
    birth_date = birth_date or random_birth_date(rng)
    date_part = birth_date.strftime("%y%m%d")
    parity = infer_belgian_insz_sequence_parity(gender_value)
    if parity is None:
        sequence_number = rng.randint(1, 999)
    else:
        start = 2 if parity == 0 else 1
        sequence_number = rng.randrange(start, 1000, 2)
    seq_part = f"{sequence_number:03d}"
    checksum = compute_belgian_insz_checksum(birth_date, sequence_number)
    return f"{date_part}-{seq_part}-{checksum:02d}"


def generate_belgian_eid(rng: random.Random) -> str:
    first_part = f"{rng.randint(0, 999):03d}"
    second_part = f"{rng.randint(0, 9_999_999):07d}"
    base_calc = int(first_part + second_part)
    checksum = base_calc % 97
    checksum = checksum or 97
    return f"{first_part}-{second_part}-{checksum:02d}"


def generate_belgian_iban_for_bank(rng: random.Random, bank_code: str) -> str:
    account_part = f"{rng.randint(0, 999_999_999):09d}"
    bban = f"{bank_code}{account_part}"
    checksum_seed = int(f"{bban}111400")
    checksum = 98 - (checksum_seed % 97)
    return f"BE{checksum:02d}{bban}"


def select_population_segment(rng: random.Random, population_model: dict | None) -> dict | None:
    if population_model is None:
        return None

    weights = [segment["normalized_weight"] for segment in population_model["segments"]]
    return rng.choices(population_model["segments"], weights=weights, k=1)[0]


def resolve_segment_value(segment_values: dict | None, key: str, field_name: str, default=MISSING):
    if segment_values is None:
        raise SkillError(f"Field {field_name!r} requires a sampled population segment, but no population model is active.")
    if key in segment_values:
        return segment_values[key]
    if default is not MISSING:
        return default
    raise SkillError(f"Field {field_name!r} could not find segment value {key!r} in the sampled population segment.")


def filter_belgian_address_catalog(
    addresses: list[dict],
    params: dict,
    *,
    segment_values: dict | None,
    field_name: str,
) -> list[dict]:
    filtered = list(addresses)

    region_value = params.get("region")
    region_segment_key = params.get("region_segment_key")
    if region_segment_key is not None:
        region_value = resolve_segment_value(segment_values, region_segment_key, field_name=field_name)
    if region_value is not None:
        filtered = [address for address in filtered if address["region"] == region_value]

    province_value = params.get("province")
    if province_value is not None:
        filtered = [address for address in filtered if address["province"] == province_value]

    postcode_prefix = params.get("postcode_prefix")
    if postcode_prefix is not None:
        filtered = [address for address in filtered if str(address["postcode"]).startswith(str(postcode_prefix))]

    city_value = params.get("city")
    if city_value is not None:
        filtered = [address for address in filtered if address["city"] == city_value]

    locality_min_size = params.get("locality_min_size")
    if locality_min_size is not None:
        filtered = [address for address in filtered if int(address.get("locality_size", 0)) >= locality_min_size]

    locality_max_size = params.get("locality_max_size")
    if locality_max_size is not None:
        filtered = [address for address in filtered if int(address.get("locality_size", 0)) <= locality_max_size]

    if not filtered:
        raise SkillError(f"Field {field_name!r} could not find any Belgian address catalog entries for the requested filters.")
    return filtered


def get_belgian_address_profile(
    rng: random.Random,
    params: dict,
    *,
    segment_values: dict | None,
    row_context: dict,
    field_name: str,
) -> dict:
    cache_key = f"belgian_address::{params.get('profile', 'default')}"
    cached = row_context.get(cache_key)
    if cached is not None:
        return cached

    addresses = load_belgian_address_catalog()
    filtered = filter_belgian_address_catalog(
        addresses,
        params,
        segment_values=segment_values,
        field_name=field_name,
    )
    weighted_localities = {}
    for address in filtered:
        locality_key = (address["region"], address["postcode"], address["city"])
        weighted_localities.setdefault(locality_key, {"weight": address.get("locality_weight", 1), "entries": []})
        weighted_localities[locality_key]["entries"].append(address)
    locality_keys = list(weighted_localities.keys())
    locality_weights = [weighted_localities[key]["weight"] for key in locality_keys]
    chosen_locality = rng.choices(locality_keys, weights=locality_weights, k=1)[0]
    chosen = rng.choice(weighted_localities[chosen_locality]["entries"])
    row_context[cache_key] = chosen
    return chosen


def get_belgian_bank_profile(
    rng: random.Random,
    params: dict,
    *,
    row_context: dict,
    field_name: str,
) -> dict:
    cache_key = f"belgian_bank::{params.get('profile', 'default')}"
    cached = row_context.get(cache_key)
    if cached is not None:
        return cached

    banks = load_belgian_bank_catalog()
    weights = [bank.get("weight", 1) for bank in banks]
    chosen = dict(rng.choices(banks, weights=weights, k=1)[0])
    chosen["iban"] = generate_belgian_iban_for_bank(rng, str(chosen["bank_code"]))
    row_context[cache_key] = chosen
    return chosen


def choose_weighted_value(rng: random.Random, weighted_values: dict[str, int | float]) -> str:
    values = list(weighted_values.keys())
    weights = list(weighted_values.values())
    return rng.choices(values, weights=weights, k=1)[0]


def choose_belgian_company_surnames(rng: random.Random, region: str | None) -> tuple[str, str]:
    pool = BELGIAN_COMPANY_SURNAMES.get(region or "", [])
    if len(pool) < 2:
        combined = []
        for region_pool in BELGIAN_COMPANY_SURNAMES.values():
            combined.extend(region_pool)
        pool = unique_preserve_order(combined)
    first, second = rng.sample(pool, 2)
    return first, second


def choose_belgian_company_token(rng: random.Random, industry: str | None, region: str | None) -> str:
    normalized_industry = str(industry or "").strip().lower()
    industry_tokens = BELGIAN_COMPANY_INDUSTRY_TOKENS.get(
        normalized_industry,
        BELGIAN_COMPANY_INDUSTRY_TOKENS["default"],
    )
    region_key = region if region in {"VLG", "WAL", "BXL"} else "BXL"
    tokens = industry_tokens.get(region_key) or industry_tokens.get("BXL") or industry_tokens.get("VLG")
    return rng.choice(tokens)


def infer_belgian_employer_shape(
    rng: random.Random,
    *,
    industry: str | None,
    collar_type: str | None,
    work_pattern: str | None,
) -> dict:
    normalized_industry = str(industry or "").strip().lower()
    normalized_collar = str(collar_type or "").strip().lower()
    normalized_work = str(work_pattern or "").strip().lower()

    if normalized_collar == "civil-service" or normalized_industry in {"education", "public administration"}:
        organization_type = "school network" if normalized_industry == "education" else "public service office"
        employer_scale = (
            "municipal or regional institution"
            if organization_type == "school network"
            else "regional public institution"
        )
        return {
            "sector_type": "public sector",
            "organization_type": organization_type,
            "employer_scale": employer_scale,
        }

    if normalized_industry in {"social services", "childcare"}:
        return {
            "sector_type": "nonprofit or community sector",
            "organization_type": "community service organization",
            "employer_scale": rng.choice(["local community organization", "regional support network"]),
        }

    if normalized_industry == "healthcare":
        sector_type = rng.choices(
            ["nonprofit or community sector", "private sector", "public sector"],
            weights=[55, 25, 20],
            k=1,
        )[0]
        organization_type = "care network" if sector_type != "private sector" else "care services group"
        return {
            "sector_type": sector_type,
            "organization_type": organization_type,
            "employer_scale": "regional care network",
        }

    if normalized_industry in {"construction", "home services", "facilities and hospitality", "hospitality"}:
        return {
            "sector_type": "private sector",
            "organization_type": "service firm",
            "employer_scale": "local SME",
        }

    if normalized_industry in {
        "retail",
        "wholesale and retail",
        "wholesale and distribution",
        "logistics",
        "transport and logistics",
    }:
        return {
            "sector_type": "private sector",
            "organization_type": "operating company",
            "employer_scale": "national or regional operator",
        }

    employer_scale = "regional mid-sized employer" if "hybrid" in normalized_work else "local or regional firm"
    return {
        "sector_type": "private sector",
        "organization_type": "office-based firm",
        "employer_scale": employer_scale,
    }


def choose_belgian_public_token(rng: random.Random, *, region: str | None, organization_type: str) -> str:
    region_key = region if region in {"VLG", "WAL", "BXL"} else "BXL"
    if organization_type == "school network":
        options = {
            "VLG": ["Stedelijk Leercentrum", "Onderwijscampus", "Scholennet"],
            "WAL": ["Reseau scolaire", "Campus public", "Centre d'enseignement"],
            "BXL": ["Education Hub", "Campus public", "Learning Campus"],
        }
    elif organization_type == "care network":
        options = {
            "VLG": ["Zorgnet", "Regionale Zorgdiensten", "Gezondheidsnet"],
            "WAL": ["Reseau sante", "Services de sante", "Pole de soins"],
            "BXL": ["Care Network", "Health Service", "Wellbeing Network"],
        }
    else:
        options = {
            "VLG": ["Stadsdiensten", "Gemeentediensten", "Publieke Dienst"],
            "WAL": ["Service public", "Services communaux", "Administration locale"],
            "BXL": ["Public Service", "Civic Service", "City Service"],
        }
    return rng.choice(options[region_key])


def choose_belgian_community_token(
    rng: random.Random,
    *,
    region: str | None,
    organization_type: str,
    industry: str | None,
) -> str:
    region_key = region if region in {"VLG", "WAL", "BXL"} else "BXL"
    if organization_type == "care network" or str(industry or "").strip().lower() == "healthcare":
        options = {
            "VLG": ["Zorgnet", "Care Services", "Gezondheidszorg"],
            "WAL": ["Reseau de soins", "Care Services", "Sante solidaire"],
            "BXL": ["Care Network", "Health Support", "Wellbeing Services"],
        }
    else:
        options = {
            "VLG": ["Buurtzorg", "Community Support", "Gezinszorg"],
            "WAL": ["Services sociaux", "Community Support", "Solidarite locale"],
            "BXL": ["Community Support", "Family Services", "Social Care"],
        }
    return rng.choice(options[region_key])


def build_belgian_company_core_name(
    rng: random.Random,
    *,
    region: str | None,
    city: str | None,
    first_surname: str,
    second_surname: str,
    token: str,
    industry: str | None,
    organization_type: str,
    sector_type: str,
) -> str:
    if sector_type == "public sector":
        public_token = choose_belgian_public_token(rng, region=region, organization_type=organization_type)
        patterns = []
        if city:
            patterns.extend([f"{public_token} {city}", f"{city} {public_token}"])
        patterns.append(f"{first_surname} {public_token}")
        return rng.choice(patterns)

    if sector_type == "nonprofit or community sector":
        community_token = choose_belgian_community_token(
            rng,
            region=region,
            organization_type=organization_type,
            industry=industry,
        )
        patterns = [f"{first_surname} {community_token}", f"{first_surname} & {second_surname} {community_token}"]
        if city:
            patterns.append(f"{city} {community_token}")
        return rng.choice(patterns)

    patterns = [f"{first_surname} {token}", f"{first_surname} & {second_surname} {token}"]
    if city:
        patterns.append(f"{city} {token}")
    if organization_type == "operating company":
        patterns.append(f"{city or first_surname} {token} Group")
    elif organization_type == "service firm":
        patterns.append(f"{first_surname} {token} Services")
    elif region == "VLG":
        patterns.append(f"{first_surname} {token} Groep")
    elif region == "WAL":
        patterns.append(f"Ateliers {first_surname} {token}")
    else:
        patterns.append(f"{first_surname} {token} Partners")
    return rng.choice(patterns)


def get_belgian_company_profile(
    fake: Faker,
    rng: random.Random,
    params: dict,
    *,
    row_context: dict,
    field_name: str,
) -> dict:
    del fake
    del field_name
    cache_key = f"belgian_company::{params.get('profile', 'default')}"
    cached = row_context.get(cache_key)
    if cached is not None:
        return cached

    region_value = params.get("region")
    if params.get("region_field"):
        resolved_region = get_context_value_or_missing(row_context, params["region_field"])
        if resolved_region is not MISSING:
            region_value = resolved_region

    city_value = params.get("city")
    if params.get("city_field"):
        resolved_city = get_context_value_or_missing(row_context, params["city_field"])
        if resolved_city is not MISSING:
            city_value = resolved_city

    industry_value = params.get("industry")
    if params.get("industry_field"):
        resolved_industry = get_context_value_or_missing(row_context, params["industry_field"])
        if resolved_industry is not MISSING:
            industry_value = resolved_industry

    collar_type_value = params.get("collar_type")
    if params.get("collar_type_field"):
        resolved_collar_type = get_context_value_or_missing(row_context, params["collar_type_field"])
        if resolved_collar_type is not MISSING:
            collar_type_value = resolved_collar_type

    work_pattern_value = params.get("work_pattern")
    if params.get("work_pattern_field"):
        resolved_work_pattern = get_context_value_or_missing(row_context, params["work_pattern_field"])
        if resolved_work_pattern is not MISSING:
            work_pattern_value = resolved_work_pattern

    region = normalize_belgian_region_label(region_value if isinstance(region_value, str) else None)
    if region is None:
        region = rng.choices(["VLG", "WAL", "BXL"], weights=[57, 32, 11], k=1)[0]

    employer_shape = infer_belgian_employer_shape(
        rng,
        industry=str(industry_value) if industry_value is not None else None,
        collar_type=str(collar_type_value) if collar_type_value is not None else None,
        work_pattern=str(work_pattern_value) if work_pattern_value is not None else None,
    )
    city = str(city_value).strip() if isinstance(city_value, str) and city_value.strip() else None
    token = choose_belgian_company_token(rng, str(industry_value) if industry_value is not None else None, region)
    first_surname, second_surname = choose_belgian_company_surnames(rng, region)
    if employer_shape["sector_type"] == "nonprofit or community sector":
        legal_form = choose_weighted_value(
            rng,
            BELGIAN_NONPROFIT_LEGAL_FORMS.get(region, BELGIAN_NONPROFIT_LEGAL_FORMS["default"]),
        )
    elif employer_shape["sector_type"] == "public sector":
        legal_form = None
    else:
        legal_form = choose_weighted_value(
            rng,
            BELGIAN_COMPANY_LEGAL_FORMS.get(region, BELGIAN_COMPANY_LEGAL_FORMS["default"]),
        )
    core_name = build_belgian_company_core_name(
        rng,
        region=region,
        city=city,
        first_surname=first_surname,
        second_surname=second_surname,
        token=token,
        industry=str(industry_value) if industry_value is not None else None,
        organization_type=employer_shape["organization_type"],
        sector_type=employer_shape["sector_type"],
    )
    chosen = {
        "company_name": f"{core_name} {legal_form}".strip() if legal_form else core_name,
        "region": region,
        "city": city,
        "industry": industry_value,
        "legal_form": legal_form,
        "organization_type": employer_shape["organization_type"],
        "sector_type": employer_shape["sector_type"],
        "employer_scale": employer_shape["employer_scale"],
    }
    row_context[cache_key] = chosen
    return chosen


def get_context_value_or_missing(row_context: dict | None, key: str):
    context = build_template_context(row_context)
    return context.get(key, MISSING)


def infer_pronouns_from_gender(gender_value, *, field_name: str) -> str:
    if gender_value is MISSING or gender_value is None:
        raise SkillError(f"Field {field_name!r} could not resolve gender for pronoun generation.")
    normalized = str(gender_value).strip().lower()
    female_values = {"f", "female", "vrouw", "femme", "woman"}
    male_values = {"m", "male", "man", "homme"}
    if normalized in female_values:
        return "she/her"
    if normalized in male_values:
        return "he/him"
    raise SkillError(f"Field {field_name!r} could not infer pronouns from gender value {gender_value!r}.")


def infer_complementary_gender(gender_value, *, field_name: str) -> str:
    if gender_value is MISSING or gender_value is None:
        raise SkillError(f"Field {field_name!r} could not resolve gender for complementary-gender generation.")
    normalized = str(gender_value).strip().lower()
    female_values = {"f", "female", "vrouw", "femme", "woman"}
    male_values = {"m", "male", "man", "homme"}
    if normalized in female_values:
        return "M"
    if normalized in male_values:
        return "F"
    raise SkillError(f"Field {field_name!r} could not infer a complementary gender from {gender_value!r}.")


def generate_logical_email(fake: Faker, rng: random.Random, row_context: dict | None) -> str:
    first_name = get_context_value_or_missing(row_context, "first_name")
    if first_name is MISSING:
        first_name = get_context_value_or_missing(row_context, "identity.first_name")
    last_name = get_context_value_or_missing(row_context, "last_name")
    if last_name is MISSING:
        last_name = get_context_value_or_missing(row_context, "identity.last_name")

    local_part = None
    if first_name is not MISSING and last_name is not MISSING:
        first_slug = slugify_text(first_name)
        last_slug = slugify_text(last_name)
        if first_slug and last_slug:
            patterns = [
                f"{first_slug}.{last_slug}",
                f"{first_slug}{last_slug}",
                f"{first_slug[0]}{last_slug}",
                f"{first_slug}.{last_slug[0]}",
            ]
            local_part = rng.choice(patterns)
            if rng.random() < 0.2:
                local_part = f"{local_part}{rng.randint(1, 99)}"

    if not local_part:
        local_part = slugify_text(fake.user_name()) or f"user{rng.randint(1000, 9999)}"

    domain = rng.choice(["example.com", "example.org", "example.net"])
    return f"{local_part}@{domain}"


def evaluate_condition(condition: dict | None, row_context: dict | None) -> bool:
    if condition is None:
        return True
    if "all" in condition:
        return all(evaluate_condition(item, row_context) for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(item, row_context) for item in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], row_context)

    actual = get_context_value_or_missing(row_context, condition["path"])
    op = condition["op"]
    if op == "exists":
        return actual is not MISSING
    if op == "truthy":
        return actual is not MISSING and bool(actual)
    if op == "falsy":
        return actual is MISSING or not bool(actual)
    if actual is MISSING:
        return False

    expected = condition["value"]
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "gt":
        return actual > expected
    if op == "gte":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "lte":
        return actual <= expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    raise SkillError(f"Unsupported condition op during evaluation: {op!r}")


def should_generate_field(field: dict, row_context: dict | None) -> bool:
    return evaluate_condition(field.get("when"), row_context)


def set_nested_path(target: dict, path: str, value) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        next_value = current.get(part)
        if next_value is None:
            next_value = {}
            current[part] = next_value
        if not isinstance(next_value, dict):
            raise SkillError(f"Cannot set nested path {path!r} because {part!r} is not an object.")
        current = next_value
    current[parts[-1]] = value


def choose_correlation_value(assignment: dict, rng: random.Random):
    if "value" in assignment:
        return assignment["value"]
    weights = assignment.get("weights")
    if weights is None:
        return rng.choice(assignment["choices"])
    return rng.choices(assignment["choices"], weights=weights, k=1)[0]


def get_generation_cache_bucket(state: dict | None, bucket_name: str) -> dict:
    if state is None:
        return {}
    bucket = state.get(bucket_name)
    if isinstance(bucket, dict):
        return bucket
    bucket = {}
    state[bucket_name] = bucket
    return bucket


def value_matches_allowed(actual_value, allowed_value) -> bool:
    if isinstance(actual_value, list):
        if isinstance(allowed_value, list):
            return any(item in actual_value for item in allowed_value)
        return allowed_value in actual_value
    if isinstance(allowed_value, list):
        return actual_value in allowed_value
    return actual_value == allowed_value


def choose_catalog_entry(
    catalog_name: str,
    *,
    config_locale: str,
    params: dict,
    row_context: dict | None,
    rng: random.Random,
    field_name: str,
) -> dict:
    catalogs_data = load_persona_catalogs()
    catalogs = catalogs_data.get("catalogs", {})
    if catalog_name not in catalogs:
        raise SkillError(f"Field {field_name!r} references unknown persona catalog {catalog_name!r}.")

    entries = catalogs[catalog_name]
    if not isinstance(entries, list) or not entries:
        raise SkillError(f"Persona catalog {catalog_name!r} must be a non-empty array.")

    allowed_locales = params.get("locales") or derive_catalog_locales(config_locale)
    filters = dict(params.get("filters", {}))
    for catalog_key, context_path in params.get("filter_from_fields", {}).items():
        context_value = get_context_value_or_missing(row_context, context_path)
        if context_value is not MISSING:
            filters[catalog_key] = context_value

    profile = params.get("profile")
    state = (row_context or {}).get("__state__") if isinstance(row_context, dict) else None
    cache_bucket = None
    cache_key = None
    if profile:
        cache_bucket = get_generation_cache_bucket(state, "catalog_choice_profiles")
        cache_key = json.dumps(
            {
                "catalog": catalog_name,
                "profile": profile,
                "locales": allowed_locales,
                "filters": filters,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        cached_entry = cache_bucket.get(cache_key)
        if cached_entry is not None:
            return cached_entry

    matching_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_locales = entry.get("locales", [])
        if allowed_locales:
            if not isinstance(entry_locales, list) or not any(locale in entry_locales for locale in allowed_locales):
                continue
        entry_matches = True
        for filter_key, allowed_value in filters.items():
            if filter_key not in entry or not value_matches_allowed(entry.get(filter_key), allowed_value):
                entry_matches = False
                break
        if entry_matches:
            matching_entries.append(entry)

    if not matching_entries:
        raise SkillError(
            f"Field {field_name!r} found no persona catalog entries in {catalog_name!r} for the requested locale/filters."
        )

    weights = [entry.get("weight", 1) for entry in matching_entries]
    chosen_entry = rng.choices(matching_entries, weights=weights, k=1)[0]
    if cache_bucket is not None and cache_key is not None:
        cache_bucket[cache_key] = chosen_entry
    return chosen_entry


def choose_profile_bundle(
    bundle_name: str,
    *,
    config_locale: str,
    params: dict,
    row_context: dict | None,
    rng: random.Random,
    field_name: str,
) -> dict:
    bundles_data = load_persona_profile_bundles()
    bundles = bundles_data.get("bundles", {})
    if bundle_name not in bundles:
        raise SkillError(f"Field {field_name!r} references unknown persona profile bundle {bundle_name!r}.")

    entries = bundles[bundle_name]
    if not isinstance(entries, list) or not entries:
        raise SkillError(f"Persona profile bundle {bundle_name!r} must be a non-empty array.")

    allowed_locales = params.get("locales") or derive_catalog_locales(config_locale)
    filters = dict(params.get("filters", {}))
    for bundle_key, context_path in params.get("filter_from_fields", {}).items():
        context_value = get_context_value_or_missing(row_context, context_path)
        if context_value is not MISSING:
            filters[bundle_key] = context_value

    matching_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_locales = entry.get("locales", [])
        if allowed_locales:
            if not isinstance(entry_locales, list) or not any(locale in entry_locales for locale in allowed_locales):
                continue
        entry_matches = True
        for filter_key, allowed_value in filters.items():
            if filter_key not in entry or not value_matches_allowed(entry.get(filter_key), allowed_value):
                entry_matches = False
                break
        if entry_matches:
            matching_entries.append(entry)

    if not matching_entries:
        raise SkillError(
            f"Field {field_name!r} found no persona profile bundle entries in {bundle_name!r} for the requested locale/filters."
        )

    weights = [entry.get("weight", 1) for entry in matching_entries]
    chosen = rng.choices(matching_entries, weights=weights, k=1)[0]
    profile = chosen.get("profile")
    if not isinstance(profile, dict):
        raise SkillError(f"Persona profile bundle {bundle_name!r} must provide an object profile.")
    return profile


def get_archetype_definition(archetype_name: str, *, field_name: str = "archetypes") -> dict:
    archetypes_data = load_persona_archetypes()
    archetypes = archetypes_data.get("archetypes", {})
    if archetype_name not in archetypes:
        raise SkillError(f"{field_name} references unknown persona archetype {archetype_name!r}.")
    definition = archetypes[archetype_name]
    if not isinstance(definition, dict):
        raise SkillError(f"Persona archetype {archetype_name!r} must be an object.")
    assignments = definition.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        raise SkillError(f"Persona archetype {archetype_name!r} must define a non-empty assignments array.")
    locales = definition.get("locales", [])
    if locales is not None and not isinstance(locales, list):
        raise SkillError(f"Persona archetype {archetype_name!r} has invalid locales; expected an array.")
    return definition


def archetype_matches_locale(definition: dict, *, config_locale: str) -> bool:
    locales = definition.get("locales", [])
    if not locales:
        return True
    allowed_locales = derive_catalog_locales(config_locale)
    return any(locale in locales for locale in allowed_locales)


def select_source_backed_segment(source_model: dict, row_context: dict | None, rng: random.Random) -> dict | None:
    matching_segments = []
    for segment in source_model["segments"]:
        matches = True
        for matcher in source_model["match_on"]:
            actual_value = get_context_value_or_missing(row_context, matcher["path"])
            if actual_value is MISSING:
                matches = False
                break
            if segment["values"].get(matcher["segment_key"]) != actual_value:
                matches = False
                break
        if matches:
            matching_segments.append(segment)

    if not matching_segments:
        return None

    weights = [segment["normalized_weight"] for segment in matching_segments]
    return rng.choices(matching_segments, weights=weights, k=1)[0]


def apply_correlation_rules(
    row: dict,
    correlation_rules: list[dict],
    rng: random.Random,
    *,
    state: dict | None = None,
) -> None:
    if not correlation_rules:
        return
    row_context = {"__root__": row, "__current__": row}
    assignment_cache = get_generation_cache_bucket(state, "correlation_assignments")
    source_segment_cache = get_generation_cache_bucket(state, "correlation_source_segments")
    for rule in correlation_rules:
        if not evaluate_condition(rule["when"], row_context):
            continue
        rule_name = str(rule.get("name") or "correlation_rule")
        if "assignments" in rule:
            for index, assignment in enumerate(rule["assignments"], start=1):
                cache_key = f"{rule_name}:{index}:{assignment['path']}"
                if cache_key not in assignment_cache:
                    assignment_cache[cache_key] = choose_correlation_value(assignment, rng)
                set_nested_path(row, assignment["path"], assignment_cache[cache_key])
            continue

        source_segment = source_segment_cache.get(rule_name)
        if source_segment is None:
            source_segment = select_source_backed_segment(rule["source_model"], row_context, rng)
            if source_segment is None:
                continue
            source_segment_cache[rule_name] = source_segment
        for assignment in rule["source_model"]["assign_from_segment"]:
            if assignment["segment_key"] not in source_segment["values"]:
                continue
            set_nested_path(row, assignment["path"], source_segment["values"][assignment["segment_key"]])


def apply_archetypes(
    row: dict,
    archetypes: list[dict],
    *,
    config_locale: str,
    rng: random.Random,
    state: dict | None = None,
) -> None:
    if not archetypes:
        return
    row_context = {"__root__": row, "__current__": row}
    assignment_cache = get_generation_cache_bucket(state, "archetype_assignments")
    for archetype in archetypes:
        if archetype["when"] is not None and not evaluate_condition(archetype["when"], row_context):
            continue
        definition = get_archetype_definition(archetype["name"])
        if not archetype_matches_locale(definition, config_locale=config_locale):
            continue
        for index, raw_assignment in enumerate(definition["assignments"], start=1):
            assignment = normalize_correlation_assignment(
                raw_assignment,
                rule_label=f"Archetype {archetype['name']!r}",
                index=index,
            )
            cache_key = f"{archetype['name']}:{index}:{assignment['path']}"
            if cache_key not in assignment_cache:
                assignment_cache[cache_key] = choose_correlation_value(assignment, rng)
            set_nested_path(row, assignment["path"], assignment_cache[cache_key])


def run_contradiction_checks(row: dict, contradiction_checks: list[dict]) -> None:
    if not contradiction_checks:
        return
    row_context = {"__root__": row, "__current__": row}
    failures = []
    for check in contradiction_checks:
        failed = False
        if check["when"] is not None and evaluate_condition(check["when"], row_context):
            failed = True
        if check["timeline_assertions"] and evaluate_timeline_assertions(check["timeline_assertions"], row_context):
            failed = True
        if failed:
            failures.append(check["message"])
    if failures:
        raise SkillError("Contradiction checks failed: " + "; ".join(failures))


def matches_timeline_selector(event: dict, selector: dict) -> bool:
    if "category" in selector and event.get("category") != selector["category"]:
        return False
    if "title" in selector and event.get("title") != selector["title"]:
        return False
    return True


def find_timeline_events(timeline: list[dict], selector: dict) -> list[dict]:
    return [event for event in timeline if isinstance(event, dict) and matches_timeline_selector(event, selector)]


def age_on_date(birth_date: date, event_date: date) -> int:
    return event_date.year - birth_date.year - (
        (event_date.month, event_date.day) < (birth_date.month, birth_date.day)
    )


def evaluate_timeline_assertions(assertions: list[dict], row_context: dict | None) -> bool:
    if not assertions:
        return False

    for assertion in assertions:
        timeline_value = get_context_value_or_missing(row_context, assertion["timeline_field"])
        if timeline_value is MISSING or not isinstance(timeline_value, list):
            return True

        if assertion["type"] == "event_exists":
            matching_events = find_timeline_events(timeline_value, assertion["event"])
            if not matching_events:
                return True
            continue

        if assertion["type"] == "ordered_events":
            first_matches = find_timeline_events(timeline_value, assertion["first_event"])
            second_matches = find_timeline_events(timeline_value, assertion["second_event"])
            if not first_matches or not second_matches:
                return True
            first_date = min(parse_iso_date(event["date"], field_label="timeline first event") for event in first_matches)
            second_date = min(parse_iso_date(event["date"], field_label="timeline second event") for event in second_matches)
            if assertion["allow_same_day"]:
                if first_date > second_date:
                    return True
            else:
                if first_date >= second_date:
                    return True
            continue

        if assertion["type"] == "minimum_age_at_event":
            matching_events = find_timeline_events(timeline_value, assertion["event"])
            if not matching_events:
                return True
            birth_date_value = get_context_value_or_missing(row_context, assertion["birth_date_field"])
            if birth_date_value is MISSING or not isinstance(birth_date_value, str):
                return True
            birth_date = parse_iso_date(birth_date_value, field_label="timeline assertion birth date")
            earliest_event_date = min(
                parse_iso_date(event["date"], field_label="timeline minimum age event")
                for event in matching_events
            )
            if age_on_date(birth_date, earliest_event_date) < assertion["min_age"]:
                return True
            continue

        if assertion["type"] == "maximum_age_at_event":
            matching_events = find_timeline_events(timeline_value, assertion["event"])
            if not matching_events:
                return True
            birth_date_value = get_context_value_or_missing(row_context, assertion["birth_date_field"])
            if birth_date_value is MISSING or not isinstance(birth_date_value, str):
                return True
            birth_date = parse_iso_date(birth_date_value, field_label="timeline assertion birth date")
            earliest_event_date = min(
                parse_iso_date(event["date"], field_label="timeline maximum age event")
                for event in matching_events
            )
            if age_on_date(birth_date, earliest_event_date) > assertion["max_age"]:
                return True
            continue

        if assertion["type"] == "minimum_gap_between_events":
            first_matches = find_timeline_events(timeline_value, assertion["first_event"])
            second_matches = find_timeline_events(timeline_value, assertion["second_event"])
            if not first_matches or not second_matches:
                return True
            first_date = min(parse_iso_date(event["date"], field_label="timeline first event") for event in first_matches)
            second_date = min(parse_iso_date(event["date"], field_label="timeline second event") for event in second_matches)
            if (second_date - first_date).days < assertion["min_gap_days"]:
                return True
            continue

    return False


def generate_field_value(
    fake: Faker,
    rng: random.Random,
    field: dict,
    custom_formats: dict,
    config_locale: str = "en_US",
    *,
    segment_values: dict | None = None,
    row_context: dict | None = None,
):
    field_type = field["type"]
    params = field["params"]
    field_name = field["name"]

    if field_type == "literal":
        return params["value"]

    if field_type == "choice":
        weights = params.get("weights")
        if weights is None:
            return rng.choice(params["values"])
        return rng.choices(params["values"], weights=weights, k=1)[0]

    if field_type == "pronouns_from_gender":
        gender_value = resolve_context_value(
            row_context,
            params["field"],
            field_name=field_name,
            purpose="gender",
        )
        return infer_pronouns_from_gender(gender_value, field_name=field_name)

    if field_type == "complementary_gender":
        gender_value = resolve_context_value(
            row_context,
            params["field"],
            field_name=field_name,
            purpose="gender",
        )
        return infer_complementary_gender(gender_value, field_name=field_name)

    if field_type == "number_int":
        return rng.randint(params.get("min", 0), params.get("max", 100))

    if field_type == "number_float":
        precision = params.get("precision", 2)
        value = rng.uniform(params.get("min", 0), params.get("max", 100))
        return round(value, precision)

    if field_type == "date_between":
        return fake.date_between(
            start_date=params.get("start_date", "-30y"),
            end_date=params.get("end_date", "today"),
        ).isoformat()

    if field_type == "child_birth_date_from_parent":
        parent_birth_date_value = resolve_context_value(
            row_context,
            params["parent_birth_date_field"],
            field_name=field_name,
            purpose="parent birth date",
        )
        if not isinstance(parent_birth_date_value, str):
            raise SkillError(f"Field {field_name!r} expected a string ISO parent birth date, received {parent_birth_date_value!r}.")
        parent_birth_date = parse_iso_date(parent_birth_date_value, field_label=f"Field {field_name!r} source parent birth date")
        reference_date = parse_iso_date(
            params.get("reference_date", date.today().isoformat()),
            field_label=f"Field {field_name!r} params.reference_date",
        )
        child_min_age = params.get("min_child_age", 0)
        child_max_age = params.get("max_child_age", 25)
        parent_min_age = params.get("min_parent_age_at_birth", 16)
        parent_max_age = params.get("max_parent_age_at_birth", 60)

        earliest_from_child_age = shift_years_safe(reference_date, -(child_max_age + 1)) + timedelta(days=1)
        latest_from_child_age = shift_years_safe(reference_date, -child_min_age)
        earliest_from_parent_age = shift_years_safe(parent_birth_date, parent_min_age)
        latest_from_parent_age = shift_years_safe(parent_birth_date, parent_max_age)

        earliest_birth_date = max(earliest_from_child_age, earliest_from_parent_age)
        latest_birth_date = min(latest_from_child_age, latest_from_parent_age)
        profile = params.get("profile")
        if profile:
            state = get_generation_state(row_context)
            sibling_dates = state.setdefault(f"child_birth_profile::{profile}", [])
            min_spacing_days = params.get("min_spacing_days", 0)
            if (
                isinstance(row_context, dict)
                and isinstance(row_context.get("__array_index__"), int)
                and isinstance(row_context.get("__array_length__"), int)
            ):
                remaining_siblings = max(row_context["__array_length__"] - row_context["__array_index__"] - 1, 0)
                if remaining_siblings > 0 and min_spacing_days > 0:
                    latest_birth_date = latest_birth_date - timedelta(days=remaining_siblings * min_spacing_days)
            if sibling_dates:
                last_birth_date = max(sibling_dates)
                earliest_birth_date = max(
                    earliest_birth_date,
                    last_birth_date + timedelta(days=min_spacing_days),
                )
                latest_birth_date = min(
                    latest_birth_date,
                    shift_years_safe(last_birth_date, params.get("max_spacing_years_between_siblings", 10)),
                )
        if latest_birth_date < earliest_birth_date:
            raise SkillError(
                f"Field {field_name!r} could not find a plausible child birth-date range for the configured parent/child age constraints."
            )
        chosen_birth_date = random_date_between(rng, earliest_birth_date, latest_birth_date)
        if profile:
            state = get_generation_state(row_context)
            state.setdefault(f"child_birth_profile::{profile}", []).append(chosen_birth_date)
        return chosen_birth_date.isoformat()

    if field_type == "birth_date_relative_to_field":
        anchor_birth_date_value = resolve_context_value(
            row_context,
            params["anchor_birth_date_field"],
            field_name=field_name,
            purpose="anchor birth date",
        )
        if not isinstance(anchor_birth_date_value, str):
            raise SkillError(f"Field {field_name!r} expected a string ISO anchor birth date, received {anchor_birth_date_value!r}.")
        anchor_birth_date = parse_iso_date(
            anchor_birth_date_value,
            field_label=f"Field {field_name!r} source anchor birth date",
        )
        reference_date = parse_iso_date(
            params.get("reference_date", date.today().isoformat()),
            field_label=f"Field {field_name!r} params.reference_date",
        )
        relative_min = shift_years_safe(anchor_birth_date, params.get("min_years_offset", -5))
        relative_max = shift_years_safe(anchor_birth_date, params.get("max_years_offset", 5))
        age_min = shift_years_safe(reference_date, -(params.get("max_age", 92) + 1)) + timedelta(days=1)
        age_max = shift_years_safe(reference_date, -params.get("min_age", 18))
        earliest_birth_date = max(relative_min, age_min)
        latest_birth_date = min(relative_max, age_max)
        if latest_birth_date < earliest_birth_date:
            raise SkillError(
                f"Field {field_name!r} could not find a plausible birth-date range from the configured relative-age constraints."
            )
        return random_date_between(rng, earliest_birth_date, latest_birth_date).isoformat()

    if field_type == "email":
        return generate_logical_email(fake, rng, row_context)

    if field_type == "catalog_choice":
        entry = choose_catalog_entry(
            params["catalog"],
            config_locale=config_locale,
            params=params,
            row_context=row_context,
            rng=rng,
            field_name=field_name,
        )
        return_key = params.get("return", "value")
        if return_key not in entry:
            raise SkillError(
                f"Field {field_name!r} requested return key {return_key!r} from catalog {params['catalog']!r}, but the key is missing."
            )
        return entry[return_key]

    if field_type == "profile_bundle":
        return choose_profile_bundle(
            params["bundle"],
            config_locale=config_locale,
            params=params,
            row_context=row_context,
            rng=rng,
            field_name=field_name,
        )

    if field_type == "age_from_birth_date":
        birth_date_value = resolve_context_value(
            row_context,
            params["field"],
            field_name=field_name,
            purpose="birth date",
        )
        if not isinstance(birth_date_value, str):
            raise SkillError(f"Field {field_name!r} expected a string ISO birth date, received {birth_date_value!r}.")
        birth_date = parse_iso_date(birth_date_value, field_label=f"Field {field_name!r} source birth date")
        reference_date = parse_iso_date(
            params.get("reference_date", date.today().isoformat()),
            field_label=f"Field {field_name!r} params.reference_date",
        )
        age = reference_date.year - birth_date.year - (
            (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day)
        )
        return age

    if field_type == "life_timeline":
        return build_life_timeline(
            rng,
            row_context=row_context,
            params=params,
            field_name=field_name,
        )

    if field_type == "persona_introduction":
        return build_persona_introduction(
            row_context=row_context,
            params=params,
            field_name=field_name,
        )

    if field_type == "biography_from_timeline":
        return build_biography_from_timeline(
            row_context=row_context,
            params=params,
            field_name=field_name,
        )

    if field_type == "daily_routine_profile":
        return build_daily_routine_profile(
            row_context=row_context,
            params=params,
            field_name=field_name,
        )

    if field_type == "belgian_language_profile":
        return build_belgian_language_profile(
            row_context=row_context,
            params=params,
            field_name=field_name,
        )

    if field_type == "belgian_education_profile":
        return build_belgian_education_profile(
            row_context=row_context,
            params=params,
            field_name=field_name,
        )

    if field_type == "belgian_company_name":
        if row_context is None:
            row_context = {}
        profile = get_belgian_company_profile(
            fake,
            rng,
            params,
            row_context=row_context,
            field_name=field_name,
        )
        return profile["company_name"]

    if field_type == "belgian_employer_component":
        if row_context is None:
            row_context = {}
        profile = get_belgian_company_profile(
            fake,
            rng,
            params,
            row_context=row_context,
            field_name=field_name,
        )
        return profile[params["component"]]

    if field_type == "template":
        context = build_template_context(row_context)
        return render_template_string(params["template"], context, field_name=field_name)

    if field_type == "object":
        nested_fields = params["fields"]
        parent_context = row_context or {}
        nested_context = {
            "__root__": parent_context.get("__root__", {}),
            "__current__": {},
            "__state__": parent_context.get("__state__", {}),
            "__locale__": parent_context.get("__locale__"),
            "__array_index__": parent_context.get("__array_index__"),
            "__array_length__": parent_context.get("__array_length__"),
        }
        nested_object = {}
        for nested_field in nested_fields:
            normalized_nested = validate_nested_field_definition(
                nested_field,
                container_label=f"Field {field_name!r} nested field",
            )
            if not should_generate_field(normalized_nested, nested_context):
                continue
            nested_value = generate_field_value(
                fake,
                rng,
                normalized_nested,
                custom_formats,
                config_locale=config_locale,
                segment_values=segment_values,
                row_context=nested_context,
            )
            nested_object[normalized_nested["name"]] = nested_value
            nested_context["__current__"][normalized_nested["name"]] = nested_value
        return nested_object

    if field_type == "array":
        count = params.get("count")
        if count is None:
            count = resolve_context_value(
                row_context,
                params["count_from_field"],
                field_name=field_name,
                purpose="array count",
            )
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise SkillError(f"Field {field_name!r} resolved an invalid array count {count!r}.")

        normalized_item = validate_nested_field_definition(
            params["item"],
            container_label=f"Field {field_name!r} params.item",
        )
        values = []
        parent_context = row_context or {}
        for index in range(count):
            item_context = {
                "__root__": parent_context.get("__root__", {}),
                "__current__": {},
                "__state__": parent_context.get("__state__", {}),
                "__locale__": parent_context.get("__locale__"),
                "__array_index__": index,
                "__array_length__": count,
            }
            values.append(
                generate_field_value(
                    fake,
                    rng,
                    normalized_item,
                    custom_formats,
                    config_locale=config_locale,
                    segment_values=segment_values,
                    row_context=item_context,
                )
            )
        return values

    if field_type == "segment_value":
        return resolve_segment_value(
            segment_values,
            params["key"],
            field_name=field_name,
            default=params.get("default", MISSING),
        )

    if field_type == "birth_date_from_age_band":
        age_band = resolve_segment_value(segment_values, params["segment_key"], field_name=field_name)
        min_age, max_age = resolve_age_range_from_band(age_band, params, field_name)
        reference_date = parse_iso_date(
            params.get("reference_date", date.today().isoformat()),
            field_label=f"Field {field_name!r} params.reference_date",
        )
        return birth_date_for_age_range(
            rng,
            min_age=min_age,
            max_age=max_age,
            reference_date=reference_date,
        ).isoformat()

    if field_type == "faker_from_segment":
        segment_value = resolve_segment_value(segment_values, params["segment_key"], field_name=field_name)
        provider_name = params["providers"].get(str(segment_value))
        if provider_name is None:
            provider_name = params.get("fallback_provider")
        if provider_name is None:
            raise SkillError(
                f"Field {field_name!r} has no Faker provider mapped for sampled segment value {segment_value!r}."
            )
        provider = getattr(fake, provider_name)
        return provider(**params.get("provider_params", {}))

    if field_type == "faker_from_field":
        source_value = resolve_context_value(
            row_context,
            params["field"],
            field_name=field_name,
            purpose="source field",
        )
        provider_name = params["providers"].get(str(source_value))
        if provider_name is None:
            provider_name = params.get("fallback_provider")
        if provider_name is None:
            raise SkillError(
                f"Field {field_name!r} has no Faker provider mapped for source field value {source_value!r}."
            )
        provider = getattr(fake, provider_name)
        return provider(**params.get("provider_params", {}))

    if field_type == "faker_from_field":
        field_value = resolve_context_value(
            row_context,
            params["field"],
            field_name=field_name,
            purpose="mapped field value",
        )
        provider_name = params["providers"].get(str(field_value))
        if provider_name is None:
            provider_name = params.get("fallback_provider")
        if provider_name is None:
            raise SkillError(
                f"Field {field_name!r} has no Faker provider mapped for resolved field value {field_value!r}."
            )
        provider = getattr(fake, provider_name)
        return provider(**params.get("provider_params", {}))

    if field_type == "belgian_address_component":
        if row_context is None:
            row_context = {}
        profile = get_belgian_address_profile(
            rng,
            params,
            segment_values=segment_values,
            row_context=row_context,
            field_name=field_name,
        )
        return profile[params["component"]]

    if field_type == "belgian_bank_account_component":
        if row_context is None:
            row_context = {}
        profile = get_belgian_bank_profile(
            rng,
            params,
            row_context=row_context,
            field_name=field_name,
        )
        return profile[params["component"]]

    if field_type == "belgian_insz":
        birth_date_value = MISSING
        gender_value = MISSING

        explicit_birth_date_field = params.get("birth_date_field")
        if explicit_birth_date_field:
            birth_date_value = resolve_context_value(
                row_context,
                explicit_birth_date_field,
                field_name=field_name,
                purpose="birth date",
            )
        else:
            for candidate in ("birth_date", "identity.birth_date"):
                birth_date_value = get_context_value_or_missing(row_context, candidate)
                if birth_date_value is not MISSING:
                    break

        explicit_gender_field = params.get("gender_field")
        if explicit_gender_field:
            gender_value = resolve_context_value(
                row_context,
                explicit_gender_field,
                field_name=field_name,
                purpose="gender",
            )
        else:
            for candidate in ("gender", "identity.gender"):
                gender_value = get_context_value_or_missing(row_context, candidate)
                if gender_value is not MISSING:
                    break

        parsed_birth_date = None
        if birth_date_value is not MISSING:
            if not isinstance(birth_date_value, str):
                raise SkillError(f"Field {field_name!r} expected a string ISO birth date, received {birth_date_value!r}.")
            parsed_birth_date = parse_iso_date(
                birth_date_value,
                field_label=f"Field {field_name!r} source birth date",
            )

        return generate_belgian_insz(
            rng,
            birth_date=parsed_birth_date,
            gender_value=gender_value,
        )

    if field_type == "belgian_eid":
        return generate_belgian_eid(rng)

    if field_type in custom_formats:
        return rstr.Xeger(_random=rng).xeger(custom_formats[field_type]["pattern"])

    provider = getattr(fake, field_type, None)
    if callable(provider):
        return provider(**params)

    raise SkillError(f"Unsupported field type during generation: {field_type!r}")


def any_population_aware_fields(config: dict) -> bool:
    return any(field["type"] in POPULATION_AWARE_FIELD_TYPES for field in config["fields"])


def iter_fields_recursive(fields: list[dict], prefix: str = ""):
    for field in fields:
        field_name = f"{prefix}.{field['name']}" if prefix else field["name"]
        yield field_name, field
        if field["type"] == "object":
            nested_fields = field.get("params", {}).get("fields", [])
            if isinstance(nested_fields, list):
                yield from iter_fields_recursive(nested_fields, prefix=field_name)


def build_representativeness_summary(config: dict) -> dict | None:
    population_model = config.get("population_model")
    if population_model is None:
        return None
    source_query = population_model.get("source_query")

    covered_fields = []
    covered_field_names = set()
    for field_name, field in iter_fields_recursive(config["fields"]):
        dimension_name = None
        if field["type"] == "segment_value":
            dimension_name = field["params"]["key"]
        elif field["type"] in {"birth_date_from_age_band", "faker_from_segment"}:
            dimension_name = field["params"]["segment_key"]

        if dimension_name is not None:
            covered_fields.append(
                {
                    "field_name": field_name,
                    "dimension": dimension_name,
                    "strategy": field["type"],
                }
            )
            covered_field_names.add(field_name)

    seen_dimensions = set()
    dimension_details = []
    for dimension in population_model["dimensions"]:
        if dimension["name"] in seen_dimensions:
            continue
        dimension_details.append(dimension)
        seen_dimensions.add(dimension["name"])

    if source_query is not None:
        for dimension_name, column_name in source_query["dimension_columns"].items():
            if dimension_name not in seen_dimensions:
                dimension_details.append(
                    {
                        "name": dimension_name,
                        "represented": True,
                        "source": {
                            "catalog_id": source_query.get("catalog_id"),
                            "dataset": source_query["dataset"],
                            "column": column_name,
                        },
                    }
                )
                seen_dimensions.add(dimension_name)

    for key in population_model["filters"]:
        if key not in seen_dimensions:
            dimension_details.append({"name": key, "represented": True})
            seen_dimensions.add(key)

    for segment in population_model["segments"]:
        for key in segment["values"]:
            if key not in seen_dimensions:
                dimension_details.append({"name": key, "represented": True})
                seen_dimensions.add(key)

    summary = {
        "mode": "weighted_population_segments",
        "segment_origin": population_model.get("segment_origin", "explicit"),
        "scope": population_model["scope"],
        "filters": population_model["filters"],
        "distribution_backed_dimensions": dimension_details,
        "distribution_backed_fields": covered_fields,
        "non_distribution_fields": [
            field["name"] for field in config["fields"] if field["name"] not in covered_field_names
        ],
        "segment_count_before_filters": population_model["segment_count_before_filters"],
        "segment_count_after_filters": population_model["segment_count_after_filters"],
        "subset_active": bool(population_model["filters"]),
    }
    if source_query is not None:
        summary["source_query"] = {
            "catalog_id": source_query.get("catalog_id"),
            "dataset": source_query["dataset"],
            "dimension_columns": source_query["dimension_columns"],
            "weight_column": source_query["weight_column"],
            "filters": source_query["filters"],
        }
    return summary


def generate_dataset(config: dict, custom_formats: dict | None = None, *, already_normalized: bool = False) -> list[dict]:
    normalized_config = config if already_normalized else normalize_config(config)
    custom_formats = custom_formats or {}

    fake = build_fake(normalized_config["locale"], normalized_config["seed"])
    rng = random.Random(normalized_config["seed"])

    if any_population_aware_fields(normalized_config) and normalized_config["population_model"] is None:
        raise SkillError("Population-aware field types require a top-level 'population_model'.")

    for field in normalized_config["fields"]:
        validate_field(fake, field, custom_formats, normalized_config["population_model"])

    generated_rows = []
    for _ in range(normalized_config["records"]):
        sampled_segment = select_population_segment(rng, normalized_config["population_model"])
        segment_values = sampled_segment["values"] if sampled_segment else None
        row = {}
        row_context = {"__root__": row, "__current__": row, "__state__": {}, "__locale__": normalized_config["locale"]}
        row_state = row_context["__state__"]
        for field in normalized_config["fields"]:
            if not should_generate_field(field, row_context):
                continue
            row[field["name"]] = generate_field_value(
                fake,
                rng,
                field,
                custom_formats,
                config_locale=normalized_config["locale"],
                segment_values=segment_values,
                row_context=row_context,
            )
            apply_correlation_rules(row, normalized_config["correlation_rules"], rng, state=row_state)
            apply_archetypes(
                row,
                normalized_config["archetypes"],
                config_locale=normalized_config["locale"],
                rng=rng,
                state=row_state,
            )
        apply_correlation_rules(row, normalized_config["correlation_rules"], rng, state=row_state)
        apply_archetypes(
            row,
            normalized_config["archetypes"],
            config_locale=normalized_config["locale"],
            rng=rng,
            state=row_state,
        )
        run_contradiction_checks(row, normalized_config["contradiction_checks"])
        generated_rows.append(row)

    return generated_rows


def ensure_output_parent(path: Path) -> None:
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def extract_row_value(row: dict, path: str, default=None):
    current = row
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "persona"


def shorten_text(value, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def describe_persona(row: dict, index: int) -> dict:
    name = (
        extract_row_value(row, "identity.full_name")
        or extract_row_value(row, "full_name")
        or extract_row_value(row, "name")
        or f"Persona {index + 1}"
    )
    role = extract_row_value(row, "professional.job_title") or extract_row_value(row, "professional.profession") or ""
    city = extract_row_value(row, "contact.city") or extract_row_value(row, "city") or ""
    intro = row.get("introduction") if isinstance(row, dict) else None
    biography = row.get("biography") if isinstance(row, dict) else None
    description = intro or biography or ""
    if not description:
        fragments = [fragment for fragment in [role, city] if fragment]
        description = ", ".join(fragments) if fragments else "Synthetic persona profile"
    filename = f"persona-{index + 1:03d}-{slugify_filename(str(name))}"
    return {
        "name": str(name),
        "role": str(role),
        "city": str(city),
        "description": str(description),
        "short_description": shorten_text(description),
        "filename": filename,
    }


def render_markdown_value(value, level: int = 0, *, locale: str | None = None) -> str:
    return render_markdown_value_with_path(value, level=level, locale=locale, path=())


def localize_bundle_display_scalar(value, *, locale: str | None = None, path: tuple[str, ...] = ()):
    language = resolve_bundle_language(locale)
    if language == "en" or not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value

    localized_by_path = PERSONA_BUNDLE_VALUE_LOCALIZATION.get(language, {})
    field_key = path[-1] if path else ""

    if field_key in {"job_title", "profession"}:
        return localize_narrative_term(stripped, locale_kind=language, category="profession")
    if field_key == "industry":
        return localize_narrative_term(stripped, locale_kind=language, category="industry")
    if field_key in {"education_level", "level"}:
        return localize_narrative_term(stripped, locale_kind=language, category="education")
    if field_key == "hobbies":
        return localize_narrative_term(stripped, locale_kind=language, category="hobby")

    wildcard_path = tuple("*" if part.isdigit() else part for part in path)
    for candidate_path in [path, wildcard_path]:
        if candidate_path in localized_by_path and stripped in localized_by_path[candidate_path]:
            return localized_by_path[candidate_path][stripped]

    localized_by_key = PERSONA_BUNDLE_VALUE_LOCALIZATION_BY_KEY.get(language, {})
    if field_key in localized_by_key and stripped in localized_by_key[field_key]:
        return localized_by_key[field_key][stripped]

    return value


def render_markdown_value_with_path(value, level: int = 0, *, locale: str | None = None, path: tuple[str, ...] = ()) -> str:
    indent = "  " * level
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            label = format_bundle_label(key, locale)
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}- **{label}**:")
                lines.append(render_markdown_value_with_path(item, level + 1, locale=locale, path=path + (str(key),)))
            else:
                display_value = localize_bundle_display_scalar(item, locale=locale, path=path + (str(key),))
                lines.append(f"{indent}- **{label}**: {display_value}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}-")
                lines.append(render_markdown_value_with_path(item, level + 1, locale=locale, path=path + ("*",)))
            else:
                display_value = localize_bundle_display_scalar(item, locale=locale, path=path)
                lines.append(f"{indent}- {display_value}")
        return "\n".join(lines) if lines else f"{indent}- {get_bundle_text(locale, 'none').lower()}"
    return f"{indent}{localize_bundle_display_scalar(value, locale=locale, path=path)}"


def render_persona_markdown(row: dict, persona: dict, *, locale: str | None = None) -> str:
    lines = [f"# {persona['name']}", ""]
    if persona["short_description"]:
        lines.extend([persona["short_description"], ""])
    for key, value in row.items():
        label = format_bundle_label(key, locale)
        lines.extend([f"## {label}", render_markdown_value_with_path(value, locale=locale, path=(str(key),)), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_html_value(value, *, locale: str | None = None) -> str:
    return render_html_value_with_path(value, locale=locale, path=())


def render_html_value_with_path(value, *, locale: str | None = None, path: tuple[str, ...] = ()) -> str:
    if isinstance(value, dict):
        items = []
        for key, item in value.items():
            label = html.escape(format_bundle_label(key, locale))
            items.append(f"<dt>{label}</dt><dd>{render_html_value_with_path(item, locale=locale, path=path + (str(key),))}</dd>")
        return "<dl>" + "".join(items) + "</dl>"
    if isinstance(value, list):
        items = "".join(
            f"<li>{render_html_value_with_path(item, locale=locale, path=path + ('*',) if isinstance(item, (dict, list)) else path)}</li>"
            for item in value
        )
        return "<ul>" + items + "</ul>"
    return html.escape(str(localize_bundle_display_scalar(value, locale=locale, path=path)))


def render_persona_html(row: dict, persona: dict, *, locale: str | None = None) -> str:
    sections = []
    for key, value in row.items():
        label = html.escape(format_bundle_label(key, locale))
        sections.append(f"<section><h2>{label}</h2>{render_html_value_with_path(value, locale=locale, path=(str(key),))}</section>")
    title = html.escape(persona["name"])
    description = html.escape(persona["short_description"])
    html_lang = html.escape(resolve_html_lang(locale))
    back_to_index = html.escape(get_bundle_text(locale, "back_to_index"))
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: Georgia, serif; margin: 2rem auto; max-width: 960px; padding: 0 1rem; color: #1f2937; background: #f8fafc; }}
    main {{ background: white; padding: 2rem; border-radius: 16px; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08); }}
    a {{ color: #0f766e; }}
    h1, h2 {{ color: #111827; }}
    section {{ margin-top: 1.75rem; padding-top: 1rem; border-top: 1px solid #e5e7eb; }}
    dl {{ display: grid; grid-template-columns: minmax(180px, 240px) 1fr; gap: 0.5rem 1rem; }}
    dt {{ font-weight: 600; }}
    dd {{ margin: 0; }}
    ul {{ margin: 0.3rem 0 0.8rem 1.25rem; }}
    .summary {{ color: #4b5563; font-size: 1.05rem; }}
  </style>
</head>
<body>
  <main>
    <p><a href="index.html">{back_to_index}</a></p>
    <h1>{title}</h1>
    <p class="summary">{description}</p>
    {''.join(sections)}
  </main>
</body>
</html>
"""


def render_persona_index_html(personas: list[dict], title: str, *, locale: str | None = None) -> str:
    rows_html = "".join(
        "<tr>"
        f"<td><a href=\"{html.escape(persona['filename'] + '.html')}\">{html.escape(persona['name'])}</a></td>"
        f"<td>{html.escape(str(localize_bundle_display_scalar(persona['role'], locale=locale, path=('professional', 'job_title'))))}</td>"
        f"<td>{html.escape(persona['city'])}</td>"
        f"<td>{html.escape(persona['short_description'])}</td>"
        "</tr>"
        for persona in personas
    )
    html_lang = html.escape(resolve_html_lang(locale))
    browse_text = html.escape(get_bundle_text(locale, "browse_personas"))
    name_label = html.escape(get_bundle_text(locale, "name"))
    role_label = html.escape(get_bundle_text(locale, "role"))
    city_label = html.escape(get_bundle_text(locale, "city"))
    summary_label = html.escape(get_bundle_text(locale, "summary"))
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; color: #111827; background: #f8fafc; }}
    main {{ background: white; padding: 2rem; border-radius: 16px; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 0.8rem; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    a {{ color: #0f766e; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    p {{ color: #4b5563; }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <p>{browse_text}</p>
    <table>
      <thead>
        <tr><th>{name_label}</th><th>{role_label}</th><th>{city_label}</th><th>{summary_label}</th></tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def render_persona_index_markdown(personas: list[dict], title: str, *, locale: str | None = None) -> str:
    lines = [
        f"# {title}",
        "",
        f"| {get_bundle_text(locale, 'name')} | {get_bundle_text(locale, 'role')} | {get_bundle_text(locale, 'city')} | {get_bundle_text(locale, 'summary')} |",
        "| --- | --- | --- | --- |",
    ]
    for persona in personas:
        localized_role = localize_bundle_display_scalar(persona["role"], locale=locale, path=("professional", "job_title"))
        lines.append(
            f"| [{persona['name']}]({persona['filename']}.md) | {localized_role} | {persona['city']} | {persona['short_description']} |"
        )
    return "\n".join(lines) + "\n"


def write_persona_bundle(
    rows: list[dict],
    output_format: str,
    output_path: Path,
    *,
    locale: str | None = None,
    output_options: dict | None = None,
) -> None:
    ensure_directory(output_path)
    output_options = output_options or {}
    include_sensitive_fields = bool(output_options.get("include_sensitive_fields", False))
    personas = [describe_persona(row, index) for index, row in enumerate(rows)]
    title = output_options.get("title") or get_bundle_text(locale, "generated_personas_title")
    if output_format == "html":
        for row, persona in zip(rows, personas):
            sanitized_row = sanitize_persona_bundle_row(row, include_sensitive_fields=include_sensitive_fields)
            (output_path / f"{persona['filename']}.html").write_text(
                render_persona_html(sanitized_row, persona, locale=locale),
                encoding="utf-8",
            )
        (output_path / "index.html").write_text(
            render_persona_index_html(personas, title, locale=locale),
            encoding="utf-8",
        )
        return
    if output_format == "markdown":
        for row, persona in zip(rows, personas):
            sanitized_row = sanitize_persona_bundle_row(row, include_sensitive_fields=include_sensitive_fields)
            (output_path / f"{persona['filename']}.md").write_text(
                render_persona_markdown(sanitized_row, persona, locale=locale),
                encoding="utf-8",
            )
        (output_path / "index.md").write_text(
            render_persona_index_markdown(personas, title, locale=locale),
            encoding="utf-8",
        )
        return


def quote_sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def to_sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def build_sql_insert_script(rows: list[dict], *, table_name: str) -> str:
    column_names = list(rows[0].keys()) if rows else []
    quoted_columns = ", ".join(quote_sql_identifier(name) for name in column_names)
    statement_lines = ["BEGIN;"]
    if rows:
        value_lines = []
        for row in rows:
            value_lines.append(
                "(" + ", ".join(to_sql_literal(row[name]) for name in column_names) + ")"
            )
        statement_lines.append(
            f"INSERT INTO {quote_sql_identifier(table_name)} ({quoted_columns}) VALUES\n  "
            + ",\n  ".join(value_lines)
            + ";"
        )
    statement_lines.append("COMMIT;")
    return "\n".join(statement_lines) + "\n"


def write_output(
    rows: list[dict],
    output_format: str,
    output_path: Path,
    *,
    locale: str | None = None,
    output_options: dict | None = None,
) -> None:
    ensure_output_parent(output_path)
    output_options = output_options or {}

    if output_format == "csv":
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
            if rows:
                writer.writeheader()
                writer.writerows(rows)
        return

    if output_format == "json":
        output_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    if output_format == "ndjson":
        with output_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return

    if output_format == "sql":
        table_name = output_options.get("table_name")
        if not isinstance(table_name, str) or not table_name.strip():
            raise SkillError("SQL output requires a non-empty output table_name.")
        output_path.write_text(build_sql_insert_script(rows, table_name=table_name), encoding="utf-8")
        return

    if output_format in {"html", "markdown"}:
        write_persona_bundle(rows, output_format, output_path, locale=locale, output_options=output_options)
        return

    raise SkillError(f"Unsupported output format: {output_format!r}")


def build_summary(config: dict, rows: list[dict], output_path: str | None, validate_only: bool, preview_rows: int) -> dict:
    preview = rows[: max(preview_rows, 0)]
    summary = {
        "status": "validated" if validate_only else "generated",
        "version": config["version"],
        "locale": config["locale"],
        "records_requested": config["records"],
        "records_previewed": len(preview),
        "seed": config["seed"],
        "field_names": [field["name"] for field in config["fields"]],
        "preview": preview,
    }
    representativeness = build_representativeness_summary(config)
    if representativeness is not None:
        summary["representativeness"] = representativeness
    if not validate_only:
        summary["records_written"] = len(rows)
        summary["output"] = {
            "format": config["output"]["format"],
            "path": output_path,
        }
        if config["output"].get("table_name"):
            summary["output"]["table_name"] = config["output"]["table_name"]
    if config.get("sql_schema") is not None:
        summary["sql_schema"] = {
            "table_name": config["sql_schema"]["table_name"],
            "column_count": len(config["sql_schema"]["columns"]),
            "derived_field_names": [field["name"] for field in config["fields"]],
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate realistic synthetic datasets from a JSON config.",
    )
    parser.add_argument("--config", required=True, help="Path to the generation config JSON file.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the config and generate an in-memory preview without writing an output file.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=5,
        help="Number of generated rows to include in the JSON summary preview.",
    )
    parser.add_argument(
        "--output",
        help="Override the output path defined in the config.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        raw_config = load_json(Path(args.config))
        custom_formats = load_custom_formats()
        config = normalize_config(raw_config)
        rows = generate_dataset(config, custom_formats=custom_formats, already_normalized=True)

        output_path = None
        if not args.validate_only:
            output_path = Path(args.output) if args.output else Path(config["output"]["path"])
            write_output(
                rows,
                config["output"]["format"],
                output_path,
                locale=config.get("locale"),
                output_options=config["output"],
            )

        summary = build_summary(
            config=config,
            rows=rows,
            output_path=str(output_path) if output_path else None,
            validate_only=args.validate_only,
            preview_rows=args.preview_rows,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except SkillError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
