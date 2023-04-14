import socket

import baopig as bp

from networking import Client


class ChifoumiApp(bp.Application):

    def __init__(self):

        bp.Application.__init__(self, theme="dark", size=(700, 700))
        self.set_style_for(bp.Text, font_height=40)

        # MENU
        menu_scene = bp.Scene(self, name="menu")
        bp.Button(menu_scene, "JOUER !", sticky="center", pos=(0, "30%"), size=(600, 200),
                  command=bp.PrefilledFunction(self.open, "waiting"))
        self.ipaddr = "172.20.10.2"
        servaddr_title = bp.Text(menu_scene, "adresse IP du serveur :", pos=("50%", "10%"), loc="midtop")
        bp.Entry(menu_scene, text=self.ipaddr, width=280, entry_type=str,
                 loc="midtop", ref=servaddr_title, refloc="midbottom",
                 command=lambda text: setattr(self, "ipaddr", text))
        self.port = 5500
        port_title = bp.Text(menu_scene, "port du serveur :", pos=("50%", "30%"), loc="midtop")
        bp.Entry(menu_scene, text=str(self.port), width=280, entry_type=int,
                 loc="midtop", ref=port_title, refloc="midbottom",
                 command=lambda text: setattr(self, "port", int(text)))

        # WAITING
        wait_scene = WaitScene(self, name="waiting")
        search = bp.Text(wait_scene, "A la recherche\nd'un adversaire", sticky="center", align_mode="center")
        self.search_animayion = bp.Text(wait_scene, "", ref=search, loc="midtop", refloc="midbottom")
        self.search_animation_index = 0
        def animate_serach():
            self.search_animation_index = (self.search_animation_index + 1) % 4
            self.search_animayion.set_text("." * self.search_animation_index)
        self.search_animator = bp.RepeatingTimer(.4, animate_serach)

        # PLAYGROUND
        self.play_scene = PlayScene(self, "playground")
        def menu():
            self.play_scene.client.disconnect()
            self.open("menu")
        bp.Button(wait_scene, "MENU", command=menu)
        bp.Button(self.play_scene, "MENU", command=menu)

        # DIALOGS
        self.set_style_for(bp.DialogFrame, width="80%")
        self.end_dialog = bp.Dialog(self, title="Votre adversaire a quitté\nla partie en cours",
                                    choices=("MENU", "NOUVELLE PARTIE"), name="end_dialog")
        self.error_dialog = bp.Dialog(self, title="Une erreur est survenue", choices=("MENU",), name="error_dialog")
        def click_end_dialog(choice):
            if choice == "MENU":
                menu_scene.open()
            else:
                wait_scene.open()
        self.end_dialog.signal.ANSWERED.connect(click_end_dialog, owner=None)
        self.error_dialog.signal.ANSWERED.connect(click_end_dialog, owner=None)

    def close(self):

        if self.play_scene.client and self.play_scene.client.is_connected:
            self.play_scene.client.disconnect()


class WaitScene(bp.Scene):

    def close(self):

        self.application.search_animator.cancel()

    def open(self):

        if self.application.focused_scene is self:
            return
        play = self.application.play_scene

        try:
            play.client = Client(ip_addr=self.application.ipaddr, port=self.application.port)
        except socket.error:
            bp.LOGGER.warning(f"No server found at address {self.application.ipaddr}")
            return self.application.open("menu")

        super().open()
        play.client_id = play.client.id
        play.you_are_player.set_text(f"Vous êtes le joueur n°{play.client_id}")
        if self.application.search_animator.is_running:
            self.application.search_animator.cancel()
        self.application.search_animator.start()

    def run(self):

        if self.application.play_scene.client.send("/game_started?") == "True":
            self.application.play_scene.open()


class PlayScene(bp.Scene):

    def __init__(self, app, name):

        bp.Scene.__init__(self, app, name=name)

        self.client = None
        self.client_id = None
        self.game = None

        self.you_are_player = bp.Text(self, "", sticky="midtop")
        border_width = 5
        line = bp.Line(self, (0, 0, 0), (0, self.you_are_player.rect.bottom + border_width),
                       (self.rect.width, self.you_are_player.rect.bottom + border_width), width=border_width)
        self.result = bp.Text(self, "", sticky="center", font_height=90, visible=False)
        other_choice_title = bp.Text(self, "Votre adversaire a choisi :", pos=(0, border_width),
                                     ref=line, loc="midtop", refloc="midbottom")
        self.other_choice_text = bp.Text(self, "-", ref=other_choice_title, loc="midtop", refloc="midbottom")

        btns_zone = bp.Zone(self, width="100%", height="30%", sticky="midbottom")
        btns_zone.set_style_for(bp.Button, width="30%", height="90%")

        self.chose = False
        self.other_choice = None
        self.choice_text = bp.Text(self, "", pos=btns_zone.rect.midtop, loc="midbottom")
        class ChoiceButton(bp.Button):
            def validate(btn, *args, **kwargs):
                if self.chose:
                    return
                self.chose = True
                self.choice_text.set_text(btn.text_widget.text)
                self.choice_text.show()
                self.client.send(btn.text_widget.text)
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

        try:
            all_news = self.client.send("get_news")
            # bp.LOGGER.fine(f"RECEIVED NEWS : -{all_news}-")
            if all_news is None:
                self.application.error_dialog.set_description("Le serveur a cessé de fonctionner")
                return self.application.error_dialog.open()
            if all_news != "n":
                for news in all_news.split("|"):
                    if not news:  # always a first empty string
                        continue

                    if news == "-":  # empty answer
                        continue
                    if news == "n":  # empty answer
                        continue

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

                    elif news.startswith("quit:"):
                        if self.client.is_connected:
                            self.client.disconnect()
                        self.application.end_dialog.open()

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

                    else:
                        raise NotImplementedError(f"Unknown news : {news}")

        except Exception as e:  # game has been deleted while this client was doing stuff
            bp.LOGGER.warning(e)
            if self.client.is_connected:
                self.client.disconnect()
            self.application.error_dialog.set_description(e)
            self.application.error_dialog.open()


if __name__ == '__main__':
    ChifoumiApp().launch()
