from math import inf
from chessmaker.chess.base import Board, Player, Piece, MoveOption
from samples import black, white # players are either white or black
from node import Node
class Search:
    MAP_PIECE_TO_VALUE = {"king": 20, "queen":9, "right":8, "knight":4, "bishop":3, "pawn":1}
    CENTER_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    bonus = {
        "center": 0.06,
        "mobility" : 0.05,
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
                centre += Search.bonus["center"] if pc.player == self.agent else -Search.bonus["center"]
            if pc.player == self.agent and pc.position in opponent_attacks:
                safety += self.bonus["safety"] * Search.MAP_PIECE_TO_VALUE[pc.name.lower()] # piece can be captured on next turn
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

        move_bonus = 0.0
        if node.move:
            piece,move = node.move
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
                if move.position.y in (0,4):
                    move_bonus += Search.bonus["promotion"]
            if enemy_king.is_attacked():
                move_bonus += Search.bonus["check"]
            if move.position in opponent_attacks:
                move_bonus += Search.bonus["unsafe-move"]
            if node.is_defended_by(self.agent, piece.position):
                move_bonus += Search.bonus["protected"]

        return material + centre + safety + mobility + king_safety + move_bonus


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

    def _score_child(self, child: Node) -> float:
        """mirrors evaluate but more aggresive"""
        if child.move is None:
            return 0

        piece, move = child.move
        opponent = white if self.agent == black else black
        opponent_attacks = child.attacks_by(opponent)
        enemy_king = child.kings[opponent.name]
        base = self.evaluate(child) - (Search.bonus["check"] if opponent_attacks else 0)
        move_bonus = 0
        attack_val = self.MAP_PIECE_TO_VALUE.get(piece.name.lower())

        if getattr(move, "captures", None):
            net_gain = 0
            for cap_sq in move.captures:
                captured = child.board[cap_sq].piece
                if captured:
                    victim_val = self.MAP_PIECE_TO_VALUE.get(captured.name.lower())
                    net_gain += victim_val - attack_val
            move_bonus += net_gain * Search.bonus["capture"] * 1.4
        if piece.name.lower() == "pawn":
            if move.position.y in (0,4):
                move_bonus += Search.bonus["promotion"] * 1.2
        if enemy_king.is_attacked():
            move_bonus += Search.bonus["check"] * 1.1
        if move.position in opponent_attacks:
            move_bonus += Search.bonus["unsafe-move"] * attack_val * 1.3
        if child.is_defended_by(self.agent, piece.position):
            move_bonus += self.bonus["protected"] * 1
        return base + move_bonus

    def get_ordered_children(self, node: Node) -> list[Node]:
        if not node.children:
            node.expand()
        for child in node.children:
            if child.order_score is None:
                child.order_score = self._score_child(child)
        node.children.sort(key=lambda n: n.order_score, reverse=True)
        return node.children
