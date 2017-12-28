from airmash import packets
from airmash.player import Player
from airmash.mob import Mob
from airmash.country import COUNTRY_CODES
import websocket
import threading
import time
import sys
import threading
import Queue


def add_input(input_queue):
    while True:
        input_queue.put(sys.stdin.read(1))


input_queue = Queue.Queue()

input_thread = threading.Thread(target=add_input, args=(input_queue,))
input_thread.daemon = True
input_thread.start()

ws = None


class StoppableThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._event = threading.Event()

    def stop(self):
        self._event.set()

    def wait(self, timeout=1):
        return self._event.wait(timeout=timeout)


class ClientUpdate(StoppableThread):
    def __init__(self, *args, **kwargs):
        StoppableThread.__init__(self, *args, **kwargs)

    def run(self):
        global input_queue
        while not self.wait():
            packet = packets.build_player_command('KEY', seq=1, key='LEFT', state=True)
            ws.send(packet, opcode=websocket.ABNF.OPCODE_BINARY)
            if not input_queue.empty():
                msg = ''
                while not input_queue.empty():
                    msg += input_queue.get()
                packet = packets.build_player_command('CHAT', text=msg)
                ws.send(packet, opcode=websocket.ABNF.OPCODE_BINARY)


players = {}
projectiles = {}
me = None

_t_update = None


def on_open(ws):
    global _t_update
    cmd = packets.build_player_command('LOGIN',
                                       protocol=5,
                                       name='cli',
                                       session='none',
                                       horizonX=1920 / 2,
                                       horizonY=1920 / 2,
                                       flag='US'
                                       )
    ws.send(cmd, opcode=websocket.ABNF.OPCODE_BINARY)
    _t_update = ClientUpdate()
    _t_update.start()


def on_close(ws):
    global _t_update
    if _t_update is not None:
        _t_update.stop()
        _t_update.join()


def on_message(ws, message):
    message = packets.decode_server_command(message)
    # print(message)
    # print(players[me])

    if message.command == 'PING':
        cmd = packets.build_player_command('PONG', num=message.num)
        ws.send(cmd, opcode=websocket.ABNF.OPCODE_BINARY)
        return

    if message.command == 'ERROR':
        error_type, error_text = packets.error_types[message.error]
        print("Server: [{} ({})] {}".format(
            message.error, error_type, error_text))
        return

    if message.command == 'LOGIN':
        global me
        me = message.id
        print(message.room)
        for player in message.players[:-1]:
            print player.name + ',',
        print ''
        last_id = ''
        for player in message.players[:-1]:
            players[player.id] = Player(player.id, player)
            last_id = player.id
        players[me].update(message)

        #players[me].on_change('rotation', track_rotation)

        #players[me].on_change('upgrades', ks)
        #players[me].on_change('keystate', ks)

        # cmd = packets.build_player_command('SCOREDETAILED')
        # ws.send(cmd, opcode=websocket.ABNF.OPCODE_BINARY)

        cmd = packets.build_player_command('COMMAND',
            com='spectate',
            data=str(message.players[0].id)
        )
        ws.send(cmd, opcode=websocket.ABNF.OPCODE_BINARY)
        return

    if message.command == 'SERVER_MESSAGE':
        print(u"Server: [{}] {}".format(message.type, message.message))
        return

    if message.command == 'CHAT_PUBLIC':
        player = players[message.id]
        print(u"Public Chat: [{}] {}".format(player.name, message.text))
        return

    if message.command == 'CHAT_TEAM':
        player = players[message.id]
        print(u"Team Chat: [{}] {}".format(player.name, message.text))
        return

    if message.command == 'CHAT_WHISPER':
        w_from = players[message.id]
        w_to = players[message.to]
        print(u"Whisper: [{}] {}".format(w_from.name, message.text))
        return


def on_error(ws, error):
    print(error)


def run():
    global ws
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(packets.SERVER_ADDR,
                                subprotocols=['binary'],
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)

    ws.run_forever(origin='https://airma.sh')


if __name__ == "__main__":
    run()
