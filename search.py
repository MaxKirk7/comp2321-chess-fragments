from __future__ import annotations

from math import inf
from typing import Any

from chessmaker.chess.base import Board, Player, Piece, MoveOption, Position
from chessmaker.chess.pieces import King
from extension.board_rules import get_result
from samples import black, white  # players are either white or black
from node import Node
from dataclasses import dataclass
from random import getrandbits

class Search:
    """
    logic to evaluate game states in perspective of agent_player to find best move
    """
    MAP_PIECE_TO_VALUE = {"king": 20, "queen":9, "right":8, "knight":4, "bishop":3, "pawn":1}
    MAP_PIECE_CENTER_TO_VALUE = {"king": -5, "queen":1, "right":2, "knight":4, "bishop":7, "pawn":8}
    CENTRE_SQUARES = {(2, 2), (1, 2), (2, 1), (3, 2), (2, 3)}
    # heuristics
    bonus = {
        "centre": 0.02,
        "mobility" : 0.05,
        "safety": -0.45,
        "king_safety": 3,
        "enemy_king_safety": 2,
        "capture": 1.1,
        "check": 0.45,
        "checkmate": 500,
        "promotion": 2,
        "unsafe-move": -0.7,
        "protected": 0.8,
        }

    def __init__(self, root_board: Board, agent_player: Player):
        self.root = Node(root_board)
        self.agent_player = agent_player

    def search(self, depth: int = 3) -> tuple[Piece | None, MoveOption | None]:
        """return best move found up to set depth or none if no move found"""
        best_score = -inf
        best_child = None
        children = self.get_ordered_children(self.root)
        for child in children:
            score = self.alphabeta(child, -inf, inf, depth - 1)
            if score > best_score:
                best_score = score
                best_child = child
        if best_child is None:
            return None, None
        return best_child.move

    def alphabeta(self, node: Node, alpha: float, beta: float, depth: int) -> float:
        """
        attempts to return highest guaranteed score agent_player can make
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
            Node.add_entry_in_tt(node, depth=depth, value=val, flag="EXACT")
            return val

        children = self.get_ordered_children(node)

        is_maximising = node.current_player == self.agent_player
        if is_maximising:
            best = -inf
            for child in children:
                val = self.alphabeta(child, alpha, beta, depth - 1)
                best = max(val, best)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
            flag = "EXACT" if alpha < beta else "LOWER"
        else:
            best = inf
            for child in children:
                val = self.alphabeta(child, alpha, beta, depth - 1)
                best = min(val, best)
                beta = min(beta, best)
                if beta <= alpha:
                    break
            flag = "EXACT" if beta > alpha else "UPPER"

        Node.add_entry_in_tt(node, depth=depth, value=best, flag=flag)
        return best

    def evaluate(self, node: Node) -> float:
        """
        Score a position from the point‑of‑view of ``self.agent_player``.
        The new version:
        * Always rewards a capture (independent of attacker value).
        * Scales the unsafe‑move penalty with the value of the piece that is moved.
        * Checks defence on the *destination* square.
        * Adds a check‑mate bonus when the opponent king is in check and has no moves.
        """
        if node.is_terminal():
            # If the side to move has no legal moves or its king is captured,
            # the previous player just delivered the win.
            if (node.kings[node.current_player.name].is_attacked()
                or not node.get_legal_moves()):
                return (inf if node.current_player != self.agent_player
                        else -inf)      # win for the opponent of the player to move
            return 0.0                    # draw

        # --------------------------------------------------------------------
        # 2️⃣  Basic material, centre control and mobility
        # --------------------------------------------------------------------
        material = centre = safety = 0.0
        opponent = node.previous_player
        opponent_attacks = node.attacks_by(opponent)

        for pc in node.board.get_pieces():
            name = pc.name.lower()
            value = self.MAP_PIECE_TO_VALUE.get(name, 0)

            # material (+ for us, – for opponent)
            material += value if pc.player == self.agent_player else -value

            # centre control
            if (pc.position.x, pc.position.y) in Search.CENTRE_SQUARES:
                centre_bonus = (Search.bonus["centre"] *
                            Search.MAP_PIECE_CENTER_TO_VALUE[name])
                centre += centre_bonus if pc.player == self.agent_player else -centre_bonus

            # safety – penalise our pieces that are currently *threatened*
            if pc.player == self.agent_player and pc.position in opponent_attacks:
                safety += self.bonus["safety"] * value   # negative because bonus["safety"] < 0
        # mobility – number of legal moves for the side that is about to move
        mobility = len(node.get_legal_moves()) * Search.bonus["mobility"]
        mobility = mobility if node.current_player == self.agent_player else -mobility

        # --------------------------------------------------------------------
        # 3️⃣  King‑safety
        # --------------------------------------------------------------------
        king_safety = 0.0
        my_king   = node.kings[self.agent_player.name]
        opp_king  = node.kings[opponent.name]

        if my_king.is_attacked():
            king_safety -= Search.bonus["king_safety"]      # big negative penalty
        if opp_king.is_attacked():
            # If opponent king is in check AND has no escape -> check‑mate
            if not opp_king.get_move_options():
                king_safety += Search.bonus["checkmate"]
            else:
                king_safety += Search.bonus["enemy_king_safety"]

        # --------------------------------------------------------------------
        # 4️⃣  Move‑specific bonuses (only for the move that created *node*)
        # --------------------------------------------------------------------
        move_bonus = 0.0
        if node.move:
            piece, mv = node.move
            pval = self.MAP_PIECE_TO_VALUE.get(piece.name.lower(), 0)

            # -------- capture ------------------------------------------------
            if getattr(mv, "captures", None):
                # reward *any* capture; we ignore the attacker value
                capt_gain = 0
                for cap_sq in mv.captures:
                    captured = node.board[cap_sq].piece
                    if captured:
                        capt_gain += self.MAP_PIECE_TO_VALUE.get(captured.name.lower(), 0)
                move_bonus += capt_gain * Search.bonus["capture"]

            # -------- promotion -----------------------------------------------
            if piece.name.lower() == "pawn" and mv.position.y in (0, 4):
                move_bonus += Search.bonus["promotion"]

            # -------- giving check ---------------------------------------------
            if opp_king.is_attacked():
                move_bonus += Search.bonus["check"]

            # -------- stepping onto a square that is attacked ------------------
            if mv.position in opponent_attacks:
                # penalty grows with the value of the piece that is being moved
                move_bonus += Search.bonus["unsafe-move"] * pval

            # -------- moving onto a defended square -----------------------------
            if node.is_defended_by(self.agent_player, mv.position):
                move_bonus += Search.bonus["protected"]

        # --------------------------------------------------------------------
        # 5️⃣  Total score
        # --------------------------------------------------------------------
        return (material + centre + safety + mobility +
                king_safety + move_bonus)


    def evaluate2(self, node: Node) -> float:
        """return score for game state in agent_player perspective"""
        if node.is_terminal():
            if (node.kings[node.current_player.name].is_attacked()
                or not node.get_legal_moves()):
                return (inf if node.current_player != self.agent_player
                        else -inf)  # win for whoever just played move
            return 0.0
        # material + centre control + safety
        material = centre = safety = 0.0
        opponent = node.previous_player
        opponent_attacks = node.attacks_by(opponent)
        for pc in node.board.get_pieces():
            name = pc.name.lower()
            val = self.MAP_PIECE_TO_VALUE.get(name, 0)
            material += val if pc.player == self.agent_player else -val

            if (pc.position.x, pc.position.y) in Search.CENTRE_SQUARES:
                bonus = Search.bonus["centre"] * Search.MAP_PIECE_CENTER_TO_VALUE[pc.name.lower()]
                centre += bonus if pc.player == self.agent_player else -bonus

            if pc.player == self.agent_player and pc.position in opponent_attacks:
                safety += (self.bonus["safety"] *
                        Search.MAP_PIECE_TO_VALUE[pc.name.lower()])

        # mobility
        mobility = len(node.get_legal_moves()) * Search.bonus["mobility"]
        if node.current_player != self.agent_player:
            mobility = -mobility

        # king safety
        king_safety = 0.0
        agent_player_king = node.kings[self.agent_player.name]
        enemy_king = node.kings[opponent.name]
        if agent_player_king.is_attacked():
            king_safety -= Search.bonus["king_safety"]
        if enemy_king.is_attacked():
            king_safety += Search.bonus["enemy_king_safety"]

        # move bonus
        move_bonus = 0.0
        if node.move:
            piece, move = node.move
            if getattr(move, "captures", None):
                net_gain = 0
                for cap_sq in move.captures:
                    captured = node.board[cap_sq].piece
                    if captured:
                        # only care victim val if attacekd
                        if captured.position in node.attacks_by(opponent):
                            attack_val = self.MAP_PIECE_TO_VALUE.get(piece.name.lower()) 
                        else:
                            attack_val = 0   
                        victim_val = self.MAP_PIECE_TO_VALUE.get(captured.name.lower())
                        net_gain += victim_val - attack_val
                move_bonus += net_gain * Search.bonus["capture"]
            if piece.name.lower() == "pawn":
                if move.position.y in (0, 4):
                    move_bonus += Search.bonus["promotion"]
            if enemy_king.is_attacked():
                move_bonus += Search.bonus["check"]
            if move.position in opponent_attacks:
                move_bonus += Search.bonus["unsafe-move"]
            if node.is_defended_by(self.agent_player, piece.position):
                move_bonus += Search.bonus["protected"]
        return material + centre + safety + mobility + king_safety + move_bonus

    def _score_child(self, child: Node) -> float:
        """aggressive evaluation for what nodes to expand first, agent_player independent evaluation"""
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
                    if captured.position not in child.attacks_by(opponent):
                        attack_val = 0
                    victim_val = self.MAP_PIECE_TO_VALUE.get(captured.name.lower(), 0)
                    net_gain += victim_val - attack_val
            bonus += net_gain * Search.bonus["capture"] * 1.4
        if pc.name.lower() == "pawn":
            if mv.position.y in (0, 4):
                bonus += Search.bonus["promotion"] * 1.2
        if enemy_king.is_attacked():
            bonus += Search.bonus["check"] * 1.1
        if mv.position in opponent_attacks:
            bonus += Search.bonus["unsafe-move"] * attack_val * 1.3
        if child.is_defended_by(self.agent_player, pc.position):
            bonus += Search.bonus["protected"] * 1
        return bonus

    def get_ordered_children(self, node: Node) -> list[Node]:
        """return list of ordered children highest heuristic eval"""
        if not node.children:
            node.expand()
        for child in node.children:
            if child.order_score is None:
                child.order_score = self._score_child(child)
        node.children.sort(key=lambda n: n.order_score, reverse=True)
        return node.children