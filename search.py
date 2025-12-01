from math import inf

from node import Node


class Search:
    """employs minimax and alpha beta on a root node to assess best move"""
    def __init__(self, root_board, player_to_optimise):
        self._agent_player = player_to_optimise
        self._root = Node(root_board)

    def start(self):
        pass

    def _evaluate_board(self, node: Node):
        """positive score favours agent, negative favours opponent
        middle of the board / proximity to king seems most powerful in early game"""
        # king, queen, right (rook + knight), knight, bishop, pawn
        _map_piece_to_value = {'K': 100, 'Q': 5, 'R': 4, 'N': 3, 'B': 1, 'P':2}
        # don't calculate if winning / loosing board state
        if node.value in [inf, -inf]:
            return node.value
        material_score = 0
        for piece in node.board.get_pieces():
            value = _map_piece_to_value[piece.name[0]]
            if piece.player == self._agent_player:
                material_score += value
            else:
                material_score -= value
        # TODO add positional factors / controlling board factors
        return material_score

    def _minimax(self):
        pass


