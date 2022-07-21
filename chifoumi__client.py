

# import sys
# sys.path.insert(0, 'C:\\Users\\symrb\\Documents\\python\\baopig')
import baopig as bp

import socket
from networking import Network, console_debug


class ChifumiScene(bp.Scene):

    def __init__(self, *args, **kwargs):

        bp.Scene.__init__(self, *args, **kwargs)




class ChifoumiApp(bp.Application):

    def __init__(self):

        bp.Application.__init__(self, theme="dark", size=(700, 700))
        self.set_style_for(bp.Text, font_height=40)

        # SCENES
        menu_scene = bp.Scene(self, name="menu")
        wait_scene = WaitScene(self, name="waiting")
        self.play_scene = PlayScene(self, "playground")

        # MENU
        bp.Button(menu_scene, "JOUER !", sticky="center", size=(700, 200), command=wait_scene.open)
        self.ipaddr = "127.0.0.1"
        servaddr_title = bp.Text(menu_scene, "adresse IP du serveur :", midtop=("50%", "10%"))
        bp.Entry(menu_scene, text=self.ipaddr, width=280, loc="midtop", ref=servaddr_title, refloc="midbottom",
                 entry_type=str, command=lambda text: setattr(self, "ipaddr", text), padding=5)

        # WAITING
        search = bp.Text(wait_scene, "A la recherche\nd'un adversaire", sticky="center", align_mode="center")
        self.search_animayion = bp.Text(wait_scene, "", ref=search, loc="midtop", refloc="midbottom")
        self.search_animation_index = 0
        def animate_serach():
            self.search_animation_index = (self.search_animation_index + 1) % 4
            self.search_animayion.set_text("." * self.search_animation_index)
        self.search_animator = bp.RepeatingTimer(.4, animate_serach)

        # PLAYGROUND
        def menu():
            self.play_scene.network.disconnect()
            menu_scene.open()
        bp.Button(wait_scene, "MENU", command=menu)
        bp.Button(self.play_scene, "MENU", command=menu)

        # DIALOGS
        self.set_style_for(bp.DialogFrame, width="80%")
        self.end_dialog = bp.Dialog(self, title="Arrêt pématuré", name="end_dialog",
                                    description="Votre adversaire a quitté\nla partie en cours",
                                    choices=("MENU", "NOUVELLE PARTIE"))
        def click_end_dialog(choice):
            if choice == "MENU":
                menu_scene.open()
            else:
                wait_scene.open()
        self.end_dialog.signal.ANSWERED.connect(click_end_dialog, owner=None)

    def _close(self):

        super()._close()

        if self.play_scene.network and self.play_scene.network.is_connected:
            self.play_scene.network.disconnect()


class WaitScene(bp.Scene):

    def _close(self):

        super()._close()

        self.application.search_animator.cancel()

    def open(self):

        super().open()

        play = self.application.play_scene

        try:
            play.network = Network(ip_addr=self.application.ipaddr, port=5554)
        except socket.error:
            bp.LOGGER.warning(f"No server found at address {self.application.ipaddr}")
            return self.application.open("menu")

        play.client_id = play.network.get_client_id()
        play.you_are_player.set_text(f"Vous êtes le joueur n°{play.client_id}")
        self.application.search_animator.start()

    def run(self):

        if self.application.play_scene.network.send("/game_started") == "True":
            self.application.play_scene.open()


class PlayScene(bp.Scene):

    def __init__(self, application, name):

        bp.Scene.__init__(self, application, name=name)

        self.network = None
        self.client_id = None
        self.game = None

        self.you_are_player = bp.Text(self, "", sticky="midtop")
        border_width = 5
        line = bp.Line(self, (0, 0, 0), (0, self.you_are_player.rect.bottom + border_width),
                       (self.rect.w, self.you_are_player.rect.bottom + border_width), width=border_width)
        self.result = bp.Text(self, "", sticky="center", font_height=90, visible=False)
        other_choice_title = bp.Text(self, "Votre adversaire a choisi :", midtop=(0, border_width),
                                     ref=line, refloc="midbottom")
        self.other_choice_text = bp.Text(self, "-", ref=other_choice_title, loc="midtop", refloc="midbottom")

        btns_zone = bp.Zone(self, width="100%", height="30%", sticky="midbottom")
        btns_zone.set_style_for(bp.Button, width="30%", height="90%")

        self.chose = False
        self.other_choice = None
        self.choice_text = bp.Text(self, "", midbottom=btns_zone.rect.midtop)
        class ChoiceButton(bp.Button):
            def handle_validate(btn):
                super().handle_validate()
                if self.chose:
                    return
                self.chose = True
                self.choice_text.set_text(btn.text_widget.text)
                self.choice_text.show()
                self.network.send(btn.text_widget.text)
        self.rock = ChoiceButton(btns_zone, "PIERRE", sticky="midleft", name="Rock")
        self.paper = ChoiceButton(btns_zone, "PAPIER", sticky="center", name="Paper")
        self.scissors = ChoiceButton(btns_zone, "CISEAUX", sticky="midright", name="Scissors")

    def _close(self):

        super()._close()

        self.chose = False
        self.other_choice = None
        self.choice_text.hide()
        self.result.hide()
        self.other_choice_text.set_text("-")

    def run(self):

        if console_debug:
            print("RUN")

        try:
            all_news = self.network.send("get_news")
            if console_debug: print(f"RECEIVED NEWS : -{all_news}-")
            if all_news is None:
                return self.application.end_dialog.open()
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
            self.application.end_dialog.open()


if __name__ == '__main__':
    ChifoumiApp().launch()
