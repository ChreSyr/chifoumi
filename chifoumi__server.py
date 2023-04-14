

# import sys
# sys.path.insert(0, 'C:\\Users\\symrb\\Documents\\python\\baopig')
import socket

import baopig as bp
from networking import Server, Player, Game


class ChifoumiPlayer(Player):

    def __init__(self, client_id):

        self.client_id = client_id  # Can change from a game to another
        self.choice = None

    chose = property(lambda self: self.choice is not None)


class ChifoumiGame(Game):

    MAX_PLAYERS_AMOUNT = 2

    def __init__(self, id):

        Game.__init__(self, id)

        self.wins = [0, 0]
        self.ties = 0
        self.p1 = None
        self.p2 = None

        def newgame():
            self._add_news("newgame")
            self.reset_chose()
        self.newgame_timer = bp.Timer(3, newgame)

    def action(self, data, player_id):

        if data == "get_news":
            return self._get_news(player_id)
        if data == "get_game":
            raise PermissionError
        else:
            self.play(player_id, data)

    def both_chose(self):

        return self._players[self.players_id[0]].chose and self._players[self.players_id[1]].chose

    def handle_close(self):

        self.newgame_timer.cancel()

    def get_player(self, player_id):

        return self._players[player_id]

    def play(self, player_id, move):

        assert move in ("PIERRE", "PAPIER", "CISEAUX")
        self._players[player_id].choice = move
        self._add_news(f"choice:{player_id}:{move}")

        if self.both_chose():
            self._add_news(f"winner:{self.get_winner()}")
            self.newgame_timer.start()

    def rem_player(self, player):

        super().rem_player(player)
        self._want_to_be_closed = True

    def reset_chose(self):

        for player in self._players.values():
            player.choice = None

    def get_winner(self):

        p1 = self._players[self.players_id[0]].choice[-1]
        p2 = self._players[self.players_id[1]].choice[-1]

        if p1 == p2:  # Tie
            return -1

        winner = -1
        if p1 == "E" and p2 == "X":
            winner = 0
        elif p1 == "X" and p2 == "E":
            winner = 1
        elif p1 == "R" and p2 == "E":
            winner = 0
        elif p1 == "E" and p2 == "R":
            winner = 1
        elif p1 == "X" and p2 == "R":
            winner = 0
        elif p1 == "R" and p2 == "X":
            winner = 1
        else:
            return -1  # impossible

        return self.players_id[winner]

for i in range(5500, 5700):
    try:
        server = Server(port=i, game_class=ChifoumiGame, player_class=ChifoumiPlayer, max_connections=2)
    except socket.error:
        continue
    else:
        server.start_listening()
        break
