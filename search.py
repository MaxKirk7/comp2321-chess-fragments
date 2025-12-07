from math import inf
from chessmaker.chess.base import Board, Player
from chessmaker.chess.pieces import King
from node import Node
class Search:
    MAP_PIECE_TO_VALUE = {"king": 20000, "queen":9, "right":7, "knight":4, "bishop":3, "pawn":1}
    CENTER_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    def __init__(self, root_board: Board, agent: Player):
        self.root = Node(root_board)
        self.agent = agent

    def search(self, depth=3):
        """finds and returns best move from root"""
        best_score = -inf
        best_child = None
        children = self.get_ordered_children(self.root)
        for child in children:
            score = self.alphabeta(child, -inf, inf, depth -1)
            if score > best_score:
                best_score = score
                best_child = child
        if best_child is None:
            return self.root.get_legal_moves()[0]
        return best_child.move

    def evaluate(self, node: Node) -> float:
        mat_score = 0.0
        pos_score = 0.0
        mobility_score = 0.0
        centre_bonus = 0.2
        mobility_bonus = 0.05
        if node.is_terminal():
            if node.kings[node.board.current_player.name].is_attacked() or not node.get_legal_moves():
                return inf if node.board.current_player != self.agent else - inf # win for whoever just played move
            return 0.0
        for piece in node.board.get_pieces():
            name = getattr(piece.__class__, "__name__", None) or piece.name
            val = self.MAP_PIECE_TO_VALUE.get(name.lower(), 0)
            mat_score += val if piece.player == self.agent else -val
            if (piece.position.x, piece.position.y) in self.CENTER_SQUARES:
                pos_score += centre_bonus if piece.player == self.agent else -centre_bonus
        enemy_mobility = 0
        if node.children:
            enemy_mobility = max(len(child.get_legal_moves() for child in node.children))
        mobility_score = (len(node.get_legal_moves()) - enemy_mobility) * mobility_bonus
        return mat_score + pos_score + mobility_score


    def alphabeta(self, node: Node, alpha: float, beta: float, depth) -> float:
        if depth == 0 or node.is_terminal():
            return self.evaluate(node)

        children = self.get_ordered_children(node)

        is_maximising = node.current_player == self.agent
        if is_maximising:
            best = - inf
            for child in children:
                best = max(self.alphabeta(child, alpha, beta, depth -1), best)
                alpha = max(alpha, best)
                if beta <= alpha:
                    return best
        else:
            best = inf
            for child in children:
                best = min(self.alphabeta(child, alpha, beta, depth -1), best)
                beta = min(beta, best)
                if beta <= alpha:
                    return best
        return best
    
    def _score_child(self, child_node: Node) -> float:
        capture_bonus = 0.5
        promotion_bonus = 0.45
        centre_bonus = 0.05
        check_bonus = 0.2
        score = 0
        enemy_king = child_node.kings[child_node.current_player.name]
        if child_node.move is None:
            return score
        
        piece, move = child_node.move
        if getattr(move, "captures", None):
            score += capture_bonus
        if piece.__class__.__name__.lower() == "pawn" and (
            move.position.y in (0,4)):
            score += promotion_bonus
        if (move.position.x, move.position.y) in Search.CENTER_SQUARES:
            score += centre_bonus
        if enemy_king.is_attacked():
            score += check_bonus
        return score
    
    def get_ordered_children(self, node: Node) -> list[Node]:
        if not node.children:
            node.expand()
        children = node.children[:]
        children.sort(key=self._score_child, reverse=True)
        return children