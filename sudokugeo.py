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


#
# This is a helper class for Sudoku puzzles, essentially defined the
# geometry of the puzzle.
#
# Abstracting this out into a separate class made it possible to
# (somewhat) cleanly enable caching on the coordinate-computations such
# as: "return the list of coordinates for the region this (r, c) is in"
# and the like, which turns out to be a significant (20%) performance
# gain in deep/difficult puzzle solves. So, it's messy but the mess is
# localized in this module.
#


import functools
import itertools
from enum import Enum
from math import isqrt


GroupType = Enum('GroupType', ['ROW', 'COL', 'REGION'])


class SudokuGeo:
    def __init__(self, size, regioninfo=None, /):
        self.size = size
        self.regioninfo = regioninfo or self.__makeregioninfo(size)

    # This returns a very long list of lists, the inner lists being
    # the (r, c) tuples of every row, every column, and every region.
    def allgroups(self):
        """Return a list of EVERY group coordinates, each as its own list."""
        return self.__agc(self.size, self.regioninfo)

    def threegroups(self, row, col):
        """Return coord lists: [row group, col group, region group]."""
        return self.__threegc(row, col, self.size, self.regioninfo)

    def allgrid(self):
        return itertools.product(range(self.size), range(self.size))

    # These are the (cacheable!) class methods that generate the
    # coordinate lists from the given parameters. Some of this may
    # look expensive but because they are cacheable it does not matter.

    @classmethod
    @functools.cache
    def __makeregioninfo(cls, size, /):
        """Make the regioninfo for default square regions."""

        regionsize = isqrt(size)
        if regionsize * regionsize != size:
            raise ValueError(f"can't make square regions {size=}")

        regioninfo = []
        for nth in range(size):
            rx = (nth // regionsize) * regionsize
            cx = (nth % regionsize) * regionsize
            regioninfo.append(
                tuple((i, j)
                      for i in range(rx, rx + regionsize)
                      for j in range(cx, cx + regionsize)))

        return tuple(regioninfo)

    @classmethod
    @functools.cache
    def __group(cls, gtype, nth, size, regioninfo, /):
        """Return list of coordinates for the nth gtype."""
        if gtype == GroupType.ROW:
            return tuple((nth, c) for c in range(size))
        elif gtype == GroupType.COL:
            return tuple((r, nth) for r in range(size))
        elif gtype == GroupType.REGION:
            return regioninfo[nth]

    @classmethod
    @functools.cache
    def __agc(cls, size, regioninfo, /):
        """Return a list of EVERY group coordinates, each as its own list."""

        return [cls.__group(gtype, nth, size, regioninfo)
                for gtype, nth in itertools.product(GroupType, range(size))]

    @classmethod
    @functools.cache
    def __threegc(cls, row, col, size, regioninfo, /):
        """Return coord lists: [row group, col group, region group]."""

        # Each of the three ways to obtain group coords
        params = ((GroupType.ROW, row),
                  (GroupType.COL, col),
                  (GroupType.REGION, cls.__rc2rgn(row, col, size, regioninfo)))

        return [cls.__group(*a, size, regioninfo) for a in params]

    @classmethod
    @functools.cache
    def __rc2rgn(cls, row, col, size, regioninfo, /):
        """Return the region # of the given row/col coordinates."""

        # this is a dumb, but easy, way to do this
        for nth in range(size):
            if (row, col) in cls.__group(
                    GroupType.REGION, nth, size, regioninfo):
                return nth
        raise ValueError(f"Could not determine region # for {row},{col}")
