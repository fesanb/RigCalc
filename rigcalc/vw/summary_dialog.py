"""Vectorworks dialog presenting a completed RigCalc run."""

from rigcalc.report.run_summary import make_run_summary_text


def show_run_summary_dialog(vs, summary):
    """Show an English, structured run summary with one explicit close action."""
    dialog = vs.CreateLayout(
        "RigCalc | Run Summary", False, "Close", "")
    summary_id, guidance_id = 4, 5
    vs.CreateStaticText(
        dialog, summary_id, make_run_summary_text(summary), 72)
    vs.CreateStaticText(
        dialog, guidance_id,
        "Detailed evidence is available in the RigCalc output reports. "
        "Review all markers and unresolved objects before using the result.",
        72)
    vs.SetFirstLayoutItem(dialog, summary_id)
    vs.SetBelowItem(dialog, summary_id, guidance_id, 0, 2)
    vs.RunLayoutDialog(dialog, lambda item, data: None)
