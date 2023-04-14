

import math
import socket
from _thread import start_new_thread
import baopig as bp
from baopig.time.timemanager import time_manager, _running_timers
# bp.LOGGER.cons_handler.setLevel(5)


class Player:

    def __init__(self, client_id):

        self.client_id = client_id  # Id of the client who controls this player


class Game:

    MAX_PLAYERS_AMOUNT = math.inf

    def __init__(self, id):

        self.id = id
        self._is_looking_for_player = True
        self._want_to_be_closed = False
        self._players = {}  # players by client_id
        self.players_id = []
        self._news = {}  # news by client_id

        self._connections = {}

        bp.LOGGER.info(f"Creating {self}")

    looking_for_players = property(lambda self: len(self.players_id) < self.MAX_PLAYERS_AMOUNT)

    def __str__(self):

        return self.__class__.__name__ + f"(id={self.id})"

    def _add_connection(self, connection, client_id):

        assert client_id not in self._connections
        self._connections[client_id] = connection

    def _add_news(self, news):
        
        for id in self.players_id:
            self._news[id] += "|" + news

    def _close(self):

        self._want_to_be_closed = False
        for id, conn in self._connections.items():
            conn.close()
        self.handle_close()
        bp.LOGGER.info(f"Closing {self}")

    def _get_news(self, client_id):

        news = self._news[client_id]
        self._news[client_id] = "n"
        return news

    def action(self, data, client_id):
        """
        When client.send("abort"), the game receive a game.action("abort", client.id)
        The return of this method is the return of Client.send()
        """

    def add_player(self, player):
        """Only called by Server.start_listening()"""

        assert self.looking_for_players
        self._players[player.client_id] = player
        self.players_id.append(player.client_id)
        self._news[player.client_id] = "n"

    def handle_close(self):
        """Only called by Server._threaded_client()"""

    def rem_player(self, client_id):
        """
        Only called by Server._threaded_client()
        The return of this method is the return of Client.disconnect()
        """
        self._news.pop(client_id)
        self.players_id.remove(client_id)
        self._players.pop(client_id)
        self._add_news(f"quit:{client_id}")


class Client:
    """
    A Client is an object who talks to a server
    This client is controlling a player remotely (the game is only accessible to the server)
    """

    def __init__(self, ip_addr, port):

        self._client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addr = (ip_addr, port)
        self._id = None
        self._connect()

    id = property(lambda self: self._id)
    is_connected = property(lambda self: self._id is not None)

    def _connect(self):

        if self._id is not None:
            raise PermissionError("This client is already connected to a server")

        self._client.connect(self.addr)
        self._id = int(self._client.recv(2048).decode())
        bp.LOGGER.debug(f"This client received the ID : {self._id}")

    def disconnect(self):

        if self._id is None:
            return bp.LOGGER.warning("The server closed the connection")

        self._id = None
        try:
            self.send("/SOCKET-DETACH")
            self._client.detach()
            bp.LOGGER.debug("Disconnection")
        except socket.error:
            pass

    def send(self, data):

        try:
            bp.LOGGER.fine(f"SENDING DATA = -{data}-")
            self._client.send(str.encode(data))
            a = self._client.recv(2048*2).decode()
            bp.LOGGER.fine(f"RECEIVED DATA 0 = -{a}-")
            return a
        except socket.error:
            # self.disconnect()
            self._id = None
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

    def _threaded_client(self, conn, client_id, game_id):

        self._send(conn, client_id)  # -> client.id
        game = self._games[game_id]

        try:
            while True:

                bp.LOGGER.debug(f"THREAD RUN : {client_id}")

                # if game._want_to_be_closed:
                #     break

                data = conn.recv(4096).decode()
                bp.LOGGER.fine(f"RECEIVED DATA FROM PLAYER n°{client_id} : -{data}-")
                if not data:
                    break

                if data.startswith("/"):
                    if data == "/SOCKET-DETACH":
                        game.rem_player(client_id)
                        self._sendall(conn, "-")
                        break
                    if data == "/game_started?":
                        self._sendall(conn, not game.looking_for_players)
                elif game.id in self._games:
                    a = game.action(data, client_id)
                    if a == "":
                        a = "-"  # not "" because it would be considered as a disconnection
                    bp.LOGGER.fine(f"ANSWER FOR {client_id} : -{a}-")
                    self._sendall(conn, a)
                else:
                    bp.LOGGER.debug(f"Player n°{client_id} left the game")
                    break  # the game ended

        # except ConnectionResetError:  # game has been closed
        #     pass
        # except OSError:  # game has been closed
        #     pass
        except Exception as e:
            print(e.__class__.__name__)
            bp.LOGGER.warning(e)

        # NOTE : if a player doesn't disconnect himself, is this thread going to stay forever ?
        if len(game.players_id) == 0:
            self._games.pop(game.id)
            game._close()

    def start_listening(self):

        start_new_thread(self._threaded_time_manager, ())
        self.socket.listen(self._max_connections)
        bp.LOGGER.info(f"Waiting for a connection, Server Started : {self.addr}")

        game_id = 0

        while True:
            conn, addr = self.socket.accept()
            client_id = addr[1]  # the id is the port dedicated the client

            if self.game_looking_for_players is None:
                game_id += 1
                self.game_looking_for_players = self._games[game_id] = self._game_class(game_id)
            self.game_looking_for_players.add_player(self._player_class(client_id))

            # Create a new thread for each player, connected to the last game
            self.game_looking_for_players._add_connection(conn, client_id)
            start_new_thread(self._threaded_client, (conn, client_id, self.game_looking_for_players.id))

            bp.LOGGER.info(f"Connected {addr} to {self.game_looking_for_players}")
            if not self.game_looking_for_players.looking_for_players:
                self.game_looking_for_players = None
