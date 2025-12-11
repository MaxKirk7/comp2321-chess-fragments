from __future__ import annotations

from math import inf
from typing import Any

from chessmaker.chess.base import Board, Player, Piece, MoveOption, Position
from chessmaker.chess.pieces import King
from extension.board_rules import get_result
from samples import black, white  # players are either white or black

from dataclasses import dataclass
from random import getrandbits
@dataclass(frozen=False)

class TTEntry:
    """holds a depth score and flag representing node"""
    depth: int
    score: float
    flag: str  # exact, lower, upper

class Node:
    """
    holds information representing game state
    """
    _z_keys: dict[str, int] = {}
    _transposition_table: dict[int, TTEntry] = {}
    __slots__ = ("board", "current_player", "previous_player", "parents", "children",
        "move", "z_hash", "_cached_moves", "kings", "order_score", "_attacked_by", "_is_terminal")

    def __init__(
            self,
            board: Board,
            parent: 'Node' | None = None,
            move: tuple[Piece, MoveOption] | None = None,
            z_hash: int | None = None
            ) -> None:
        """
        initialise a new node representing unique game state,
        initialises Node zobrist keys class if first node created
        """
        if not Node._z_keys:
            Node._initialise_zobrist_keys()
        self.board: Board = board
        self.current_player: Player = self.board.current_player
        # previous_player is always the opposite of current_player
        self.previous_player: Player = white if self.current_player == black else black
        self.parents: list['Node'] = [] if parent is None else [parent]
        self.children: list['Node'] = []
        self.move: tuple[Piece, MoveOption] | None = move
        self.order_score: float | None = None
        self.z_hash: int = z_hash if z_hash is not None else Node._calc_root_hash(self)
        self._cached_moves: list[tuple[Piece, MoveOption]] = []
        self._attacked_by: dict[str, set[Position]] = {}
        self._is_terminal: bool = False
        self.kings: dict[str, King]
        if parent is None:
            # find king on this board
            self.kings = {}
            for pc in self.board.get_pieces():
                if isinstance(pc, King):
                    self.kings[pc.player.name] = pc
            # add entry to TT
            Node.add_entry_in_tt(self, flag ="EXACT")
        else:
            # can use copy of parents kings and adjust if king move
            self.kings = parent.kings.copy()

    @classmethod
    def get_entry_in_tt(cls, z_hash: int) -> tuple[int | None, float | None, str | None]:
        """
        take a nodes hash and find entry in TT,
        returns depth, score, flag
        """
        entry = cls._transposition_table.get(z_hash)
        if entry is None:
            return None, None, None
        return entry.depth, entry.score, entry.flag

    @classmethod
    def add_entry_in_tt(
        cls,
        node: "Node",
        depth: int = 0,
        value: float = 0,
        flag: str = "Lower"
    ) -> None:
        """
        adds an entry for hash of game state into tt,
        validates flag to make sure correct
        """
        if (flag_str := flag.upper()) not in ("LOWER", "UPPER", "EXACT"):
            raise ValueError("Flag must be exact lower or upper bound")
        cls._transposition_table[node.z_hash] = TTEntry(depth, value, flag_str)

    @classmethod
    def get_piece_key(cls, piece: Piece, position: Position | None = None) -> str:
        """
        helper generates and returns key for piece "type,player,x,y"
        """
        if position is None:
            position = piece.position
        pc_type = piece.name.lower()
        player = piece.player.name.lower()
        return f"{pc_type}_{player}_{position.x}_{position.y}"

    @classmethod
    def _get_player_key(cls, player: Player | str) -> str:
        """helper generates and returns key for whose turn it is"""
        if isinstance(player, Player):
            name = player.name.lower()
        else:
            name = player.lower()
        return f"turn_{name}"

    @classmethod
    def _initialise_zobrist_keys(cls) -> None:
        """initialise key representing each possible square in game, piece x turn x squares"""
        piece_types = ["king", "queen", "right", "knight", "bishop", "pawn"]
        players = [white.name.lower(), black.name.lower()]
        randbits = 64
        bits_so_far = set()
        # fixed 5x5 board
        for x in range(5):
            for y in range(5):
                for p in players:
                    for pt in piece_types:
                        key = f"{pt}_{p}_{x}_{y}"
                        # ensure uniqueness of random bits per key
                        while True:
                            random = getrandbits(randbits)
                            if random not in bits_so_far:
                                cls._z_keys[key] = random
                                bits_so_far.add(random)
                                break
                    # player turn key
                    turn_key = cls._get_player_key(p)
                    while True:
                        random = getrandbits(randbits)
                        if random not in bits_so_far:
                            cls._z_keys[turn_key] = random
                            bits_so_far.add(random)
                            break

    @classmethod
    def _calc_root_hash(cls, root: "Node") -> int:
        """calculate hash of node if root"""
        board = root.board
        z_hash = 0
        for pc in board.get_pieces():
            pc_key = cls.get_piece_key(pc)
            z_hash ^= cls._z_keys[pc_key]
        player_key = cls._z_keys[cls._get_player_key(board.current_player)]
        z_hash ^= player_key
        return z_hash

    @classmethod
    def _calc_incremental_hash(
        cls,
        parent: "Node",
        piece_to_move: Piece,
        move_opt: MoveOption,
        new_board: Board
        ) -> int:
        """calculate hash for node if is not root (has parents)"""
        z_hash = parent.z_hash
        # remove piece from old position
        old_pc_key = cls.get_piece_key(piece_to_move)
        z_hash ^= cls._z_keys[old_pc_key]
        # remove any pieces that are captured
        for captured_pos in getattr(move_opt, "captures", []):
            if square := parent.board[captured_pos]:
                captured_pc_key = cls.get_piece_key(square.piece)
                z_hash ^= cls._z_keys[captured_pc_key]
        # change player turn
        z_hash ^= cls._z_keys[cls._get_player_key(parent.current_player)]
        z_hash ^= cls._z_keys[cls._get_player_key(new_board.current_player)]
        # add moved piece in new position
        moved_pc = new_board[move_opt.position].piece
        moved_pc_key = cls.get_piece_key(moved_pc, move_opt.position)
        z_hash ^= cls._z_keys[moved_pc_key]
        return z_hash

    def is_defended_by(self, player: Player, position: Position) -> bool:
        """returns true if `position` is defended by another piece"""
        return position in self.attacks_by(player)

    def attacks_by(self, player: Player) -> set[Position]:
        """gathers and returns all square positions player attacks"""
        key = player.name
        if key not in self._attacked_by:
            attacks = set()
            for pc in self.board.get_player_pieces(player):
                for mv in pc.get_move_options():
                    if getattr(mv, "captures", None):
                        attacks.update(mv.captures)
                    attacks.add(mv.position)
            self._attacked_by[key] = attacks
        return self._attacked_by[key]

    def get_legal_moves(self) -> list[tuple[Piece, MoveOption]]:
        """returns cached moves or generates and caches legal moves, updates king position"""
        if self._cached_moves:
            return self._cached_moves

        legal: list[tuple[Piece, MoveOption]] = []
        own_king = self.kings[self.current_player.name]

        if self.parents:
            opponents_attacks = self.attacks_by(self.previous_player)
        else:
            opponents_attacks = set()

        for pc in self.board.get_player_pieces(self.current_player):
            for mv in pc.get_move_options():
                # if move king just check we aren't moving into a check
                if isinstance(pc, King):
                    if mv.position in opponents_attacks:
                        continue
                    legal.append((pc,mv))
                    continue
            
                tmp_board = self.board.clone()
                tmp_pc = tmp_board[pc.position].piece
                tmp_pc.move(mv)
                tmp_king_sq = tmp_board[own_king.position] if tmp_pc != own_king else tmp_board[mv.position]
                if tmp_king_sq.piece.is_attacked():
                    continue
                legal.append((pc, mv))
        self._cached_moves = legal
        return self._cached_moves

    def is_terminal(self) -> bool:
        """return true if node is terminal"""
        if not self._is_terminal:
            self._is_terminal = get_result(self.board) is not None
        return self._is_terminal

    def expand(self) -> None:
        """generates children lazily one depth lower than this node or if already generated links"""
        # if node is already expanded or is terminal dont expand
        if self.children or self.is_terminal():
            return
        parent_depth, _, _ = Node.get_entry_in_tt(self.z_hash)
        for pc, mv in self.get_legal_moves():
            new_board = self.board.clone()
            new_pc = new_board[pc.position].piece
            new_pc.move(mv)
            child_hash = Node._calc_incremental_hash(self, pc, mv, new_board)
            depth, _, _ = Node.get_entry_in_tt(child_hash)
            if depth is not None:
                child = Node(new_board, parent=self, move=(pc, mv), z_hash=child_hash)
                self.children.append(child)
                child.parents.append(self)
                continue
            child = Node(
                board=new_board,
                parent=self,
                move=(pc, mv),
                z_hash=child_hash
            )
            Node.add_entry_in_tt(child, depth=parent_depth + 1, value=0, flag="EXACT")
            if isinstance(pc, King):
                child.kings[pc.player.name] = new_pc
            self.children.append(child)

