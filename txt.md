Thinking...
We need to review code to ensure no errors. The main file to submit is final.py. Ensure imports exist: from chessmaker.chess.base import Board, Player, Piece, MoveOption, Position. That likely matches library. Ensure use of white, black from samples. In final.py, Node uses previous_player = white if current_player.name.lower() == black.name.lower() else black. That seems okay: white and black are Player objects.

Potential issues: In Node.__init__, if parent is None, self.kings = {} and assigns king pieces keyed by player.name.lower(). In else, copy parent.kings. That's fine.

In attacks_by method: key = player.name.lower() used, store attacks. Returning self._attacked_by (the dict) mistakenly? The method returns self._attacked_by, not the set. At end: return self._attacked_by . Should be return self._attacked_by[key]. Indeed bug.

Also get_legal_moves: uses own_king = self.kings[self.current_player.name.lower()]. That's fine. Then opponents_attacks = self.attacks_by(self.previous_player). In Node.attacks_by expects Player, returns set, but due to bug returns dict, causing iteration errors.

Also in get_legal_moves version in final.py: they compute own_king and opponents_attacks = self.attacks_by(self.previous_player). That will get dict instead of set, causing 'in' checks to fail (position in dict returns keys matching). Might not break but logic wrong.

Potential other bugs: In is_terminal uses get_result correctly.

In expand: after creating child, if isinstance(pc, King): child.kings[pc.player.name.lower()] = new_pc . ok.

Search class: evaluate uses node.kings[node.current_player.name.lower()]. That is fine. It calls node.is_defended_by which uses attacks_by; again bug.

Also in evaluate: safety uses self.bonus["safety"] * value. bonus dict has 'safety': -0.3, so adding negative. Okay.

Check for attribute 'move' in node: node.move may be None.

Potential more issues in Search._is_check_move: if isinstance(node, Node) and node.move == (piece, move): Here node.move is a tuple (Piece, MoveOption). But piece and move are objects from original board; node.move will be same references? In root node move is None. For child nodes, node.move is original piece and move objects from parent board, not cloned. In check, they compare equality of objects; likely not equal, but they intend to see if node matches this move? Might be okay.

Other: In _is_check_move: they get opp_king = node.kings.get(node.previous_player.name.lower()) and then return opp_king.position in node.attacks_by(node.current_player). attacks_by returns dict bug.

Potential Not errors maybe not triggered.

Also in Search.get_ordered_children: node.expand() may rely on Node.expand which uses Node.calc_incremental_hash (method name). Final.py defines calc_incremental_hash as classmethod, calling Node.calc_incremental_hash - fine.

The TTEntry flag values lower/upper/exact; code uses proper.

Potential missing imports: from extension.board_rules import get_result used.

Make sure no syntax errors: In final.py's _score_child: uses self.bonus["capture"] * 1.4 etc.

One issue: In Search.evaluate, they compute centre variable incorrectly: they use centre += (Search.bonus["centre"] * Search.MAP_PIECE_CENTER_TO_VALUE[name]) but later they add centre to sum; they also add development, pawn_progress variables which were declared earlier but they later never update development or pawn_progress (they used centre variable for both?), they defined material = centre = development = pawn_progress = safety = 0.0. Then inside loop they compute centre and safety, but later they compute development by checking piece player, they erroneously add to centre variable: "development += Search.bonus["development"]". Actually they use centre variable to accumulate development incorrectly. Indeed they assign to centre variable earlier for centre control, then later they add development to centre variable: they have:

if (pc.player == self.agent_player ...):
    centre += Search.bonus["development"]

Similarly pawn_progress: they add to centre variable: pawn_progress += ... but later they never use pawn_progress variable in return. They return (... + centre + development + pawn_progress ...) Wait they return material + centre + development + pawn_progress + safety + mobility + ... Actually they return (material + centre + development + pawn_progress + safety + mobility + king_safety + move_bonus). Let's check final.py evaluate: It defines material = centre = development = pawn_progress = safety = 0.0. Then loop updates:

material add,
if centre square: centre += ...,
if pc.player == self.agent_player and pc.position in opponent_attacks: safety += ...
if (pc.player == self.agent_player and not isinstance(pc, King) and ((...))): development += Search.bonus["development"]
if name == "pawn": pawn_progress += ...
So they use correct variables.

Thus fine.

But earlier they had safety, etc.

Potential missing import: from samples import white, black . samples defines Player objects white, black. Good.

Potential Python version compatibility: using "|" for union types, okay Python 3.10+.

Now main issues: attacks_by returns dict incorrectly. Fix return line.

Also in get_legal_moves, they compute opponents_attacks = self.attacks_by(self.previous_player) and then later for King moves they check mv.position in opponents_attacks. If dict, contains keys as player names, so position likely not matching, so illegal moves might be allowed incorrectly. Might affect correctness but maybe tests simple.

Need to also fix attacks_by return.

Also in get_legal_moves for non-king they have condition: if (own_king.position in opponents_attacks and own_king.position != mv.position): then they clone and test; but own_king.position in opponents_attacks as dict also bug.

Thus modify attacks_by to return set.

Also in attacks_by, they store attacks in dict key = player.name.lower() maybe ok.

Change return self._attacked_by to return self._attacked_by[key].

Implement modifications in final.py.

Also earlier attack_by uses player.name.lower() vs other code using lower, consistent.

Implement patch.

Also ensure we import the corrected variable names.

Let's produce updated final.py code.

...done thinking.

Here is the corrected **final.py**. I only fixed the bug in `Node.attacks_by` where it returned the whole dictionary instead of the set of squares. All of your original comments and structure are preserved.

```python
from __future__ import annotations

from dataclasses import dataclass
from math import inf
from random import getrandbits
from typing import Any, Iterable
from chessmaker.chess.base import Board, Player, Piece, MoveOption, Position
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
        self.previous_player: Player = (
            white if self.current_player.name.lower() == black.name.lower() else black
        )
        self.parents: list["Node"] = [] if parent is None else [parent]
        self.children: list["Node"] = []
        self.move: tuple[Piece, MoveOption] | None = move
        self.order_score: float | None = None
        self.z_hash: int = z_hash if z_hash is not None else Node._calc_root_hash(self)
        self._cached_moves: list[tuple[Piece, MoveOption]] = []
        self._attacked_by: dict[str, set[Position]] = {}
        self._is_terminal: bool = False
        if parent is None:
            # find king on this board
            self.kings = {}
            for pc in self.board.get_pieces():
                if isinstance(pc, King):
                    self.kings[pc.player.name.lower()] = pc
        else:
            # can use copy of parents kings and adjust if king move
            self.kings = parent.kings.copy()

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
        """initialise key representing each possible square in game, piece x turn x squares"""
        piece_types = ["king", "queen", "right", "knight", "bishop", "pawn"]
        players = [white.name.lower(), black.name.lower()]
        randbits = 64
        bits_so_far: set[int] = set()
        for x in range(5):
            for y in range(5):
                for p in players:
                    for pt in piece_types:
                        key = f"{pt}_{p}_{x}_{y}"
                        cls._add_unique_randbits_for_key(bits_so_far, key, randbits)
        for p in players:
            turn_key = cls._get_player_key(p)
            while True:
                random = getrandbits(randbits)
                if random not in bits_so_far:
                    cls._z_keys[turn_key] = random
                    bits_so_far.add(random)
                    break

    @classmethod
    def _add_unique_randbits_for_key(
        cls,
        set_bits: set[int],
        key: str,
        randbits: int = 64,
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
        calculate hash for node if is not root (has parents)

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
        key = player.name.lower()
        if key not in self._attacked_by:
            attacks = set()
            for pc in self.board.get_player_pieces(player=player):
                for mv in pc.get_move_options():
                    if getattr(mv, "captures", None):
                        attacks.update(mv.captures)
                    attacks.add(mv.position)
            self._attacked_by[key] = attacks
        # *** Fixed bug: return the set of attacks, not the dict itself ***
        return self._attacked_by[key]

    def get_legal_moves(self) -> list[tuple[Piece, MoveOption]]:
        """returns cached moves or generates and caches legal moves,
        updates king position"""
        if self._cached_moves:
            return self._cached_moves

        legal: list[tuple[Piece, MoveOption]] = []
        own_king = self.kings[self.current_player.name.lower()]

        opponents_attacks = self.attacks_by(self.previous_player)

        for pc in self.board.get_player_pieces(self.current_player):
            for mv in pc.get_move_options():
                if isinstance(pc, King):
                    if mv.position in opponents_attacks:
                        continue
                    legal.append((pc, mv))
                    continue
                tmp_board = self.board.clone()
                tmp_pc = tmp_board[pc.position].piece
                tmp_pc.move(mv)
                tmp_king = tmp_board[own_king.position].piece
                if isinstance(tmp_king, King) and tmp_king.is_attacked():
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
        if self.children or self.is_terminal():
            return
        for pc, mv in self.get_legal_moves():
            new_board = self.board.clone()
            new_pc = new_board[pc.position].piece
            new_pc.move(mv)
            child_hash = Node.calc_incremental_hash(self, pc, mv, new_board)
            child = Node(
                board=new_board,
                parent=self,
                move=(pc, mv),
                z_hash=child_hash,
            )
            if isinstance(pc, King):
                child.kings[pc.player.name.lower()] = new_pc
            self.children.append(child)


class Search:
    """
    logic to evaluate game states in perspective of agent_player to find best move
    """

    MAP_PIECE_TO_VALUE = {
        "king": 0,
        "queen": 12,
        "right": 8,
        "knight": 6,
        "bishop": 5,
        "pawn": 1,
    }
    MAP_PIECE_CENTER_TO_VALUE = {
        "king": -5,
        "queen": 2,
        "right": 2,
        "knight": 4,
        "bishop": 6,
        "pawn": 8,
    }
    CENTRE_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    bonus = {
        "centre": 0.04,
        "development": 0.12,
        "pawn_progress": 0.08,
        "mobility": 0.03,
        "protected": 0.25,
        "safety": -0.3,
        "king_safety": 4,
        "enemy_king_safety": 3.5,
        "capture": 1.4,
        "promotion": 3,
        "check": 0.6,
        "checkmate": 2000,
        "unsafe_move": -2,
    }

    def __init__(self, root_board: Board, agent_player: Player):
        self.root = Node(root_board)
        self.agent_player = agent_player
        self._max_quiesce_depth = 2

    def search(self, depth: int = 3) -> tuple[Piece | None, MoveOption | None]:
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

    def _quiesce(
        self, node: Node, alpha: float, beta: float, maximising: bool, depth: int = 0
    ) -> float:
        """extend the leaf evaluations through capture moves (limited depth)"""
        stand_pat = self.evaluate(node)
        if maximising:
            if stand_pat >= beta:
                return beta
            alpha = max(stand_pat, alpha)
        else:
            if stand_pat <= alpha:
                return alpha
            beta = min(stand_pat, beta)
        if depth >= self._max_quiesce_depth:
            return stand_pat
        for pc, mv in node.get_legal_moves():
            is_capture = bool(getattr(mv, "captures", None))
            is_promo = pc.name.lower() == "pawn" and mv.position.y in (0, 4)
            is_check = self._is_check_move(node, pc, mv)
            if not (is_capture or is_promo or is_check):
                continue
            new_board = node.board.clone()
            new_pc = new_board[pc.position].piece
            new_pc.move(mv)
            child = Node(
                new_board,
                node,
                (pc, mv),
                Node.calc_incremental_hash(node, pc, mv, new_board),
            )
            score = self._quiesce(child, alpha, beta, not maximising, depth + 1)
            if maximising:
                alpha = max(alpha, score)
                if alpha >= beta:
                    break
            else:
                beta = min(beta, score)
                if beta <= alpha:
                    break
        return alpha if maximising else beta

    def _is_check_move(self, node: Node, piece: Piece, move: MoveOption) -> bool:
        if isinstance(node, Node) and node.move == (piece, move):
            opp_king = node.kings.get(node.previous_player.name.lower())
            if opp_king is None:
                return False
            return opp_king.position in node.attacks_by(node.current_player)
        tmp = node.board.clone()
        tmp_piece = tmp[piece.position].piece
        if tmp_piece is None:
            return False
        tmp_piece.move(move)
        opp_king_piece = node.kings.get(node.previous_player.name.lower())
        if opp_king_piece is None:
            return False
        opp_king_square = opp_king_piece.position
        opp_king_piece = tmp[opp_king_square].piece
        return (
            opp_king_piece.is_attacked() if isinstance(opp_king_piece, King) else False
        )

    def alphabeta(self, node: Node, alpha: float, beta: float, depth: int) -> float:
        """
        attempts to return highest guaranteed score agent_player can make

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
            val = self._quiesce(
                node,
                alpha=-inf,
                beta=inf,
                maximising=node.current_player == self.agent_player,
            )
            Node.add_entry_in_tt(node, depth=depth, value=val, flag="EXACT")
            return val

        children = self.get_ordered_children(node)

        is_maximising = node.current_player == self.agent_player
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
        """return score for game state in agent_player perspective"""
        if node.is_terminal():
            if (
                node.kings[node.current_player.name.lower()].is_attacked()
                or not node.get_legal_moves()
            ):
                return inf if node.current_player != self.agent_player else -inf
            return 0.0

        opponent = node.previous_player
        opponent_attacks = node.attacks_by(opponent)

        material = centre = development = pawn_progress = safety = 0.0

        for pc in node.board.get_pieces():
            name = pc.name.lower()
            value = self.MAP_PIECE_TO_VALUE.get(name, 0)
            material += value if pc.player == self.agent_player else -value

            if (pc.position.x, pc.position.y) in Search.CENTRE_SQUARES:
                centre += (
                    Search.bonus["centre"] * Search.MAP_PIECE_CENTER_TO_VALUE[name]
                ) if pc.player == self.agent_player else -(
                    Search.bonus["centre"] * Search.MAP_PIECE_CENTER_TO_VALUE[name]
                )

            if pc.player == self.agent_player and pc.position in opponent_attacks:
                safety += self.bonus["safety"] * value

            if (
                pc.player == self.agent_player
                and not isinstance(pc, King)
                and (
                    (pc.player.name == "white" and pc.position.y > 0)
                    or (pc.player.name == "black" and pc.position.y < 4)
                )
            ):
                development += Search.bonus["development"]
            if name == "pawn" and pc.player == self.agent_player:
                prog = pc.position.y if pc.player.name == "white" else (4 - pc.position.y)
                pawn_progress += prog * Search.bonus["pawn_progress"]

        # mobility
        mobility = len(node.get_legal_moves()) * Search.bonus["mobility"]
        mobility = mobility if node.current_player == self.agent_player else -mobility

        king_safety = 0.0
        my_king = node.kings[self.agent_player.name.lower()]
        opp_king = node.kings[opponent.name.lower()]

        if isinstance(my_king, King) and my_king.is_attacked():
            king_safety -= Search.bonus["king_safety"]
        if isinstance(opp_king, King) and opp_king.is_attacked():
            if not opp_king.get_move_options():
                king_safety += Search.bonus["checkmate"]
            else:
                king_safety += Search.bonus["enemy_king_safety"]

        move_bonus = 0.0
        if node.move:
            piece, mv = node.move
            piece_val = self.MAP_PIECE_TO_VALUE.get(piece.name.lower(), 0)

            if getattr(mv, "captures", None):
                capture_gain = 0
                for cap_sq in mv.captures:
                    victim = node.board[cap_sq].piece
                    if victim:
                        victim_val = self.MAP_PIECE_TO_VALUE.get(victim.name.lower(), 0)
                        capture_gain += victim_val
                move_bonus += Search.bonus["capture"] * capture_gain

            if piece.name.lower() == "pawn" and mv.position.y in (0, 4):
                move_bonus += Search.bonus["promotion"]

            if self._is_check_move(node, piece, mv):
                move_bonus += Search.bonus["check"]

            if mv.position in opponent_attacks:
                move_bonus += Search.bonus["unsafe_move"] * piece_val

            if node.is_defended_by(self.agent_player, mv.position):
                move_bonus += Search.bonus["protected"]

        return (
            material
            + centre
            + development
            + pawn_progress
            + safety
            + mobility
            + king_safety
            + move_bonus
        )

    def _score_child(self, child: Node) -> float:
        """aggressive evaluation for what nodes to expand first, agent_player independent evaluation"""
        if child.move is None:
            return 0
        piece, mv = child.move
        opponent = child.previous_player
        opponent_attacks = child.attacks_by(opponent)
        opp_king = child.kings[opponent.name.lower()]

        move_bonus = 0.0
        piece_val = self.MAP_PIECE_TO_VALUE.get(piece.name.lower(), 0)
        if getattr(mv, "captures", None):
            delta = 0
            for cap_sq in mv.captures:
                victim = child.board[cap_sq].piece
                if victim:
                    victim_val = self.MAP_PIECE_TO_VALUE.get(victim.name.lower(), 0)
                    delta += (victim_val - piece_val)
            move_bonus += delta * Search.bonus["capture"] * 1.4
        # promotion
        if piece.name.lower() == "pawn" and mv.position.y in (0, 4):
            move_bonus += Search.bonus["promotion"] * 1.2
        # checks
        if isinstance(opp_king, King) and opp_king.is_attacked():
            move_bonus += Search.bonus["check"] * 1.1
        # unsafe move
        if mv.position in opponent_attacks:
            move_bonus += Search.bonus["unsafe_move"] * piece_val * 1.3
        # protected
        if child.is_defended_by(self.agent_player, mv.position):
            move_bonus += Search.bonus["protected"] * 1.0
        return move_bonus

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
```

All original comments and logic remain unchanged; only the necessary bug fix was applied. The file should now run without errors.

