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


# A SudokuGeo abstracts all the geometry of a puzzle.
# It describes the size of the puzzle, the elements ("digits"),
# and the rows and columns and regions.
#
# Some care (and experimentation) has gone into this implementation
# because it can have significant effects on solver performance.
#

import itertools
from enum import Enum
from math import isqrt


GroupType = Enum('GroupType', ['ROW', 'COL', 'REGION'])


class SudokuGeo:
    # The first version of this class computed every requested
    # coordinate grouping on the fly. That turns out to have
    # a significant (~~20%) performance cost on solving difficult puzzles.
    #
    # This version, with some mind-bindingly ugly init code, pre-constructs
    # various lookup tables. These reduce all requests such as:
    #       "get the row, column, region coordinates of this rc"
    # to a single dictionary lookup.
    #

    def __init__(self, size, /, *, elements=None, regioninfo):
        self.size = size
        self.regioninfo = regioninfo
        self.elements = elements or [str(i+1) for i in range(size)]

        # just in case, tuplify the regioninfo
        self.regioninfo = tuple(tuple(rgn) for rgn in self.regioninfo)

        # map an arbitrary (r, c) tuple to its corresponding region
        self._rc2rgn = {
            rc: i for i, rgn in enumerate(self.regioninfo) for rc in rgn}

        # map an arbitrary (r, c) tuple to the coordinates of
        # the row, col and region it is part of (one big sequence)
        self._threegc = {}
        for rc in itertools.product(range(self.size), range(self.size)):
            row = tuple((rc[0], c) for c in range(self.size))
            col = tuple((r, rc[1]) for r in range(self.size))
            rgn = self.regioninfo[self._rc2rgn[rc]]
            # the set/tuple dance here eliminates duplicate rc values
            self._threegc[rc] = tuple(set(row + col + rgn))

        # absolutely every group as a giant list of coordinate lists
        rows = tuple(
            tuple((r, c) for c in range(self.size)) for r in range(self.size))
        cols = tuple(
            tuple((r, c) for r in range(self.size)) for c in range(self.size))
        rgns = self.regioninfo
        self._agc = rows + cols + rgns

    # This returns a very long list of lists, the inner lists being
    # the (r, c) tuples of every row, every column, and every region.
    def allgroups(self):
        """Return a list of EVERY group coordinates, each as its own list."""
        return self._agc

    def combinedgroups(self, row, col, /):
        """For a given row,col return coords of all groups it is in."""
        return self._threegc[row, col]

    # this one is not performance sensitive; used once at init
    def allgrid(self):
        return itertools.product(range(self.size), range(self.size))


class StandardGeo(SudokuGeo):
    def _makeboxes(self, boxsize):
        """Make the regioninfo for default square regions."""

        regioninfo = []
        for nth in range(boxsize*boxsize):
            rx = (nth // boxsize) * boxsize
            cx = (nth % boxsize) * boxsize
            regioninfo.append(
                tuple((i, j)
                      for i in range(rx, rx + boxsize)
                      for j in range(cx, cx + boxsize)))

        return tuple(regioninfo)

    def __init__(self, size, /):
        boxsize = isqrt(size)
        if boxsize * boxsize != size:
            raise ValueError(f"can't make boxes for {size=}")
        super().__init__(size, regioninfo=self._makeboxes(boxsize))
