from math import inf
from chessmaker.chess.base import Board, Player, Piece, MoveOption
from samples import black, white
from node import Node
class Search:
    MAP_PIECE_TO_VALUE = {"king": 20, "queen":9, "right":7, "knight":4, "bishop":3, "pawn":1}
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
            return None, None
        return best_child.move

    def evaluate(self, node: Node) -> float:
        """evaluate the position for agent"""
        centre_bonus = 0.05
        if node.is_terminal():
            if (node.kings[node.board.current_player.name].is_attacked()
                or not node.get_legal_moves()):
                return (inf if node.board.current_player != self.agent
                        else - inf) # win for whoever just played move
            return 0.0
        # material + centre control + safety
        material = centre = safety = 0.0
        opponent = white if node.board.current_player == black else black
        opponent_attacks = node.attacks_by(opponent)
        for pc in node.board.get_pieces():
            name = pc.name.lower()
            val = self.MAP_PIECE_TO_VALUE.get(name, 0)
            material += val if pc.player == self.agent else -val

            if (pc.position.x, pc.position.y) in self.CENTER_SQUARES:
                centre += centre_bonus if pc.player == self.agent else -centre_bonus
            if pc.player == self.agent and pc.position in opponent_attacks:
                safety -= 0.30 # piece can be captured on next turn
        # mobility
        mobility = len(node.get_legal_moves()) * 0.05
        if node.current_player != self.agent:
            mobility = -mobility
        # king safety
        king_safety = 0.0
        agent_king = node.kings[self.agent.name]
        enemy_king = node.kings[opponent.name]
        if agent_king.is_attacked():
            king_safety -= 2
        if enemy_king.is_attacked():
            king_safety += 1.5
        return material + centre + safety + mobility + king_safety


    def alphabeta(self, node: Node, alpha: float, beta: float, depth) -> float:
        entry_depth, entry_val, entry_flag = Node.get_entry_in_tt(node.hash)
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
            Node.add_entry_in_tt(node, depth= depth, value=val, flag = "EXACT")
            return val

        children = self.get_ordered_children(node)

        is_maximising = node.current_player == self.agent
        if is_maximising:
            best = - inf
            for child in children:
                val = self.alphabeta(child, alpha, beta, depth -1)
                best = max(val, best)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
            flag = "EXACT" if alpha < beta else "LOWER"
        else:
            best = inf
            for child in children:
                val = self.alphabeta(child, alpha, beta, depth -1)
                best = min(val, best)
                beta = min(beta, best)
                if beta <= alpha:
                    break
            flag = "EXACT" if beta > alpha else "UPPER"

        Node.add_entry_in_tt(node, depth=depth, value=best, flag=flag)
        return best

    def _score_child(self, child_node: Node) -> float:
        capture_bonus = 0.8
        promotion_bonus = 0.7
        centre_bonus = 0.1
        check_bonus = 0.4
        unsafe_piece_penalty = -0.5
        score = 0
        if child_node.move is None:
            return score

        opponent = white if self.agent == black else black
        enemy_king = child_node.kings[opponent.name]

        piece, move = child_node.move
        if getattr(move, "captures", None):
            for cap_sqr in move.captures:
                captured = child_node.board[cap_sqr].piece
                if captured:
                    attacker_value = Search.MAP_PIECE_TO_VALUE.get(
                        piece.__class__.__name__.lower(), 1
                    )
                    victim_value = Search.MAP_PIECE_TO_VALUE.get(
                        captured.__class__.__name__.lower(), 1)
                    score += (victim_value - attacker_value) * capture_bonus
        if piece.__class__.__name__.lower() == "pawn" and (
            move.position.y in (0,4)):
            score += promotion_bonus
        if (move.position.x, move.position.y) in Search.CENTER_SQUARES:
            score += centre_bonus
        if enemy_king.is_attacked():
            score += check_bonus

        if move.position in child_node.attacks_by(opponent):
            score += unsafe_piece_penalty
        return score

    def get_ordered_children(self, node: Node) -> list[Node]:
        if not node.children:
            node.expand()
        for child in node.children:
            if child.order_score is None:
                child.order_score = self._score_child(child)
        node.children.sort(key=lambda n: n.order_score, reverse=True)
        return node.children
