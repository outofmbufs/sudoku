# MIT License
#
# Copyright (c) 2022,2023,2024 Neil Webber
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# ****************** NOTE ***************
# This is a generic breadth-first puzzle solving framework and can be
# used for arbitrary puzzle solving/searching. See comments for how to
# interface to it; the Sudoku module simply implements the API required
# by this framework and other puzzles could do the same.
# ***************************************

import itertools
from collections import namedtuple
from types import SimpleNamespace
from saverestore import SSRAttrs, AttrSpec
import time


class TimeLimitExceeded(Exception):
    pass


class PuzzleSolver:
    """ps = PuzzleSolver()

       ps.solve(puzzle) - return a move sequence, or None, to solve puzzle.

       ATTRIBUTES only valid after a solve():
       ps.stats         - miscellaneous statistics, only valid after solve()
       ps.entiretree    - If True, the *entire* search tree was explored
       ps.timedout      - If True, the timelimit aborted the search.
                          See ps.solutions for any solutions discovered
                          prior to time expiration.
    """

    Stats = namedtuple('PuzzleStatistics',
                       ['maxq', 'iterations', 'moves', 'elapsed'])

    def __init__(self, /, **kwargs):
        self.progress_controls(**kwargs)

    def _solve(self, puzzle):
        """Arbitrary puzzle search/solver. This is the GENERATOR.

        Generates an iterable of moves which is a puzzle solution, or None.

        The puzzle must have the following methods:

        for m in puzzle.legalmoves():  -- generate (all) legal 'moves' from
                                          the current puzzle state.
                                          See discussion below.

        puzzle.copy_and_move(m)        -- copy the puzzle, and perform move 'm'
                                          on the copy. Return the copy. Must
                                          not modify puzzle object state.

        s = puzzle.canonicalstate()    -- return a hashable canonical state
                                          See discussion below.

        The puzzle also must implement the following ATTRIBUTE/PROPERTY:
        puzzle.endstate              -- True if the puzzle is 'solved'

        MOVEs:
        The puzzle's legalmoves() method must generate legal moves.  It can
        be a generator or return a sequence. Each legal move is an opaque
        object from the solver's perspective. It will pass them one-by-one
        into the copy_and_move() method, which is expected to (as the name
        implies) copy the puzzle object and execute the move, returning the
        new object and leaving the original unchanged.

        CANONICAL STATE:
        A hashable abstraction representing the current puzzle "situation".
        The solver only cares that these are hashable and can be compared
        for equality. It does not examine their values in any semantic way.

        Important canonical state rules:
          1) The canonical state for puzzle situations that are different
             from a gameplay/solution perspective MUST be different.

          2) The canonical state for two completely identical puzzle
             situations MUST compare equal.

          3) The canonical state for puzzle situations that differ in some
             irrelevant detail but are isomorphic from a gameplay/solution
             perspective SHOULD be equal, but don't have to be.

        For example, a tic-tac-toe canonical state could just be a string
        of 9 letters, one for each square left-to-right/top-to-bottom.
        Thus: "........." at the start, "X........" after X moves into the
        top-left corner, etc.

        Note, however, that each of the four initial corner moves results
        in an identical gameplay situation, just rotated in a way that has
        no semantic effect on the game. An ideal canonical state meets
        rule #3 by somehow making all the opening-move-in-corner variations
        result in the same canonical state.

        A poor implementation of #3 (or not even trying) will still work;
        however the solver will end up exploring extra search spaces that
        are functionally identical (i.e., solving will take longer).
        """

        # breadth-first search: Appends moves at end of queue, which means
        # each new proposed state is queued so that it won't be examined
        # until all prior proposed states have been tried. Those states,
        # in turn, may of course also queue more future proposed states.
        # In this way, the solution with the fewest moves (least "depth")
        # will be found if any solutions exist at all.
        #
        # statetrail: Detects (and therefore does not explore) duplicate paths
        #             to identical states.
        #

        statetrail = {puzzle.canonicalstate()}

        self.progress_start()
        self._c.maxq = 0
        q = [(puzzle, [])]        # state queue: [(puzzle, trail), ...]
        for self._c.iterations in itertools.count(1):
            try:
                z, movetrail = q.pop(0)
            except IndexError:
                # no solution was found
                return

            for move in z.legalmoves():
                self.progress()
                z2 = z.copy_and_move(move)
                z2state = z2.canonicalstate()
                if z2state not in statetrail:
                    if z2.endstate:
                        yield movetrail + [move]
                    else:
                        statetrail.add(z2state)
                        mx = (z2, movetrail + [move])
                        q.append(mx)
                        self._c.maxq = max(self._c.maxq, len(q))

    def solve(self, puzzle, /, *, n=1, timelimit=None, checkinterval=None):
        """Solve the puzzle, generate n solutions

        If n <= 0 then search for ALL solutions.
        If n == 1 stop after finding the first ("best") solution
        If n > 1 limit the search to at most n solutions

        NOTE: timelimit applies to *each* solution separately if n > 1
        """

        # searching for all solutions, or just n
        limiter = range(n) if n > 0 else itertools.count()
        try:
            yield from (sol for _, sol in zip(limiter, self._solve(puzzle)))
        except TimeLimitExceeded:
            pass
        else:
            self.entiretree = True

        self._c.elapsed = time.time() - self._c.t0

    @property
    def stats(self):
        """miscellaneous statistics attribute."""
        d = {s: getattr(self._c, s, 0) for s in self.Stats._fields}
        return self.Stats(**d)

    # There's a whole bunch of 'clutter' related to logging, time limits,
    # keeping track of various statistics, etc. All that is encapsulated in:
    #    progress_controls (initializing all that)
    #    progress_start    (initializing per-solve stuff)
    #    progress          (called once per iteration of the search)
    #
    def progress_controls(self, /, *,
                          timelimit=1e21, checkinterval=100,
                          logger=None, loginterval=1000):

        if logger is not None:
            checkinterval = min(checkinterval, loginterval)

        self._c = SimpleNamespace(
            timelimit=timelimit,
            checkinterval=checkinterval,
            dflt_timelimit=timelimit,
            dflt_checkinterval=checkinterval,
            logger=logger,
            loginterval=loginterval,
            maxq=0,
            moves=0)

    def progress_start(self, /, *, timelimit=None, checkinterval=None):
        if timelimit is None:
            timelimit = self._c.dflt_timelimit
        if checkinterval is None:
            checkinterval = self._c.dflt_checkinterval
        if self._c.logger is not None:
            checkinterval = min(checkinterval, loginterval)

        self._c.timelimit = timelimit
        self._c.checkinterval = checkinterval
        self.timedout = False
        self.entiretree = False
        self._c.t0 = time.time()

    def progress(self):
        self._c.moves += 1
        if self._c.moves % self._c.checkinterval == 0:
            self._c.elapsed = time.time() - self._c.t0
            if self._c.elapsed > self._c.timelimit:
                self.timedout = True
                raise TimeLimitExceeded()
            if self._c.logger and self._c.moves % self._c.loginterval == 0:
                self._c.logger.info(f"{self.stats}")


if __name__ == "__main__":
    import unittest
    import copy

    class TowerOfHanoi:
        def __init__(self, *, ndiscs=5, npins=3):
            self.ndiscs = ndiscs
            self.pins = [list() for _ in range(npins)]
            self.pins[0] = list(range(ndiscs, 0, -1))

        def legalmoves(self):
            """Yield tuples (src, dst) describing a disc move."""
            for sn, src in enumerate(self.pins):
                for dn, dst in enumerate(self.pins):
                    if (sn != dn) and src:
                        if (not dst) or (src[-1] < dst[-1]):
                            yield sn, dn

        def move(self, sndn):
            sn, dn = sndn
            srcdisc = self.pins[sn][-1]
            dst = self.pins[dn]
            if dst and dst[-1] < srcdisc:
                raise ValueError(f"Illegal move {sn}->{dn}")
            self.pins[sn].pop()
            dst.append(srcdisc)
            return self

        def copy_and_move(self, sndn):
            return copy.deepcopy(self).move(sndn)

        def canonicalstate(self):
            return tuple(tuple(p) for p in self.pins)

        @property
        def endstate(self):
            return len(self.pins[-1]) == self.ndiscs

    class TestMethods(unittest.TestCase):
        def test1(self):
            ps = PuzzleSolver()
            difficulty = ps.stats.iterations

            # this is a weak test but it is what it is.
            for puzzlesize in range(1, 9):
                with self.subTest(puzzlesize=puzzlesize):
                    h = TowerOfHanoi(ndiscs=puzzlesize)
                    s = ps.solve(h)
                    self.assertEqual(len(s), (2**puzzlesize)-1)

                    # the difficulty, arbitrarily defined as the iterations
                    # in the stats, should increase with puzzle size
                    self.assertTrue(ps.stats.iterations > difficulty)
                    difficulty = ps.stats.iterations

    unittest.main()
