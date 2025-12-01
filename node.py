from math import inf
from extension.board_rules import get_result, cannot_move
from extension.board_utils import list_legal_moves_for, copy_piece_move, take_notes

def execute_move_onboard(board,piece,move):
    """creates a new board state by cloning given board and applying move"""
    try:
        temp_board = board.clone()
        _ , temp_piece, temp_move = copy_piece_move(temp_board, piece, move)
        if temp_piece and temp_move:
            temp_piece.move(temp_move)
            try:
                next(temp_board.turn_iterator)
            except StopIteration:
                take_notes("failed to iterate to next player")
            return temp_board
        take_notes(f"Error, no piece or move for {piece.name} at {piece.position}")
        return None
    except AttributeError as e:
        take_notes(f"Fatal: {e}")
        return None


class Node:
    """PLAYER should be set before a node is created. to know who to optimise minimax for"""
    PLAYER = None
    _transposition_table = {} # maps board signature to nodes
    dupes = 0
    nodes = 0
    def __init__(self, board, parent=None, move=None, max_depth = 3):
        """board = current state of board
        parent = parent node
        move = move that parent made to get to this node
        children = list of child nodes
        value = evaluated value of this node
        depth = current nodes depth in tree"""
        Node.nodes += 1
        self.board = board
        # same board state can come from many paths so possibly multiple parents
        self.parent = [] if parent is None else [parent]
        self.move = move
        self.children = []
        self.value = 0
        self.depth = 0 if parent is None else parent.depth + 1
        self.board_signature = self._set_board_signature()
        if self.board_signature not in Node._transposition_table:
            Node._transposition_table[self.board_signature] = self

        if self._is_terminal(): # do not continue to recurse if terminal
            if cannot_move(self.board):
                self.value = inf # winning move
            else:
                self.value = -inf # loosing move
            return
        self._expand(max_depth)

    def _is_terminal(self) -> bool:
        """checks current board state is not terminal"""
        result = get_result(self.board)
        return result is not None

    def _expand(self, max_depth):
        """expand legal moves and create children that aren't terminal"""
        #TODO sort each time in order of highest value and expand that node first if winning state stop recurse
        if self.depth >= max_depth:
            return
        Node._transposition_table[self.board_signature] = self

        player_to_expand = self.board.current_player
        # take_notes(f"D:{self.depth} found {len(list_legal_moves_for(self.board, player_to_expand))} for {player_to_expand.name}")
        for piece, move in list_legal_moves_for(self.board, player_to_expand):
            new_board = execute_move_onboard(self.board, piece, move)

            if new_board:
                child_signature = self._calculate_signature(new_board)
                # if child's signature already exists link and dont create new node
                if child_signature in Node._transposition_table:
                    existing_child = Node._transposition_table[child_signature]
                    if self not in existing_child.parent:
                        existing_child.parent.append(self)
                    self.children.append(existing_child)
                    # take_notes(f"D{self.depth} Linked existing child (D{existing_child.depth}) via transposition.")
                    Node.dupes += 1
                    continue
                child = Node(new_board, parent=self, move=move, max_depth=max_depth)
                self.children.append(child)
        # take_notes(f"--- EXPANSION COMPLETE D{self.depth}. Total children: {len(self.children)} ---")

    def _calculate_signature(self, board):
        #! there are not any repeated states up to at least depth 3
        """calculates hashable signature for given board"""
        def get_piece_letter(piece):
            """returns upper case for black lower case for white"""
            base = piece.name[0].upper()
            return base.lower() if piece.player.name == "white" else base
        parts = []
        for piece in board.get_pieces():
            sig = f"{piece.position.x}{piece.position.y}{get_piece_letter(piece)}"
            parts.append(sig)
        parts.sort()
        parts.append(f"Turn:{board.current_player.name[0]}")
        return "|".join(parts)

    def _set_board_signature(self):
        return self._calculate_signature(self.board)
