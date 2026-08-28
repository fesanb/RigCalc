import unittest

from rigcalc.vw.progress import RigCalcCancelled, VWProgress


class FakeVS:
    def __init__(self):
        self.cancelled = False
        self.yields = []
        self.messages = []

    def ProgressDlgOpen(self, title, can_cancel): pass
    def ProgressDlgStart(self, percentage, count): pass
    def ProgressDlgSetMeter(self, message): self.messages.append(message)
    def ProgressDlgSetTopMsg(self, message): self.messages.append(message)
    def ProgressDlgSetBotMsg(self, message): self.messages.append(message)
    def ProgressDlgYield(self, count): self.yields.append(count)
    def ProgressDlgEnd(self): pass
    def ProgressDlgClose(self): pass
    def ProgressDlgHasCancel(self): return self.cancelled


class ProgressTests(unittest.TestCase):
    def test_workflow_keeps_completed_phase_names(self):
        vs = FakeVS()
        progress = VWProgress(vs)
        progress.begin_workflow(2)
        progress.start(2, "Modell 0/2")
        progress.update(2, "Modell 2/2")
        progress.start(1, "Solver 0/1")
        self.assertTrue(any("ferdig: Modell" in item for item in vs.messages))
        self.assertTrue(any("kjører: Solver" in item for item in vs.messages))

    def test_cancel_is_raised_at_next_yield(self):
        vs = FakeVS()
        progress = VWProgress(vs)
        progress.begin_workflow(1)
        progress.start(2, "Modell 0/2")
        vs.cancelled = True
        with self.assertRaises(RigCalcCancelled):
            progress.update(1, "Modell 1/2")


if __name__ == "__main__":
    unittest.main()
