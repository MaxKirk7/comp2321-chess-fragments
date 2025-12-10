from math import inf
from chessmaker.chess.base import Board, Player, Piece, MoveOption
from samples import black, white # players are either white or black
from node_r import Node

class Search:
    """
    logic to evaluate game states in perspective of agent to find best move
    """
    MAP_PIECE_TO_VALUE = {"king": 20, "queen":9, "right":8, "knight":4, "bishop":3, "pawn":1}
    MAP_PIECE_CENTER_TO_VALUE = {"king": -5, "queen":1, "right":2, "knight":4, "bishop":7, "pawn":8}
    CENTRE_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    # heuristics
    bonus = {
        "centre": 0.06,
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
    
    def search(self, depth=3) -> tuple[Piece, MoveOption] | tuple[None,None]:
        """return best move found up to set depth or none if no move found"""
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

    def alphabeta(self, node:Node, alpha: float, beta: float, depth) -> float:
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
    
    def evaluate(self, node: Node) -> float:
        """return score for game state in agent perspective"""
        if node.is_terminal():
            if (node.kings[node.current_player.name].is_attacked()
                or not node.get_legal_moves()):
                return (inf if node.current_player != self.agent
                        else -inf) # whoever go is next loses
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
                bonus = Search.bonus["centre"] * Search.MAP_PIECE_CENTER_TO_VALUE[pc.name.lower()]
                centre += bonus if pc.player == self.agent else -bonus

            if pc.player == self.agent and pc.position in opponent_attacks:
                # piece can be captured on next turn
                safety += (self.bonus["safety"] *
                        Search.MAP_PIECE_TO_VALUE[pc.name.lower()])
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
            if mv.position.y in (0,4):
                bonus += Search.bonus["promotion"] * 1.2
        if enemy_king.is_attacked():
            bonus += Search.bonus["check"] * 1.1
        if mv.position in opponent_attacks:
            bonus += Search.bonus["unsafe-move"] * attack_val * 1.3
        if child.is_defended_by(self.agent, pc.position):
            bonus += Search.bonus["protected"] * 1

        return bonus

    def get_ordered_children(self,node: Node) -> list[Node]:
        """return list of ordered children highest heuristic eval"""
        if not node.children:
            node.expand()
        for child in node.children:
            if child.order_score is None:
                child.order_score = self._score_child(child)
        node.children.sort(key= lambda n: n.order_score, reverse=True)
        return node.children