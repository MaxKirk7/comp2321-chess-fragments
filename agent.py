from __future__ import annotations
from dataclasses import dataclass
from math import inf
from random import getrandbits
from chessmaker.chess.base import Board, Piece, MoveOption, Player, Position
from chessmaker.chess.pieces import King
from extension.board_rules import get_result
from samples import white, black

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
    __slots__ = (
        "board",
        "current_player",
        "previous_player",
        "parents",
        "children",
        "move",
        "z_hash",
        "_cached_moves",
        "kings",
        "order_score",
        "_attacked_by",
        "_is_terminal",
        "__dict__"
    )

    def __init__(
        self,
        board: Board,
        parent: "Node" | None = None,
        move: tuple[Piece, MoveOption] | None = None,
        z_hash: int | None = None,
    ) -> None:
        """
        initialise a new node representing unique game state,
        initialises Node zobrist keys class if first node created

        :param self: this instance of a node
        :param board: board object representing this node of game tree
        :type board: Board
        :param parent: node that led to this node, None for root
        :type parent: 'Node' | None
        :param move: move that led to this game state
        :type move: tuple[Piece, MoveOption] | None
        :param z_hash: zobrist hash belonging to this game state
        :type z_hash: int | None
        :rtype: None
        """
        if not Node._z_keys:
            Node._initialise_zobrist_keys()
        self.board: Board = board
        self.current_player: Player = self.board.current_player
        self.previous_player: Player = white if self.current_player == black else black
        self.parents: list["Node"] = [] if parent is None else [parent]
        self.children: list["Node"] = []
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
            Node.add_entry_in_tt(self, flag="EXACT")
        else:
            # can use copy of parents kings and adjust if king move
            self.kings = parent.kings.copy()

    @classmethod
    def get_entry_in_tt(
        cls, z_hash: int
    ) -> tuple[int, float, str] | tuple[None, None, None]:
        """
        take a nodes hash and find entry in TT,
        returns depth, score, flag
        return tuple of None if not

        :param cls: Node class
        :param z_hash: hash representing the game state
        :type z_hash: int
        :return: return depth, score, flag as tuple or Nones if no entry
        :rtype: tuple[int, float, str] | tuple[None, None, None]
        """
        entry = cls._transposition_table.get(z_hash)
        if entry is None:
            return None, None, None
        return entry.depth, entry.score, entry.flag

    @classmethod
    def add_entry_in_tt(
        cls, node: "Node", depth: int = 0, value: float = 0, flag: str = "Lower"
    ) -> None:
        """
        adds an entry for hash of game state into tt,
        validates flag to make sure correct

        :param node: node whose game state we are saving
        :type node: "Node"
        :param depth: depth that this node was evaluated at
        :type depth: int
        :param value: value this game state was given
        :type value: float
        :param flag: bound of value
        :type flag: str
        """
        if (flag_str := flag.upper()) not in ("LOWER", "UPPER", "EXACT"):
            raise ValueError("Flag must be exact lower or upper bound")
        cls._transposition_table[node.z_hash] = TTEntry(
            depth=depth, score=value, flag=flag_str
        )

    @classmethod
    def get_piece_key(cls, piece: Piece, position: Position | None = None) -> str:
        """
        helper generates and returns key for piece "type,player,x,y"

        :param piece: piece the key is for
        :type piece: Piece
        :param position: optionally chose the position
        :type position: Position | None
        :return: return key to use for lookup
        :rtype: str
        """
        if position is None:
            position = piece.position
        pc_type = piece.name.lower()
        player = piece.player.name.lower()
        return f"{pc_type}_{player}_{position.x}_{position.y}"

    @classmethod
    def _get_player_key(cls, player: Player | str) -> str:
        """
        helper generates and returns key for whose turn it is

        :param player: player whose turn it is
        :type player: Player
        :return: return key for player turn
        :rtype: str
        """
        if isinstance(player, Player):
            name = player.name.lower()
        else:
            name = player.lower()
        return f"turn_{name}"

    @classmethod
    def _initialise_zobrist_keys(cls) -> None:
        """
        initialise key representing each possible square in game,
        piece x turn x squares
        """
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
                        Node._add_unique_randbits_for_key(bits_so_far, key)
                    key = cls._get_player_key(p)
                    while True:
                        random = getrandbits(randbits)
                        if random not in bits_so_far:
                            cls._z_keys[key] = random
                            bits_so_far.add(random)
                            break

    @classmethod
    def _add_unique_randbits_for_key(
        cls, set_bits: set[int], key: str, randbits: int = 64
    ) -> None:
        """helper adds unique randbits for each key"""
        while True:
            random = getrandbits(randbits)
            if random not in set_bits:
                cls._z_keys[key] = random
                set_bits.add(random)
                return

    @classmethod
    def _calc_root_hash(cls, root: "Node") -> int:
        """
        calculate hash of node if root

        :param root: node that hash needs to be created for
        :type root: "Node"
        :return: returns hash representing game state
        :rtype: int
        """
        board = root.board
        z_hash = 0
        for pc in board.get_pieces():
            pc_key = cls.get_piece_key(pc)
            z_hash ^= cls._z_keys[pc_key]
        player_key = cls._z_keys[cls._get_player_key(board.current_player)]
        z_hash ^= player_key
        return z_hash

    @classmethod
    def calc_incremental_hash(
        cls,
        parent: "Node",
        piece_to_move: Piece,
        move_opt: MoveOption,
        new_board: Board,
    ) -> int:
        """
        calculates hash for node if is not root (has parents)

        :param parent: node that this child came from
        :type parent: "Node"
        :param piece_to_move: piece that has moved on parent board
        :type piece_to_move: Piece
        :param move_opt: move made on the piece to move
        :type move_opt: MoveOption
        :param new_board: board state of node we are calculating
        :type new_board: Board
        :return: return incremented hash for new node using parent
        :rtype: int
        """
        # make xor changes to parent hash to avoid full recalculation
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
        """
        returns true if `position` is defended by another piece

        :param player: player we want to check is defending position
        :type player: Player
        :param position: position to check defence
        :type position: Position
        :return: returns true if position is defended
        :rtype: bool
        """
        return position in self.attacks_by(player)

    def attacks_by(self, player: Player) -> set[Position]:
        """
        gathers and returns all square positions player attacks

        :param player: player we are checking attacks of
        :type player: Player
        :return: set of all positions player attacks
        :rtype: set[Position]
        """
        key = player.name
        if key not in self._attacked_by:
            attacks = set()
            for pc in self.board.get_player_pieces(player=player):
                for mv in pc.get_move_options():
                    if getattr(mv, "captures", None):
                        attacks.update(mv.captures)
                    attacks.add(mv.position)
            self._attacked_by[key] = attacks
        return self._attacked_by

    def get_legal_moves(self) -> list[tuple[Piece, MoveOption]]:
        """
        returns cached moves or generates and caches legal moves,
        updates king position

        :return: return list of legal moves
        :rtype: list[tuple[Piece | EventPublisher, MoveOption]]
        """
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
                if isinstance(pc, King):
                    if mv.position in opponents_attacks:
                        continue
                else:
                    if (
                        own_king.position in opponents_attacks
                        and own_king.position != mv.position
                    ):
                        tmp_board = self.board.clone()
                        tmp_pc = tmp_board[pc.position].piece
                        tmp_pc.move(mv)
                        tmp_king = tmp_board[own_king].piece
                        if tmp_king.is_attacked():
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
        """generates children lazily one depth lower than this node
        or if already generated links"""
        # if node is already expanded or is terminal dont expand
        if self.children or self.is_terminal():
            return
        parent_depth, _, _ = Node.get_entry_in_tt(self.z_hash)
        for pc, mv in self.get_legal_moves():
            new_board = self.board.clone()
            new_pc = new_board[pc.position].piece
            new_pc.move(mv)
            child_hash = Node.calc_incremental_hash(
                parent=self, piece_to_move=pc, move_opt=mv, new_board=new_board
            )
            depth, _, _ = Node.get_entry_in_tt(child_hash)
            if depth is not None:
                child = Node(new_board, parent=self, move=(pc, mv), z_hash=child_hash)
                self.children.append(child)
                child.parents.append(self)
                continue
            child = Node(board=new_board, parent=self, move=(pc, mv), z_hash=child_hash)
            Node.add_entry_in_tt(
                node=child, depth=parent_depth + 1, value=0, flag="EXACT"
            )
            if isinstance(pc, King):
                child.kings[pc.player.name] = new_pc
            self.children.append(child)


class Search:
    """
    logic to evaluate game states in perspective of agent to find best move
    """

    MAP_PIECE_TO_VALUE = {
        "king": 20,
        "queen": 9,
        "right": 8,
        "knight": 4,
        "bishop": 3,
        "pawn": 1,
    }
    MAP_PIECE_CENTER_TO_VALUE = {
        "king": -5,
        "queen": 1,
        "right": 2,
        "knight": 4,
        "bishop": 7,
        "pawn": 8,
    }
    CENTRE_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    # heuristics
    bonus = {
        "centre": 0.06,
        "mobility": 0.05,
        "safety": -0.45,
        "king_safety": -3,
        "enemy_king_safety": 2,
        "capture": 1.1,
        "check": 0.45,
        "checkmate": 500,
        "promotion": 2,
        "unsafe-move": -0.7,
        "protected": 0.8,
    }

    def __init__(self, root_board: Board, agent: Player):
        self.root = Node(root_board)
        self.agent = agent

    def search(self, depth=3) -> tuple[Piece, MoveOption] | tuple[None, None]:
        """return best move found up to set depth or none if no move found"""
        best_score = -inf
        best_child = None
        children = self.get_ordered_children(self.root)
        for child in children:
            score = self.alphabeta(child, -inf, inf, depth - 1)
            if score > best_score:
                best_score = score
                best_child = child
        if best_child is None:
            return None, None
        return best_child.move

    def alphabeta(self, node: Node, alpha: float, beta: float, depth) -> float:
        """
        attempts to return highest guaranteed score agent can make

        :param node: node that is to be mini-maxed next
        :type node: Node
        :param alpha: the best score found so far
        :type alpha: float
        :param beta: the worst score found so far
        :type beta: float
        :param depth: current depth of game tree expansion
        :return: highest guaranteed score
        :rtype: float
        """
        entry_depth, entry_val, entry_flag = Node.get_entry_in_tt(node.z_hash)
        if entry_depth is not None and entry_depth >= depth:
            if entry_flag == "EXACT":
                return entry_val
            if entry_flag == "LOWER" and entry_val > alpha:
                alpha = entry_val
            if entry_flag == "UPPER" and entry_val < beta:
                beta = entry_val
            if alpha >= beta:
                return entry_val

        if depth == 0 or node.is_terminal():
            val = self.evaluate(node)
            Node.add_entry_in_tt(node, depth=depth, value=val, flag="EXACT")
            return val

        children = self.get_ordered_children(node)

        is_maximising = node.current_player == self.agent
        if is_maximising:
            best = -inf
            for child in children:
                val = self.alphabeta(child, alpha, beta, depth - 1)
                best = max(val, best)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
            flag = "EXACT" if alpha < beta else "LOWER"
        else:
            best = inf
            for child in children:
                val = self.alphabeta(child, alpha, beta, depth - 1)
                best = min(val, best)
                beta = min(beta, best)
                if beta <= alpha:
                    break
            flag = "EXACT" if beta > alpha else "UPPER"

        Node.add_entry_in_tt(node, depth=depth, value=best, flag=flag)
        return best

    def evaluate(self, node: Node) -> float:
        """return score for game state in agent perspective"""
        if node.is_terminal():
            if (
                node.kings[node.current_player.name].is_attacked()
                or not node.get_legal_moves()
            ):
                return (
                    inf if node.current_player != self.agent else -inf
                )  # whoever go is next loses
            return 0.0
        # material + centre control + safety
        material = centre = safety = 0.0
        opponent = node.previous_player
        opponent_attacks = node.attacks_by(opponent)
        for pc in node.board.get_pieces():
            name = pc.name.lower()
            val = self.MAP_PIECE_TO_VALUE.get(name, 0)
            material += val if pc.player == self.agent else -val

            if (pc.position.x, pc.position.y) in Search.CENTRE_SQUARES:
                bonus = (
                    Search.bonus["centre"]
                    * Search.MAP_PIECE_CENTER_TO_VALUE[pc.name.lower()]
                )
                centre += bonus if pc.player == self.agent else -bonus

            if pc.player == self.agent and pc.position in opponent_attacks:
                # piece can be captured on next turn
                safety += (
                    self.bonus["safety"] * Search.MAP_PIECE_TO_VALUE[pc.name.lower()]
                )
        # mobility
        mobility = len(node.get_legal_moves()) * Search.bonus["mobility"]
        if node.current_player != self.agent:
            mobility = -mobility
        # king safety
        king_safety = 0.0
        agent_king = node.kings[self.agent.name]
        enemy_king = node.kings[opponent.name]
        if agent_king.is_attacked():
            king_safety -= Search.bonus["king_safety"]
        if enemy_king.is_attacked():
            king_safety += Search.bonus["enemy_king_safety"]
        # score move
        move_bonus = 0.0
        if node.move:
            piece, move = node.move
            if getattr(move, "captures", None):
                net_gain = 0
                for cap_sq in move.captures:
                    captured = node.board[cap_sq].piece
                    if captured:
                        attack_val = self.MAP_PIECE_TO_VALUE.get(piece.name.lower())
                        victim_val = self.MAP_PIECE_TO_VALUE.get(captured.name.lower())
                        net_gain += victim_val - attack_val
                move_bonus += net_gain * Search.bonus["capture"]
            if piece.name.lower() == "pawn":
                if move.position.y in (0, 4):
                    move_bonus += Search.bonus["promotion"]
            if enemy_king.is_attacked():
                move_bonus += Search.bonus["check"]
            if move.position in opponent_attacks:
                move_bonus += Search.bonus["unsafe-move"]
            if node.is_defended_by(self.agent, piece.position):
                move_bonus += Search.bonus["protected"]
            # if node.current_player == self.agent:
            #     move_bonus = -move_bonus
        return material + centre + safety + mobility + king_safety + move_bonus

    def _score_child(self, child: Node) -> float:
        """aggressive evaluation for what nodes to expand first,
        agent independent evaluation"""
        if child.move is None:
            return 0
        pc, mv = child.move
        opponent = child.previous_player
        opponent_attacks = child.attacks_by(opponent)
        enemy_king = child.kings[opponent.name]

        bonus = 0
        attack_val = self.MAP_PIECE_TO_VALUE.get(pc.name.lower(), 0)
        if getattr(mv, "captures", None):
            net_gain = 0
            for cap_sq in mv.captures:
                captured = child.board[cap_sq].piece
                if captured:
                    victim_val = self.MAP_PIECE_TO_VALUE.get(captured.name.lower(), 0)
                    net_gain += victim_val - attack_val
            bonus += net_gain * Search.bonus["capture"] * 1.4
        if pc.name.lower() == "pawn":
            if mv.position.y in (0, 4):
                bonus += Search.bonus["promotion"] * 1.2
        if enemy_king.is_attacked():
            bonus += Search.bonus["check"] * 1.1
        if mv.position in opponent_attacks:
            bonus += Search.bonus["unsafe-move"] * attack_val * 1.3
        if child.is_defended_by(self.agent, pc.position):
            bonus += Search.bonus["protected"] * 1

        return bonus

    def get_ordered_children(self, node: Node) -> list[Node]:
        """return list of ordered children highest heuristic eval"""
        if not node.children:
            node.expand()
        for child in node.children:
            if child.order_score is None:
                child.order_score = self._score_child(child)
        node.children.sort(key=lambda n: n.order_score, reverse=True)
        return node.children

def agent(board, player, var):
    print(f"Ply: {var[0]}")
    ai = Search(board, player)
    piece, move_opt = ai.search(3)
    return piece, move_opt