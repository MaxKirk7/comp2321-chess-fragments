from math import inf
from extension.board_utils import list_legal_moves_for, copy_piece_move
from extension.board_rules import get_result
from node import Node

class AI:
    def __init__(root_board, player):
        self._heuristic =  {K: inf, Q: 8, R: 6, N: 2, B: 3, P: 1}
        self.root = Node(board)

    def Eval():
        pass


