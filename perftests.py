import time
from sudoku import Sudoku
from solver import PuzzleSolver

# an assortment of puzzles to try

puzzles = [
    ["926.15...",
     "1.87639..",
     "3.79..165",
     "..9....38",
     "7.....6..",
     "...396...",
     ".7.....16",
     "694...7.2",
     "5.36..4.9"
     ],

    ["...4....3",
     "2..5976..",
     "8.4.1.5..",
     ".7.2.134.",
     "3.5...1.8",
     ".487.5.9.",
     "..2.6.7.1",
     "..3859..2",
     "4....2..."
     ],

    ["5.1.7...6",
     "6.....14.",
     ".....4.2.",
     ".5...92.8",
     "....8....",
     "2.85...7.",
     ".3.1.....",
     ".65.....2",
     "9...6.3.7",
     ],

    ["1....3.6.",
     ".7....8..",
     ".........",
     "3.6......",
     "...1..4..",
     "2........",
     ".4.87....",
     "....4...3",
     ".5.....2."
     ],

    [".9.3..7..",
     "......5..",
     ".......6.",
     "35....8..",
     "....26...",
     ".1..4....",
     "7.6....4.",
     "...1.....",
     "2........"
     ],

    ["...4....1",
     "...9.28..",
     "3......57",
     ".7.3.....",
     "..2.4.1..",
     "..8.2..65",
     ".....9..8",
     "....1.2..",
     ".8.....3.",
     ],

    ["..9...2..",
     ".8.5...1.",
     "7.......6",
     "..6.9....",
     ".5.8..3..",
     "4....7...",
     ".....4..9",
     ".3..1..8.",
     "...2..5.."
     ],
]


def timetest():
    mintime = 5

    for nth, givens in enumerate(puzzles):
        puzz = Sudoku(givens)

        # some Sudoku puzzles resolve immediately to solved state
        # just from the givens (and the 'kills' they imply)
        if puzz.endstate:
            print(f"Puzzle #{nth}: Solved immediately at initialization.")
        else:
            ps = PuzzleSolver()
            moves = ps.solve(puzz)
            print(f"Puzzle #{nth}: {ps.stats}")
            for m in moves:
                puzz.move(m, autosolve=True)
            print(puzz)


if __name__ == "__main__":
    timetest()
