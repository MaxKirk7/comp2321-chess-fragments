from math import inf
from node import Node


class Search:
    """employs minimax and alpha beta on a root node to assess best move"""

    def __init__(self, root_board, player_to_optimise, maximum_depth=3):
        self._agent_player = player_to_optimise
        self.max_depth = maximum_depth
        self._root = Node(root_board)

    def start(self):
        # first find highest potential value
        best_value = self._minimax(self._root, -inf, inf)

        self._root.expand(self.max_depth)
        best_move = None
        for child in self._root.children:
            # use first move that is of equal value to highest value move
            if child.value == best_value:
                best_move = child.move
                break
        return best_move

    def _evaluate_board(self, node: Node):
        """positive score favours agent, negative favours opponent
        middle of the board / proximity to king seems most powerful in early game"""
        _map_piece_to_value = {"K": 100, "Q": 5, "R": 4, "N": 3, "B": 1, "P": 2}
        if node.value in [inf, -inf]:
            return node.value
        material_score = 0
        for piece in node.board.get_pieces():
            value = _map_piece_to_value[piece.name[0]]
            if piece.player == self._agent_player:
                material_score += value
            else:
                material_score -= value
        return material_score


    def _minimax(self, node: Node, alpha: float, beta: float) -> float:
        entry = Node.transposition_table.get(node.board_signature)
        if entry is not None and entry.value is not None:
            return entry.value

        # base -> if at maximum depth / terminal return the current value
        if node.depth >= self.max_depth or node.is_terminal():
            if node.value is None:
                node.value = self._evaluate_board(node)
            Node.transposition_table[node.board_signature] = node
            return node.value

        # expand next set of children as needed
        node.expand(self.max_depth)
        if not node.children:
            node.value = self._evaluate_board(node)
            Node.transposition_table[node.board_signature] = node
            return node.value

        # recursive step
        is_maximising_player = node.board.current_player == self._agent_player

        if is_maximising_player:
            max_eval = -inf
            for child in node.children:
                evaluation = self._minimax(child, alpha, beta)

                if evaluation is None:  # ← REQUIRED FIX
                    evaluation = self._evaluate_board(child)

                max_eval = max(max_eval, evaluation)
                alpha = max(alpha, evaluation)
                if beta <= alpha:
                    break
            node.value = max_eval

        else:  # minimising
            min_eval = inf
            for child in node.children:
                evaluation = self._minimax(child, alpha, beta)

                if evaluation is None:  # ← REQUIRED FIX
                    evaluation = self._evaluate_board(child)

                min_eval = min(min_eval, evaluation)
                beta = min(beta, evaluation)
                if beta <= alpha:
                    break
            node.value = min_eval

        Node.transposition_table[node.board_signature] = node
        return node.value
