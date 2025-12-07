from random import getrandbits
from chessmaker.chess.base import Board, Piece, MoveOption, Player, Position
from chessmaker.chess.pieces import King
from extension.board_utils import copy_piece_move, list_legal_moves_for, take_notes
from extension.board_rules import get_result, cannot_move

class Node:
    _z_keys: dict[str, int] = {}
    _transposition_table: dict[int, 'Node'] = {}
    __slots__ = ("board", "current_player", "parents", "children",
        "move", "hash", "_cached_moves", "kings")
    
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
        self.hash: int = z_hash if z_hash is not None else Node._calc_root_hash(self)
        self._cached_moves: list[tuple[Piece, MoveOption]] = []
        self.kings: dict[str, King]
        if parent is None:
            # find kings
            self.kings = {}
            for pc in board.get_pieces():
                if isinstance(pc, King):
                    self.kings[pc.player.name] = pc
        else:
            self.kings = parent.kings.copy()


    @classmethod
    def _get_piece_key(cls, piece: Piece, pos: Position = None) -> str:
        """return key to identify each piece on board"""
        if pos is None:
            pos = piece.position
        piece_type = getattr(piece.__class__, "__name__", None) or piece.name
        take_notes(piece_type)
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
            key = cls._get_piece_key(p)
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
        old_piece_key = cls._get_piece_key(piece_to_move)
        z_hash ^= cls._z_keys[old_piece_key]
        # remove any piece that was captured
        for captured_pos in getattr(move_opt, "captures", []):
            if square := parent.board[captured_pos]:
                captured_key = cls._get_piece_key(square.piece)
                z_hash ^= cls._z_keys[captured_key]
        # remove last players turn and add current players turn
        z_hash ^= cls._z_keys[cls._get_player_key(parent.current_player)]
        z_hash ^= cls._z_keys[cls._get_player_key(new_board.current_player)]
        # add in piece after move
        new_piece_key = cls._get_piece_key(piece_to_move, move_opt.position)
        z_hash ^= cls._z_keys[new_piece_key]
        return z_hash


    def get_legal_moves(self) -> list[tuple[Piece,MoveOption]]:
        """returns a cached list of legal moves"""
        if not self._cached_moves:
            self._cached_moves = list_legal_moves_for(self.board, self.current_player)
        return self._cached_moves

    def is_terminal(self) -> bool:
        """returns true if node is a terminal state"""
        return get_result(self.board) is not None or cannot_move(self.board)

    def expand(self) -> None:
        """expands next set of children"""
        if self.children or self.is_terminal():
            return

        for piece, move in self.get_legal_moves():
            new_board = self.board.clone()
            _, new_piece, new_move = copy_piece_move(new_board, piece, move)
            if new_piece is None or new_move is None:
                continue
            new_piece.move(new_move)
            child_hash = Node._calc_incremental_hash(self, piece, move, new_board)
            if child_hash in Node._transposition_table:
                child = Node._transposition_table[child_hash]
                if self not in child.parents:
                    child.parents.append(self)
                self.children.append(child)
                continue
            child = Node(
                board=new_board,
                parent=self,
                move=(piece,move),
                z_hash=child_hash
            )
            # update position of kings
            if isinstance(piece, King):
                child.kings[piece.player.name] = new_piece
            Node._transposition_table[child_hash] = child
            self.children.append(child)
