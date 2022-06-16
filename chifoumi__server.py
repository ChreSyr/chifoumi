

from networking import Server
from chifoumi__client import ChifoumiGame, ChifoumiPlayer

server = Server(port=5554, game_class=ChifoumiGame, player_class=ChifoumiPlayer, max_connections=2)
server.start_listening()
