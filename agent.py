import random
from extension.board_utils import list_legal_moves_for, take_notes
from AI import *
from node import Node


def agent(board, player, var):
    piece, move_opt = None, None
    print(f"Ply: {var[0]}")
    Node.PLAYER = player
    root = Node(board, max_depth = 2)
    if player.name == "white":
        legal = list_legal_moves_for(board, player)
        if legal:
            # Randome choice from a list of legal move from all pieces
            piece, move_opt = random.choice(legal)
    else:
        legal = list_legal_moves_for(board, player)
        if legal:
            # Randome choice from a list of legal move from all pieces
            piece, move_opt = random.choice(legal)

    return piece, move_opt

