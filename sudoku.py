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

import copy
import itertools
from collections import namedtuple, defaultdict

from sudokugeo import StandardGeo


# TERMINOLOGY:
#    A Sudoku is a 'SIZE' x 'SIZE' 'grid' of 'cells' into which
#    'elements' are placed according to the 'One Rule'.
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
#        The One Rule:  Each element appears exactly once in each group.
#
#    A solved Sudoko is a completely-filled grid obeying the One Rule.
#


# Indicates a OneRule constraint violation
class RuleViolation(Exception):
    pass


# Raised when an internal sanity-check fails; "should never happen"
class AlgorithmFailure(Exception):
    pass


# A specific 'move' (i.e., filling in a cell with a known element value)
CellMove = namedtuple('CellMove', ['row', 'col', 'elem'])


class Cell:
    """A Sudoku puzzle is a grid of Cells."""

    # Each cell contains its row and col coordinates and a set 'elems'
    # representing element values that are not yet precluded from this
    # cell by the One Rule.
    def __init__(self, row, col, elems):
        self.row = row
        self.col = col
        self.elems = frozenset(elems)

        # A Cell has a non-None 'value' if it has been determined to be one
        # specific element. If it still could be one of several elements
        # then its 'value' attribute will be None.
        #
        # The original version of this code used @property to compute the
        # value attribute from self.elems dynamically. That is simple,
        # pythonic, and always correct; however, it slows down puzzle
        # searching by more than 20% difference. Thus, 'value' is instead
        # updated manually any place that self.elems is modified.

        self.value = list(self.elems)[0] if len(self.elems) == 1 else None

    def remove_element(self, elem):
        """Take an element out of the choices for this cell.

        Is a no-op if the element has already been removed.
        Raises RuleViolation if that leaves no choices at all.

        Returns True if the cell had 2 possibilities, elem being one of them
        (in other words: returns True if this makes the cell 'resolve')
        """
        if elem not in self.elems:       # a no-op
            return False

        if len(self.elems) == 1:
            raise RuleViolation(f"dead cell ({self.row}, {self.col})")
        self.elems -= {elem}    # NOTE: this makes a *new* frozenset
        if len(self.elems) > 1:
            return False
        self.value = list(self.elems)[0]
        return True

    def resolve(self, elem):
        """Make the cell be specifically the given elem."""
        if elem not in self.elems:
            raise RuleViolation(f"Can't set {elem} @ ({self.row}, {self.col})")
        if self.value != elem:    # avoid unneeded garbage
            self.elems = frozenset({elem})
            self.value = elem
            return True        # means it just got resolved
        return False           # means it was already resolved

    def __repr__(self):
        # this is a hack but it really helps for debugging.. if the
        # elements are all single-character strings, mash them all
        # together in the repr because that would be a valid Cell() call.
        #
        # So, for normal puzzles that are 9x9 and have elements '1' .. '9'
        # the repr would be, e.g.
        #
        #       Cell(0, 0, '123456789')
        #
        # instead of
        #
        #       Cell(0, 0, ['1', '2', '3', '4', '5', '6', '7', '8', '9'])
        #
        try:
            elems = ''.join(sorted(self.elems))
        except TypeError:
            elems = None
        else:
            if len(elems) != len(self.elems):
                elems = None
            else:
                elems = repr(elems)
        if elems is None:
            elems = list(sorted(self.elems))

        return self.__class__.__name__ + f"({self.row}, {self.col}, {elems})"

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
    def __init__(self, givens=[], /, *, geo=None, autosolve=True):

        self.geo = geo or StandardGeo(9)

        # The grid is a dict of Cell objects, indexed by (row, col) tuple.
        # Each Cell starts out with all possible elements as a potential
        # choice; as the solver progresses each Cell's choices are
        # narrowed until eventually (if the puzzle gets solved) there is
        # only one choice in each individual Cell.
        self.grid = {
            rc: Cell(*rc, self.geo.elements) for rc in self.geo.allgrid()
        }

        self.__cached = None    # see legalmoves() and copy_and_move()
        self.knowns = {elem: 0 for elem in self.geo.elements}

        # Process any initial given cells
        for r, row in enumerate(givens):
            for c, elem in enumerate(row):
                if elem in self.geo.elements:
                    self.move(CellMove(r, c, elem), autosolve=autosolve)

        # move() ensured givens (if any) were valid, so start out valid
        self._valid = True

    def __deepcopy__(self, memo):
        #
        # Optimizing __deepcopy__ like this cut more than 50% off the
        # solving time for large/difficult puzzles.
        #
        # Significant deepcopy performance gains came from:
        #    * shallow-copying geo because it is a large, readonly, object.
        #    * shallow-copying __cached ... see discussion below.
        #    * hybrid-copying the grid ... see discussion below.
        #
        # Why shallow-copying __cached works and is an improvement:
        #    The __cached attribute is a tuple:
        #          (CellMove object, Sudoku object)
        #    (i.e., "proposed move" and "resulting puzzle") and if it is
        #    deepcopy'd then every __deepcopy__ call copies TWO Sudoku
        #    objects - the primary one ('self') and, potentially, the
        #    "resulting puzzle" in the __cached tuple. However, there
        #    is no need to deep copy the "resulting puzzle" because it will
        #    never be mutated until/unless it becomes 'self' here in a
        #    subsequent copy_and_move().  Thus it need not be copied here.
        #    This one optimization led to a substantial performance
        #    improvement for difficult puzzles (involving much copying).
        #
        # Why hybrid-copying the grid works and is an improvement:
        #    Cell objects are definitely mutable and need to be copied,
        #    but THEIR underlying frozenset objects are not mutable and
        #    can be shared by the copied Cell objects. It would be nice
        #    if deepcopy understood this about frozensets but either it does
        #    not, or, in any case, there is still a significant performance
        #    gain to be had by optimizing this part of the deepcopy.
        #
        #    **COUPLING NOTE**: This means this __deepcopy__ understands
        #                       more than it "should" about Cells.
        #
        s2 = copy.copy(self)
        s2.grid = {rc: Cell(*rc, c.elems) for rc, c in self.grid.items()}
        s2.knowns = dict(self.knowns)
        return s2

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

    def _validate(self):
        # Look for One Rule violations in all groups
        for gcoords in self.geo.allgroups():
            knowns = list(
                itertools.filterfalse(
                    lambda k: k is None,
                    (self.grid[rc].value for rc in gcoords)))

            # if the length of a set (which eliminates dups) is not
            # the same as the length of the knowns, there were dups
            if len(knowns) != len(set(knowns)):
                return False
        return True

    def unresolved_cells(self):
        return itertools.filterfalse(
            lambda c: c.value is not None, self.grid.values())

    def resolved_cells(self):
        return itertools.filterfalse(
            lambda c: c.value is None, self.grid.values())

    def unsolved_elems(self):
        """Return a sequence of elements that are not fully solved."""
        return [k for k, v in itertools.filterfalse(
            lambda kv: kv[1] == self.geo.size, self.knowns.items())]

    def legalmoves(self):
        """Generate all potential legal moves."""
        if not self.valid:
            return

        # Brute force: Try each candidate in each cell, in order.
        # The combinatoric explosion here would be enormous; however,
        # 'kills' and various solving strategies dramatically limit that.
        #
        # There is an optimization: to determine if something is a
        # a legal move, it has to actually be made (and chased with
        # all of its kills/etc). That's expensive, and after this legal
        # move is returned the solving framework will turn right back
        # around and say "ok, do that move". The __cached attribute
        # allows the work done here to find the move to be used when/if
        # the move is then immediately used.
        #
        # To preserve semantics all methods that mutate self (puzzle state)
        # must maintain (usually that means: clear) the __cached attribute.
        # See, for example move().

        for cell, elem in self.heuristic_order():
            move = CellMove(cell.row, cell.col, elem)
            try:
                self.__cached = (move, self.copy_and_move(move))
            except RuleViolation:
                pass
            else:
                yield move

    # The heuristic_order is used in legalmoves and determines the order
    # in which cells and elements will be fed to the search framework.
    #
    # This heuristic sorts the elements by how many cells they appear in
    # as possibilities, fewest first, and thus yields (cell, elem) pairs
    # favoring "nearly solved" elements before elements that have myriad
    # possibilities all over the puzzle. This seems (albeit with scant data
    # points) to reduce the search space, and mimics what people often
    # do: "let's see if we can set the rest of the remaining sixes"
    #
    def heuristic_order(self):
        unresolveds = list(self.unresolved_cells())
        elemsort = (
            k for k, v in sorted(self.knowns.items(), key=lambda t: t[1]))
        for elem in elemsort:
            haselem = list(
                itertools.filterfalse(
                    lambda c: elem not in c.elems,
                    unresolveds))
            for cell in haselem:
                if not cell.value:
                    yield (cell, elem)
                unresolveds.remove(cell)
        for c in unresolveds:
            if not cell.value:
                raise AlgorithmFailure("H")

    # NOT USED; preserved here for reference
    def old_simple_heuristic_order(self):
        yield from ((cell, elem)
                    for cell in self.unresolved_cells()
                    for elem in sorted(cell.elems))

    def copy_and_move(self, m):
        # See legalmoves for discussion of __cached
        try:
            cached_m, cached_obj = self.__cached
        except TypeError:             # __cached was None
            cached_m = None

        self.__cached = None
        if cached_m == m:
            return cached_obj

        # otherwise, really have to do the copy, and the move
        s2 = copy.deepcopy(self)
        s2.move(m, autosolve=True)
        return s2

    def move(self, m, /, *, autosolve=False):
        """Perform a CellMove on the puzzle, in-place.

        If autosolve is True (default is False) then the any moves
        unambiguously implied by the resulting puzzle state will be
        automatically made. NOTE: This often solves a LOT of cells.

        Raises RuleViolation if the move is illegal (or if any
        autosolve moves lead to a contradition)
        """
        cell = self.grid[(m.row, m.col)]
        if m.elem not in cell.elems:
            raise RuleViolation(f"{m} element is not a candidate")

        self.__cached = None           # see legalmoves/copy_and_move
        self._valid = None             # force revalidation next time
        if cell.resolve(m.elem):       # this is THE element here now
            self.knowns[m.elem] += 1

        if autosolve:
            self._autosolve(m)

    def _autosolve(self, m, /):
        """Given a just-made move m, resolve everything it implies."""

        # Remove this element from other cells in immediate groups
        self._kill(m.row, m.col, m.elem)

        if not self.valid:
            raise RuleViolation("POST-KILL")

        # keep looping over singletons until none are found.
        strategies = (self.find_singletons,
                      self.find_pointingpairs,
                      self.find_doublepairs)
        while True:
            if not any(strategy() for strategy in strategies):
                break

    # KILLing simply means if, for example, a '5' was placed at (0, 0)
    # then a '5' cannot be anywhere else in row 0, column 0, or region 0.
    # During a kill, if removing the element from a cell resolves *that*
    # cell (i.e., it had two possibilities but now has only 1) then the
    # kill is recursively carried out accordingly. In many cases the entire
    # puzzle will end up resolving from cascading kills.
    def _kill(self, row, col, elem):
        # the OTHER cells of every group this (row, col) cell is in
        this = self.grid[(row, col)]         # excluded from killcells
        killcells = itertools.filterfalse(
            lambda c: c is this,
            (self.grid[rc] for rc in self.geo.combinedgroups(row, col)))

        for cell in killcells:
            if cell.remove_element(elem):
                # this is now resolved, so recursively kill!
                self.knowns[cell.value] += 1
                self._kill(cell.row, cell.col, cell.value)

    def find_singletons(self):
        for elem in self.geo.elements:
            singleton_m = self.deduce_a_singleton(elem)
            if singleton_m:
                self.move(singleton_m, autosolve=True)
                return True
        return False

    # Search to see if there is any group where 'elem' appears
    # in only one unresolved cell of that group; if so it is called
    # (here) a "singleton" and it can be immediately resolved.
    #
    def deduce_a_singleton(self, elem):
        # NOTE: this had been written with comprehensions but this
        #       explicit looping makes it possible to fail faster
        #       which speeds up the solution search.
        for gcoords in self.geo.allgroups():
            savedcell = None
            for cell in (self.grid[rc] for rc in gcoords):
                if cell.value is None and elem in cell.elems:
                    if savedcell:
                        savedcell = None
                        break
                    savedcell = cell

            if savedcell:
                return CellMove(savedcell.row, savedcell.col, elem)
        return None

    #
    # A double-pair is a pair of elements (a, b) appearing in EXACTLY two
    # cells as possibilities in any group.
    #
    # While this doesn't allow resolving those cells, it *does* mean that
    # any other possibilities in that pair of cells can be eliminated,
    # because whichever one 'a' ends up in, 'b' will end up in the other
    # and so none of the other possibilities are live.
    #
    def find_doublepairs(self):

        # If there are any solved elements don't include them in the search
        unsolved_elems = self.unsolved_elems()
        nelems = len(unsolved_elems)

        # Because (a, b) is the same as (b, a) as a double pair, and
        # because (a, a) must be excluded... nested loops like this:
        for i, a in enumerate(unsolved_elems):
            for b in unsolved_elems[i+1:]:
                abcells = self.find_a_doublepair(a, b)
                if abcells:
                    for cell in abcells:
                        for elem in unsolved_elems:
                            if elem not in (a, b) and elem in cell.elems:
                                cell.remove_element(elem)
                        # sanity check but remove this later
                        assert len(cell.elems) == 2, "XXX 1"
                        assert a in cell.elems, "XXX a"
                        assert b in cell.elems, "XXX b"

                    return True
        return False

    def find_a_doublepair(self, a, b):
        if a == b:
            return None
        for gcoords in self.geo.allgroups():
            abcells = []
            for cell in (self.grid[rc] for rc in gcoords):
                has_a = a in cell.elems
                has_b = b in cell.elems
                if (has_a and not has_b) or (has_b and not has_a):
                    abcells = []
                    break
                if has_a and has_b:
                    if len(abcells) == 2:    # means this is the third
                        abcells = []         # which is too many
                        break
                    else:
                        abcells.append(cell)

            if len(abcells) == 2:
                # check to make sure there's something else to eliminate
                if any(map(lambda c: len(c.elems) > 2, abcells)):
                    return abcells

        return None

    #
    # A pointing "pair" is any element in a given region that:
    #     1) Has more than 1 possibility in that region
    #     2) those possibilities are all on the same row or column
    #
    # Whichever row or column the elements all lie on is called
    # the "pointer". The significance of the pointer is that since
    # the element must appear *somewhere* in the region, it therefore
    # cannot appear anywhere else in the same group as the pointer.
    # Example: if a region has two 3's as possibilities and they are on
    # the same ROW within the region, 3's can then be eliminated from
    # that ROW entirely outside of the region.

    def find_pointingpairs(self):
        for elem in self.geo.elements:
            for rc in self.find_a_pointing_pair(elem):
                cell = self.grid[rc]
                if cell.remove_element(elem):
                    # striking this one resolved the cell, so
                    # recursively invoke all the move() magic again
                    self.move(CellMove(*rc, cell.value), autosolve=True)
                    return True
        return False

    # A seqeunce of coordinates is a pointing pair if:
    #      All the rows are the same OR All the columns are the same
    #  AND there are at least 2 coordinates
    #
    def is_pp(self, elem, coords):
        """Return pointing pair info as a tuple (row, col).

        If the row is NOT a "pointing pair" row is None (else the row)
        Same for col.

        Note that "pointing pairs" have at least 2 coordinates but can
        have any number. But "pair" is the sudoku terminology regardless.
        """
        rows = [r for r, c in coords]
        cols = [c for r, c in coords]
        row_pp = len(rows) > 1 and len(set(rows)) == 1
        col_pp = len(cols) > 1 and len(set(cols)) == 1
        return rows[0] if row_pp else None, cols[0] if col_pp else None

    # Find any single "pointing pair" in a region.
    def find_a_pointing_pair(self, elem):
        for rgn in self.geo.regioninfo:
            coords = tuple(rc for rc in rgn if elem in self.grid[(rc)].elems)
            rpp, cpp = self.is_pp(elem, coords)
            if rpp is not None:
                # convert from just the row number to a list of all the
                # coordinates on this row, but NOT in the region
                return tuple((rpp, c)
                             for c in range(self.geo.size)
                             if (rpp, c) not in rgn)
            elif cpp is not None:
                return tuple((r, cpp)
                             for r in range(self.geo.size)
                             if (r, cpp) not in rgn)

        return []

    # The human __str__ representation works just fine, and experimentation
    # shows that performance (and size) here don't seem to matter.
    def canonicalstate(self):
        return str(self)

    @property
    def endstate(self):
        return len(tuple(self.unresolved_cells())) == 0

    STRDOT = '.'           # if needs overriding for an absurd reason

    def __str__(self):

        # the goal of this is to make the string field for the elements
        # the same width for all, even if some are longer than others
        efmt = '{' + f":^{2+max(map(len, map(str, self.geo.elements)))}s" + '}'
        s = ""
        prevrow = None
        for cell in self.grid.values():
            if cell.row != prevrow and prevrow is not None:
                s += '\n'
            s += efmt.format(cell.value if cell.value is not None
                             else self.STRDOT)
            prevrow = cell.row
        return s + '\n'
