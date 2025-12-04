from search import Search


def agent(board, player, var):
    piece, move_opt = None, None
    print(f"Ply: {var[0]}")
    ai = Search(board, player, maximum_depth = 4)
    piece, move_opt = ai.start()

    return piece, move_opt
