# Mock nova3 novaprinter for testing
import re
import urllib.parse
from typing import NotRequired, TypedDict, get_type_hints

SearchResults = TypedDict('SearchResults', {
    'link': str,
    'name': str,
    'size': float | int | str,
    'seeds': int,
    'leech': int,
    'engine_url': str,
    'desc_link': NotRequired[str],
    'pub_date': NotRequired[int]
})

_unescapedFields = tuple(field for field in get_type_hints(SearchResults).keys() if field not in {'name'})
captured_output = []

def prettyPrinter(dictionary: SearchResults) -> None:
    delimiter = "|"
    for key in _unescapedFields:
        value = str(dictionary.get(key, ''))
        if delimiter in value:
            raise ValueError(f'found unexpected delimiter character ({delimiter}) in value. Key: "{key}". Value: "{value}".')

    outtext = delimiter.join((
        dictionary["link"],
        urllib.parse.quote(dictionary["name"]),
        str(anySizeToBytes(dictionary['size'])),
        str(dictionary["seeds"]),
        str(dictionary["leech"]),
        dictionary["engine_url"],
        dictionary.get("desc_link", ""),
        str(dictionary.get("pub_date", -1))
    ))
    captured_output.append(outtext)

_sizeUnitRegex: re.Pattern[str] = re.compile(r"^(?P<size>\d*\.?\d+) *(?P<unit>[a-z]+)?", re.IGNORECASE)

def anySizeToBytes(size_string: float | int | str) -> int:
    if isinstance(size_string, int):
        return size_string
    if isinstance(size_string, float):
        return round(size_string)

    match = _sizeUnitRegex.match(size_string.strip())
    if match is None:
        return -1

    size = float(match.group('size'))
    unit = match.group('unit')
    if unit is not None:
        units_exponents = {'T': 40, 'G': 30, 'M': 20, 'K': 10}
        exponent = units_exponents.get(unit[0].upper(), 0)
        size *= 2**exponent

    return round(size)
