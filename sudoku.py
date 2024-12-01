# MIT License
#
# Copyright (c) 2024 Neil Webber
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import itertools
from collections import namedtuple
from enum import Enum
from math import isqrt

# TERMINOLOGY:
#    A Sudoku is a 'SIZE' x 'SIZE' 'grid' of 'cells' into which
#    'symbols' are placed according to the 'One Rule'.
#
#    The grid has SIZE 'rows', and SIZE 'columns', numbered top-to-bottom
#    and left-to-right starting with zero (e.g., "row zero" is the top row).
#
#    The grid also has SIZE arbitrarily-shaped 'regions' of SIZE cells each.
#    A standard 9x9 Sudoku has nine 3x3 regions arranged/numbered like this:
#
#              REGIONS                  NUMBERING
#
#            ...  ...  ...
#            ...  ...  ...             0    1    2
#            ...  ...  ...
#
#            ...  ...  ...
#            ...  ...  ...             3    4    5
#            ...  ...  ...
#
#            ...  ...  ...
#            ...  ...  ...             6    7    8
#            ...  ...  ...
#
#    When regions are square (e.g., in a 9x9 puzzle w/3x3 regions) they are
#    often called 'boxes'; however, this code sticks to 'region' as a term.
#    If the SIZE of the puzzle is not a square, the regions will be
#    irregular shapes (of SIZE cells) instead of boxes.
#
#    Every cell contains an 'element' chosen from a set of SIZE choices.
#    In a standard 9x9 Sudoku the elements are usually digits 1 through 9.
#    However, nothing about the puzzle relies on the mathematic properties
#    of such a choice. As an example, in a 9x9 puzzle these nine elements
#    would work equally well instead of digits 1 through 9:
#
#          '@' 'x' 'q' 'b' '%' 'd' '7' '!' '4'
#
#    Collectively, rows, columns and regions are called "groups", leading
#    to this expression for the One Rule that defines Sudoku puzzles:
#
#           The One Rule:  Each symbol appears exactly once in each group.
#
#    A solved Sudoko is a completely-filled grid obeying the One Rule.
#


# Indicates a OneRule constraint violation
class RuleViolation(Exception):
    pass


# Raised when an internal sanity-check fails; "should never happen"
class AlgorithmFailure(Exception):
    pass


GroupType = Enum('GroupType', ['ROW', 'COL', 'REGION'])

CellMove = namedtuple('CellMove', ['row', 'col', 'elem'])


class Cell:
    # Each cell contains its row and col coordinates and a set 'elems'
    # representing element values that are not yet precluded from this
    # cell by the One Rule.
    def __init__(self, row, col, elems):
        self.row = row
        self.col = col
        self.elems = set(elems)

    # If a Cell becomes 'known' that means there is only one element
    # in the elems list, and this method will return that if so (else
    # it returns None meaning the Cell is not yet fully-determined).
    @property
    def known(self):
        """Return a single element, if determined; else None."""
        if len(self.elems) == 1:
            return list(self.elems)[0]
        else:
            return None

    @property
    def resolved(self):
        return self.known is not None

    def remove_element(self, elem):
        """Take an element out of the choices for this cell.
        Is a no-op if the element has already been removed.

        Raises RuleViolation if that leaves no choices at all.
        """
        if elem in self.elems:
            if len(self.elems) == 1:
                raise RuleViolation(f"row={self.row}, col={self.col}")
            self.elems.remove(elem)


class Sudoku:

    # Create a Sudoku puzzle. The 'givens' are a list of strings such as:
    #       givens = [
    #             "...4....1",
    #             "...9.28..",
    #             "3......57",
    #             ".7.3.....",
    #             "..2.4.1..",
    #             "..8.2..65",
    #             ".....9..8",
    #             "....1.2..",
    #             ".8.....3.",
    #       ]
    #
    # for initializing the given/known squares
    #
    def __init__(self, givens=[], /, *,
                 size=9,
                 elements=['1', '2', '3', '4', '5', '6', '7', '8', '9'],
                 regioninfo=None,
                 ):

        self.elements = elements
        self.size = size

        # The grid is a dict of Cell objects, indexed by (row, col) tuple.
        # Each Cell starts out with all possible elements as a potential
        # choice; as the solver progresses each Cell's choices are narrowed
        # until eventually (if the puzzle gets solved) there is only one
        # choice in each individual Cell.
        self.grid = {
            (r, c): Cell(r, c, self.elements)
            for r, c in itertools.product(range(self.size), range(self.size))
        }

        # Region "shapes" (automatic for square regions)
        self.regioninfo = regioninfo or self.makeregions()

        # Process any initial given cells
        for r, row in enumerate(givens):
            for c, elem in enumerate(row):
                if elem in self.elements:
                    self.move(CellMove(r, c, elem))
        self.valid = True

    def group_coords(self, gtype, nth, /):
        """Return list of coordinates for the nth gtype."""
        if gtype == GroupType.ROW:
            return [(nth, c) for c in range(self.size)]
        elif gtype == GroupType.COL:
            return [(r, nth) for r in range(self.size)]
        elif gtype == GroupType.REGION:
            return self.regioninfo[nth]

    def threegroups_coords(self, row, col, /):
        """Return coords for (row group, col group, region group)."""

        # parameters for each of the three ways to obtain group coords
        params = ((GroupType.ROW, row),
                  (GroupType.COL, col),
                  (GroupType.REGION, self.rc2region(row, col)))

        return [self.group_coords(*a) for a in params]

    def allgroups_coords(self):
        return [self.group_coords(gtype, nth)
                for gtype, nth in itertools.product(
                        GroupType, range(self.size))]

    def rc2region(self, row, col):
        """Return the region # of the given row/col coordinates."""

        # this is a dumb, but easy, way to do this
        for nth in range(self.size):
            if (row, col) in self.group_coords(GroupType.REGION, nth):
                return nth
        raise ValueError(f"Could not determine region # for {row},{col}")

    # Attribute (property) .valid is True if the puzzle conforms to
    # the One Rule; False if it does not, and None if not currently
    # known (i.e., the _validate() function needs re-running).
    # "None" is never seen externally, but gets set when, e.g.,
    # the deduction logic has resolved a bunch of knowns.
    @property
    def valid(self):
        if self._valid is None:
            self._valid = self._validate()
        return self._valid

    @valid.setter
    def valid(self, val):
        self._valid = val

    def _validate(self):
        # Look for One Rule violations in all groups
        for gcoords in self.allgroups_coords():
            knowns = list(
                itertools.filterfalse(
                    lambda k: k is None,
                    (self.grid[rc].known for rc in gcoords)))

            # if the length of a set (which eliminates dups) is not
            # the same as the length of the knowns, there were dups
            if len(knowns) != len(set(knowns)):
                return False
        return True

    def unresolved_cells(self):
        return itertools.filterfalse(
            lambda c: c.resolved, self.grid.values())

    def resolved_cells(self):
        return itertools.filterfalse(
            lambda c: not c.resolved, self.grid.values())

    def legalmoves(self):
        """Generate all potential legal moves."""
        if not self.valid:
            return

        # Brute force: Try each candidate in each cell, in order.
        # The combinatoric explosion here would be enormous; however,
        # the 'kills' and deducing singletons dramatically limit that.
        # In practice a "bad" move is discovered very quickly and a "good"
        # move will resolve the puzzle in only a few recursions.

        for cell in self.unresolved_cells():
            for elem in cell.elems:
                move = CellMove(cell.row, cell.col, elem)
                try:
                    _ = self.copy_and_move(move)
                except RuleViolation:
                    pass
                else:
                    yield move

    def copy_and_move(self, m):
        s2 = self.__class__()
        for cell in self.resolved_cells():
            s2.move(CellMove(cell.row, cell.col, cell.known))
        s2.move(m)
        return s2

    # search to see if there is any group where 'elem' appears
    # in only one unresolved cell of that group; if so it is called
    # (here) a "singleton" and it can be immediately resolved.
    #
    # Returns True if a singleton is found. NOTE that JUST THAT ONE
    # singleton is processed. See how this is looped around in move().
    #
    # Returns False if no singletons for 'elem' are found.

    def deduce_a_singleton(self, elem):

        for gcoords in self.allgroups_coords():
            cells_with_elem = [c for c in (self.grid[rc] for rc in gcoords)
                               if elem in c.elems and not c.resolved]
            if len(cells_with_elem) == 1:
                cell = cells_with_elem[0]
                return CellMove(cell.row, cell.col, elem)
        return None

    def move(self, m):
        cell = self.grid[(m.row, m.col)]
        if m.elem not in cell.elems:
            raise RuleViolation(f"{m} element is not a candidate")

        # redundant moves happen when prior moves rendered this move
        # a no-up via kills and inferences. Allow for that.
        if cell.known == m.elem:
            return

        self.valid = None              # force revalidation next time
        cell.elems = {m.elem}          # this is THE element here now

        # Remove this element from other cells in immediate groups
        self._kill(m.row, m.col, m.elem)

        if not self.valid:
            raise RuleViolation("KILL CONFLICT")

        # keep looping over singletons until none are found.
        while True:
            for elem in self.elements:
                singleton_m = self.deduce_a_singleton(elem)
                if singleton_m is not None:
                    self.move(singleton_m)
                    break    # this restarts the 'for' bcs of outer while
            else:
                break        # the 'for' found nothing, so all done

        if not self.valid:    # this validate should NEVER fail
            raise AlgorithmFailure("CODING ERROR")

    # KILLing simply means if, for example, a '5' was placed a (0, 0)
    # then a '5' cannot be anywhere else in row 0, column 0, or region 0.
    # During a kill, if removing the element from a cell resolves *that*
    # cell (i.e., it had two possibilities but now has only 1) then the
    # kill is recursively carried out accordingly. In many cases the entire
    # puzzle will end up resolving from cascading kills.
    def _kill(self, row, col, elem):

        # the cells of every group this (row, col) is in:
        killcells = (self.grid[(r, c)]
                     for r, c in itertools.chain.from_iterable(
                             self.threegroups_coords(row, col)))

        for cell in killcells:
            if cell.resolved:      # don't take out the last element!
                continue
            try:
                cell.elems.remove(elem)
            except KeyError:       # this elem was already killed in cell
                pass
            else:
                # if this is now resolved, recursively kill based on *this*
                if cell.resolved:
                    self._kill(cell.row, cell.col, cell.known)

    # curiously enough the human __str__ representation makes
    # a completely reasonable canonicalstate for the solver search
    def canonicalstate(self):
        return str(self)

    @property
    def endstate(self):
        return len(tuple(self.unresolved_cells())) == 0

    STRDOT = '.'           # if needs overriding for an absurd reason

    def __str__(self):

        # the goal of this is to make the string field for the elements
        # the same width for all, even if some are longer than others
        efmt = '{' + f":^{2+max(map(len, map(str, self.elements)))}s" + '}'
        s = ""
        prevrow = None
        for cell in self.grid.values():
            if cell.row != prevrow and prevrow is not None:
                s += '\n'
            s += efmt.format(cell.known if cell.resolved else self.STRDOT)
            prevrow = cell.row
        return s + '\n'

    def makeregions(self):
        """Make the regioninfo for default square regions."""

        regionsize = isqrt(self.size)
        if regionsize * regionsize != self.size:
            raise ValueError(f"can't make square regions (size={self.size})")

        regioninfo = []
        for nth in range(self.size):
            rx = (nth // regionsize) * regionsize
            cx = (nth % regionsize) * regionsize
            regioninfo.append(
                [(i, j)
                 for i in range(rx, rx + regionsize)
                 for j in range(cx, cx + regionsize)])

        return regioninfo


pzs = [
    "926.15...",
    "1.87639..",
    "3.79..165",
    "..9....38",
    "7.....6..",
    "...396...",
    ".7.....16",
    "694...7.2",
    "5.36..4.9"
]


pz37 = [
    "...4....3",
    "2..5976..",
    "8.4.1.5..",
    ".7.2.134.",
    "3.5...1.8",
    ".487.5.9.",
    "..2.6.7.1",
    "..3859..2",
    "4....2..."
]

pz307 = [
    "5.1.7...6",
    "6.....14.",
    ".....4.2.",
    ".5...92.8",
    "....8....",
    "2.85...7.",
    ".3.1.....",
    ".65.....2",
    "9...6.3.7",
]


pz307b = [
    "541372896",
    "6.....14.",
    ".....4.2.",
    ".5...92.8",
    "....8....",
    "2.85...7.",
    ".3.1.....",
    ".65.....2",
    "9...6.3.7",
]


pz17s = [
    "1....3.6.",
    ".7....8..",
    ".........",
    "3.6......",
    "...1..4..",
    "2........",
    ".4.87....",
    "....4...3",
    ".5.....2."
]

pz17s_2 = [
    ".9.3..7..",
    "......5..",
    ".......6.",
    "35....8..",
    "....26...",
    ".1..4....",
    "7.6....4.",
    "...1.....",
    "2........"
]

pzjefftest = [
    "...4....1",
    "...9.28..",
    "3......57",
    ".7.3.....",
    "..2.4.1..",
    "..8.2..65",
    ".....9..8",
    "....1.2..",
    ".8.....3.",
]
