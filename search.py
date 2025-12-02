from math import inf
from chessmaker.chess.base import Board, Piece, MoveOption, Player
from node import Node
class Search:
    """optimise for best move in game tree"""
    MAP_PIECE_TO_VALUE = {"K": 1000, "Q": 5, "R": 4, "N": 3, "B": 2, "P": 2}
    CENTER_SQUARES = [(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)]
    CENTER_BONUS = 0.2
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
        # select move that causes best score
        best_move = None
        children = self._get_sorted_children(self._root)
        for child in children:
            value = child.get_value()
            if value is not None and value == best_value:
                best_move = child.get_move()
                break
        if best_move is None and children:
            best_move = children[0].get_move()
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
        remaining_depth = self._max_depth - node.get_depth()
        # if node exists in transposition able nad has value use that value
        entry = Node.transposition_table.get(node.node_signature)
        if entry is not None:
            value = entry.get_value()
            if value is not None and entry.get_search_depth() >= remaining_depth:
                return value

        # base -> if at max depth / leaf node return current value
        if node.get_depth() >= self._max_depth or node.is_terminal():
            if node.get_value() is None:
                node.set_value(self.eval(node), 0)
            return node.get_value()

        # expand next depth of children sorted
        children = self._get_sorted_children(node)
        if not children:
            if node.get_value() is None:
                node.set_value(self.eval(node), remaining_depth)
            return node.get_value()

        # recursive step
        is_maximising = node.get_board().current_player == self._agent_player
        best: float
        if is_maximising:
            best = -inf # not found anything yet
            for child in children:
                value = self._minimax(child, alpha, beta)
                best = max(best, value)
                alpha = max(best, alpha)
                if beta <= alpha: # we have a guaranteed better move prune
                    break
            # update nodes value (and in TT) to be best value found
            node.set_value(best, remaining_depth)
        else:
            best = inf # not found anything to minimise against yet
            for child in children:
                value = self._minimax(child, alpha, beta)
                best = min(best, value)
                beta = min(best, beta)
                if beta <= alpha:
                    break
            node.set_value(best, remaining_depth)
        return best

    def eval(self, node: Node):
        """returns a float higher positive favours agent, negative favours opp"""
        value = node.get_value()
        if value in (inf, -inf): # winning / loosing leaf
            return value
        material_score = self._calculate_material_score(node)
        positional_score = self._calculate_positional_score(node)
        return material_score + positional_score


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

    def _calculate_positional_score(self, node:Node) -> float:
        """calculate bonus score for controlling centre"""
        positional_score = 0
        for piece in node.get_board().get_pieces():
            if (piece.position.x, piece.position.y) in self.CENTER_SQUARES:
                if piece.player == self._agent_player:
                    positional_score += self.CENTER_BONUS
                else:
                    positional_score -= self.CENTER_BONUS
        return positional_score

    def _get_sorted_children(self, node: Node) -> list[Node]:
        """expand node returns children sorted by heuristic score"""
        node.expand(self._max_depth)
        children = node.get_children()
        children.sort(key=self._score_move, reverse = True)
        return children

    def _score_move(self, child_node: Node) -> int:
        score = 0
        if move_info := child_node.get_move():
            _ , move_opt = move_info
            if move_opt.captures:
                score += 100
            # todo add least valuable piece highest take
        return score
