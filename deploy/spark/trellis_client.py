"""Hand one 3D job to the resident TRELLIS.2 (trellis_resident.py) and wait.

The media service runs this in place of a one-off container when the resident answers
(media_spark.command), so the service's lock, memory floor, cancellation and output checks stay
exactly as they are. Exit 0 once output.glb is written. Standard library only.
usage: trellis_client.py JOB_FOLDER
"""
import socket
import sys
from pathlib import Path

SOCKET = Path.home() / 'spark-media' / 'resident' / 'trellis.sock'


def main(job, socket_path=SOCKET, timeout_s=1500):
    job = Path(job)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout_s)
        connection.connect(str(socket_path))
        connection.sendall(job.name.encode() + b'\n')
        answer = connection.makefile('rb').readline().decode('utf-8', 'replace').strip()
    print(answer or 'no answer', flush=True)
    return 0 if answer == 'ok' and (job / 'output.glb').is_file() else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
