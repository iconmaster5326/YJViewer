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
    ygojson.SetEdition.FIRST: "1st Edition",
    ygojson.SetEdition.UNLIMTED: "Unlimited",
    ygojson.SetEdition.LIMITED: "Limited Edition",
    ygojson.SetEdition.NONE: "N/A",
    ygojson.Format.DUELLINKS: "Duel Links",
    ygojson.Format.MASTERDUEL: "Master Duel",
    ygojson.Format.OCG: "OCG",
    ygojson.Format.TCG: "TCG",
    ygojson.Format.SPEED: "Speed Duel",
    ygojson.CardRarity.COMMON: "C",
    ygojson.CardRarity.SHORTPRINT: "SP/SSP",
    ygojson.CardRarity.RARE: "R",
    ygojson.CardRarity.SUPER: "SR",
    ygojson.CardRarity.ULTRA: "UR",
    ygojson.CardRarity.ULTIMATE: "UtR",
    ygojson.CardRarity.SECRET: "ScR",
    ygojson.CardRarity.ULTRASECRET: "UScR",
    ygojson.CardRarity.PRISMATICSECRET: "PScR",
    ygojson.CardRarity.GHOST: "GR/HR",
    ygojson.CardRarity.PARALLEL: "PR",
    ygojson.CardRarity.COMMONPARALLEL: "PC/NPR",
    ygojson.CardRarity.RAREPARALLEL: "RPR",
    ygojson.CardRarity.SUPERPARALLEL: "SPR",
    ygojson.CardRarity.ULTRAPARALLEL: "UPR",
    ygojson.CardRarity.DTPC: "DPC/DNPR",
    ygojson.CardRarity.DTPSP: "DPSP/DNRPR",
    ygojson.CardRarity.DTRPR: "DRPR",
    ygojson.CardRarity.DTSPR: "DSPR",
    ygojson.CardRarity.DTUPR: "DUPR",
    ygojson.CardRarity.DTSCPR: "DScPR",
    ygojson.CardRarity.GOLD: "Gold",
    ygojson.CardRarity.TENTHOUSANDSECRET: "10,000ScR",
    ygojson.CardRarity.TWENTITHSECRET: "20ScR",
    ygojson.CardRarity.COLLECTORS: "CR",
    ygojson.CardRarity.EXTRASECRET: "EScR",
    ygojson.CardRarity.EXTRASECRETPARALLEL: "EScPR",
    ygojson.CardRarity.GOLDGHOST: "G/GR",
    ygojson.CardRarity.GOLDSECRET: "GScR",
    ygojson.CardRarity.STARFOIL: "Starfoil",
    ygojson.CardRarity.MOSAIC: "Mosaic",
    ygojson.CardRarity.SHATTERFOIL: "Shatterfoil",
    ygojson.CardRarity.GHOSTPARALLEL: "GPR",
    ygojson.CardRarity.PLATINUM: "PtR",
    ygojson.CardRarity.PLATINUMSECRET: "PtScR",
    ygojson.CardRarity.PREMIUMGOLD: "PGR",
    ygojson.CardRarity.TWENTYFIFTHSECRET: "25ScR",
    ygojson.CardRarity.SECRETPARALLEL: "PScR",
    ygojson.CardRarity.STARLIGHT: "StR/AltR",
    ygojson.CardRarity.PHARAOHS: "PUR",
    ygojson.CardRarity.KCCOMMON: "KCC",
    ygojson.CardRarity.KCRARE: "KCR",
    ygojson.CardRarity.KCSUPER: "KCSR",
    ygojson.CardRarity.KCULTRA: "KCUR",
    ygojson.CardRarity.KCSECRET: "KCScR",
    ygojson.CardRarity.MILLENIUM: "MR",
    ygojson.CardRarity.MILLENIUMSUPER: "MSR",
    ygojson.CardRarity.MILLENIUMULTRA: "MUR",
    ygojson.CardRarity.MILLENIUMSECRET: "MScR",
    ygojson.CardRarity.MILLENIUMGOLD: "MGR",
}

FORMAT_TRANSLATED = {
    "tcg": "TCG",
    "speed": "Speed Duel",
    "ocg": "OCG",
    "ocg-kr": "Korean OCG",
    "ocg-sc": "Chinese OCG",
    "masterduel": "Master Duel",
    "duellinks": "Duel Links",
}

LOCALE_TRANSLATED = {
    "en": "English",
    "it": "Italian",
    "jp": "Japanese",
    "sc": "Simplified Chinese",
    "tc": "Traditional Chinese",
    "ae": "Asian-English",
    "eu": "English (Europe)",
    "na": "English (North America)",
    "fr": "French",
    "sp": "Spanish",
    "de": "German",
    "pt": "Portugese",
    "ja": "Japanese",
    "au": "English (Austrailia)",
    "kr": "Korean",
    # TODO: what is "fc"?
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
def translatelocale(l: str) -> str:
    return LOCALE_TRANSLATED.get(l, l)


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


@app.template_filter()
def getsetlocalecontents(
    set_: ygojson.Set, locale: typing.Optional[ygojson.SetLocale]
) -> typing.Iterable[ygojson.SetContents]:
    if not locale:
        yield from set_.contents
        return
    for content in set_.contents:
        if locale in content.locales:
            yield content


CARD_BACK_URL = "https://ms.yugipedia.com//e/e5/Back-EN.png"


@app.template_filter()
def printingimage(
    set_: ygojson.Set,
    printing: ygojson.CardPrinting,
    locale: typing.Optional[ygojson.SetLocale],
    edition: typing.Optional[ygojson.SetEdition],
) -> str:
    if not edition:
        edition = ygojson.SetEdition.NONE
    if not locale:
        if printing.card.images:
            return printing.card.images[0].card_art or CARD_BACK_URL
        return CARD_BACK_URL
    if edition in locale.card_images and printing in locale.card_images[edition]:
        return locale.card_images[edition][printing]
    if (
        ygojson.SetEdition.NONE in locale.card_images
        and printing in locale.card_images[ygojson.SetEdition.NONE]
    ):
        return locale.card_images[ygojson.SetEdition.NONE][printing]
    return CARD_BACK_URL


@app.template_filter()
def dbsetlinks(db_ids: typing.Iterable[int]) -> typing.Iterable[str]:
    return [
        f'<a href="https://www.db.yugioh-card.com/yugiohdb/card_search.action?ope=1&pid={id}&rp=99999&request_locale=en">{id}</a>'
        for id in db_ids
    ]


@app.template_filter()
def setgenericboximage(set_: ygojson.Set) -> str:
    for preferred_locale in ["en", "na", "ja", "jp"]:
        if (
            preferred_locale in set_.locales
            and set_.locales[preferred_locale].box_image
        ):
            return set_.locales[preferred_locale].box_image or ""
    for locale in set_.locales.values():
        if locale.box_image:
            return locale.box_image
    for content in set_.contents:
        if content.box_image:
            return content.box_image
    return ""


@app.template_filter()
def setgenericimage(set_: ygojson.Set) -> str:
    for preferred_locale in ["en", "na", "ja", "jp"]:
        if preferred_locale in set_.locales and set_.locales[preferred_locale].image:
            return set_.locales[preferred_locale].image or ""
    for locale in set_.locales.values():
        if locale.image:
            return locale.image
    for content in set_.contents:
        if content.image:
            return content.image
    return setgenericboximage(set_)


@app.template_filter()
def setformats(set_: ygojson.Set) -> typing.Iterable[ygojson.Format]:
    return {f for l in set_.locales.values() for f in l.formats}


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


@app.route("/random-set")
def random_set():
    return app.redirect(
        flask.url_for(
            set_.__name__,
            uuid=random.choice([*ygodb.sets_by_id]),
        )
    )


@app.route("/set/<uuid:uuid>")
def set_(uuid: uuid.UUID):
    return flask.render_template(
        "set.j2",
        ygodb=ygodb,
        set=ygodb.sets_by_id[uuid],
    )
