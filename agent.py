from search import Search


def agent(board, player, var):
    piece, move_opt = None, None
    print(f"Ply: {var[0]}")
    AI = Search(board, player, maximum_depth = 2)
    piece, move_opt = AI.start()

    return piece, move_opt

