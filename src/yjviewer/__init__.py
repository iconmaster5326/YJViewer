import datetime
import enum
import math
import os
import random
import time
import typing
import uuid

import flask
import jinja2.filters
import tqdm
import ygojson

import yjviewer.search as search

from .locales import LOCALE_TRANSLATED
from .version import __version__

if os.path.exists(ygojson.AGGREGATE_DIR):
    ygodb = ygojson.load_from_file(aggregates_dir=ygojson.AGGREGATE_DIR)
else:
    ygodb = ygojson.load_from_internet(aggregates_dir=ygojson.AGGREGATE_DIR)
ygodb.regenerate_backlinks()

portenial_cotd = [x for x in ygodb.cards if x.images and x.images[0].card_art]
cards_of_the_day = [random.choice(portenial_cotd) for i in range(5)]
del portenial_cotd

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
    ygojson.SpecialDistroType.PRECON: "Preconstructed",
}

FORMAT_TRANSLATED = {
    ygojson.Format.TCG: "TCG",
    ygojson.Format.SPEED: "Speed Duel",
    ygojson.Format.OCG: "OCG",
    ygojson.Format.OCG_KR: "Korean OCG",
    ygojson.Format.OCG_SC: "Chinese OCG",
    ygojson.Format.OCG_AE: "Asian-English OCG",
    ygojson.Format.MASTERDUEL: "Master Duel",
    ygojson.Format.DUELLINKS: "Duel Links",
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
def translateformat(f: ygojson.Format) -> str:
    return FORMAT_TRANSLATED.get(f, f.value)


@app.template_filter()
def translatelocale(l: ygojson.Locale) -> str:
    return LOCALE_TRANSLATED.get(l, l.value)


def getDefaultLegality(
    card: ygojson.Card, format: typing.Optional[ygojson.Format]
) -> typing.Optional[ygojson.Legality]:
    if not format:
        return None

    locales = format.locales
    dates = []
    for set_ in card.sets:
        for locale in locales:
            if locale in set_.locales:
                locale = set_.locales[locale]
                if locale.date:
                    dates.append(locale.date)
        else:
            if set_.date:
                dates.append(set_.date)

    if not dates:
        results: typing.List[ygojson.Legality] = []
        for subformat in format.subformats:
            result = getDefaultLegality(card, subformat)
            if result:
                results.append(result)

        if any(x == ygojson.Legality.UNLIMITED for x in results):
            return ygojson.Legality.UNLIMITED
        if results:
            return ygojson.Legality.UNRELEASED
        return None

    today = datetime.datetime.now().date()
    if all(date > today for date in dates):
        return ygojson.Legality.UNRELEASED
    else:
        return ygojson.Legality.UNLIMITED


@app.template_filter()
def currentlegality(
    card: ygojson.Card, format: ygojson.Format
) -> typing.Optional[ygojson.Legality]:
    if card.illegal:
        return ygojson.Legality.FORBIDDEN

    if format in card.legality.keys():
        legality = card.legality[format]
        if legality.current:
            return legality.current
        if legality.history:
            return legality.history[-1].legality

    return getDefaultLegality(card, format)


@app.template_filter()
def getlocales(
    thing: typing.Union[ygojson.Set, ygojson.SealedProduct],
) -> typing.Iterable[
    typing.Optional[typing.Union[ygojson.SetLocale, ygojson.SealedProductLocale]]
]:
    if not thing.locales:
        yield None
        return
    yield from thing.locales.values()


@app.template_filter()
def getlocalecontents(
    thing: typing.Union[ygojson.Set, ygojson.SealedProduct],
    locale: typing.Optional[
        typing.Union[ygojson.SetLocale, ygojson.SealedProductLocale]
    ],
) -> typing.Iterable[typing.Union[ygojson.SetContents, ygojson.SealedProductContents]]:
    if not locale:
        yield from thing.contents
        return
    for content in thing.contents:
        if locale in content.locales:
            yield content


@app.template_filter()
def getseteditions(
    set_: ygojson.Set, locale: typing.Optional[ygojson.SetLocale]
) -> typing.Iterable[typing.Optional[ygojson.SetEdition]]:
    result = set()
    if not locale:
        for content in set_.contents:
            result.update(content.editions)
    else:
        result.update(locale.editions)
    if not result:
        yield None
    else:
        yield from result


CARD_BACK_URL = "https://ms.yugipedia.com//e/e5/Back-EN.png"


@app.template_filter()
def printingimage(
    set_: ygojson.Set,
    card: ygojson.Card,
    printing: ygojson.CardPrinting,
    locale: typing.Optional[ygojson.SetLocale],
    edition: typing.Optional[ygojson.SetEdition],
) -> str:
    if not edition:
        edition = ygojson.SetEdition.NONE

    if not printing or not locale:
        if card.images:
            return card.images[0].card_art or CARD_BACK_URL
        return CARD_BACK_URL

    printing = ygodb.printings_by_id[
        printing.id
    ]  # Flask loves to make copies of random objects

    if edition in locale.card_images and printing in locale.card_images[edition]:
        return locale.card_images[edition][printing]
    if edition == ygojson.SetEdition.NONE:
        for e in locale.card_images:
            if printing in locale.card_images[e]:
                return locale.card_images[e][printing]
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


PREFERRED_LOCALES = [
    ygojson.Locale.ENGLISH,
    ygojson.Locale.ENGLISH_AMERICA,
    ygojson.Locale.JAPANESE,
]


@app.template_filter()
def setgenericpackimage(set_: ygojson.Set) -> str:
    for preferred_locale in PREFERRED_LOCALES:
        if preferred_locale in set_.locales and set_.locales[preferred_locale].image:
            return set_.locales[preferred_locale].image or ""
    for locale in set_.locales.values():
        if locale.image:
            return locale.image
    for content in set_.contents:
        if content.image:
            return content.image
    return ""


@app.template_filter()
def setgenericimage(set_: ygojson.Set) -> str:
    return setgenericpackimage(set_) or CARD_BACK_URL


@app.template_filter()
def productgenericimage(product: ygojson.SealedProduct) -> str:
    for preferred_locale in PREFERRED_LOCALES:
        if (
            preferred_locale in product.locales
            and product.locales[preferred_locale].image
        ):
            return product.locales[preferred_locale].image or CARD_BACK_URL
    for locale in product.locales.values():
        if locale.image:
            return locale.image
    for content in product.contents:
        if content.image:
            return content.image
    return CARD_BACK_URL


@app.template_filter()
def seriesgenericimage(series: ygojson.Series) -> str:
    return CARD_BACK_URL


@app.template_filter()
def setformats(set_: ygojson.Set) -> typing.Iterable[ygojson.Format]:
    return {
        f for l in set_.contents for f in l.formats
    }  # TODO: stop using deprecated member


@app.template_filter()
def cardlocales(card: ygojson.Card) -> typing.Iterable[ygojson.Locale]:
    return sorted(
        {
            lc
            for set_ in card.sets
            for lc in set_.locales
            if any(
                p.card.id == card.id
                for content in set_.contents
                for p in content.cards
                if set_.locales[lc] in content.locales
            )
        },
        key=lambda x: x.value,
    )


@app.template_filter()
def cardformats(card: ygojson.Card) -> typing.Iterable[str]:
    return sorted(
        {
            printingformat(None, locale, content)
            for set_ in card.sets
            for content in set_.contents
            for locale in content.locales or [None]
            if any(p.card.id == card.id for p in content.cards)
        }
    )


@app.template_filter()
def cardeditions(card: ygojson.Card) -> typing.Iterable[ygojson.SetEdition]:
    return sorted(
        {
            edition
            for set_ in card.sets
            for content in set_.contents
            for edition in content.editions
            if any(p.card.id == card.id for p in content.cards)
        },
        key=lambda x: x.value,
    )


@app.template_filter()
def cardrarities(card: ygojson.Card) -> typing.Iterable[ygojson.CardRarity]:
    return sorted(
        {
            printing.rarity
            for set_ in card.sets
            for content in set_.contents
            for printing in content.cards
            if printing.card.id == card.id and printing.rarity
        },
        key=lambda x: x.value,
    )


@app.template_filter()
def printingformat(
    printing: typing.Optional[ygojson.CardPrinting],
    locale: typing.Optional[ygojson.SetLocale],
    content: ygojson.SetContents,
) -> str:
    if locale:
        return "/".join(x.value for x in locale.formats)
    return "/".join(x.value for x in content.formats)


@app.template_filter()
def setproducts(set_: ygojson.Set) -> typing.List[ygojson.SealedProduct]:
    result = []
    for product in ygodb.products:
        yielded = False
        for contents in product.contents:
            for pack in contents.packs:
                if pack.set == set_:
                    result.append(product)
                    yielded = True
                    break
            if yielded:
                break
    return result


@app.template_filter()
def getdistrobyid(id: uuid.UUID) -> typing.Optional[ygojson.PackDistrobution]:
    return ygodb.distros_by_id.get(id)


@app.template_filter()
def distrolen(
    distro: ygojson.PackDistrobution, locales: typing.Iterable[ygojson.SetLocale]
) -> int:
    result = 0
    for slot in distro.slots:
        if type(slot) is ygojson.PackDistroSlotCards:
            result += len(slot.cards)
        elif type(slot) is ygojson.PackDistroSlotSet:
            result += max(
                [
                    len(x.cards)
                    for locale in locales
                    for x in getlocalecontents(slot.set, locale)
                ]
            )
        elif type(slot) is ygojson.PackDistroSlotPool:
            result += slot.qty
    return result


@app.template_filter()
def groupcontentsbydistro(
    set_: ygojson.Set,
) -> typing.Dict[
    typing.Union[ygojson.SpecialDistroType, uuid.UUID], typing.List[ygojson.SetContents]
]:
    result: typing.Dict[
        typing.Union[ygojson.SpecialDistroType, uuid.UUID],
        typing.List[ygojson.SetContents],
    ] = {}
    for contents in set_.contents:
        if contents.distrobution:
            result.setdefault(contents.distrobution, [])
            result[contents.distrobution].append(contents)
    return result


@app.template_filter()
def distrolocales(
    set: ygojson.Set, contentslist: typing.List[ygojson.SetContents]
) -> str:
    if len(contentslist) == len(set.contents):
        return ""
    return f" ({'/'.join({*(translatelocale(l.key) for c in contentslist for l in c.locales)})})"


@app.template_filter()
def flatten(xs):
    return search.flatten(xs)


@app.template_test()
def oftypecard(thing) -> bool:
    return type(thing) == ygojson.Card


@app.template_test()
def oftypeset(thing) -> bool:
    return type(thing) == ygojson.Set


@app.template_test()
def oftypeseries(thing) -> bool:
    return type(thing) == ygojson.Series


@app.template_test()
def oftypedistro(thing) -> bool:
    return type(thing) == ygojson.PackDistrobution


@app.template_test()
def oftypeproduct(thing) -> bool:
    return type(thing) == ygojson.SealedProduct


@app.template_test()
def specialdistro(distro) -> bool:
    return type(distro) == ygojson.SpecialDistroType


@app.template_test()
def slotpool(thing) -> bool:
    return type(thing) == ygojson.PackDistroSlotPool


@app.template_test()
def slotcards(thing) -> bool:
    return type(thing) == ygojson.PackDistroSlotCards


@app.template_test()
def slotset(thing) -> bool:
    return type(thing) == ygojson.PackDistroSlotSet


page_load_start_time = time.time()


@app.before_request
def before_request():
    global page_load_start_time
    page_load_start_time = time.time()


@app.after_request
def after_request(response):
    diff = time.time() - page_load_start_time
    if (
        (response.response)
        and (200 <= response.status_code < 300)
        and (response.content_type.startswith("text/html"))
    ):
        response.set_data(
            response.get_data().replace(
                b"__EXECUTION_TIME__", bytes(f"{diff:.4f}", "utf-8")
            )
        )
    return response


def common_template_vars():
    return {
        "yjv_version": __version__,
        "db_version": ygojson.__version__,
        "schema_version": ygojson.SCHEMA_VERSION,
        "accesstime": datetime.datetime.now().isoformat(),
        "en": ygojson.Language.ENGLISH,
    }


@app.route("/")
def index():
    return flask.render_template(
        "index.j2",
        **common_template_vars(),
        ygodb=ygodb,
        cards_of_the_day=cards_of_the_day,
    )


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
        **common_template_vars(),
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
        **common_template_vars(),
        ygodb=ygodb,
        set=ygodb.sets_by_id[uuid],
    )


@app.route("/random-series")
def random_series():
    return app.redirect(
        flask.url_for(
            series.__name__,
            uuid=random.choice([*ygodb.series_by_id]),
        )
    )


@app.route("/series/<uuid:uuid>")
def series(uuid: uuid.UUID):
    return flask.render_template(
        "series.j2",
        **common_template_vars(),
        ygodb=ygodb,
        series=ygodb.series_by_id[uuid],
    )


@app.route("/random-product")
def random_product():
    return app.redirect(
        flask.url_for(
            product.__name__,
            uuid=random.choice([*ygodb.products_by_id]),
        )
    )


@app.route("/product/<uuid:uuid>")
def product(uuid: uuid.UUID):
    return flask.render_template(
        "product.j2",
        **common_template_vars(),
        ygodb=ygodb,
        product=ygodb.products_by_id[uuid],
    )


@app.route("/search")
def search_():
    query = flask.request.args.get("query", "")
    page = int(flask.request.args.get("page", "1"))
    try:
        search_ = search.Search(query)
        results = search_.execute(ygodb)
        hrq = search_.human_readable_query()
        error_msg = None
    except search.SearchFailedException as e:
        results = []
        hrq = None
        error_msg = str(e)
        app.logger.exception(e)

    return flask.render_template(
        "search.j2",
        **common_template_vars(),
        ygodb=ygodb,
        query=query,
        results=results[search.SEARCH_RESULTS_PER_PAGE * (page - 1) :][
            : search.SEARCH_RESULTS_PER_PAGE
        ],
        n_results=len(results),
        SEARCH_RESULTS_PER_PAGE=search.SEARCH_RESULTS_PER_PAGE,
        page=page,
        n_pages=math.ceil(len(results) / search.SEARCH_RESULTS_PER_PAGE),
        human_readable_query=hrq,
        error_message=error_msg,
    )


@app.route("/about")
def about():
    return flask.render_template(
        "about.j2",
        **common_template_vars(),
    )


@app.route("/syntax")
def syntax():
    return flask.render_template(
        "syntax.j2",
        **common_template_vars(),
        FILTERS=search.FILTERS,
        SORTERS=search.SORTERS,
    )
