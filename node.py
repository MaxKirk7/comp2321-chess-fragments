from extension.board_rules import get_result, cannot_move
from extension.board_utils import list_legal_moves_for, copy_piece_move, take_notes
from math import inf

def execute_move_onboard(board,piece,move):
    """creates a new board stae by cloning given board and applying move"""
    try:
        temp_board = board.clone()
        _ , temp_piece, temp_move = copy_piece_move(temp_board, piece, move)
        if temp_piece and temp_move:
            temp_piece.move(temp_move)
            return temp_board
        else:
            take_notes(f"Error, no piece or move for {piece.name} at {piece.position}")
            return None
    except AttributeError as e:
        take_notes(f"Fatal: {e}")
        return None


class Node:
    """PLAYER should be set before a node is created. to know who to optimise minimax for"""
    PLAYER = None
    _transposition_table = {} # maps board signature to nodes
    def __init__(self, board, parent=None, move=None, max_depth = 3):
        """board = current state of board
        parent = parent node
        move = move that parent made to get to this node
        children = list of child nodes
        value = evaluated value of this node
        depth = current nodes depth in tree"""
        
        self.board = board
        self.parent = [] if parent is None else [parent] #! same board state can come from many paths so possibly multiple parents
        self.move = move
        self.children = []
        self.value = 0
        self.depth = 0 if parent == None else parent.depth + 1
        self.board_signature = self._setBoardSignature()
        if self._isTerminal(): # do not continue to recurse if terminal
            if cannot_move(self.board):
                self.value = inf
            else:
                self.value = -inf
            return
        else:
            self._expand(max_depth)

    def _isTerminal(self) -> bool:
        """checks current board state is not terminal"""
        result = get_result(self.board)
        return result is not None #! if the opponent has no moves we win

    def _expand(self, max_depth):
        """expand legal moves and create children that aren't terminal"""
        #TODO sort each time in order of highest value and expand that node first if winning state stop recurse
        if self.depth >= max_depth:
            return
        
        Node._transposition_table[self._getBoardSignature()] = self

        player_to_expand = self.board.current_player

        for piece, move in list_legal_moves_for(self.board, player_to_expand):
            new_board = execute_move_onboard(self.board, piece, move)

            if new_board:
                child_signature = self._calculateSignature(new_board)
                # if child's signature already exists link and dont create new node
                if child_signature in Node._transposition_table:
                    existing_child = Node._transposition_table[child_signature]
                    if self not in existing_child.parent:
                        existing_child.parent.append(self)
                    self.children.append(existing_child)
                    continue
                child = Node(new_board, parent=self, move=move, max_depth=max_depth)
                self.children.append(child)


    def _calculateSignature(self, board):
        """calculates hashsable signature for given board"""
        parts = []
        for piece in board.get_pieces():
            sig = f"{piece.position.x}{piece.position.y}{piece.player.name[0]}{piece.name[0]}"
            parts.append(sig)
        
        parts.sort()
        parts.append(f"Turn:{board.current_player}")
        return "|".join(parts)
        
    
    def _setBoardSignature(self):
        return self._calculateSignature(self.board)
