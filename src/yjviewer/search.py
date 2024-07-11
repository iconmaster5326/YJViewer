import datetime
import enum
import os
import typing

import lark
import ygojson

SEARCH_RESULTS_PER_PAGE = 200

Thing = typing.Union[ygojson.Card, ygojson.Set, ygojson.Series, ygojson.SealedProduct]


class SearchFailedException(Exception):
    pass


class SortDir(enum.Enum):
    ASC = 0
    DESC = 1


class Sorter:
    names: typing.ClassVar[typing.List[str]]

    @classmethod
    def execute(cls, db: ygojson.Database, result: Thing, dir: SortDir) -> typing.Any:
        raise NotImplementedError


class Sort:
    sorter: typing.Type[Sorter]
    dir: SortDir

    def __init__(self, sorter: typing.Type[Sorter], dir: SortDir) -> None:
        self.sorter = sorter
        self.dir = dir

    def execute(self, db: ygojson.Database, result: Thing) -> typing.Any:
        return self.sorter.execute(db, result, self.dir)


class FilterMode(enum.Enum):
    DEFAULT = ":"
    EQ = "="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


class Filter:
    names: typing.ClassVar[typing.List[str]]

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
        predicate: "TermPredicate",
        results: typing.Iterable[Thing],
    ) -> typing.Iterable[Thing]:
        raise NotImplementedError


class Term:
    def execute(
        self, db: ygojson.Database, results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        raise NotImplementedError


def _flatten(xs):
    if not isinstance(xs, list):
        yield xs
        return
    for x in xs:
        yield from _flatten(x)


SORT_FILTER = "sort"


class QueryParser(lark.Transformer):
    def __init__(self, search: "Search") -> None:
        super().__init__(True)
        self.search = search

    def start(self, data) -> typing.Any:
        self.search.terms.extend(_flatten(data))

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

        if filtername_normalized not in FILTER_NAME_MAP:
            raise SearchFailedException(f"Unknown filter '{filtername}'!")
        return TermPredicate(
            FILTER_NAME_MAP[filtername_normalized], FilterMode(cmpop), word
        )

    def parens(self, data) -> typing.Any:
        return data

    def alternation(self, data) -> typing.Any:
        return TermOr([*_flatten(data)])

    def negation(self, data) -> typing.Any:
        return TermNegate([*_flatten(data)])

    def WORD(self, token) -> typing.Any:
        return str(token)

    def ESCAPED_STRING(self, token) -> typing.Any:
        return str(token)[1:-1]


class Search:
    query: str
    terms: typing.List[Term]
    sorts: typing.List[Sort]

    def __init__(self, query: str) -> None:
        self.query = query
        self.terms = []
        self.sorts = []

        tree = LANGUAGE.parse(query)
        # print(tree.pretty())
        QueryParser(self).transform(tree)

        if not self.sorts:
            self.sorts = [Sort(SorterClass, SortDir.ASC), Sort(SorterName, SortDir.ASC)]

    def human_readable_query(self) -> str:
        return f"things whose name contains '{self.query}'"

    def execute(self, db: ygojson.Database) -> typing.List[Thing]:
        results = [*db.cards, *db.sets, *db.products, *db.series]
        for term in self.terms:
            results = term.execute(db, results)
        return sorted(
            results, key=lambda x: tuple(sort.execute(db, x) for sort in self.sorts)
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
        self, db: ygojson.Database, results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        return self.filter.execute(db, self, results)


class TermOr(Term):
    terms: typing.List[Term]

    def __init__(self, terms: typing.List[Term]) -> None:
        super().__init__()
        self.terms = terms

    def execute(
        self, db: ygojson.Database, results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        for result in results:
            for term in self.terms:
                if [*term.execute(db, [result])]:
                    yield result
                    break


class TermNegate(Term):
    terms: typing.List[Term]

    def __init__(self, terms: typing.List[Term]) -> None:
        super().__init__()
        self.terms = terms

    def execute(
        self, db: ygojson.Database, results: typing.Iterable[Thing]
    ) -> typing.Iterable[Thing]:
        for result in results:
            subresults = [result]
            for term in self.terms:
                subresults = [*term.execute(db, subresults)]
            if not subresults:
                yield result


###################
# FILTERS
###################


class FilterName(Filter):
    names = ["name", "n"]

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
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
                if cmp(result.text["en"].name.lower()):
                    yield result
            elif type(result) is ygojson.Set:
                if cmp(result.name["en"].lower()):
                    yield result
            elif type(result) is ygojson.Series:
                if cmp(result.name["en"].lower()):
                    yield result
            elif type(result) is ygojson.SealedProduct:
                if cmp(result.name["en"].lower()):
                    yield result


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


class FilterClass(Filter):
    names = ["class", "cl", ""]

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
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


class FilterType(Filter):
    names = ["type", "t"]

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
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


class FilterAttribute(Filter):
    names = ["attribute", "attr", "a"]

    @classmethod
    def execute(
        cls,
        db: ygojson.Database,
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


class FilterATK(FilterInt):
    names = ["attack", "atk", "at"]

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.atk
        return None


class FilterDEF(FilterInt):
    names = ["defence", "defense", "def", "de"]

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.def_
        return None


class FilterLevel(FilterInt):
    names = ["level", "lvl", "lv", "l"]

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.level
        return None


class FilterRank(FilterInt):
    names = ["rank", "r"]

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.rank
        return None


class FilterScale(FilterInt):
    names = ["scale", "sc"]

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return result.scale
        return None


class FilterLinkRating(FilterInt):
    names = ["linkrating", "link", "lr"]

    @classmethod
    def get_int_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Union[None, int, str]:
        if type(result) is ygojson.Card:
            return len(result.link_arrows or [])
        return None


def _date_to_timestamp(date: datetime.date) -> float:
    return datetime.datetime(date.year, date.month, date.day).timestamp()


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


class FilterDateOfRelease(FilterDate):
    names = ["date", "d"]

    @classmethod
    def get_date_prop(
        cls, db: ygojson.Database, predicate: "TermPredicate", result: Thing
    ) -> typing.Optional[datetime.date]:
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
        return None


FILTERS = [
    FilterName,
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

    @classmethod
    def execute(cls, db: ygojson.Database, result: Thing, dir: SortDir) -> typing.Any:
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


class SorterName(Sorter):
    names = ["names", "name", "n"]

    @classmethod
    def execute(cls, db: ygojson.Database, result: Thing, dir: SortDir) -> typing.Any:
        if type(result) is ygojson.Card:
            s = result.text["en"].name.lower()
        elif type(result) is ygojson.Set:
            s = result.name["en"].lower()
        elif type(result) is ygojson.Series:
            s = result.name["en"].lower()
        elif type(result) is ygojson.SealedProduct:
            s = result.name["en"].lower()
        else:
            s = str(result)

        if dir == SortDir.ASC:
            return s
        else:
            return tuple(-ord(c) for c in s)


SORTERS = [
    SorterClass,
    SorterName,
]

SORTER_NAME_MAP = {name: sorter for sorter in SORTERS for name in sorter.names}
