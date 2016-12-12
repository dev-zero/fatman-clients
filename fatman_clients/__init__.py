

from os import path

try:
    from collections.abc import Iterator
except ImportError:
    from collections import Iterator

CA_BUNDLE_SEARCH_PATHS = [
    "/etc/ssl/ca-bundle.pem",  # OpenSUSE
    "/etc/ssl/certs/ca-certificates.crt",  # Gentoo
    ]


def try_verify_by_system_ca_bundle():
    """Try to locate a system CA bundle and use that if available,
       otherwise, return True to use the bundled (provided by certifi) CA package"""

    for ca_path in CA_BUNDLE_SEARCH_PATHS:
        if path.exists(ca_path):
            return ca_path

    # Return None to fallback to the Python-Requests Session default
    return None


def xyz_parser_iterator(string, include_match_object=False):
    """
    Yields a tuple `(natoms, comment, atomiter)`for each frame
    in a XYZ file where `atomiter` is an iterator yielding a
    nested tuple `(symbol, (x, y, z))` for each entry.

    :param string: a string containing XYZ-structured text
    :param include_match_object: append the original regex match object to the returned tuple
    """

    class BlockIterator(Iterator):
        """
        An iterator for wrapping the iterator returned by `match.finditer`
        to extract the required fields directly from the match object
        """

        def __init__(self, it, natoms, include_match_object=False):
            self._it = it
            self._natoms = natoms
            self._catom = 0
            self._include_match_object = include_match_object

        def __iter__(self):
            return self

        def __next__(self):
            try:
                match = self._it.next()
            except StopIteration:
                # if we reached the number of atoms declared, everything is well
                # and we re-raise the StopIteration exception
                if self._catom == self._natoms:
                    raise
                else:
                    # otherwise we got too less entries
                    raise TypeError("Number of atom entries ({}) is smaller "
                                    "than the number of atoms ({})".format(
                                        self._catom, self._natoms))

            self._catom += 1

            if self._catom > self._natoms:
                raise TypeError("Number of atom entries ({}) is larger "
                                "than the number of atoms ({})".format(
                                    self._catom, self._natoms))

            if self._include_match_object:
                return (
                    match.group('sym'),
                    (
                        float(match.group('x')),
                        float(match.group('y')),
                        float(match.group('z'))
                    ),
                    match)
            else:
                return (
                    match.group('sym'),
                    (
                        float(match.group('x')),
                        float(match.group('y')),
                        float(match.group('z'))
                    ))

        def next(self):
            """
            The iterator method expected by python 2.x,
            implemented as python 3.x style method.
            """
            return self.__next__()

    import re

    pos_regex = re.compile(r"""
^                                                                             # Linestart
[ \t]*                                                                        # Optional white space
(?P<sym>[A-Za-z]+[A-Za-z0-9]*)\s+                                             # get the symbol
(?P<x> [\-|\+]?  ( \d*[\.]\d+  | \d+[\.]?\d* )  ([E | e][+|-]?\d+)? ) [ \t]+  # Get x
(?P<y> [\-|\+]?  ( \d*[\.]\d+  | \d+[\.]?\d* )  ([E | e][+|-]?\d+)? ) [ \t]+  # Get y
(?P<z> [\-|\+]?  ( \d*[\.]\d+  | \d+[\.]?\d* )  ([E | e][+|-]?\d+)? )         # Get z
""", re.X | re.M)
    pos_block_regex = re.compile(r"""
                                                            # First line contains an integer
                                                            # and only an integer: the number of atoms
^[ \t]* (?P<natoms> [0-9]+) [ \t]*[\n]                      # End first line
(?P<comment>.*) [\n]                                        # The second line is a comment
(?P<positions>                                              # This is the block of positions
    (
        (
            \s*                                             # White space in front of the element spec is ok
            (
                [A-Za-z]+[A-Za-z0-9]*                       # Element spec
                (
                   \s+                                      # White space in front of the number
                   [\- | \+ ]?                              # Plus or minus in front of the number (optional)
                    (\d*                                    # optional decimal in the beginning .0001 is ok, for example
                    [\.]                                    # There has to be a dot followed by
                    \d+)                                    # at least one decimal
                    |                                       # OR
                    (\d+                                    # at least one decimal, followed by
                    [\.]?                                   # an optional dot
                    \d*)                                    # followed by optional decimals
                    ([E | e][+|-]?\d+)?                     # optional exponents E+03, e-05
                ){3}                                        # I expect three float values
                |
                \#                                          # If a line is commented out, that is also ok
            )
            .*                                              # I do not care what is after the comment/the position spec
            |                                               # OR
            \s*                                             # A line only containing white space
         )
        [\n]                                                # line break at the end
    )+
)                                                           # A positions block should be one or more lines
                    """, re.X | re.M)

    for block in pos_block_regex.finditer(string):
        natoms = int(block.group('natoms'))
        if include_match_object:
            yield (
                natoms,
                block.group('comment'),
                BlockIterator(
                    pos_regex.finditer(block.group('positions')),
                    natoms,
                    True),
                block
            )
        else:
            yield (
                natoms,
                block.group('comment'),
                BlockIterator(
                    pos_regex.finditer(block.group('positions')),
                    natoms),
                block
            )
