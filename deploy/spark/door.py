"""The Spark's public door: TLS on 127.0.0.1:7000, bytes handed to the studio on 7060.

The organisers publish node port 7000 as public port 7100, and their relay reaches a
listener bound to loopback only (tested), so nothing else on the node's
network sees this port. A browser gives the class page its camera and microphone only on
a secure address, so the door speaks TLS with the certificate door-setup.sh made; the
studio itself asks for the password (studio/server/serve_door.py).

It reads no HTTP. One thread per connection copies bytes both ways, from one thread
because an SSL socket is not safe to read and write from two at once, so the studio's
event streams arrive as they are written. Standard library only: the node's system
python3 runs it, as start.sh does.
"""
import select
import socket
import ssl
import threading
from pathlib import Path

FOLDER = Path.home() / '.config/beyond-canvas/door'
MAX_OPEN = 64      # a class needs a handful; anything past this is refused, not queued
HANDSHAKE_S = 15
IDLE_S = 300       # the studio's streams speak every 2 s; a connection silent this long is closed


def relay(client, studio):
    """Copy bytes both ways until either side closes or both fall silent."""
    while True:
        ready = [client] if client.pending() else select.select([client, studio], [], [], IDLE_S)[0]
        if not ready:
            return
        for source in ready:
            data = source.recv(65536)
            if not data:
                return
            (studio if source is client else client).sendall(data)


def serve(raw, context, studio_address, slots):
    client = studio = None
    try:
        raw.settimeout(HANDSHAKE_S)
        client = context.wrap_socket(raw, server_side=True)
        client.settimeout(IDLE_S)
        studio = socket.create_connection(studio_address, timeout=10)
        studio.settimeout(IDLE_S)
        relay(client, studio)
        # End TLS properly when the studio hangs up, as it does after a stream's `done`;
        # a bare close reads as a truncated reply ("record layer failure").
        client.settimeout(2)
        client.unwrap()
    except (OSError, ssl.SSLError):
        pass  # a scanner, a closed tab or a studio restart: nothing to tell anyone
    finally:
        for sock in (client, studio, raw):
            if sock is not None:
                sock.close()
        slots.release()


def main(listen=('127.0.0.1', 7000), studio=('127.0.0.1', 7060), folder=FOLDER):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(Path(folder) / 'server.crt', Path(folder) / 'server.key')
    slots = threading.BoundedSemaphore(MAX_OPEN)
    listener = socket.create_server(listen)
    print(f'door on https://{listen[0]}:{listen[1]} for the studio on {studio[1]}', flush=True)
    while True:
        raw, _ = listener.accept()
        if not slots.acquire(blocking=False):
            raw.close()
            continue
        threading.Thread(target=serve, args=(raw, context, studio, slots), daemon=True).start()


if __name__ == '__main__':
    main()
