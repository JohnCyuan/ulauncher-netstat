import logging
import os
import subprocess
import ipdb
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from itertools import islice
from subprocess import check_call, CalledProcessError
from gi.repository import Notify
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem

logger = logging.getLogger(__name__)
dead_icon = 'images/dead.png'
exec_icon = 'images/exec.png'


class NetStatExtension(Extension):

    def __init__(self):
        super(NetStatExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())

    def show_notification(self, title, text=None, icon=dead_icon):
        logger.debug('Show notification: %s' % text)
        icon_full_path = os.path.join(os.path.dirname(__file__), icon)
        Notify.init("NetStatExtension")
        Notify.Notification.new(title, text, icon_full_path).show()


class KeywordQueryEventListener(EventListener):

    def on_event(self, event, extension):
        return RenderResultListAction(list(islice(self.generate_results(event), 10)))

    def generate_results(self, event):
        arg = event.get_argument()
        if arg is None or len(arg) < 1:
            return RenderResultListAction([])
        temp = []
        for i1, val1 in enumerate(get_process_list(event)):
            if len(temp) == 0:
                temp.append(val1)
                continue
            for i, val in enumerate(temp):
                if val1[0] != val[0]:
                    if i == (len(temp) - 1):
                        temp.append(val1)
                        break
                else:
                    break
        for (pid, port, name, description) in temp:
            yield ExtensionResultItem(
                icon=exec_icon,
                name=name.title() + '(' + port + '/' + pid + ')',
                description=description,
                on_enter=ExtensionCustomAction(pid),
            )


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        pid = event.get_data()
        if pid is None and len(pid) <= 0:
            return
        self.kill(extension, pid, '9')

    def kill(self, extension, pid, signal):
        cmd = ['kill', '-s', signal, pid]
        logger.info(' '.join(cmd))
        try:
            check_call(cmd) == 0
            extension.show_notification("Done", "It's dead now", icon=dead_icon)
        except CalledProcessError as e:
            extension.show_notification("Error", "'kill' returned code %s" % e.returncode)
        except Exception as e:
            logger.error('%s: %s' % (type(e).__name__, e.args[0]))
            extension.show_notification("Error", "Check the logs")
            raise


def get_process_list(event):
    argument = event.get_argument()
    proc1 = subprocess.Popen(['netstat', '-atunp'], stdout=subprocess.PIPE)
    proc2 = subprocess.Popen(['grep', argument], stdin=proc1.stdout,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    proc1.stdout.close()  # Allow proc1 to receive a SIGPIPE if proc2 exits.
    out, err = proc2.communicate()
    out = out.decode('utf8').split('\n')
    print(len(out))
    for idx, line in enumerate(out):
        col = line.split()
        if len(col):
            print(col)
            if col[0].find('udp') != -1:
                if col[5] == '-':
                    continue
                info = col[5].split('/')
                pid = info[0]
                name = info[1]
                description = col[0] + "|" + col[3] + "|" + col[5]
                local = col[3]
                yield (pid, get_port(local), name, description)
            elif col[0].find('tcp') != -1:
                if col[6] == '-':
                    continue
                info = col[6].split('/')
                pid = info[0]
                name = info[1]
                description = col[0] + "|" + col[3] + "|" + col[5]
                local = col[3]
                yield (pid, get_port(local), name, description)


def get_port(local):
    index = local.rfind(':')
    port = ''
    if index != -1:
        port = local[index + 1:]
    return port


if __name__ == '__main__':
    NetStatExtension().run()
