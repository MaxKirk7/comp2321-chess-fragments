from search import Search


def agent(board, player, var):
    print(f"Ply: {var[0]}")
    ai = Search(board, player, maximum_depth=100)
    piece, move_opt = ai.start()
    return piece, move_opt