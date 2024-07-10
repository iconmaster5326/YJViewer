import datetime
import enum
import os
import random
import typing
import uuid

import flask
import jinja2.filters
import tqdm
import ygojson

from .version import __version__

if os.path.exists(ygojson.AGGREGATE_DIR):
    ygodb = ygojson.load_from_file(aggregates_dir=ygojson.AGGREGATE_DIR)
else:
    ygodb = ygojson.load_from_internet(aggregates_dir=ygojson.AGGREGATE_DIR)
ygodb.regenerate_backlinks()

app = flask.Flask(__name__)

ENUM_TRANSLATED: typing.Dict[enum.Enum, str] = {
    ygojson.CardType.MONSTER: "Monster",
    ygojson.CardType.SPELL: "Spell",
    ygojson.CardType.TRAP: "Trap",
    ygojson.CardType.TOKEN: "Token",
    ygojson.CardType.SKILL: "Skill",
    ygojson.Attribute.DARK: "DARK",
    ygojson.Attribute.DIVINE: "DIVINE",
    ygojson.Attribute.EARTH: "EARTH",
    ygojson.Attribute.FIRE: "FIRE",
    ygojson.Attribute.LIGHT: "LIGHT",
    ygojson.Attribute.WATER: "WATER",
    ygojson.Attribute.WIND: "WIND",
    ygojson.MonsterCardType.FUSION: "Fusion",
    ygojson.MonsterCardType.LINK: "Link",
    ygojson.MonsterCardType.PENDULUM: "Pendulum",
    ygojson.MonsterCardType.RITUAL: "Ritual",
    ygojson.MonsterCardType.SYNCHRO: "Synchro",
    ygojson.MonsterCardType.XYZ: "Xyz",
    ygojson.Race.BEASTWARRIOR: "Beast-Warrior",
    ygojson.Race.ZOMBIE: "Zombie",
    ygojson.Race.FIEND: "Fiend",
    ygojson.Race.DINOSAUR: "Dinosaur",
    ygojson.Race.DRAGON: "Dragon",
    ygojson.Race.BEAST: "Beast",
    ygojson.Race.ILLUSION: "Illusion",
    ygojson.Race.INSECT: "Insect",
    ygojson.Race.WINGEDBEAST: "Winged-Beast",
    ygojson.Race.WARRIOR: "Warrior",
    ygojson.Race.SEASERPENT: "Sea-Serpent",
    ygojson.Race.AQUA: "Aqua",
    ygojson.Race.PYRO: "Pyro",
    ygojson.Race.THUNDER: "Thunder",
    ygojson.Race.SPELLCASTER: "Spellcaster",
    ygojson.Race.PLANT: "Plant",
    ygojson.Race.ROCK: "Rock",
    ygojson.Race.REPTILE: "Reptile",
    ygojson.Race.FAIRY: "Fairy",
    ygojson.Race.FISH: "Fish",
    ygojson.Race.MACHINE: "Machine",
    ygojson.Race.DIVINEBEAST: "Divine-Beast",
    ygojson.Race.PSYCHIC: "Psychic",
    ygojson.Race.CREATORGOD: "Creator-God",
    ygojson.Race.WYRM: "Wyrm",
    ygojson.Race.CYBERSE: "Cyberse",
    ygojson.Classification.EFFECT: "Effect",
    ygojson.Classification.TUNER: "Tuner",
    ygojson.Classification.SPECIALSUMMON: "Special Summon",
    ygojson.Classification.NORMAL: "Normal",
    ygojson.Classification.PENDULUM: "Pendulum",
    ygojson.Ability.FLIP: "Flip",
    ygojson.Ability.GEMINI: "Gemini",
    ygojson.Ability.SPIRIT: "Spirit",
    ygojson.Ability.TOON: "Toon",
    ygojson.Ability.UNION: "Union",
    ygojson.LinkArrow.BOTTOMCENTER: "⬇",
    ygojson.LinkArrow.BOTTOMLEFT: "↙",
    ygojson.LinkArrow.BOTTOMRIGHT: "↘",
    ygojson.LinkArrow.MIDDLELEFT: "⬅",
    ygojson.LinkArrow.MIDDLERIGHT: "➡",
    ygojson.LinkArrow.TOPCENTER: "⬆",
    ygojson.LinkArrow.TOPLEFT: "↖",
    ygojson.LinkArrow.TOPRIGHT: "↗",
    ygojson.SubCategory.CONTINUOUS: "Continuous",
    ygojson.SubCategory.COUNTER: "Counter",
    ygojson.SubCategory.EQUIP: "Equip",
    ygojson.SubCategory.FIELD: "Field",
    ygojson.SubCategory.NORMAL: "Normal",
    ygojson.SubCategory.QUICKPLAY: "Quick-Play",
    ygojson.SubCategory.RITUAL: "Ritual",
    ygojson.Legality.UNLIMITED: "Unlimited",
    ygojson.Legality.FORBIDDEN: "Forbidden",
    ygojson.Legality.LIMIT1: "Limit 1",
    ygojson.Legality.LIMIT2: "Limit 2",
    ygojson.Legality.LIMIT3: "Limit 3",
    ygojson.Legality.LIMITED: "Limited",
    ygojson.Legality.SEMILIMITED: "Semilimited",
    ygojson.Legality.UNRELEASED: "Unreleased",
    ygojson.VideoGameRaity.NORMAL: "N",
    ygojson.VideoGameRaity.RARE: "R",
    ygojson.VideoGameRaity.SUPER: "SR",
    ygojson.VideoGameRaity.ULTRA: "UR",
}

FORMAT_TRANSLATED = {
    "tcg": "TCG",
    "speed": "TCG Speed Duel",
    "ocg": "OCG",
    "ocg-kr": "Korean OCG",
    "ocg-sc": "Chinese OCG",
    "masterduel": "Master Duel",
    "duellinks": "Duel Links",
}

FORMAT_TO_LOCALES = {
    "tcg": ["en", "na", "eu", "au", "es", "pt", "de", "it", "fr"],
    "speed": ["en", "na", "eu", "au", "es", "pt", "de", "it", "fr"],
    "ocg": ["ja", "ae"],
    "ocg-kr": ["kr"],
    "ocg-sc": ["sc", "zh-CN"],
}


@app.template_filter()
def zfill(s, n: int):
    return str(s).zfill(n)


@app.template_filter()
def translateenum(e: enum.Enum):
    return ENUM_TRANSLATED.get(e, e)


@app.template_filter()
def translateenums(es: typing.Iterable[enum.Enum]) -> typing.Iterable:
    for e in es:
        yield translateenum(e)


@app.template_filter()
def translateformat(f: str) -> str:
    return FORMAT_TRANSLATED.get(f, f)


@app.template_filter()
def currentlegality(
    card: ygojson.Card, format: str
) -> typing.Optional[ygojson.Legality]:
    if card.illegal:
        return ygojson.Legality.FORBIDDEN

    if format in card.legality:
        legality = card.legality[format]
        if legality.current:
            return legality.current
        if legality.history:
            return legality.history[-1].legality

    locales = FORMAT_TO_LOCALES.get(format, [])
    dates = []
    for set_ in card.sets:
        for localecode in locales:
            if localecode in set_.locales:
                locale = set_.locales[localecode]
                if locale.date:
                    dates.append(locale.date)
        else:
            if set_.date:
                dates.append(set_.date)

    if not dates:
        return None
    today = datetime.datetime.now().date()
    if all(date > today for date in dates):
        return ygojson.Legality.UNRELEASED
    else:
        return ygojson.Legality.UNLIMITED


@app.route("/")
def index():
    return flask.render_template("index.j2", ygodb=ygodb)


@app.route("/random-card")
def random_card():
    return app.redirect(
        flask.url_for(
            card.__name__,
            uuid=random.choice([*ygodb.cards_by_id]),
        )
    )


@app.route("/card/<uuid:uuid>")
def card(uuid: uuid.UUID):
    return flask.render_template(
        "card.j2",
        ygodb=ygodb,
        card=ygodb.cards_by_id[uuid],
    )
