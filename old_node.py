from math import inf
from random import getrandbits
from extension.board_rules import get_result, cannot_move
from extension.board_utils import list_legal_moves_for, copy_piece_move, take_notes


class Node:
    """represents a single state in the game tree"""

    ZOBRIST_KEYS: dict[str, int] = {}
    transposition_table: dict[int, 'Node'] = {}  # maps board signature to nodes

    def __init__(self, board, parent=None, move=None, signature: int = None):
        """initialise a new node -> non-automatic expansion"""
        if not Node.ZOBRIST_KEYS:
            self._initialise_zobrist_keys()
        self.board = board
        # same board state can come from many paths so possibly multiple parents
        self.parent = [] if parent is None else [parent]
        self.move = move
        self.children = []
        self.value = None
        self.depth = 0 if parent is None else parent.depth + 1
        self.board_signature = signature if signature is not None else self._calculate_zobrist_signature(self.board)
        if self.board_signature not in self.transposition_table:
            self.transposition_table[self.board_signature] = self

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
                child_signature = self._calculate_incremental_zobrist(self, piece, move, new_board)
                # if child's signature already exists link and dont create new node
                if child_signature in self.transposition_table:
                    existing_child = self.transposition_table[child_signature]
                    if self not in existing_child.parent:
                        existing_child.parent.append(self)
                    self.children.append(existing_child)
                    continue
                child = Node(new_board, parent=self, move=(piece, move), signature= child_signature)
                self.children.append(child)

    @classmethod
    def _get_piece_key(cls, piece) -> str:
        """helper to generate consistent key for piece"""
        pos = piece.position
        return f"{piece.player.name.lower()}_{piece.name}_{pos.x}_{pos.y}"

    @classmethod
    def _calculate_zobrist_signature(cls, board):
        """xor each of the keys to get zobrist hash of board"""
        zobrist_hash = 0
        for piece in board.get_pieces():
            key = cls._get_piece_key(piece)
            try:
                zobrist_hash ^= cls.ZOBRIST_KEYS[key]
            except KeyError:
                take_notes(f"missing key for {key}")
        turn_key = f"turn_{board.current_player.name.lower()}"
        zobrist_hash ^= cls.ZOBRIST_KEYS[turn_key]
        # todo keys for en-peasant

        return zobrist_hash

    @classmethod
    def _calculate_incremental_zobrist(cls, parent: 'Node', piece_to_move, move_option, new_board):
        current_hash = parent.board_signature
        # xor out old state
        old_piece_key = cls._get_piece_key(piece_to_move)
        current_hash ^= cls.ZOBRIST_KEYS[old_piece_key]

        # remove captured pieces
        for capture_pos in move_option.captures:
            captured_piece_details = find_piece_at_position(parent.board, capture_pos)
            if captured_piece_details:
                captured_key = cls._get_piece_key(captured_piece_details)
                current_hash ^= cls.ZOBRIST_KEYS[captured_key]
            else:
                take_notes(f"no piece at {capture_pos}")

        # out old players turn
        old_turn_key = f"turn_{parent.board.current_player.name.lower()}"
        current_hash ^= cls.ZOBRIST_KEYS[old_turn_key]

        # xor in new state
        new_pos = move_option.position
        #* piece state could change (pawn promotion) so use new board for keys
        piece_new_board = find_piece_at_position(new_board, new_pos)
        if piece_new_board:
            new_piece_key = cls._get_piece_key(piece_new_board)
            current_hash ^= cls.ZOBRIST_KEYS[new_piece_key]
        else:
            take_notes(f"no piece at location {new_pos}")
        
        # in new player turn
        new_turn_key = f"turn_{new_board.current_player.name.lower()}"
        current_hash ^= cls.ZOBRIST_KEYS[new_turn_key]

        # todo keys for en-peasent

        return current_hash


    @classmethod
    def _initialise_zobrist_keys(cls):
        piece_types = ['King','Queen','Right','Knight','Bishop','Pawn']
        players = ["white", "black"]
        board_size = (5,5)
        for x in range(board_size[0]):
            for y in range(board_size[1]):
                for player in players:
                    for piece_type in piece_types:
                        key_name = f"{player}_{piece_type}_{x}_{y}"
                        cls.ZOBRIST_KEYS[key_name] = getrandbits(64)
        for player in players:
            cls.ZOBRIST_KEYS[f"turn_{player}"] = getrandbits(64)

        # todo add for en-peasant

def find_piece_at_position(board, position):
    for piece in board.get_pieces():
        if piece.position == position:
            return piece
    return None



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
