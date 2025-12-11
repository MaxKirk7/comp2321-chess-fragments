from search import Search

def agent(board , player , var ):
    """
    Wrapper required by the platform – creates a Search instance and asks for the best move.
    """
    print(f"Ply: {var[0]}")
    ai = Search(board, player)
    piece, move_opt = ai.search(4)
    return piece, move_opt
