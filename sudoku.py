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
import copy
from collections import namedtuple

from sudokugeo import SudokuGeo


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


CellMove = namedtuple('CellMove', ['row', 'col', 'elem'])


class Cell:

    # Each cell contains its row and col coordinates and a set 'elems'
    # representing element values that are not yet precluded from this
    # cell by the One Rule.
    def __init__(self, row, col, elems):
        self.row = row
        self.col = col
        self.elems = frozenset(elems)

    def __deepcopy__(self, memo):
        return copy.copy(self)       # because frozenset; optimization

    # A Cell is said to be 'resolved' if it has been determined
    # to be one specific element. That element will also be its 'value'
    @property
    def resolved(self):
        return self.value is not None

    # A Cell only has a 'value' if it is resolved, i.e., there
    # is only one possible element that it can be.
    #
    # Unresolved Cells return None for their 'value'
    @property
    def value(self):
        """A Cell's single element, if resolved; else None."""
        if len(self.elems) == 1:
            return list(self.elems)[0]     # e.g., unpack the only element
        else:
            return None

    def remove_element(self, elem):
        """Take an element out of the choices for this cell.
        Is a no-op if the element has already been removed.

        Raises RuleViolation if that leaves no choices at all.
        """
        if elem in self.elems:
            if len(self.elems) == 1:
                raise RuleViolation(f"row={self.row}, col={self.col}")
            self.elems -= {elem}    # NOTE: this makes a *new* frozenset

    def resolve(self, elem):
        """Make the cell be specifically the given elem."""
        if elem not in self.elems:
            raise RuleViolation(f"Can't set {elem} @ ({self.row}, {self.col})")
        self.elems = frozenset({elem})


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
        self.geo = SudokuGeo(size, regioninfo)

        # The grid is a dict of Cell objects, indexed by (row, col) tuple.
        # Each Cell starts out with all possible elements as a potential
        # choice; as the solver progresses each Cell's choices are
        # narrowed until eventually (if the puzzle gets solved) there is
        # only one choice in each individual Cell.
        self.grid = {rc: Cell(*rc, elements) for rc in self.geo.allgrid()}

        self.__cached = None    # see legalmoves() and copy_and_move()

        # Process any initial given cells
        for r, row in enumerate(givens):
            for c, elem in enumerate(row):
                if elem in self.elements:
                    self.move(CellMove(r, c, elem))

        # move() ensured givens (if any) were valid, so start out valid
        self._valid = True

    def __deepcopy__(self, memo):
        # performance optimizations; NOTE: deepcopy semantics preserved
        s2 = copy.copy(self)
        s2.grid = {rc: Cell(*rc, c.elems) for rc, c in self.grid.items()}
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
        # In practice a "bad" move is discovered quickly enough that
        # even the hardest puzzles can be solved in ~~10000 evaluations.

        for cell, elem in self.heuristic_order():
            move = CellMove(cell.row, cell.col, elem)
            try:
                self.__cached = (move, self.copy_and_move(move))
            except RuleViolation:
                pass
            else:
                yield move

    def copy_and_move(self, m):

        # About caching: (__cached) ... When the puzzlesolver is driving
        # legalmoves/copy_and_move, what happens is legalmoves has to
        # dry-run copy_and_move() to make sure it is not yielding an
        # illegal move (which fouls the search algorithm). The solver
        # immediately sends that same move right back to copy_and_move,
        # so this simple cache strategy is nearly a 2x speed optimization.
        # Note that move() also invalidates this cache to preserve semantics.

        try:
            cached_m, cached_obj = self.__cached
        except TypeError:             # __cached was None
            cached_m = None

        self.__cached = None
        if cached_m == m:
            return cached_obj

        # otherwise, really have to do the copy
        s2 = copy.deepcopy(self)
        s2.move(m)
        return s2

    # The heuristic_order is used in legalmoves and determines the order
    # in which cells and elements will be fed to the search framework.
    # This can be overridden in subclasses to experiment; this default
    # version simply examines all cells/elements in order.
    #
    # Two things to note:
    #   1) cell.elems is a frozenset and the ordering will vary.
    #      The call to sorted() has no measurable effect on performance
    #      but brings the advantage of predictable/unvarying results.
    #      If it is taken out everything still works; however, runs in
    #      two different python interpreter instances will explore the
    #      search space in different orders.
    #   2) As of this writing, no heuristic tried has performed
    #      better than "just do them in order".
    def heuristic_order(self):
        for cell in self.unresolved_cells():
            for elem in sorted(cell.elems):
                yield cell, elem

    # search to see if there is any group where 'elem' appears
    # in only one unresolved cell of that group; if so it is called
    # (here) a "singleton" and it can be immediately resolved.
    #
    # Returns True if a singleton is found. NOTE that JUST THAT ONE
    # singleton is processed. See how this is looped around in move().
    #
    # Returns False if no singletons for 'elem' are found.

    def deduce_a_singleton(self, elem):

        for gcoords in self.geo.allgroups():
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
        if cell.resolved and cell.value == m.elem:
            return

        self._valid = None             # force revalidation next time
        self.__cached = None           # see legalmoves/copy_and_move
        cell.resolve(m.elem)           # this is THE element here now

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

    # KILLing simply means if, for example, a '5' was placed at (0, 0)
    # then a '5' cannot be anywhere else in row 0, column 0, or region 0.
    # During a kill, if removing the element from a cell resolves *that*
    # cell (i.e., it had two possibilities but now has only 1) then the
    # kill is recursively carried out accordingly. In many cases the entire
    # puzzle will end up resolving from cascading kills.
    def _kill(self, row, col, elem):

        # the cells of every group this (row, col) is in:
        killcells = (self.grid[rc]
                     for rc in self.geo.threegroups(row, col, chain=True))

        for cell in killcells:
            if cell.resolved:      # don't take out the last element!
                continue
            cell.remove_element(elem)
            # if this is now resolved, recursively kill based on *this*
            if cell.resolved:
                self._kill(cell.row, cell.col, cell.value)

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
        efmt = '{' + f":^{2+max(map(len, map(str, self.elements)))}s" + '}'
        s = ""
        prevrow = None
        for cell in self.grid.values():
            if cell.row != prevrow and prevrow is not None:
                s += '\n'
            s += efmt.format(cell.value if cell.resolved else self.STRDOT)
            prevrow = cell.row
        return s + '\n'
