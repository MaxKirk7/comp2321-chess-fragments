from math import inf
from chessmaker.chess.base import Board, Piece, MoveOption, Player
from extension.board_rules import cannot_move
from node import Node


class Search:
    """optimise for best move in game tree"""

    MAP_PIECE_TO_VALUE = {"K": 100, "Q": 8, "R": 7, "N": 4, "B": 3, "P": 1}
    CENTER_SQUARES = [(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)]
    CENTER_BONUS = 0.3
    PRESSURE_BONUS = 0.5
    CAPTURE_BONUS = 0.5
    TERMINAL_SCORE = inf
    PRESEARCHED_BONUS = inf

    def __init__(
        self, root_board: Board, player_to_optimise: Player, maximum_depth: int = 3
    ):
        self._agent_player: Player = player_to_optimise
        self._max_depth: int = maximum_depth
        self._root: Node = Node(root_board)

    def start(self) -> tuple[Piece, MoveOption]:
        """find and return most optimal move"""
        # Node.transposition_table.clear()
        _ = self._minimax(self._root, self._max_depth, -inf, inf)
        best_move = None
        children = self._root.get_children()
        if children:
            best_child = max(children, key=self._get_node_score)
            best_move = best_child.get_move()
        if best_move is None:
            self._root.expand(self._max_depth)
            children = self._root.get_children()
            if children:
                best_move = children[0].get_move()
        return best_move
    
    def _get_node_score(self, node: Node) -> float:
        """helper to get score from TT"""
        entry = Node.transposition_table.get(node.node_signature)
        if entry:
            return entry["value"]
        return -inf
    
    def _minimax(self, node: Node, depth: int, alpha: float, beta: float) -> float:
        alpha_original = alpha
        # TT lookup
        entry = Node.transposition_table.get(node.node_signature)
        if entry and entry["depth"] >= depth:
            if entry["flag"] == Node.FLAG_EXACT:
                return entry["value"]
            if entry["flag"] == Node.FLAG_LOWERBOUND:
                alpha = max(alpha, entry["value"])
            elif entry["flag"] == Node.FLAG_UPPERBOUND:
                beta =  min(beta, entry["value"])
            if alpha >= beta:
                return entry["value"]
        # terminal leaf check
        if depth == 0 or node.is_terminal():
            val = self.eval(node)
            node.store_in_tt(val,depth, node.FLAG_EXACT)
            return val
        # expand and sort moves
        children = self._get_sorted_children(node)
        if not children:
            val = self.eval(node)
            node.store_in_tt(val, depth, node.FLAG_EXACT)
            return val
        # recurse
        is_maxing = node.get_board().current_player == self._agent_player
        best_val = -inf if is_maxing else inf
        for child in children:
            val = self._minimax(child, depth-1, alpha, beta)
            if is_maxing:
                best_val = max(best_val, val)
                alpha = max(alpha, best_val)
            else:
                best_val = min(best_val, val)
                beta = min(beta, best_val)
            if alpha >= beta:
                break # prune if our move is better
        # store in TT for fast lookup
        flag = Node.FLAG_EXACT
        if is_maxing and best_val <= alpha_original:
            flag = Node.FLAG_UPPERBOUND
        elif not is_maxing and best_val >= beta:
            flag = Node.FLAG_LOWERBOUND
        node.store_in_tt(best_val, depth, flag)
        return best_val
    
    def eval(self, node: Node):
        if node.is_terminal():
            board = node.get_board()
            if cannot_move(board):
                if board.current_player == self._agent_player:
                    return -self.TERMINAL_SCORE # prefer to delay loosing
                return self.TERMINAL_SCORE # prefer to win sooner
        material = self._calculate_material_score(node)
        position = self._calculate_positional_score(node)
        return material + position


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

    def _calculate_positional_score(self, node: Node) -> float:
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
        children.sort(key=self._score_move, reverse=True)
        return children

    def _score_move(self, child_node: Node) -> int:
        score = 0
        piece, move = child_node.get_move()
        tt_entry = Node.transposition_table.get(child_node.node_signature)
        if tt_entry:
            # reward searching pre-calculated sub-tree
            return self.PRESEARCHED_BONUS + tt_entry["value"]
        # MVV LVA captures
        if move.captures:
            score += self.CAPTURE_BONUS
            for pos in move.captures:
                square = child_node.get_board()[pos]
                if square and square.piece:
                    victim = square.piece
                    victim_val = self.MAP_PIECE_TO_VALUE[victim.name[0]]
                    attacker_val = self.MAP_PIECE_TO_VALUE[piece.name[0]]
                    score += victim_val - attacker_val
        score += 5
        return score
