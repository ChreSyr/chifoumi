

import socket
from _thread import start_new_thread
import baopig as bp
from baopig.time.timemanager import time_manager, _running_timers
console_debug = False


class Player:

    def __init__(self, ingame_id):

        self.ingame_id = ingame_id  # Can change from a game to another


class Game:

    MAX_PLAYERS_AMOUNT = None

    def __init__(self, id):

        self.id = id
        self._is_looking_for_player = True
        self._want_to_be_closed = False
        self._players = {}
        self.players_id = []
        self._news = {}

        self._connections = {}

        bp.LOGGER.info(f"Creating {self}")

    def __str__(self):

        return self.__class__.__name__ + f"(id={self.id})"

    def _add_connection(self, connection, player_id):

        assert player_id not in self._connections
        self._connections[player_id] = connection

    def _add_news(self, news):
        
        for id in self.players_id:
            self._news[id] += "|" + news

    def _close(self):

        self._want_to_be_closed = False
        for id, conn in self._connections.items():
            conn.close()
        self.handle_close()
        bp.LOGGER.info(f"Closing {self}")

    def _send_news(self, player_id):

        news = self._news[player_id]
        self._news[player_id] = "n"
        return news

    def action(self, data, player_id):
        """
        When network.send("abort"), the game receive a game.action("abort", network.player_id)
        The return of this method is the return of network.send()
        """

    def add_player(self, player):
        """Only called by Server.start_listening()"""

        assert self._is_looking_for_player
        assert player.ingame_id == len(self._players)
        assert len(self._players) < self.MAX_PLAYERS_AMOUNT
        self._players[player.ingame_id] = player
        self.players_id.append(player.ingame_id)
        self._news[player.ingame_id] = "n"

    def handle_close(self):
        """Only called by Server._threaded_client()"""

    def rem_player(self, player_id):
        """
        Only called by Server._threaded_client()
        The return of this method is the return of network.disconnect()
        """
        self._news.pop(player_id)
        self.players_id.remove(player_id)
        return self._players.pop(player_id)


class Network:
    """
    A Network is an object who establishes a discussion between a server and a client
    The client is controlling a player remotely
    The player is managed by a game
    A game is only accessible to the server
    """

    def __init__(self, ip_addr, port):

        self._client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addr = (ip_addr, port)
        self._client_id = None
        self._connect()

    is_connected = property(lambda self: self._client_id is not None)

    def _connect(self):

        if self._client_id is not None:
            raise PermissionError("This network is already connected to a server")

        self._client.connect(self.addr)
        self._client_id = int(self._client.recv(2048).decode())

    def disconnect(self):

        if self._client_id is None:
            raise PermissionError("This network is not connected to a server")

        self._client_id = None
        try:
            self.send("/SOCKET-DETACH")
            self._client.detach()
        except socket.error:
            pass

    def get_client_id(self):

        return self._client_id

    def send(self, data):

        try:
            if console_debug: print(f"SENDING DATA = -{data}-")
            self._client.send(str.encode(data))
            if console_debug: print(f"WAITING FOR DATA")
            a = self._client.recv(2048*2).decode()
            if console_debug: print(f"RECEIVED DATA 0 = -{a}-")
            return a
        except socket.error:
            # self.disconnect()
            self._client_id = None
            try:
                self._client.detach()
            except socket.error:
                pass
            return None


class Server:

    def __init__(self, port, game_class, player_class, max_connections=10):
        """
        max_connections : the number of connections wich are kept waiting if the server is busy
                          if another socket tries to connect then the connection is refused
        """

        ip_addr = socket.gethostbyname(socket.gethostname())
        self.addr = (ip_addr, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(self.addr)

        self._game_class = game_class
        self._player_class = player_class
        self._max_connections = max_connections
        self._games = {}

        self.game_looking_for_players = None

        self.time_manager = time_manager  # TODO : time_manager.update() in another thread
        bp.Timer(10000000, command=lambda: None).start()

    def _send(self, connection, data):

        connection.send(str.encode(str(data)))

    def _sendall(self, connection, data):

        connection.sendall(str.encode(str(data)))

    def _threaded_time_manager(self):

        while True:
            self.time_manager.update()

    def _threaded_client(self, conn, player_id, game_id):

        self._send(conn, player_id)  # -> network.player_id
        game = self._games[game_id]

        try:
            while True:

                if game._want_to_be_closed:
                    break

                data = conn.recv(4096).decode()
                if console_debug: print(f"RECEIVED DATA FROM {player_id} : -{data}-")
                if not data:
                    break

                if data.startswith("/"):
                    if data == "/SOCKET-DETACH":
                        self._sendall(conn, game.rem_player(player_id))
                        break
                    if data == "/game_started":
                        self._sendall(conn, not game._is_looking_for_player)
                elif game.id in self._games:
                    a = game.action(data, player_id)
                    if a == "":
                        a = "-"  # not "" because it would be considered as a disconnection
                    if console_debug: print(f"ANSWER FOR {player_id} : -{a}-")
                    self._sendall(conn, a)
                else:
                    if console_debug: print("GAME ENDED FROM OTHER PLAYER")
                    break  # the game ended

        except ConnectionResetError:  # game has been closed
            pass
        except OSError:  # game has been closed
            pass
        except Exception as e:
            print(e.__class__.__name__)
            bp.LOGGER.warning(e)

        if game is self.game_looking_for_players:
            self.game_looking_for_players = None
        if game._want_to_be_closed:
            self._games.pop(game.id)
            game._close()

    def start_listening(self):

        start_new_thread(self._threaded_time_manager, ())
        self.socket.listen(self._max_connections)
        bp.LOGGER.info(f"Waiting for a connection, Server Started : {self.addr}")

        game_id = 0
        player_id = 0

        while True:
            conn, addr = self.socket.accept()

            if self.game_looking_for_players is None:
                player_id = 0
                game_id += 1
                self.game_looking_for_players = self._games[game_id] = self._game_class(game_id)
            else:
                player_id += 1
            self.game_looking_for_players.add_player(self._player_class(player_id))

            # Create a new thread for each player, connected to the last game
            self.game_looking_for_players._add_connection(conn, player_id)
            start_new_thread(self._threaded_client, (conn, player_id, self.game_looking_for_players.id))

            bp.LOGGER.info(f"Connected {addr} to {self.game_looking_for_players}")
            if player_id == self.game_looking_for_players.MAX_PLAYERS_AMOUNT - 1:
                self.game_looking_for_players._is_looking_for_player = False
                self.game_looking_for_players = None
