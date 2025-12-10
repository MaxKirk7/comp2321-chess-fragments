from dataclasses import dataclass
from random import getrandbits
from chessmaker.chess.base import Board, Piece, MoveOption, Player, Position
from chessmaker.chess.pieces import King
from extension.board_utils import copy_piece_move, list_legal_moves_for, take_notes
from extension.board_rules import get_result, cannot_move

@dataclass(frozen=False)
class TTEntry:
    depth: int
    score: float
    flag: str


class Node:
    _z_keys: dict[str, int] = {}
    _transposition_table: dict[int, TTEntry] = {}
    __slots__ = ("board", "current_player", "parents", "children",
        "move", "hash", "_cached_moves", "kings", "order_score", "_attacked_by")
    
    def __init__(
            self,
            board: Board,
            parent: 'Node'= None,
            move: tuple[Piece,MoveOption] = None,
            z_hash: int = None
            ) -> None:
        
        if not Node._z_keys:
            Node._initialise_zobrist_keys()
        self.board: Board = board
        self.current_player: Player  = self.board.current_player
        self.parents: list['Node'] = [] if parent is None else [parent]
        self.children: list['Node'] = []
        self.move: tuple[Piece, MoveOption] | None = move
        self.order_score: float | None = None
        self.hash: int = z_hash if z_hash is not None else Node._calc_root_hash(self)
        self._cached_moves: list[tuple[Piece, MoveOption]] = []
        self._attacked_by: dict[str,set[Position]] = {}
        self.kings: dict[str, King]
        if parent is None:
            # find kings
            self.kings = {}
            for pc in board.get_pieces():
                if isinstance(pc, King):
                    self.kings[pc.player.name] = pc
            # add root entry to TT
            Node.add_entry_in_tt(self, flag="EXACT")
        else:
            self.kings = parent.kings.copy()

    @classmethod
    def get_entry_in_tt(cls, z_hash: int) -> tuple[int, float, str]:
        """returns node, depth, value, flag"""
        entry = cls._transposition_table.get(z_hash, None)
        if entry is None:
            return None, None, None
        return entry.depth, entry.score, entry.flag

    @classmethod
    def add_entry_in_tt(
        cls, node: "Node", depth: int = 0, value: float = 0.0, flag: str = "Lower") -> None:
        if (flag_str := flag.upper()) not in ("LOWER", "UPPER", "EXACT"):
            raise ValueError("Flag must be exact, lower, or upper")
        cls._transposition_table[node.hash] = TTEntry(depth, value, flag_str)


    @classmethod
    def get_piece_key(cls, piece: Piece, pos: Position = None) -> str:
        """return key to identify each piece on board"""
        if pos is None:
            pos = piece.position
        piece_type = getattr(piece.__class__, "__name__", None) or piece.name
        piece_type = piece_type.lower()
        player = piece.player.name.lower()
        return f"{piece_type}_{player}_{pos.x}_{pos.y}"


    @classmethod
    def _get_player_key(cls, player:Player) -> str:
        """return key to identify whose turn it is"""
        return f"turn_{player.name.lower()}"


    @classmethod
    def _initialise_zobrist_keys(cls) -> None:
        """initialise keys for each piece, square and player turn"""
        piece_types = ["king", "queen", "right", "knight", "bishop", "pawn"]
        players = ["white", "black"]
        randbits = 64
        for x in range(5):
            for y in range(5):
                for p in players:
                    for pt in piece_types:
                        key = f"{pt}_{p}_{x}_{y}"
                        cls._z_keys[key] = getrandbits(randbits)
        for p in players:
            cls._z_keys[f"turn_{p}"] = getrandbits(randbits)


    @classmethod
    def _calc_root_hash(cls, node: 'Node') -> int:
        """calculates zobrist hash for root"""
        board = node.board
        z_hash = 0
        for p in board.get_pieces():
            key = cls.get_piece_key(p)
            z_hash ^= cls._z_keys[key]
        z_hash ^= cls._z_keys[cls._get_player_key(board.current_player)]
        return z_hash

    @classmethod
    def _calc_incremental_hash(
        cls,
        parent: 'Node',
        piece_to_move: Piece,
        move_opt: MoveOption,
        new_board: Board
        ) -> int:
        """calculates hash by altering parents hash with xor"""
        z_hash = parent.hash
        # remove piece from old position
        old_piece_key = cls.get_piece_key(piece_to_move)
        z_hash ^= cls._z_keys[old_piece_key]
        # remove any piece that was captured
        for captured_pos in getattr(move_opt, "captures", []):
            if square := parent.board[captured_pos]:
                captured_key = cls.get_piece_key(square.piece)
                z_hash ^= cls._z_keys[captured_key]
        # remove last players turn and add current players turn
        z_hash ^= cls._z_keys[cls._get_player_key(parent.current_player)]
        z_hash ^= cls._z_keys[cls._get_player_key(new_board.current_player)]
        # add in piece after move
        new_piece = new_board[move_opt.position].piece
        new_piece_key = cls.get_piece_key(new_piece, move_opt.position)
        z_hash ^= cls._z_keys[new_piece_key]
        return z_hash
    
    def is_defended_by(self, player: Player, position: Position) -> bool:
        return position in self.attacks_by(player)

    def attacks_by(self, player: Player) -> set[Position]:
        """return set of sqaures attacked by player on this node"""
        key = player.name
        if key not in self._attacked_by:
            attacks = set()
            for pc in self.board.get_player_pieces(player):
                for mv in pc.get_move_options():
                    if getattr(mv, "captures", None):
                        attacks.update(mv.captures)
                    attacks.add(mv.position)
            self._attacked_by[key] = attacks
        return self._attacked_by


    def get_legal_moves(self) -> list[tuple[Piece,MoveOption]]:
        """returns a cached list of legal moves"""
        if self._cached_moves:
            return self._cached_moves
        legal: list[tuple[Piece,MoveOption]] = []
        own_king = self.kings[self.current_player.name]
        if self.parents:
            opponent = self.parents[0].current_player
            opponent_attacks = self.attacks_by(opponent)
        else:
            opponent_attacks = set()
        for piece in self.board.get_player_pieces(self.current_player):
            for move in piece.get_move_options():
                if isinstance(piece,King):
                    if move.position in opponent_attacks:
                        continue
                else:
                    if own_king.position in opponent_attacks and own_king.position != move.position:
                        tmp_board = self.board.clone()
                        tmp_piece = tmp_board[piece.position].piece
                        tmp_piece.move(move)
                        tmp_king = tmp_board[own_king.position].piece
                        if tmp_king.is_attacked():
                            continue
                legal.append((piece,move))

        self._cached_moves = legal
        return self._cached_moves

    def is_terminal(self) -> bool:
        """returns true if node is a terminal state"""
        return get_result(self.board) is not None or cannot_move(self.board)

    def expand(self) -> None:
        """expands next set of children"""
        if self.children or self.is_terminal():
            return
        
        parent_depth, _, _ = Node.get_entry_in_tt(self.hash)

        for piece, move in self.get_legal_moves():
            new_board = self.board.clone()
            new_piece = new_board[piece.position].piece
            new_piece.move(move)
            child_hash = Node._calc_incremental_hash(self, piece, move, new_board)
            
            depth, score, flag = Node.get_entry_in_tt(child_hash)
            if depth is not None:
                child = Node(new_board, parent=self, move=(piece,move), z_hash=child_hash)
                self.children.append(child)
                child.parents.append(self)
                continue

            child = Node(
                board=new_board,
                parent=self,
                move=(piece,move),
                z_hash=child_hash
            )
            Node.add_entry_in_tt(child, depth= parent_depth +1, value= 0, flag="EXACT")
            # update position of kings
            if isinstance(piece, King):
                child.kings[piece.player.name] = new_piece
            self.children.append(child)
