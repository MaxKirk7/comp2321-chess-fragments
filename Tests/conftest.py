import pytest
from chessmaker.chess.base import Player, Board
from chessmaker.chess.base import Square
from chessmaker.chess.pieces import King, Knight, Queen, Bishop, Pawn
from extension.piece_right import Right
from extension.piece_pawn import Pawn_Q
from samples import sample0, sample1, white, black


@pytest.fixture
def tiny_board():
    """Creates a 5x5 board with the sample0 layout (has all custom pieces)."""
    board = Board(
        squares=sample0,
        players=[white, black],
        turn_iterator=iter([white, black]),
    )
    return board


@pytest.fixture
def simple_board():
    """A board with only two kings – fastest possible terminal detection."""
    squares = [
        [Square(King(white)), Square()],
        [Square()],
        [Square()],
        [Square(King(black))],
    ]  # 5×5 flattened for brevity; actual `Board` will accept a list of  rows
    # Build proper 5×5 rows:
    rows = [
        [Square(), Square(), Square(), Square(), Square()],
        [Square(King(white)), Square(), Square(), Square(), Square()],
        [Square(), Square(), Square(), Square(), Square()],
        [Square(), Square(), Square(), Square(), Square()],
        [Square(King(black)), Square(), Square(), Square(), Square()],
    ]
    board = Board(
        squares=rows,
        players=[white, black],
        turn_iterator=iter([white, black]),
    )
    return board
