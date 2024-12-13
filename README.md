# sudoku
Sudoku puzzle solver in python.

A `Sudoku` object (sudoku.py) represents an arbitrarily-sized sudoku puzzle, with a geometry described by a `SudokuGeo` object (sukodugeo.py).

To make a standard 9x9 SudokuGeo object:

    from sudokugeo import SudokuGeo
    geo = SudokuGeo(9)

To make a standard Sudoku 9x9 puzzle from that standard geometry:

    from sudokugeo import SudokuGeo
    from sudoku import Sudoku
    puzz = Sudoku(geo=SudokuGeo(9))

The 9x9 geometry/configuration is the default so this also works:

    from sudoku import Sudoku
    puzz = Sudoku()

# Terminology

A `Sudoku` contains a square `grid` made up of `cells` that will eventually contain one `element` each when the puzzle is solved.

The length of one side of the grid is called the `size` of the puzzle. The normal most-common Sudoku puzzle format is size 9 (a 9x9 grid of 81 cells total).

There are three different types of `group` arrangements that each completely tile (i.e., cover) the grid:

 - rows
 - columns
 - regions
 
Rows cover ("tile") the grid in the obvious way and are numbered from the top down, starting with row zero. In a size N Sudoku there are N rows each containing N cells.

Columns are also obvious, starting with column zero on the left. In a size N Sudoku there are N columns each containing N cells.

Each region is a clump of `size` cells. Regions can have arbitrary shapes but in any Sudoku puzzle with a size that is a perfect square (4, 9, 16, 25, etc) the regions are boxes with sides based on the square root of the puzzle size (2, 3, 4, 5, etc). Thus, in a standard size 9 Sudoku, the regions would be 3x3 boxes arranged in a typical "tic-tac-toe" formation, tiling the grid.

For puzzles of that are not perfect-square sizes, regions are arbitrary shapes and are specified via a more-detailed SudokuGeo object (described later). As an example here is a picture showing how a 5x5 puzzle might be divided into 5 irregularly-shaped regions. In this drawing the letters Q R S T U represent the five regions in the 5x5 grid:

    Q  Q  R  R  R

    Q  Q  R  R  S

    Q  U  U  S  S

    U  U  U  T  S

    T  T  T  T  S

Note that in puzzles where the size is not a perfect square, there is typically (probably never?) no single tiling that can be formed by N identical regions; the regions will have varying shapes as shown in the example above and the specific choice of region assignment is arbitrary. These are still valid Sudoku puzzles though they are less commonly seen than puzzles with the simpler geometry when the size is a perfect square such as 9x9, 16x16, etc.

The elements that appear in each cell are typically thought of as digits; in particular in a size 9 Sudoku the elements are conventionally the digits 1 through 9. The `Sudoku` object always represents elements as strings, as they are entirely arbitrary and need not be digits or even single characters.

For example, a size 16 Sudoku could have elements that are:

    '1', '2', '3', ... '9', 'A', 'B', 'C', 'D', 'E', 'F', 'G'

or (more computer-science oriented, "hex digits"):

    '0', '1', '2', ... '9', 'A', 'B', 'C', 'D', 'E', 'F',

or even:

    '1', '2', ... '9', '10', '11', '12', ... '16'

The choice of element strings is completely arbitrary and can be controlled at SudokuGeo initialization time.


