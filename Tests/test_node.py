from itertools import cycle
from chessmaker.chess.base import Board
from samples import white, black, sample0, sample1
from extension.board_utils import list_legal_moves_for
from node import Node
from math import inf
import pytest

@pytest.fixture
def start_board():
    """Returns a fresh Board object using sample0 for every test."""
    players = [white, black]

    board = Board(
        squares=sample0,
        players=players,
        turn_iterator=cycle(players),
    )
    return board, players

@pytest.fixture(autouse=True)
def set_player_to_optimise(start_board):
    board, _ = start_board
    Node.PLAYER = board.current_player
    Node._transposition_table = {}
    yield


def test_node_initialise(start_board):
    board, _ = start_board
    node = Node(board, max_depth=0)
    assert node.board == board
    assert node.parent == []
    assert node.depth == 0
    assert node.value == 0
    assert len(node.children) == 0
    node._expand(1)
    assert len(node.children) > 0, "node should have expanded once initialised"


def test_initial_expansion(start_board):
    board, _ = start_board
    root = Node(board, max_depth=2)
    assert len(root.children) == 7 , f"length: {len(root.children)}"
    if root.children:
        child = root.children[0]
        assert child.depth == 1
        if child.children:
            assert child.children[0].depth == 2
            assert child in child.children[0].parent

def test_children_created(start_board):
    board, _ = start_board
    depth = 4
    root = Node(board, max_depth=depth)
    assert len(Node._transposition_table) > 8, f"expanded up to depth {depth}, creating {len(Node._transposition_table) - 1} nodes (not root)"
    print(f"expanding to depth {depth} created {len(Node._transposition_table)} unique nodes")