import socket

import baopig as bp
import pygame

from networking import Player, Game, Network, console_debug


class ChifoumiPlayer(Player):

    def __init__(self, ingame_id):

        self.ingame_id = ingame_id  # Can change from a game to another
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
            return self._send_news(player_id)
        if data == "get_game":
            raise PermissionError
        else:
            self.play(player_id, data)

    def both_chose(self):

        return self._players[0].chose and self._players[1].chose

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

        p1 = self._players[0].choice[-1]
        p2 = self._players[1].choice[-1]

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

        return winner


class ChifoumiApp(bp.Application):

    def __init__(self):

        bp.Application.__init__(self, theme="dark", size=(700, 700))
        self.set_style_for(bp.Text, font_height=40)

        # MENU
        menu_scene = bp.Scene(self, name="menu")
        bp.Button(menu_scene, "JOUER !", sticky="center", size=(700, 200),
                  command=bp.PrefilledFunction(self.open, "waiting"))
        self.ipaddr = "127.0.0.1"
        servaddr_title = bp.Text(menu_scene, "adresse IP du serveur :", pos=("50%", "10%"), pos_location="top")
        bp.Entry(menu_scene, text=self.ipaddr, width=280, entry_type=str,
                 pos_location="top", pos_ref=servaddr_title, pos_ref_location="bottom",
                 command=lambda text: setattr(self, "ipaddr", text))

        # WAITING
        wait_scene = WaitScene(self, name="waiting")
        search = bp.Text(wait_scene, "A la recherche\nd'un adversaire", sticky="center", align_mode="center")
        self.search_animayion = bp.Text(wait_scene, "", pos_ref=search, pos_location="top", pos_ref_location="bottom")
        self.search_animation_index = 0
        def animate_serach():
            self.search_animation_index = (self.search_animation_index + 1) % 4
            self.search_animayion.set_text("." * self.search_animation_index)
        self.search_animator = bp.RepeatingTimer(.4, animate_serach)

        # PLAYGROUND
        self.play_scene = PlayScene(self, "playground")
        def menu():
            self.play_scene.network.disconnect()
            self.open("menu")
        bp.Button(wait_scene, "MENU", command=menu)
        bp.Button(self.play_scene, "MENU", command=menu)

        # DIALOGS
        self.set_style_for(bp.DialogFrame, width="80%")
        self.end_dialog = bp.Dialog(self, "Votre adversaire a quitté\nla partie en cours",
                                    choices=("MENU", "NOUVELLE PARTIE"), name="end_dialog")
        def click_end_dialog(choice):
            if choice == "MENU":
                menu_scene.open()
            else:
                wait_scene.open()
        self.end_dialog.signal.ANSWERED.connect(click_end_dialog)

    def close(self):

        if self.play_scene.network and self.play_scene.network.is_connected:
            self.play_scene.network.disconnect()


class WaitScene(bp.Scene):

    def close(self):

        self.app.search_animator.cancel()

    def open(self):

        play = self.app.play_scene

        try:
            play.network = Network(ip_addr=self.app.ipaddr, port=5554)
        except socket.error:
            bp.LOGGER.warning(f"No server found at address {self.app.ipaddr}")
            return self.app.open("menu")

        play.client_id = play.network.get_client_id()
        play.you_are_player.set_text(f"Vous êtes le joueur n°{play.client_id}")
        self.app.search_animator.start()

    def run(self):

        if self.app.play_scene.network.send("/game_started") == "True":
            self.app.play_scene.open()


class PlayScene(bp.Scene):

    def __init__(self, app, name):

        bp.Scene.__init__(self, app, name=name)

        self.network = None
        self.client_id = None
        self.game = None

        self.you_are_player = bp.Text(self, "", sticky="top")
        border_width = 5
        line = bp.Line(self, (0, 0, 0), (0, self.you_are_player.bottom + border_width),
                       (self.w, self.you_are_player.bottom + border_width), width=border_width)
        self.result = bp.Text(self, "", sticky="center", font_height=90, visible=False)
        other_choice_title = bp.Text(self, "Votre adversaire a choisi :", pos=(0, border_width),
                                     pos_ref=line, pos_location="top", pos_ref_location="bottom")
        self.other_choice_text = bp.Text(self, "-",
                                         pos_ref=other_choice_title, pos_location="top", pos_ref_location="bottom")

        btns_zone = bp.Zone(self, width="100%", height="30%", sticky="bottom")
        btns_zone.set_style_for(bp.Button, width="30%", height="90%")

        self.chose = False
        self.other_choice = None
        self.choice_text = bp.Text(self, "", pos=btns_zone.midtop, pos_location="bottom")
        class ChoiceButton(bp.Button):
            def validate(btn, *args, **kwargs):
                if self.chose:
                    return
                self.chose = True
                self.choice_text.set_text(btn.text_widget.text)
                self.choice_text.show()
                self.network.send(btn.text_widget.text)
        self.rock = ChoiceButton(btns_zone, "PIERRE", sticky="midleft", name="Rock")
        self.paper = ChoiceButton(btns_zone, "PAPIER", sticky="center", name="Paper")
        self.scissors = ChoiceButton(btns_zone, "CISEAUX", sticky="midright", name="Scissors")

    def close(self):

        self.chose = False
        self.other_choice = None
        self.choice_text.hide()
        self.result.hide()
        self.other_choice_text.set_text("-")

    def run(self):

        if console_debug: print("RUN")

        try:
            all_news = self.network.send("get_news")
            if console_debug: print(f"RECEIVED NEWS : -{all_news}-")
            if all_news is None:
                return self.app.end_dialog.open()
            if all_news != "n":
                for news in all_news.split("|"):
                    if not news:  # always a first empty string
                        continue
                    if console_debug: print("NEWS :", news)

                    if news == "newgame":
                        self.choice_text.hide()
                        self.result.hide()
                        self.other_choice_text.set_text("-")
                        self.chose = False
                        self.other_choice = "None"

                    elif news.startswith("choice"):
                        title, player_id, choice = news.split(":")
                        if int(player_id) != self.client_id:
                            self.other_choice = choice

                    elif news.startswith("winner:"):
                        winner = int(news[7:])
                        if winner == self.client_id:
                            text = "Gagné !"
                        elif winner == -1:
                            text = "Egalité !"
                        else:
                            text = "Perdu..."
                        self.result.set_text(text)
                        self.result.show()
                        self.other_choice_text.set_text(self.other_choice)

        except Exception as e:  # game has been deleted while this client was doing stuff
            bp.LOGGER.warning(e)
            if self.network.is_connected:
                self.network.disconnect()
            self.app.end_dialog.open()


if __name__ == '__main__':
    ChifoumiApp().launch()
