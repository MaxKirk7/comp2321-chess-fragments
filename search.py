from math import inf
from chessmaker.chess.base import Board, Piece, MoveOption, Player
from node import Node
class Search:
    """optimise for best move in game tree"""
    MAP_PIECE_TO_VALUE = {"K": 100, "Q": 5, "R": 4, "N": 3, "B": 2, "P": 2}
    def __init__(self, root_board: Board, player_to_optimise: Player, maximum_depth: int = 3):
        """
        Docstring for __init__
        
        :param root_board: board to begin the expansion from
        :type root_board: Board
        :param player_to_optimise: player we are maximising score for
        :param maximum_depth: maximum recurse depth -> higher is better but longer
        :type maximum_depth: int
        """
        self._agent_player : Player = player_to_optimise
        self._max_depth : int = maximum_depth
        self._root : Node = Node(root_board)

    def start(self) -> tuple[Piece, MoveOption]:
        """find and return most optimal move"""
        # find highest value move possible
        best_value = self._minimax(self._root, -inf, inf)
        # expand root and find first move that grantees best_value
        self._root.expand(self._max_depth)
        best_move = None
        for child in self._root.get_children():
            if child.get_value() >= best_value:
                best_move = child.get_move()
                break
        return best_move

    def _minimax(self, node: Node, alpha: float, beta: float) -> float:
        """
        minimax algorithm with alpha beta pruning
        
        :param node: current node
        :type node: Node
        :param alpha: best score maximiser has found
        :type alpha: float
        :param beta: best score minimiser has found
        :type beta: float
        :return: return highest guaranteed score
        :rtype: float
        """
        # if node exists in transposition able nad has value use that value
        entry = Node.transposition_table.get(node.node_signature)
        if entry is not None:
            if value := entry.get_value() is not None:
                return value
        # base -> if at max depth / leaf node return current value
        if node.get_depth() >= self._max_depth or node.is_terminal():
            if node.get_value() is None:
                node.set_value(self.eval(node))
            Node.transposition_table[node.node_signature] = node
            return node.get_value()

        # expand next depth of children
        node.expand(self._max_depth)
        if not node.has_children():
            node.set_value(self.eval(node))
            Node.transposition_table[node.node_signature] = node
            return node.get_value()

        # recursive step
        is_maximising = node.get_board().current_player == self._agent_player
        best: float
        if is_maximising:
            best = -inf # not found anything yet
            for child in node.get_children():
                value = self._minimax(child, alpha, beta)
                best = max(best, value)
                alpha = max(best, alpha)
                if beta <= alpha: # we have a guaranteed better move prune
                    break
            # update nodes value (and in TT) to be best value found
            node.set_value(best)
            Node.transposition_table[node.node_signature] = node

        else:
            best = inf # not found anything to minimise against yet
            for child in node.get_children():
                value = self._minimax(child, alpha, beta)
                best = min(best, value)
                beta = min(best, beta)
                if beta <= alpha:
                    break
            node.set_value(best)
            Node.transposition_table[node.node_signature] = node
        return best

    def eval(self, node: Node):
        """returns a float higher positive favours agent, negative favours opp"""
        if value := node.get_value() in [inf, -inf]: # winning / loosing leaf
            return value
        material_score = self._calculate_material_score(node)

        return material_score


    def _calculate_material_score(self, node: Node) -> float:
        """helper to separate logic, calculates and returns material score"""
        material_score = 0
        for piece in node.get_board().get_pieces():
            value = Search.MAP_PIECE_TO_VALUE[piece.name[0]]
            if piece.player == self._agent_player:
                material_score += value
            else:
                material_score -= value
        return material_score
