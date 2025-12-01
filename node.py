from math import inf
from extension.board_rules import get_result, cannot_move
from extension.board_utils import list_legal_moves_for, copy_piece_move, take_notes


class Node:
    """ "represents a single state in the game tree"""

    PLAYER = None
    _transposition_table = {}  # maps board signature to nodes

    def __init__(self, board, parent=None, move=None, max_depth=3):
        """initialise a new node -> non-automatic expansion"""
        self.board = board
        # same board state can come from many paths so possibly multiple parents
        self.parent = [] if parent is None else [parent]
        self.move = move
        self.children = []
        self.value = 0
        self.depth = 0 if parent is None else parent.depth + 1
        self.board_signature = self._set_board_signature()

        if self.board_signature not in Node._transposition_table:
            Node._transposition_table[self.board_signature] = self

        if self.is_terminal():  # do not continue to recurse if terminal
            if cannot_move(self.board):
                self.value = inf  # winning move
            else:
                self.value = -inf  # loosing move

    def is_terminal(self) -> bool:
        """checks current board state is not terminal"""
        result = get_result(self.board)
        return result is not None

    def expand(self, max_depth):
        """expand legal moves and create children that aren't terminal, up to depth
        and hasn't already been expanded"""

        # TODO sort each time in order of highest value and expand that node first if winning state stop recurse
        # if has children (already expanded) or reached max depth don't expand
        if self.children or self.depth >= max_depth:
            return

        player_to_expand = self.board.current_player
        moves_to_expand = list_legal_moves_for(self.board, player_to_expand)
        for piece, move in moves_to_expand:
            new_board = execute_move_onboard(self.board, piece, move)

            if new_board:
                child_signature = self._calculate_signature(new_board)
                # if child's signature already exists link and dont create new node
                if child_signature in Node._transposition_table:
                    existing_child = Node._transposition_table[child_signature]
                    if self not in existing_child.parent:
                        existing_child.parent.append(self)
                    self.children.append(existing_child)
                    continue
                child = Node(new_board, parent=self, move=(piece, move), max_depth=max_depth)
                self.children.append(child)

    def _calculate_signature(self, board):
        """calculates hashable signature for given board"""

        def get_piece_letter(piece):
            """returns upper case for black lower case for white"""
            base = piece.name[0].upper()
            return base.lower() if piece.player.name == "white" else base

        parts = []
        for piece in board.get_pieces():
            sig = f"{piece.position.x}{piece.position.y}{get_piece_letter(piece)}"
            parts.append(sig)
        parts.sort()
        parts.append(f"Turn:{board.current_player.name[0]}")
        return "|".join(parts)

    def _set_board_signature(self):
        return self._calculate_signature(self.board)


def execute_move_onboard(board, piece, move):
    """creates a new board state by cloning given board and applying move"""
    try:
        temp_board = board.clone()
        _, temp_piece, temp_move = copy_piece_move(temp_board, piece, move)
        if temp_piece and temp_move:
            temp_piece.move(temp_move)
            try:
                next(temp_board.turn_iterator)
            except StopIteration:
                take_notes("failed to iterate to next player")
            return temp_board
        take_notes(f"Error, no piece or move for {piece.name} at {piece.position}")
        return None
    except AttributeError as e:
        take_notes(f"Fatal: {e}")
        return None
