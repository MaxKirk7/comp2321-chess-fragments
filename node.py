from math import inf
from random import getrandbits
from extension.board_rules import get_result, cannot_move
from extension.board_utils import list_legal_moves_for, copy_piece_move, take_notes
from chessmaker.chess.base import Board, Piece, MoveOption, Square


class Node:
    """represent single state in game tree"""

    _zobrist_keys: dict[str, int] = {}
    transposition_table: dict[int, "Node"] = {}  # map board z_hash to node
    _RANDBITS: int = 64

    # todo add en-peasant keys to class methods
    @classmethod
    def _initialise_zobrist_keys(cls, board_size=(5, 5)):
        """initialise keys for chess fragments default 5x5 grid"""
        piece_types = ["King", "Queen", "Right", "Knight", "Bishop", "Pawn"]
        players = ["white", "black"]
        # 5 x 5 x 6 x 2 keys representing all possible combinations for each square on board
        for x in range(board_size[0]):
            for y in range(board_size[1]):
                for player in players:
                    for piece_type in piece_types:
                        key_name = f"{player}_{piece_type}_{x}_{y}"
                        cls._zobrist_keys[key_name] = getrandbits(cls._RANDBITS)
        # unique key for whose turn it is
        for player in players:
            cls._zobrist_keys[f"turn_{player}"] = getrandbits(cls._RANDBITS)

    @classmethod
    def _get_piece_key(cls, piece: Piece) -> str:
        """helper to return consistent key for pieces"""
        pos = piece.position
        player = piece.player
        return f"{player.name.lower()}_{piece.name}_{pos.x}_{pos.y}"

    @classmethod
    def _get_player_turn_key(cls, board: Board) -> str:
        """helper to return consistent key for boards current player"""
        player = board.current_player
        return f"turn_{player.name.lower()}"

    @classmethod
    def _calculate_zobrist_signature(cls, node: "Node") -> None:
        """calculate and set nodes signature using xor (^=) operations
        , incremental calculation if has a parent"""
        if not node.is_root():
            # incremental zobrist
            node.node_signature = cls._calculate_incremental_signature(
                node, node.parent
            )
        else:
            # calculate new signature
            board = node.get_board()
            z_hash = 0
            for piece in board.get_pieces():
                key = cls._get_piece_key(piece)
                try:
                    z_hash ^= cls._zobrist_keys[key]
                except KeyError:
                    take_notes(f"missing key for {key}")
            z_hash ^= cls._zobrist_keys[cls._get_player_turn_key(board)]
            node.node_signature = z_hash

    @classmethod
    def _calculate_incremental_signature(
        cls,
        parent: "Node",
        piece_to_move: Piece,
        move_opt: MoveOption,
        new_board: Board,
    ) -> int:
        """increments signature. intuition: xor is own inverse
        use parents hash, xor off and on differences, generate new hash
        bitwise operations, so should be fast
        """
        # xor out piece that moves
        z_hash = parent.node_signature
        old_piece_key = cls._get_piece_key(piece_to_move)
        z_hash ^= cls._zobrist_keys[old_piece_key]
        # xor out piece if captured
        for captured_pos in move_opt.captures:
            if square := new_board[captured_pos]:
                captured_key = cls._get_piece_key(square.piece)
                z_hash ^= captured_key
            else:
                take_notes(f"no piece at capture location {captured_pos}")
        # xor out last players turn
        old_turn_key = cls._get_player_turn_key(parent.board)
        z_hash ^= old_turn_key
        # xor in pieces new position
        new_pos = move_opt.position
        if square := new_board[new_pos]:
            new_piece_key = cls._get_piece_key(square.piece)
            z_hash ^= cls._zobrist_keys[new_piece_key]
        else:
            take_notes(f"no piece at new location {new_pos}")
        # xor in current player
        current_player_key = cls._get_player_turn_key(new_board)
        z_hash ^= cls._zobrist_keys[current_player_key]
        return z_hash


    def __init__(self, board, parent=None, move=None, signature: int = None):
        """initialise new node"""
        if not Node._zobrist_keys:
            Node._initialise_zobrist_keys()
        self._board: Board = board
        self._move: tuple[Piece, "Move"] = move
        self.parent: list[Node] = [] if parent is None else [parent]
        self._children: list[Node] = []
        self._value: float | None = None
        self._depth: int = 0 if parent is None else parent.depth + 1
        self.node_signature: float = (
            self._calculate_zobrist_signature() if signature is None else signature
        )
        # if node signature has not already been seen add new instance
        if self.node_signature not in Node.transposition_table:
            Node.transposition_table[self.node_signature] = self
        # if terminal game ending move
        if self.is_terminal():
            if cannot_move(self._board):
                self.value = inf  # wins game
            else:
                self.value = -inf  # looses game

    def get_board(self):
        return self._board

    def is_root(self) -> bool:
        return not self.parent
