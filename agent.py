from search import Search


def agent(board, player, var):
    print(f"Ply: {var[0]}")
    ai = Search(board, player)
    piece, move_opt = ai.search(2)
    return piece, move_opt