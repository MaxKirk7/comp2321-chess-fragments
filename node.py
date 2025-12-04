from math import inf
from random import getrandbits
from extension.board_rules import get_result
from extension.board_utils import list_legal_moves_for, take_notes, copy_piece_move
from chessmaker.chess.base import Board, Piece, MoveOption, Player


class Node:
    """represent single state in game tree"""

    _zobrist_keys: dict[str, int] = {}
    transposition_table: dict[int, "Node"] = {}  # map board z_hash to node
    _RANDBITS: int = 64
    AGENT_PLAYER: Player = None
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
        agent: Player = None
    ):
        """initialise new node"""
        if not Node.AGENT_PLAYER:
            if agent is None:
                raise RuntimeError("Agent was not set")
            Node.AGENT_PLAYER = agent
        if not Node._zobrist_keys:
            Node._initialise_zobrist_keys()

        self._board: Board = board
        self._move: tuple[Piece, MoveOption] = move
        self.parent: list[Node] = [] if parent is None else [parent]
        self._children: list[Node] = []
        self._value: float | None = None
        self.depth: int = 0 if parent is None else parent.get_depth() + 1
        self._search_depth : int = 0
        
        self.node_signature: int = (
            signature if signature is not None else Node._calculate_zobrist_signature(self)
        )
        # if node signature has not already been seen add new instance
        if self.node_signature not in Node.transposition_table:
            Node.transposition_table[self.node_signature] = self
        # if terminal game ending move
        if self.is_terminal():
            self._value = self.evaluate_terminal()
        
        self._cached_moves: list[tuple[Piece,MoveOption]] = None

    def get_board(self) -> Board:                   return self._board
    def get_depth(self) -> int:                     return self.depth
    def get_value(self) -> float:                   return self._value
    def get_move(self) -> tuple[Piece,MoveOption]:  return self._move
    def get_children(self) -> list[Node]:           return self._children
    def is_root(self) -> bool:                      return not self.parent
    def is_terminal(self) -> bool:                  return get_result(self._board) is not None
    def _get_legal_moves(self) -> list[tuple[Piece,MoveOption]]:
        """returns cached list of legal move tuples"""
        if self._cached_moves is None:
            player = self._board.current_player
            self._cached_moves = list_legal_moves_for(self._board, player)
        return self._cached_moves

    def set_value(self, val: float, depth: int) -> None:
        self._value = val
        self._search_depth = depth

    def evaluate_terminal(self) -> float:
        """determines if terminal is winning or loosing
        if we cause stalemate we win or checkmate, otherwise
        we loose / draw"""
        result = get_result(self._board)
        if result is None:
            return 0
        agent = Node.AGENT_PLAYER.name.lower()
        if "wins" in result and agent in result:
            return inf
        if "wins" in result and agent not in result:
            return -inf
        if "draw" in result:
            return 0
        return -inf # stalemate for current side

    def expand(self, max_depth: int)-> None:
        """create child nodes unless depth limit or alr expanded"""
        if self._children or self.depth >= max_depth:
            return
        for piece, move in self._get_legal_moves():
            # clone board and apply move
            new_board = self._board.clone()
            _, new_piece, new_move = copy_piece_move(new_board, piece, move)
            if new_piece is None or new_move is None:
                continue
            new_piece.move(new_move)
            # compute child signature
            child_sig = Node._calculate_incremental_signature(self, piece, move, new_board)
            if child_sig in Node.transposition_table:
                child = Node.transposition_table[child_sig]
                if self not in child.parent:
                    child.parent.append(self)
                child.depth = min(child.depth, self.depth + 1)
                self._children.append(child)
                continue
            child = Node(
                board=new_board,
                parent=self,
                move=(piece,move),
                signature=child_sig
            )
            self._children.append(child)

    def __repr__(self) -> str:
        return f"<Node depth={self.depth} value={self._value} moves={len(self._children)}>"
