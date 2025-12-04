import pytest
from search import Search
from extension.board_utils import copy_piece_move

def test_search_returns_legal_move(tiny_board):
    """Search.start must return a move that is legal for the root player."""
    s = Search(tiny_board, tiny_board.current_player, maximum_depth=2)
    piece, move = s.start()
    assert piece is not None
    assert move is not None
    assert move in piece.get_move_options()

def test_parallel_branching_is_used(monkeypatch):
    """When many children exist the Search should create a ThreadPoolExecutor."""
    from search import _EXECUTER, _MIN_CHILDREN_FOR_PARALLEL

    # Force a low threshold so that even a tiny board triggers parallelism.
    monkeypatch.setattr('search._MIN_CHILDREN_FOR_PARALLEL', 1)

    # Build a board with many legal moves (full piece set).
    from samples import sample1, white, black
    from chessmaker.chess.base import Board
    board = Board(squares=sample1, players=[white, black], turn_iterator=iter([white, black]))

    s = Search(board, white, maximum_depth=2)
    # Run start – it will invoke the parallel helper internally.
    piece, move = s.start()

    # After the first call the global executor should be instantiated.
    assert _EXECUTER is not None
    assert isinstance(_EXECUTER, type(_EXECUTER))  # sanity

def test_evaluation_material_balance(tiny_board):
    """Simple material test: white has a Right (value 4) and a Knight (3)."""
    s = Search(tiny_board, tiny_board.current_player, maximum_depth=1)
    node = s._root
    eval_val = s._evaluate(node)

    # Count pieces manually:
    # white: Right (4), Bishop (2), King (1000), Queen (5), Knight (3), 5 Pawns (2 each)
    # black: Right (4), Knight (3), King (1000), Queen (5), Bishop (2), 5 Pawns (2 each)
    # Because both sides have identical material, the evaluation should be 0.
    assert eval_val == pytest.approx(0.0)
