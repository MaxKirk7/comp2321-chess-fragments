import pytest
from node import Node
from extension.board_utils import copy_piece_move

def test_zobrist_signature_consistency(tiny_board):
    """Root signature should equal the incremental signature of a child after a legal move."""
    root = Node(tiny_board, agent=tiny_board.current_player)
    root_sig = root.node_signature

    # Expand one child
    root.expand(max_depth=2)
    assert root.get_children()  # sanity
    child = root.get_children()[0]

    # Re‑calculate signature from scratch and compare
    fresh_sig = Node._calculate_zobrist_signature(child)
    assert fresh_sig == child.node_signature

def test_expand_uses_transposition_table(tiny_board):
    """If two different move sequences lead to the same position,
    both nodes must reference the same object in the TT."""
    root = Node(tiny_board, agent=tiny_board.current_player)
    root.expand(max_depth=3)

    # Pick two children that are different moves.
    children = root.get_children()
    assert len(children) >= 2

    # Manually force both children to reach the same board state:
    # (this is artificial – we clone one child and apply the move of the other)
    child_a = children[0]
    child_b = children[1]

    # Clone child_a's board and apply child_b's move – should hit TT entry.
    board_clone = child_a.get_board().clone()
    _, piece, move = copy_piece_move(board_clone, *child_b.get_move())
    piece.move(move)

    sig = Node._calculate_zobrist_signature(Node(board_clone, agent=child_a.get_board().current_player))
    # If TT works, the signature already exists.
    assert sig in Node.transposition_table