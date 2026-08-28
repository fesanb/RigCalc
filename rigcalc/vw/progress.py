"""Small wrapper around Vectorworks' modeless, cancelable progress dialog."""


class RigCalcCancelled(Exception):
    pass


class VWProgress:
    def __init__(self, vs, title="RigCalc arbeider"):
        self.vs = vs
        self.title = title
        self.opened = False
        self.current = 0
        self.total = 1
        self.workflow = False
        self.phase_count = 1
        self.phase_index = -1
        self.phase_names = []

    def _check_cancel(self):
        try:
            if self.opened and self.vs.ProgressDlgHasCancel():
                raise RigCalcCancelled()
        except AttributeError:
            pass

    def begin_workflow(self, phase_count):
        self.close()
        self.workflow = True
        self.phase_count = max(1, int(phase_count))
        self.phase_index = -1
        self.phase_names = []
        try:
            self.vs.ProgressDlgOpen(self.title, True)
            self.opened = True
            self.vs.ProgressDlgSetBotMsg(
                "RigCalc arbeider. Trykk Avbryt for å stoppe før writeback.")
        except Exception:
            self.opened = False

    def _phase_summary(self):
        lines = []
        for index, name in enumerate(self.phase_names):
            state = "ferdig" if index < self.phase_index else "kjører"
            lines.append("{}: {}".format(state, name))
        remaining = self.phase_count-len(self.phase_names)
        lines.extend("venter: neste fase" for _ in range(max(0, remaining)))
        return "\n".join(lines)

    def start(self, total, message):
        if self.workflow and self.opened:
            if self.phase_index >= 0:
                try:
                    self.vs.ProgressDlgEnd()
                except Exception:
                    pass
            self.phase_index += 1
            self.current = 0
            self.total = max(1, int(total))
            self.phase_names.append(message.split(" 0/")[0])
            try:
                self.vs.ProgressDlgStart(
                    100.0/self.phase_count, self.total)
                self.vs.ProgressDlgSetTopMsg(self._phase_summary())
                self.vs.ProgressDlgSetMeter(message)
            except Exception:
                self.opened = False
            self._check_cancel()
            return
        self.close()
        self.workflow = False
        self.current = 0
        self.total = max(1, int(total))
        try:
            self.vs.ProgressDlgOpen(self.title, True)
            self.vs.ProgressDlgStart(100.0, self.total)
            self.vs.ProgressDlgSetMeter(message)
            self.opened = True
        except Exception:
            self.opened = False

    def update(self, current=None, message=None):
        if not self.opened:
            return
        target = self.current+1 if current is None else min(
            self.total, max(self.current, int(current)))
        try:
            if message:
                self.vs.ProgressDlgSetMeter(message)
            while self.current < target:
                self.vs.ProgressDlgYield(1)
                self.current += 1
        except Exception:
            self.opened = False
            return
        self._check_cancel()

    def pulse(self, message):
        if not self.opened:
            return
        try:
            self.vs.ProgressDlgSetMeter(message)
            self.vs.ProgressDlgYield(0)
        except Exception:
            self.opened = False
            return
        self._check_cancel()

    def close(self):
        if not self.opened:
            return
        try:
            self.vs.ProgressDlgEnd()
            self.vs.ProgressDlgClose()
        except Exception:
            pass
        self.opened = False
        self.workflow = False
