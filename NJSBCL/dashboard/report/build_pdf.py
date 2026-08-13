"""Builds the NJSBCL Scout PDF intelligence report for the next upcoming match from
report_data.json (produced by extract_report_data.js) and saves it to ~/Downloads/.

Usage: uv run --with fpdf2 python3 build_pdf.py
"""
import json
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).parent
DOWNLOADS = Path.home() / "Downloads"

GOLD = (230, 168, 0)
BLUE = (58, 134, 255)
MUTED = (110, 118, 133)
DARK = (30, 33, 41)
LINE = (222, 226, 233)
WIN = (20, 150, 110)
LOSS = (210, 70, 70)

# fpdf2's core fonts (Helvetica/Times/Courier) are Latin-1 only — swap the Unicode
# punctuation this dataset's copy uses (em dashes, curly quotes) for ASCII rather
# than bundling a TTF just for a handful of characters.
_REPLACEMENTS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...",
}


def clean(s):
    if s is None:
        return ""
    s = str(s)
    for k, v in _REPLACEMENTS.items():
        s = s.replace(k, v)
    return s


class Report(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, clean(f"NJSBCL Scout - {self.title_line}"), align="L")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 8, f"Page {self.page_no()}", align="R")
        self.ln(12)

    def footer(self):
        pass

    def section_title(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*DARK)
        self.cell(0, 8, clean(text), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*GOLD)
        self.set_line_width(0.6)
        y = self.get_y()
        self.line(self.l_margin, y, self.l_margin + 30, y)
        self.ln(4)

    def subhead(self, text, color=DARK):
        self.set_font("Helvetica", "B", 10.5)
        self.set_text_color(*color)
        self.cell(0, 6, clean(text), new_x="LMARGIN", new_y="NEXT")

    def body(self, text, size=9.5, color=(60, 64, 74)):
        self.set_font("Helvetica", "", size)
        self.set_text_color(*color)
        self.multi_cell(0, 5, clean(text))

    def kv_row(self, label, value, label_w=58):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*MUTED)
        x0, y0 = self.get_x(), self.get_y()
        self.cell(label_w, 6, clean(label))
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*DARK)
        self.set_xy(x0 + label_w, y0)
        self.multi_cell(self.epw - label_w, 6, clean(value), new_x="LMARGIN", new_y="NEXT")

    def _wrap_line_count(self, text, width, font_family, font_style, font_size):
        """Simulate fpdf2's word-wrap to get an accurate line count for height planning
        (used to size boxes before drawing them, since rect() doesn't auto-paginate)."""
        self.set_font(font_family, font_style, font_size)
        words = clean(text).split(" ")
        lines, line = 1, ""
        for word in words:
            trial = f"{line} {word}".strip()
            if self.get_string_width(trial) > width and line:
                lines += 1
                line = word
            else:
                line = trial
        return lines

    def _ensure_space(self, height):
        """Force a fresh page if `height` mm won't fit below the current y — keeps a
        block (table/callout) from being split across a page boundary mid-row/mid-box."""
        if self.get_y() + height > self.page_break_trigger:
            self.add_page()

    def table(self, headers, rows, col_widths, align=None):
        align = align or ["L"] * len(headers)
        needed = 6.5 + 6 * len(rows) + 2
        self._ensure_space(needed)
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(245, 246, 248)
        self.set_text_color(*MUTED)
        for h, w in zip(headers, col_widths):
            self.cell(w, 6.5, clean(h), border="B", fill=True, align="C")
        self.ln(6.5)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*DARK)
        for r in rows:
            for val, w, a in zip(r, col_widths, align):
                self.cell(w, 6, clean(val), border="B", align=a)
            self.ln(6)
        self.ln(2)

    def subhead_table(self, title, headers, rows, col_widths, align=None, color=DARK):
        """subhead() immediately followed by table() over the combined height, so a
        table never lands orphaned on the next page while its heading stays behind."""
        self._ensure_space(6 + 6.5 + 6 * len(rows) + 2)
        self.subhead(title, color=color)
        self.table(headers, rows, col_widths, align=align)

    def callout(self, title, big, note, accent=GOLD):
        w = self.epw
        note_lines = self._wrap_line_count(note, w - 8, "Helvetica", "", 8.5)
        h = 20 + note_lines * 4.2
        self._ensure_space(h + 4)
        x0, y0 = self.get_x(), self.get_y()
        self.set_fill_color(250, 250, 251)
        self.set_draw_color(*LINE)
        self.rect(x0, y0, w, h, style="DF")
        self.set_xy(x0 + 4, y0 + 3)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*MUTED)
        self.cell(w - 8, 5, clean(title))
        self.set_xy(x0 + 4, y0 + 9)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*accent)
        self.cell(w - 8, 8, clean(big))
        self.set_xy(x0 + 4, y0 + 18)
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*DARK)
        self.multi_cell(w - 8, 4.2, clean(note))
        self.set_xy(x0, y0 + h + 4)


def form_string(recent_results):
    return " ".join(r["result"][0] for r in recent_results) if recent_results else "no data"


def dismissal_line(breakdown, max_types=3):
    """Comma-joined 'Type pct%' summary, capped at `max_types` — fpdf2's plain cell()
    doesn't wrap, so an uncapped list can overflow into the next column for anyone
    with 4+ dismissal types on record."""
    if not breakdown:
        return "no dismissal data"
    shown = breakdown[:max_types]
    line = ", ".join(f"{b['type']} {b['pct']}%" for b in shown)
    if len(breakdown) > max_types:
        line += f" (+{len(breakdown) - max_types} more)"
    return line


def main():
    data = json.loads((HERE / "report_data.json").read_text())
    us, them = data["us"], data["them"]
    gladiators, opponent = data["gladiators"], data["opponent"]
    fixture = data["fixture"]

    pdf = Report()
    pdf.title_line = f"{gladiators} vs {opponent}"
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 14, 16)
    pdf.add_page()

    # ── Title block ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 10, "NJSBCL Scout - Match Intelligence Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*GOLD)
    pdf.cell(0, 9, clean(f"{gladiators}  vs  {opponent}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, clean(f"{data['seriesLabel']} - {fixture['date']}, {fixture['time']} - {fixture['venue']}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, clean(f"Built from dashboard data as of {data['generated']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Win probability ──────────────────────────────────────────────
    pdf.section_title("Win probability")
    win_pct = them.get("gladiatorsWinProbability")
    us_pct = win_pct if win_pct is not None else 50
    them_pct = round(100 - us_pct, 1) if win_pct is not None else 50
    pdf.callout(
        f"{gladiators} vs {opponent} (Elo-based)",
        f"{us_pct}% / {them_pct}%",
        f"Elo rating - {gladiators}: {us['elo']}, {opponent}: {them['elo']}. "
        "Form/strength estimate only - doesn't know toss, weather, or availability.",
    )
    pdf.ln(2)

    # ── Toss advice ──────────────────────────────────────────────────
    pdf.section_title("Toss advice")
    toss = them["toss"]
    toss_labels = {"bat": "BAT FIRST", "bowl": "BOWL FIRST", "even": "EITHER WORKS"}
    pdf.subhead(f"Recommendation: {toss_labels.get(toss['recommendation'], 'NOT ENOUGH DATA')}")
    pdf.body(toss["reason"])
    pdf.ln(1)
    bf, ch = toss["battingFirst"], toss["chasing"]
    pdf.kv_row("Batting first:",
               f"{bf['wins']}/{bf['matches']} won"
               + (f" ({bf['winPct']}%), avg score {bf['avgScore']}" if bf["winPct"] is not None else ""))
    pdf.kv_row("Chasing:",
               f"{ch['wins']}/{ch['matches']} won"
               + (f" ({ch['winPct']}%), avg winning chase {ch['avgChaseSuccess']}" if ch["winPct"] is not None else ""))
    pt = them["parTarget"]
    if pt["parScoreToSet"]["value"] is not None:
        pdf.kv_row("Par score to set:", f"{pt['parScoreToSet']['value']} (n={pt['parScoreToSet']['sampleSize']})")
    if pt["targetToChase"]["value"] is not None:
        pdf.kv_row("Target to chase:", f"{pt['targetToChase']['value']} (n={pt['targetToChase']['sampleSize']})")
    pdf.ln(2)

    # ── Season record & standing ─────────────────────────────────────
    pdf.section_title("Season record & standing")
    st_us, st_them = us.get("standing") or {}, them.get("standing") or {}
    pdf.table(
        ["Team", "Record", "Group", "Rank", "Pts", "Win%", "NRR"],
        [
            [gladiators, f"{us['wins']}-{us['losses']}-{us['ties']}",
             st_us.get("group", "-"), f"{st_us.get('rank', '-')}/{st_us.get('rankOf', '-')}",
             str(st_us.get("pts", "-")), f"{st_us.get('winPct', '-')}", f"{st_us.get('netRR', '-')}"],
            [opponent, f"{them['wins']}-{them['losses']}-{them['ties']}",
             st_them.get("group", "-"), f"{st_them.get('rank', '-')}/{st_them.get('rankOf', '-')}",
             str(st_them.get("pts", "-")), f"{st_them.get('winPct', '-')}", f"{st_them.get('netRR', '-')}"],
        ],
        [46, 26, 18, 22, 18, 18, 20],
    )
    h2h = them["headToHead"]
    if h2h and h2h["played"]:
        pdf.kv_row("Head-to-head this season:", f"{h2h['wins']}-{h2h['losses']}-{h2h['ties']} ({h2h['played']} played)")
    else:
        pdf.kv_row("Head-to-head this season:", "first meeting")
    ha = them["homeAway"]
    pdf.kv_row(f"{opponent} home/away:",
               f"home {ha['home']['wins']}/{ha['home']['matches']} ({ha['home']['winPct']}%), "
               f"away {ha['away']['wins']}/{ha['away']['matches']} ({ha['away']['winPct']}%)")
    pdf.ln(2)

    # ── Recent form ───────────────────────────────────────────────────
    pdf.section_title(f"{opponent} - recent form")
    pdf.kv_row("Last 5 results:", form_string(them["recentResults"]))
    bc = them["battingCollapses"]
    collapse_note = f"{bc['collapseCount']}/{bc['totalInnings']} innings ({bc['collapsePct']}%)"
    if bc.get("worst"):
        w = bc["worst"]
        collapse_note += f" - worst: {w['wickets']} wkts for {w['runs']} runs vs {w['opponent']}"
    pdf.kv_row("Batting collapse rate:", collapse_note)
    pdf.ln(2)

    # ── Key batsmen ───────────────────────────────────────────────────
    pdf.section_title(f"{opponent} - key batsmen")
    rows = []
    for b in them["topBatsmen"]:
        trend = b.get("recentForm", {}).get("trend", "-") if b.get("recentForm") else "-"
        rows.append([b["player"], str(b["innings"]), str(b["runs"]), str(b["avg"]), str(b["sr"]),
                     dismissal_line(b["dismissals"]["breakdown"]), trend])
    pdf.table(
        ["Player", "Inns", "Runs", "Avg", "SR", "Gets out", "Form"],
        rows, [34, 12, 16, 14, 14, 66, 16],
        align=["L", "C", "C", "C", "C", "L", "C"],
    )
    wi = them.get("keyBatsmanWinImpact")
    top_bat_name = them["topBatsmen"][0]["player"] if them["topBatsmen"] else "their top scorer"
    if wi:
        pdf.callout(
            f"What if we get {top_bat_name} out early?",
            f"+{wi['swing']}pp swing",
            f"{opponent} win {wi['highWinPct']}% of matches (n={wi['highN']}) when he scores {wi['threshold']}+, "
            f"but just {wi['lowWinPct']}% (n={wi['lowN']}) when held under {wi['threshold']}. "
            "Runs scored is the closest proxy available for an early dismissal.",
        )
    pdf.ln(2)

    # ── Key bowlers ───────────────────────────────────────────────────
    pdf.section_title(f"{opponent} - key bowlers")
    rows = []
    for b in them["topBowlers"]:
        wt = b.get("wicketTypes", {}).get("breakdown", [])
        rows.append([b["player"], str(b["wickets"]), str(b["overs"]), str(b["econ"]), dismissal_line(wt)])
    pdf.table(
        ["Player", "Wkts", "Overs", "Econ", "Wicket types"],
        rows, [40, 16, 18, 16, 82],
        align=["L", "C", "C", "C", "L"],
    )
    pdf.ln(2)

    pdf.add_page()

    # ── Bowling battle ────────────────────────────────────────────────
    pdf.section_title("Bowling battle")
    rows = [[b["player"], f"{b['overs']}", str(b["wickets"]), str(b["econ"]), f"{b['dotPct']}%"]
            for b in us["bowlingStrengths"]]
    pdf.subhead_table(f"{gladiators} - bowlers to build the attack around",
                       ["Player", "Overs", "Wkts", "Econ", "Dot%"], rows, [50, 26, 24, 24, 24],
                       align=["L", "C", "C", "C", "C"], color=WIN)
    rows = [[b["player"], f"{b['overs']}", str(b["wickets"]), str(b["econ"]),
             f"{b['worstSpellRuns']}/{b['worstSpellBalls']}b", f"{b['extrasRate']}/ov"]
            for b in them["weakBowlers"]]
    pdf.subhead_table(f"{opponent} - bowlers to target for runs",
                       ["Player", "Overs", "Wkts", "Econ", "Worst spell", "Extras"],
                       rows, [42, 20, 18, 18, 34, 26], align=["L", "C", "C", "C", "C", "C"], color=LOSS)
    rows = [[d["player"], f"{d['oversBowled']} overs", f"{d['runs']} runs", f"{d['econ']}/over"]
            for d in data["deathOversLeaders"]]
    pdf.subhead_table(f"{gladiators} - death overs (last 3), who to trust",
                       ["Player", "Overs", "Runs conceded", "Econ"], rows, [50, 30, 40, 30],
                       align=["L", "C", "C", "C"], color=WIN)
    pdf.ln(2)

    # ── Other signals ─────────────────────────────────────────────────
    pdf.section_title("Other signals")
    top3 = them["topBatsmen"][:3]
    lean = round(100 * top3[0]["runs"] / max(1, sum(b["runs"] for b in top3))) if top3 else None
    pdf.kv_row(f"Lean on {top_bat_name}:",
               f"{lean}% of top-3 batsmen's runs" if lean is not None else "n/a")
    pdf.kv_row("Boundary dependence:", f"{opponent} {them['boundaryDependencyPct']}% vs {gladiators} {us['boundaryDependencyPct']}%")
    us_strike = us["topBowlers"][0] if us["topBowlers"] else None
    them_strike = them["topBowlers"][0] if them["topBowlers"] else None
    if us_strike and them_strike:
        pdf.kv_row("Strike bowler match-up:",
                   f"{gladiators}: {us_strike['player']} ({us_strike['wickets']}w @ {us_strike['econ']}) vs "
                   f"{opponent}: {them_strike['player']} ({them_strike['wickets']}w @ {them_strike['econ']})")
    pdf.ln(2)

    # ── Appendix: our squad ───────────────────────────────────────────
    pdf.section_title(f"Appendix - who does {gladiators} depend on to win?")
    pdf.body("Split each player's games into their own good half and bad half (runs for batters, "
              "economy for bowlers) and compare our win rate in each. Small season - a notable "
              "pattern, not a guarantee.")
    pdf.ln(1)
    wd = data["gladiatorsCharts"]["winDependency"]
    if wd:
        rows = [[w["player"], "Bat" if w["role"] == "bat" else "Bowl", str(w["matches"]),
                 f"+{w['swing']}pp", f"{w['goodWinPct']}%", f"{w['badWinPct']}%"]
                for w in wd]
        pdf.table(["Player", "Role", "Matches", "Swing", "Good half", "Bad half"],
                   rows, [50, 20, 24, 24, 28, 26], align=["L", "C", "C", "C", "C", "C"])
    else:
        pdf.body("Not enough matches yet to compute this.")

    pdf.ln(3)
    xi = data["gladiatorsCharts"]["bestXI"]["players"]
    rows = [[p["player"], p["role"]] for p in xi]
    pdf.subhead_table("Suggested best XI", ["Player", "Role"], rows, [70, 60], align=["L", "L"])

    out_name = f"NJSBCL_Scout_Report_{re.sub(r'[^A-Za-z0-9]+', '_', opponent).strip('_')}_{fixture['date'].split(', ')[-1].replace(' ', '-')}.pdf"
    out_path = DOWNLOADS / out_name
    pdf.output(str(out_path))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
