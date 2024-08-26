import datetime
import enum
import math
import os
import sys
import typing

import lark
import ygojson

from .locales import LOCALE_TRANSLATED

SEARCH_RESULTS_PER_PAGE = 100

Thing = typing.Union[ygojson.Card, ygojson.Set, ygojson.Series, ygojson.SealedProduct]


class SearchFailedException(Exception):
    pass


class SortDir(enum.Enum):
    ASC = 0
    DESC = 1


class Sorter:
    names: typing.ClassVar[typing.List[str]]
    desc: typing.ClassVar[str]

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        raise NotImplementedError

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        raise NotImplementedError


class Sort:
    sorter: typing.Type[Sorter]
    dir: SortDir

    def __init__(self, sorter: typing.Type[Sorter], dir: SortDir) -> None:
        self.sorter = sorter
        self.dir = dir

    def execute(
        self, db: ygojson.Database, search: "Search", result: Thing
    ) -> typing.Any:
        return self.sorter.execute(search, db, result, self.dir)

    def human_readable_query(self, search: "Search") -> str:
        if self.dir == SortDir.ASC:
            return self.sorter.human_readable_query(search)
        else:
            return self.sorter.human_readable_query(search) + " (descending)"


class FilterMode(enum.Enum):
    DEFAULT = ":"
    EQ = "="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


class Filter:
    names: typing.ClassVar[typing.List[str]]
    desc: typing.ClassVar[str]

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        raise NotImplementedError

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        raise NotImplementedError


class Term:
    def execute(
        self, db: ygojson.Database, search: "Search", results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        raise NotImplementedError

    def human_readable_query(self, search: "Search") -> str:
        raise NotImplementedError


def flatten(xs):
    if not isinstance(xs, list):
        yield xs
        return
    for x in xs:
        yield from flatten(x)


SORT_FILTER = "sort"
LOCALE_FILTER = "locale"


class QueryParser(lark.Transformer):
    def __init__(self, search: "Search") -> None:
        super().__init__(True)
        self.search = search

    def start(self, data) -> typing.Any:
        self.search.terms.extend(flatten(data))

    def predicate_simple(self, data) -> typing.Any:
        (word,) = data
        return TermPredicate(FilterName, FilterMode.DEFAULT, word)

    def predicate_class(self, data) -> typing.Any:
        (cmpop, word) = data
        return TermPredicate(FilterClass, FilterMode(cmpop), word)

    def predicate_full(self, data) -> typing.Any:
        (filtername, cmpop, word) = data
        filtername_normalized = filtername.strip().lower()

        if filtername_normalized == SORT_FILTER:
            sorter_split = [x.strip() for x in word.split("-")]
            if not sorter_split:
                raise SearchFailedException(
                    f"No sorter given! You need something after the 'sort:'."
                )
            if len(sorter_split) > 2:
                raise SearchFailedException(
                    f"Too many arguments to the sorter given! The format is 'sort:SORTER[-DIRECTION]'."
                )
            sortername = sorter_split[0]
            if len(sorter_split) == 2:
                if sorter_split[1] == "asc":
                    dir_ = SortDir.ASC
                elif sorter_split[1] == "desc":
                    dir_ = SortDir.DESC
                else:
                    raise SearchFailedException(
                        f"Unknown sorting direction '{sorter_split[1]}'!"
                    )
            else:
                dir_ = SortDir.ASC
            if sortername not in SORTER_NAME_MAP:
                raise SearchFailedException(f"Unknown sorter '{filtername}'!")
            self.search.sorts.append(Sort(SORTER_NAME_MAP[sortername], dir_))
            return []

        if filtername_normalized == LOCALE_FILTER:
            try:
                self.search.locales.add(ygojson.Locale.normalize(word.strip().lower()))
            except ValueError:
                raise SearchFailedException(f"Unknown locale '{word}'!")
            return []

        if filtername_normalized not in FILTER_NAME_MAP:
            raise SearchFailedException(f"Unknown filter '{filtername}'!")
        return TermPredicate(
            FILTER_NAME_MAP[filtername_normalized], FilterMode(cmpop), word
        )

    def parens(self, data) -> typing.Any:
        return data

    def alternation(self, data) -> typing.Any:
        return TermOr([*flatten(data)])

    def negation(self, data) -> typing.Any:
        return TermNegate([*flatten(data)])

    def WORD(self, token) -> typing.Any:
        return str(token)

    def ESCAPED_STRING(self, token) -> typing.Any:
        return str(token)[1:-1]


class Search:
    query: str
    terms: typing.List[Term]
    sorts: typing.List[Sort]
    locales: typing.Set[ygojson.Locale]

    def __init__(self, query: str) -> None:
        self.query = query
        self.terms = []
        self.sorts = []
        self.locales = set()

        try:
            tree = LANGUAGE.parse(query)
            # print(tree.pretty())
            QueryParser(self).transform(tree)
        except lark.exceptions.VisitError as e:
            if type(e.orig_exc) is SearchFailedException:
                raise e.orig_exc
            else:
                raise
        except (lark.exceptions.LexError, lark.exceptions.ParseError) as e:
            raise SearchFailedException(f"{e}")

        if not self.sorts:
            self.sorts = [Sort(SorterClass, SortDir.ASC), Sort(SorterName, SortDir.ASC)]

    def human_readable_query(self) -> str:
        result = "all things"
        if self.terms:
            result += " "
            result += " AND ".join(x.human_readable_query(self) for x in self.terms)
        if self.sorts:
            result += ", sorted by "
            result += " and then ".join(
                x.human_readable_query(self) for x in self.sorts
            )
        if self.locales:
            result += ", in "
            result += " / ".join(
                LOCALE_TRANSLATED.get(x, x.value) for x in self.locales
            )
        return result

    def _exclude_cards_out_of_locale(
        self, results: typing.Iterable[ygojson.Card]
    ) -> typing.Iterable[ygojson.Card]:
        if not self.locales:
            yield from results
            return
        for result in results:
            if any(l in result.text and result.text[l].official for l in self.locales):
                yield result

    def _exclude_sets_out_of_locale(
        self, results: typing.Iterable[typing.Union[ygojson.Set, ygojson.SealedProduct]]
    ) -> typing.Iterable[typing.Union[ygojson.Set, ygojson.SealedProduct]]:
        if not self.locales:
            yield from results
            return
        for result in results:
            if any(l in result.locales for l in self.locales):
                yield result

    def _exclude_series_out_of_locale(
        self, results: typing.Iterable[ygojson.Series]
    ) -> typing.Iterable[ygojson.Series]:
        if not self.locales:
            yield from results
            return
        for result in results:
            if any(l in result.name for l in self.locales):
                yield result

    def execute(self, db: ygojson.Database) -> typing.List[Thing]:
        results = [
            *self._exclude_cards_out_of_locale(db.cards),
            *self._exclude_sets_out_of_locale(db.sets),
            *self._exclude_sets_out_of_locale(db.products),
            *self._exclude_series_out_of_locale(db.series),
        ]
        if not self.locales:
            self.locales = {ygojson.Locale.ENGLISH, ygojson.Locale.JAPANESE}
        for term in self.terms:
            results = term.execute(db, self, results)
        return sorted(
            results,
            key=lambda x: tuple(sort.execute(db, self, x) for sort in self.sorts),
        )


with open(
    os.path.join(os.path.dirname(__file__), "search.lark"), encoding="utf-8"
) as file:
    LANGUAGE = lark.Lark(file)

###################
# TERMS
###################


class TermPredicate(Term):
    filter: typing.Type[Filter]
    mode: FilterMode
    value: str

    def __init__(
        self, filter: typing.Type[Filter], mode: FilterMode, value: str
    ) -> None:
        super().__init__()
        self.filter = filter
        self.mode = mode
        self.value = value

    def execute(
        self, db: ygojson.Database, search: "Search", results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        return self.filter.execute(db, search, self, results)

    def human_readable_query(self, search: "Search") -> str:
        return self.filter.human_readable_query(search, self)


class TermOr(Term):
    terms: typing.List[Term]

    def __init__(self, terms: typing.List[Term]) -> None:
        super().__init__()
        self.terms = terms

    def execute(
        self, db: ygojson.Database, search: "Search", results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        for result in results:
            for term in self.terms:
                if [*term.execute(db, search, [result])]:
                    yield result
                    break

    def human_readable_query(self, search: "Search") -> str:
        return (
            "(" + " OR ".join(x.human_readable_query(search) for x in self.terms) + ")"
        )


class TermNegate(Term):
    terms: typing.List[Term]

    def __init__(self, terms: typing.List[Term]) -> None:
        super().__init__()
        self.terms = terms

    def execute(
        self, db: ygojson.Database, search: "Search", results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        for result in results:
            subresults = [result]
            for term in self.terms:
                subresults = [*term.execute(db, search, subresults)]
            if not subresults:
                yield result

    def human_readable_query(self, search: "Search") -> str:
        return (
            "NOT ("
            + " AND ".join(x.human_readable_query(search) for x in self.terms)
            + ")"
        )


###################
# FILTERS
###################


class FilterName(Filter):
    names = ["name", "n"]
    desc = "Filter by card name in the selected locales."

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()

        def cmp(s: str) -> bool:
            if predicate.mode == FilterMode.DEFAULT:
                return query_normalized in s
            elif predicate.mode == FilterMode.EQ:
                return query_normalized == s
            raise SearchFailedException(
                f"Search filter 'name' does not accept filter mode '{predicate.mode.value}'!"
            )

        for result in results:
            if type(result) is ygojson.Card:
                if any(
                    l.language in result.text
                    and cmp(result.text[l.language].name.lower())
                    for l in search.locales
                ):
                    yield result
            elif type(result) is ygojson.Set:
                if any(
                    l.language in result.name and cmp(result.name[l.language].lower())
                    for l in search.locales
                ):
                    yield result
            elif type(result) is ygojson.Series:
                if any(
                    l.language in result.name and cmp(result.name[l.language].lower())
                    for l in search.locales
                ):
                    yield result
            elif type(result) is ygojson.SealedProduct:
                if any(
                    l.language in result.name and cmp(result.name[l.language].lower())
                    for l in search.locales
                ):
                    yield result

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        if predicate.mode == FilterMode.DEFAULT:
            return f"whose name contains '{predicate.value}'"
        elif predicate.mode == FilterMode.EQ:
            return f"named '{predicate.value}'"
        else:
            return f"<ERROR: bad mode '{predicate.mode.value}'>"


class FilterEffect(Filter):
    names = ["effect", "e"]
    desc = "Filter by effect text or card lore in the selected locales."

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()

        def cmp(s: str) -> bool:
            if predicate.mode == FilterMode.DEFAULT:
                return query_normalized in s
            elif predicate.mode == FilterMode.EQ:
                return query_normalized == s
            raise SearchFailedException(
                f"Search filter 'effect' does not accept filter mode '{predicate.mode.value}'!"
            )

        for result in results:
            if type(result) is ygojson.Card:
                if any(
                    l in result.text
                    and cmp(
                        (
                            (result.text[l].pendulum_effect or "")
                            + "\n"
                            + (result.text[l].effect or "")
                        )
                        .strip()
                        .lower()
                    )
                    for l in search.locales
                ):
                    yield result

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        if predicate.mode == FilterMode.DEFAULT:
            return f"whose effect contains '{predicate.value}'"
        elif predicate.mode == FilterMode.EQ:
            return f"whose effect is '{predicate.value}'"
        else:
            return f"<ERROR: bad mode '{predicate.mode.value}'>"


FILTER_CLASS_OPTIONS = {
    "card": ygojson.Card,
    "c": ygojson.Card,
    "set": ygojson.Set,
    "pack": ygojson.Set,
    "s": ygojson.Set,
    "product": ygojson.SealedProduct,
    "sealed": ygojson.SealedProduct,
    "sealedproduct": ygojson.SealedProduct,
    "sealed-product": ygojson.SealedProduct,
    "sealed_product": ygojson.SealedProduct,
    "p": ygojson.SealedProduct,
    "sp": ygojson.SealedProduct,
    "series": ygojson.Series,
    "archetype": ygojson.Series,
    "a": ygojson.Series,
}

THING_NAMES = {
    ygojson.Card: "cards",
    ygojson.Set: "sets",
    ygojson.SealedProduct: "sealed products",
    ygojson.Series: "series/archetypes",
}


class FilterClass(Filter):
    names = ["class", "cl", ""]
    desc = "Filter by what type of thing you want to see: <tt>card</tt>, <tt>set<tt>, <tt>product</tt>, or <tt>series</tt>."

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()
        if predicate.mode not in {FilterMode.DEFAULT, FilterMode.EQ}:
            raise SearchFailedException(
                f"Search filter 'class' does not accept filter mode '{predicate.mode.value}'!"
            )
        if query_normalized not in FILTER_CLASS_OPTIONS:
            raise SearchFailedException(
                f"""Search filter 'class' does not accept value '{query_normalized}'!
Accaptable values include 'card' (or 'c'), 'pack'/'set' or ('s'), 'sealed'/'product' (or 'p'), or 'series'/'archetype' (or 'a')."""
            )
        clazz = FILTER_CLASS_OPTIONS[query_normalized]
        for result in results:
            if type(result) is clazz:
                yield result

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        thingtype = FILTER_CLASS_OPTIONS.get(predicate.value.strip().lower())
        if not thingtype:
            return f"<ERROR: bad value '{predicate.value}'>"
        return f"that are {THING_NAMES[thingtype]}"


class FilterType(Filter):
    names = ["type", "t"]
    desc = "Filter by the contents of a card's typeline."

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()

        def cmp(s: str) -> bool:
            if predicate.mode == FilterMode.DEFAULT:
                return query_normalized in s
            elif predicate.mode == FilterMode.EQ:
                return query_normalized in s.split("\n")
            raise SearchFailedException(
                f"Search filter 'type' does not accept filter mode '{predicate.mode.value}'!"
            )

        for result in results:
            if type(result) is ygojson.Card:
                if cmp(
                    "\n".join(
                        [
                            result.card_type.value,
                            result.type.value if result.type else "",
                            result.subcategory.value if result.subcategory else "",
                            result.character if result.character else "",
                            result.skill_type if result.skill_type else "",
                            *[t.value for t in result.monster_card_types or []],
                            *[t.value for t in result.classifications or []],
                            *[t.value for t in result.abilities or []],
                        ]
                    )
                ):
                    yield result

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        if predicate.mode == FilterMode.DEFAULT:
            return f"whose typeline contains '{predicate.value}'"
        elif predicate.mode == FilterMode.EQ:
            return f"whose typeline contains exactly '{predicate.value}'"
        else:
            return f"<ERROR: bad mode '{predicate.mode.value}'>"


class FilterAttribute(Filter):
    names = ["attribute", "attr", "a"]
    desc = "Filter by a card's attribute."

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()

        def cmp(s: str) -> bool:
            if predicate.mode == FilterMode.DEFAULT:
                return query_normalized in s
            elif predicate.mode == FilterMode.EQ:
                return query_normalized == s
            raise SearchFailedException(
                f"Search filter 'attribute' does not accept filter mode '{predicate.mode.value}'!"
            )

        for result in results:
            if type(result) is ygojson.Card:
                if result.attribute and cmp(result.attribute.value):
                    yield result

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"whose attribute is '{predicate.value}'"


class FilterInt(Filter):
    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        raise NotImplementedError

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()

        def cmp(s: typing.Union[str, int]) -> bool:
            try:
                query_int = int(query_normalized)
                if (
                    predicate.mode == FilterMode.DEFAULT
                    or predicate.mode == FilterMode.EQ
                ):
                    return query_int == s
                elif predicate.mode == FilterMode.GT and type(s) is int:
                    return s > query_int
                elif predicate.mode == FilterMode.GE and type(s) is int:
                    return s >= query_int
                elif predicate.mode == FilterMode.LT and type(s) is int:
                    return s < query_int
                elif predicate.mode == FilterMode.LE and type(s) is int:
                    return s <= query_int
                return False
            except ValueError:
                if (
                    predicate.mode == FilterMode.DEFAULT
                    or predicate.mode == FilterMode.EQ
                ):
                    return query_normalized == s
                raise SearchFailedException(
                    f"Search filter '{cls.names[0]}' does not accept filter mode '{predicate.mode.value}' for non-number values!"
                )

        for result in results:
            value = cls.get_int_prop(db, predicate, result)
            if value is not None and cmp(value):
                yield result


FILTER_MODE_TO_NAME = {
    FilterMode.DEFAULT: "is",
    FilterMode.EQ: "is exactly",
    FilterMode.GT: "is greater than",
    FilterMode.LT: "is less than",
    FilterMode.GE: "is greater than or equal to",
    FilterMode.LE: "is less than or equal to",
}


class FilterATK(FilterInt):
    names = ["attack", "atk", "at"]
    desc = "Filter by cards with, greater than, or less than a certain ATK."

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.atk
        return None

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"whose ATK {FILTER_MODE_TO_NAME[predicate.mode]} {predicate.value}"


class FilterDEF(FilterInt):
    names = ["defence", "defense", "def", "de"]
    desc = "Filter by cards with, greater than, or less than a certain DEF."

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.def_
        return None

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"whose DEF {FILTER_MODE_TO_NAME[predicate.mode]} {predicate.value}"


class FilterLevel(FilterInt):
    names = ["level", "lvl", "lv", "l"]
    desc = "Filter by cards with, greater than, or less than a certain level. This does NOT match to Xyz monsters."

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.level
        return None

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"whose level {FILTER_MODE_TO_NAME[predicate.mode]} {predicate.value}"


class FilterRank(FilterInt):
    names = ["rank", "r"]
    desc = "Filter by cards with, greater than, or less than a certain rank. This does NOT match to non-Xyz monsters."

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.rank
        return None

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"whose rank {FILTER_MODE_TO_NAME[predicate.mode]} {predicate.value}"


class FilterScale(FilterInt):
    names = ["scale", "sc"]
    desc = "Filter by cards with, greater than, or less than a certain pendulum scale."

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.scale
        return None

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"whose pendulum scale {FILTER_MODE_TO_NAME[predicate.mode]} {predicate.value}"


class FilterLinkRating(FilterInt):
    names = ["linkrating", "link", "lr"]
    desc = "Filter by cards with, greater than, or less than a certain link rating."

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return len(result.link_arrows or [])
        return None

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return (
            f"whose link rating {FILTER_MODE_TO_NAME[predicate.mode]} {predicate.value}"
        )


def _date_to_timestamp(date: datetime.date) -> float:
    return datetime.datetime(date.year, date.month, date.day).timestamp()


FILTER_MODE_TO_DATE_NAME = {
    FilterMode.DEFAULT: "on",
    FilterMode.EQ: "on exactly",
    FilterMode.GT: "after",
    FilterMode.LT: "before",
    FilterMode.GE: "on or after",
    FilterMode.LE: "on or before",
}


class FilterDate(Filter):
    @classmethod
    def get_date_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Optional[datetime.date]:
        raise NotImplementedError

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        search: "Search",
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        query_normalized = predicate.value.strip().lower()

        def cmp(s: float) -> bool:
            try:
                query_timestamp = _date_to_timestamp(
                    datetime.date.fromisoformat(query_normalized)
                )
                if (
                    predicate.mode == FilterMode.DEFAULT
                    or predicate.mode == FilterMode.EQ
                ):
                    return s == query_timestamp
                elif predicate.mode == FilterMode.GT:
                    return s > query_timestamp
                elif predicate.mode == FilterMode.GE:
                    return s >= query_timestamp
                elif predicate.mode == FilterMode.LT:
                    return s < query_timestamp
                elif predicate.mode == FilterMode.LE:
                    return s <= query_timestamp
                return False
            except ValueError:
                raise SearchFailedException(
                    f"Search filter '{cls.names[0]}' does not accept non-date values!\nDates are expected in ISO format (YYYY-MM-DD)."
                )

        for result in results:
            value = cls.get_date_prop(db, predicate, result)
            if value is not None and cmp(_date_to_timestamp(value)):
                yield result


def _get_release_date(result: Thing) -> typing.Optional[datetime.date]:
    if type(result) is ygojson.Card:
        dates = []
        for set_ in result.sets:
            locales: typing.Set[ygojson.SetLocale] = set()
            for content in set_.contents:
                for printing in content.cards:
                    if printing.card == result:
                        locales.update(content.locales)
            if not locales and set_.date:
                dates.append(set_.date)
            for locale in locales:
                if locale.date:
                    dates.append(locale.date)
        if dates:
            return min(dates)
    elif type(result) is ygojson.Set or type(result) is ygojson.SealedProduct:
        if result.date:
            return result.date
        dates = [x.date for x in result.locales.values() if x.date]
        if dates:
            return min(dates)
    else:
        return None


class FilterDateOfRelease(FilterDate):
    names = ["date", "d"]
    desc = "Filter by cards and/or sets that came out for the first time at, before, or after the given date."

    @classmethod
    def get_date_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Optional[datetime.date]:
        return _get_release_date(result)

    @classmethod
    def human_readable_query(cls, search: "Search", predicate: "TermPredicate") -> str:
        return f"who were released {FILTER_MODE_TO_DATE_NAME[predicate.mode]} {predicate.value}"


FILTERS = [
    FilterName,
    FilterEffect,
    FilterClass,
    FilterType,
    FilterAttribute,
    FilterATK,
    FilterDEF,
    FilterLevel,
    FilterScale,
    FilterLinkRating,
    FilterLevel,
    FilterRank,
    FilterScale,
    FilterLinkRating,
    FilterDateOfRelease,
]

FILTER_NAME_MAP = {name: filter for filter in FILTERS for name in filter.names}

###################
# SORTERS
###################


class SorterClass(Sorter):
    names = ["classes", "class", "cl"]
    desc = "Sort by what type of thing it is, in card -> set -> sealed product -> series/archetype order."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        dir_factor = 1 if dir == SortDir.ASC else -1
        if type(result) is ygojson.Card:
            return 1 * dir_factor
        elif type(result) is ygojson.Set:
            return 2 * dir_factor
        elif type(result) is ygojson.Series:
            return 4 * dir_factor
        elif type(result) is ygojson.SealedProduct:
            return 3 * dir_factor
        else:
            return 5 * dir_factor

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "class"


class SorterName(Sorter):
    names = ["names", "name", "n"]
    desc = "Sort by names in the selected locale."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            s = "\n".join(
                (
                    result.text[l.language].name.lower()
                    if l.language in result.text
                    else "�"
                )
                for l in sorted(search.locales, key=lambda x: x.value)
            )
        elif type(result) is ygojson.Set:
            s = "\n".join(
                (result.name[l.language].lower() if l.language in result.name else "�")
                for l in sorted(search.locales, key=lambda x: x.value)
            )
        elif type(result) is ygojson.Series:
            s = "\n".join(
                (result.name[l.language].lower() if l.language in result.name else "�")
                for l in sorted(search.locales, key=lambda x: x.value)
            )
        elif type(result) is ygojson.SealedProduct:
            s = "\n".join(
                (result.name[l.language].lower() if l.language in result.name else "�")
                for l in sorted(search.locales, key=lambda x: x.value)
            )
        else:
            return None

        if dir == SortDir.ASC:
            return s
        else:
            return tuple(-ord(c) for c in s)

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "name"


class SorterATK(Sorter):
    names = ["attack", "atk", "at"]
    desc = "Sort by ATK."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            v = result.atk
            if v is None:
                return sys.maxsize
            elif type(v) is str:
                return sys.maxsize - 1
            elif dir == SortDir.ASC:
                return v
            else:
                return -int(v)
        else:
            return sys.maxsize

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "ATK"


class SorterDEF(Sorter):
    names = ["defence", "defense", "def", "de"]
    desc = "Sort by DEF."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            v = result.def_
            if v is None:
                return sys.maxsize
            elif type(v) is str:
                return sys.maxsize - 1
            elif dir == SortDir.ASC:
                return v
            else:
                return -int(v)
        else:
            return sys.maxsize

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "DEF"


class SorterLevel(Sorter):
    names = ["level", "lvl", "lv", "l"]
    desc = "Sort by level. Does NOT sort ranks in with levels."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            v = result.level
            if v is None:
                return sys.maxsize
            elif dir == SortDir.ASC:
                return v
            else:
                return -int(v)
        else:
            return sys.maxsize

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "level"


class SorterRank(Sorter):
    names = ["rank", "r"]
    desc = "Sort by rank. Does NOT sort levels in with ranks."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            v = result.rank
            if v is None:
                return sys.maxsize
            elif dir == SortDir.ASC:
                return v
            else:
                return -int(v)
        else:
            return sys.maxsize

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "rank"


class SorterScale(Sorter):
    names = ["scale", "sc"]
    desc = "Sort by pendulum scale."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            v = result.scale
            if v is None:
                return sys.maxsize
            elif dir == SortDir.ASC:
                return v
            else:
                return -int(v)
        else:
            return sys.maxsize

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "pendulum scale"


class SorterLink(Sorter):
    names = ["linkranking", "link", "lr"]
    desc = "Sort by link rating."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        if type(result) is ygojson.Card:
            v = len(result.link_arrows or [])
            if dir == SortDir.ASC:
                return v
            else:
                return -int(v)
        else:
            return sys.maxsize

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "link rating"


class SorterDate(Sorter):
    names = ["date", "d"]
    desc = "Sort by first release date."

    @classmethod
    def execute(
        cls, search: "Search", db: ygojson.Database, result: Thing, dir: SortDir
    ) -> typing.Any:
        date = _get_release_date(result)
        if date is None:
            return math.inf
        elif dir == SortDir.ASC:
            return _date_to_timestamp(date)
        elif dir == SortDir.DESC:
            return -_date_to_timestamp(date)

    @classmethod
    def human_readable_query(cls, search: "Search") -> str:
        return "release date"


SORTERS = [
    SorterClass,
    SorterName,
    SorterATK,
    SorterDEF,
    SorterLevel,
    SorterRank,
    SorterScale,
    SorterLink,
    SorterDate,
]

SORTER_NAME_MAP = {name: sorter for sorter in SORTERS for name in sorter.names}
