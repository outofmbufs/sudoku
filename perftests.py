from sudoku import Sudoku
from sudokugeo import SudokuGeo
from solver import PuzzleSolver
from collections import namedtuple

TimingTestCase = namedtuple(
    'TimingTestCase', ['givens', 'solution', 'geo', 'iterations'])


# geometry for 12x12 puzzles with 3x4 regions
def g12():
    return SudokuGeo(
        12,
        elements="123456789ABC",
        regioninfo=tuple(
            ((rx+0, cx+0), (rx+0, cx+1), (rx+0, cx+2), (rx+0, cx+3),
             (rx+1, cx+0), (rx+1, cx+1), (rx+1, cx+2), (rx+1, cx+3),
             (rx+2, cx+0), (rx+2, cx+1), (rx+2, cx+2), (rx+2, cx+3))
            for rx in (0, 3, 6, 9) for cx in (0, 4, 8)))


# an assortment of puzzles to try
puzzles = [

    # Very quick 9x9 puzzle, iterate it 100 times to get a timing
    TimingTestCase(
        givens=[
            "5.1.7...6",
            "6.....14.",
            ".....4.2.",
            ".5...92.8",
            "....8....",
            "2.85...7.",
            ".3.1.....",
            ".65.....2",
            "9...6.3.7",
        ],
        solution=[
            "541372896",
            "627958143",
            "389614725",
            "156749238",
            "473286951",
            "298531674",
            "834127569",
            "765893412",
            "912465387",
        ],
        geo=None,         # default is 9x9 standard geometry
        iterations=100
    ),

    # Another very quick 9x9 puzzle ... also iterate this 100 times
    TimingTestCase(
        givens=[
            "...4....1",
            "...9.28..",
            "3......57",
            ".7.3.....",
            "..2.4.1..",
            "..8.2..65",
            ".....9..8",
            "....1.2..",
            ".8.....3.",
        ],
        solution=[
            "859437621",
            "617952843",
            "324186957",
            "176395482",
            "532648179",
            "498721365",
            "243569718",
            "765813294",
            "981274536",
        ],
        geo=None,         # default is 9x9 standard geometry
        iterations=100
    ),

    # This one is difficult, takes about 5 seconds on typical laptop
    TimingTestCase(
        givens=[
            "..9...2..",
            ".8.5...1.",
            "7.......6",
            "..6.9....",
            ".5.8..3..",
            "4....7...",
            ".....4..9",
            ".3..1..8.",
            "...2..5.."
        ],
        solution=[
            "319468275",
            "682573914",
            "745921836",
            "876392451",
            "251846397",
            "493157628",
            "528734169",
            "934615782",
            "167289543",
        ],
        geo=None,         # default is 9x9 standard geometry
        iterations=1
    ),

    # a 12x12 that takes < 1 second to solve,
    TimingTestCase(
        givens=[
            "..1.6.2.A7..",
            "62.5B...1...",
            ".8....C3B.62",
            "A97.2.6..B5.",
            ".5.......37C",
            "3B.....7...9",
            "57B.4......1",
            "8......A.9..",
            ".4..97...6..",
            ".1C........B",
            "4......2.C..",
            "....5C..7126"
        ],
        solution=[
            "C31B6425A798",
            "62A5B97814C3",
            "7894A1C3B562",
            "A97C23618B54",
            "15468BA9237C",
            "3B28C5476A19",
            "57B9468C32A1",
            "8C61325A49B7",
            "243A971BC685",
            "91C27A36584B",
            "465718B29C3A",
            "BA835C947126"
        ],
        geo=g12(),
        iterations=50
    ),
]


def timetest():
    for i, x in enumerate(puzzles):
        puzz = Sudoku(x.givens, geo=x.geo)

        # if the puzzle was simple enough to solve at construction time...
        if puzz.endstate:
            print(f"Case {i}: resolved immediately by autosolve rules.")
            continue

        fastest = 1e21              # surely the first will be faster :)
        for _ in range(x.iterations):
            ps = PuzzleSolver()
            moves = ps.solve1(puzz)
            fastest = min(fastest, ps.stats.elapsed)

        # this is a performance test program, not a functional test,
        # but nevertheless test/assert a few things that should be true
        # 1) carry out the moves that got returned
        for m in moves:
            puzz.move(m, autosolve=True)

        #    ... which should bring the puzzle to a solution
        assert puzz.endstate, "Puzzle did not get solved!!"

        # 2) verify that solution against the "known" solution
        for r, row in enumerate(x.solution):
            for c, elem in enumerate(row):
                assert puzz.grid[(r, c)].value == elem, "solution mismatch"

        if fastest < 1.0:
            estr = f" {fastest*1000:.2f} milliseconds"
        else:
            estr = f" {fastest:.2f} seconds"

        if not puzz.endstate:
            mstr = "; no solution found -- timed out."
        elif ps.stats.moves > 10:
            mstr = f"; {(fastest / ps.stats.moves)*1000:.2f} msec/move ("
        else:
            mstr = f" (only "
        mstr += f"{ps.stats.moves} examined)"

        nsolstr = f"{len(moves)} move"
        if len(moves) != 1:
            nsolstr += "s"

        print(f"Case {i}:{estr}{mstr}. Solution: {nsolstr}.")


if __name__ == "__main__":
    timetest()
