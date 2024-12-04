import time
from sudoku import Sudoku
from solver import PuzzleSolver
from collections import namedtuple

TimingTestCase = namedtuple(
    'TimingTestCase', ['givens', 'solution', 'iterations'])

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
        iterations=100
    ),

    # This one is very difficult, takes about 12 seconds on typical laptop
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
        iterations=1
    ),
]


def timetest():
    for i, x in enumerate(puzzles):
        puzz = Sudoku(x.givens)
        fastest = 1e21              # surely the first will be faster :)
        for _ in range(x.iterations):
            ps = PuzzleSolver()
            t0 = time.time()
            moves = ps.solve(puzz)
            elapsed = time.time() - t0
            fastest = min(fastest, elapsed)

        # make sure that (the last one) actually worked
        for m in moves:
            puzz.move(m, autosolve=True)
        assert puzz.endstate, "Puzzle did not get solved!!"

        if elapsed < 1.0:
            estr = f" {elapsed*1000:.2f} milliseconds"
        else:
            estr = f" {elapsed:.2f} seconds"

        if ps.stats.moves > 100:
            mstr = f"; {(elapsed / ps.stats.moves)*1000:.2f} msec/move"
            mstr += f", {ps.stats.moves} moves examined"
        else:
            mstr = ""

        print(f"Case {i}:{estr}{mstr}")


if __name__ == "__main__":
    timetest()
