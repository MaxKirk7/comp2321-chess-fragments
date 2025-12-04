from math import inf
from chessmaker.chess.base import Board, Piece, MoveOption, Player
from node import Node

class Search:
    MAP_PIECE_TO_VALUE = {"K": 1000, "Q": 5, "R": 4, "N": 3, "B": 2, "P": 2}
    CENTER_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    CENTER_BONUS = 0.2

    def __init__(self, root_board: Board, player: Player, maximum_depth: int):
        self._agent = player
        self._root = Node(root_board, agent=self._agent)
        self._max_depth = maximum_depth
    
    def start(self) -> tuple[Piece, MoveOption]:
        """iterative deepening up to max depth"""
        best_move = None
        best_value = -inf
        for depth in range (1, self._max_depth + 1):
            # minimax search for current depth
            value = self._minimax(self._root, -inf, inf, depth)
            for child in self._root.get_children():
                if child.get_value() == value:
                    best_move = child.get_move()
                    best_value = value
                    break
        if best_move is None:
            legal = self._root.get_legal_moves()
            best_move = legal[0]
        piece, move_opt = best_move
        return piece, move_opt
    
    def _minimax(self, node: Node, alpha: float, beta: float, depth_limit: int) -> float:
        """depth limited minimax with alpha beta"""
        # TT lookup
        entry = Node.transposition_table.get(node.node_signature)
        if entry is not None and entry.search_depth >= (depth_limit - node.get_depth()):
            return entry.get_value()
        # terminal / leaf
        if node.is_terminal() or node.get_depth() == depth_limit:
            if node.get_value() is None:
                node.set_value(self._evaluate(node), depth_limit - node.get_depth())
            return node.get_value()
        # generate / fetch sorted children
        node.expand(depth_limit)
        children = node.get_children()
        children.sort(key=self._move_score, reverse=True)
        # recurse
        maximising = node.get_board().current_player == self._agent
        if maximising:
            val = -inf
            for child in children:
                val = max(val, self._minimax(child, alpha, beta, depth_limit))
                alpha = max(val, alpha)
                if beta <= alpha:
                    break
        else:
            val = inf
            for child in children:
                val = min(val, self._minimax(child,alpha,beta, depth_limit))
                beta = min(val, beta)
                if beta <= alpha:
                    break
        node.set_value(val, depth_limit - node.get_depth())
        return val
    
    def _evaluate(self, node: Node) -> float:
        if node.get_value() in (inf, -inf):
            return node.get_value()
        mat_score = 0.0
        pos_score = 0.0
        for piece in node.get_board().get_pieces():
            val = self.MAP_PIECE_TO_VALUE[piece.name[0]]
            mat_score += val if piece.player == self._agent else -val
            if (piece.position.x, piece.position.y) in self.CENTER_SQUARES:
                pos_score += self.CENTER_BONUS if piece.player == self._agent else -self.CENTER_BONUS
        return mat_score + pos_score
    
    def _move_score(self, node: Node) -> float:
        """simple heuristic for move ordering"""
        capture_bonus = 100
        promotion_bonus = 80
        centre_bonus = 20
        score = 0
        if move_option := node.get_move():
            _, move = move_option
            if getattr(move, "captures", []):
                score += capture_bonus
            if getattr(move, "promotion_bonus", False):
                score += promotion_bonus
            if (move.position.x, move.position.y) in self.CENTER_SQUARES:
                score += centre_bonus
        return score





