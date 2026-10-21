"""Background RAM sampling and stale-sample suppression for HTTP clients."""
import threading
import time

from ram import Tracker, decode_snapshot


class Feed:
    def __init__(self, pid=None, snapshot=None, emulator='auto', gdb_port=None):
        self.tracker = Tracker(pid, emulator=emulator, gdb_port=gdb_port)
        self.stop = threading.Event()
        self.state = {'status':'connecting', 'message':'Connecting to local emulator…'}
        self.snapshot = snapshot
        self.worker = threading.Thread(target=self.run, daemon=True)

    def current(self):
        state = self.state
        if state.get('source') == 'live' and time.time() - state.get('sample_time', time.time()) > 1.5:
            return {'status':'error', 'source':'live', 'message':'RAM samples are stale; position hidden.'}
        return state

    def run(self):
        try:
            if self.snapshot:
                try:
                    data = self.snapshot.read_bytes()
                    self.state = {**decode_snapshot(data), 'source':'snapshot', 'message':'Recorded RAM snapshot — not live.', 'epoch':0}
                except (OSError, ValueError) as error:
                    self.state = {'status':'error', 'source':'snapshot', 'message':f'Cannot read snapshot: {error}'}
                return
            while not self.stop.is_set():
                try:
                    self.state = {**self.tracker.sample(), 'source':'live'}
                except Exception as error:
                    self.state = {'status':'error','message':f'RAM reader: {error}', 'source':'live'}
                self.stop.wait(1 / 30)
        finally:
            self.tracker.close()
