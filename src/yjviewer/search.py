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
    NE = "!="
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


class QueryParser(lark.Transformer):
    def __init__(self, search: "Search") -> None:
        super().__init__(True)
        self.search = search

    def start(self, data) -> typing.Any:
        self.search.terms.extend(data)

    def WORD(self, data) -> typing.Any:
        return TermPredicate(FilterName, FilterMode.DEFAULT, str(data))


class Search:
    query: str
    terms: typing.List[Term]
    sorts: typing.List[Sort]

    def __init__(self, query: str) -> None:
        self.query = query
        self.terms = []
        self.sorts = []

        tree = LANGUAGE.parse(query)
        parsed = QueryParser(self).transform(tree)

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
        if predicate.mode not in {FilterMode.DEFAULT, FilterMode.EQ}:
            raise SearchFailedException(
                f"Search filter 'name' does not accept filer mode '{predicate.mode.value}'!"
            )
        for result in results:
            if type(result) is ygojson.Card:
                if query_normalized in result.text["en"].name.lower():
                    yield result
            elif type(result) is ygojson.Set:
                if query_normalized in result.name["en"].lower():
                    yield result
            elif type(result) is ygojson.Series:
                if query_normalized in result.name["en"].lower():
                    yield result
            elif type(result) is ygojson.SealedProduct:
                if query_normalized in result.name["en"].lower():
                    yield result


FILTERS = [
    FilterName,
]

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
