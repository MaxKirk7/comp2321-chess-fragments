from math import inf
from random import getrandbits
from extension.board_rules import get_result, cannot_move
from extension.board_utils import list_legal_moves_for, take_notes, copy_piece_move
from chessmaker.chess.base import Board, Piece, MoveOption


def execute_move_onboard(board, piece, move):
    """creates a new board state by cloning given board and applying move"""
    try:
        copy_board = board.clone()
        _, copy_piece, copy_move = copy_piece_move(copy_board, piece, move)
        if copy_piece and copy_move:
            copy_piece.move(copy_move)
            try:
                copy_board.current_player = next(copy_board.turn_iterator)
            except StopIteration:
                take_notes("failed to iterate to next player")
            return copy_board
        take_notes(f"Error, no piece or move for {piece.name} at {piece.position}")
        return None
    except AttributeError as e:
        take_notes(f"Fatal: {e}")
        return None


class Node:
    """represent single state in game tree"""

    _zobrist_keys: dict[str, int] = {}
    transposition_table: dict[int, dict] = {}  # map board z_hash to node
    _RANDBITS: int = 64
    # TT flags
    FLAG_EXACT = 0
    FLAG_LOWERBOUND = 1 # beta cut off
    FLAG_UPPERBOUND = 2 # alpha cut off

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
    def _calculate_zobrist_signature(cls, node: "Node") -> int:
        """calculate and returns nodes signature using xor (^=) operations for ROOT"""
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
        return z_hash

    @classmethod
    def _calculate_incremental_signature(
        cls,
        parent: "Node",
        piece_to_move: Piece,
        move_opt: MoveOption,
        copy_board: Board,
    ) -> int:
        """increments signature. intuition: xor is own inverse
        use parents hash, xor off and on differences, generate new hash
        bitwise operations, so should be fast
        """
        # xor out piece that moves
        z_hash = parent.node_signature
        old_piece_key = cls._get_piece_key(piece_to_move)
        z_hash ^= cls._zobrist_keys[old_piece_key]
        # xor out piece if captured from parent
        for captured_pos in move_opt.captures:
            if square := parent.get_board()[captured_pos]:
                captured_key = cls._get_piece_key(square.piece)
                z_hash ^= cls._zobrist_keys[captured_key]
            else:
                take_notes(f"no piece at capture location {captured_pos}")
        # xor out last players turn
        old_turn_key = cls._get_player_turn_key(parent.get_board())
        z_hash ^= cls._zobrist_keys[old_turn_key]
        # xor in pieces new position
        new_pos = move_opt.position
        if square := copy_board[new_pos]:
            new_piece_key = cls._get_piece_key(square.piece)
            z_hash ^= cls._zobrist_keys[new_piece_key]
        else:
            take_notes(f"no piece at new location {new_pos}")
        # xor in current player
        current_player_key = cls._get_player_turn_key(copy_board)
        z_hash ^= cls._zobrist_keys[current_player_key]
        return z_hash

    def __init__(
        self,
        board: Board,
        parent: "Node" = None,
        move: tuple[Piece, MoveOption] = None,
        signature: int = None,
    ):
        """initialise new node"""
        if not Node._zobrist_keys:
            Node._initialise_zobrist_keys()

        self._board: Board = board
        self._move: tuple[Piece, MoveOption] = move
        self._children: list[Node] = []
        self._depth: int = 0 if parent is None else parent.get_depth() + 1
        if signature is None:
            self.node_signature = Node._calculate_zobrist_signature(self)
        else:
            self.node_signature = signature
        # add to TT when evaluating in search

    def get_board(self) -> Board:
        """return current nodes board"""
        return self._board

    def get_depth(self) -> int:
        """returns current nodes depth"""
        return self._depth

    def get_children(self) -> list['Node']:
        """returns nodes list of children"""
        return self._children


    def get_move(self) -> tuple[Piece, MoveOption]:
        """return move that led to this node"""
        return self._move


    def is_terminal(self) -> bool:
        """returns if the current board state is leaf"""
        result = get_result(self.get_board())
        return result is not None


    def store_in_tt(self, value: float, search_depth: int, flag: int):
        """store evaluations in transposition table"""
        Node.transposition_table[self.node_signature] = {
            "value": value,
            "depth": search_depth,
            "flag": flag,
        }


    def expand(self, max_depth: int):
        """generate children nodes"""
        if self._children:
            return
        board = self.get_board()
        moves_to_expand = list_legal_moves_for(board, board.current_player)
        for piece, move in moves_to_expand:
            copy_board = execute_move_onboard(board, piece, move)
            if copy_board:
                # calc child signatures
                child_signature = Node._calculate_incremental_signature(self, piece, move, copy_board)
                child = Node(
                    copy_board,
                    parent=self,
                    move=(piece,move),
                    signature=child_signature
                )
                self._children.append(child)
