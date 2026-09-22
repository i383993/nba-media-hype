"""Build the SSAC27 abstract as a submission-ready one-page PDF."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

styles = getSampleStyleSheet()
title_style = ParagraphStyle("TitleC", parent=styles["Title"], fontSize=14.5, leading=17, spaceAfter=8)
head_style = ParagraphStyle("Head", parent=styles["Heading2"], fontSize=10.5, spaceBefore=6, spaceAfter=2)
body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5, leading=12.5, alignment=4)  # justified
caption_style = ParagraphStyle("Caption", parent=styles["Normal"], fontSize=8, leading=10,
                                textColor=colors.HexColor("#444444"), spaceBefore=4)

TITLE = "Buzz Kill: Media Attention Surges as a Contrarian Signal of NBA Team Trajectory"

INTRO = ('Fans and journalists build "wisdom of the crowd" rankings constantly &mdash; from '
    'all-time player debates to who&rsquo;s the season&rsquo;s MVP frontrunner &mdash; on the '
    'assumption that collective attention tracks who is actually playing well. We test this '
    'directly for the NBA: does the aggregate attention of journalists (news coverage) and fans '
    '(Wikipedia interest) predict team performance? A naive test fails outright: among the last '
    'nine MVP races, the most-covered candidate in news matched the actual winner zero times, '
    'picking LeBron James six of nine years regardless of who won. Front offices, media partners, '
    'and analysts routinely read public buzz as a proxy for team momentum when making trade, '
    'valuation, and roster-confidence decisions, so knowing whether that signal is trustworthy has '
    'real stakes. This raises the sharper question: is crowd attention just noise, or does it '
    'carry real, usable information once measured correctly?')

METHODS = ('We built two independent public "crowd" measures for every NBA team across eleven '
    'seasons (2015-16 to 2025-26): media attention and tone from GDELT&rsquo;s global news index '
    '(via Google BigQuery), and fan attention from daily Wikipedia pageviews. Rather than raw '
    'attention share, which is dominated by fixed market-size effects, we define "buzz" as a '
    'team&rsquo;s current attention relative to its own trailing three-year baseline, isolating '
    'genuine surges from a team&rsquo;s normal profile. Prior work has tested social-media '
    'sentiment against betting lines or measured popularity bias baked into bookmakers&rsquo; '
    'spreads; we instead isolate deviations from a team&rsquo;s own attention baseline and test '
    'them directly against team trajectory, independent of any market. We regress rest-of-season '
    'win percentage and playoff series outcomes on buzz, controlling for both season-to-date point '
    'differential and recent (last-10-game) form, with standard errors clustered by team.')

RESULTS = ('Media buzz is a significant, robust negative predictor of performance: controlling '
    'for current point differential and recent form, a one-standard-deviation buzz surge is '
    'associated with roughly one fewer win over an 82-game season (p=0.013, n=941 '
    'team-checkpoints) and cuts a playoff team&rsquo;s odds of winning its series to about 57% of '
    'baseline (p=0.006, n=151 series) &mdash; see Table 1. The effect is unchanged by controlling '
    'for hot-streak form, ruling out simple mean reversion as the explanation. Fan-attention buzz '
    'shows the same direction but falls short of significance (p=0.066).')

CONCLUSION = ('Collective attention is not simply noisy about NBA outcomes &mdash; it is '
    'systematically miscalibrated in a specific, exploitable way: sudden hype is a warning sign, '
    'not a confirmation. Front offices and analysts evaluating a team&rsquo;s trajectory, whether '
    'for trades, valuations, or public confidence, should treat an attention spike as reason for '
    'scrutiny rather than optimism. All data, code, and the robustness checks above are public and '
    'fully reproducible at github.com/i383993/nba-media-hype.')

TABLE_DATA = [
    ["Target", "Controls", "Coefficient", "p-value", "n"],
    ["Rest-of-season win %", "Point differential only", "−0.041", "0.011", "941"],
    ["Playoff series won", "Point differential only", "−1.054", "0.006", "151"],
    ["Rest-of-season win %", "+ last-10-game form", "−0.041", "0.013", "941"],
    ["Playoff series won", "+ last-10-game form", "−1.052", "0.006", "151"],
]


def main():
    doc = SimpleDocTemplate("SSAC27_abstract.pdf", pagesize=letter,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.8 * inch, rightMargin=0.8 * inch)
    story = [Paragraph(TITLE, title_style)]
    for head, text in [("Introduction", INTRO), ("Methods", METHODS),
                       ("Results", RESULTS), ("Conclusion", CONCLUSION)]:
        story.append(Paragraph(head, head_style))
        story.append(Paragraph(text, body_style))

    story.append(Spacer(1, 8))
    t = Table(TABLE_DATA, colWidths=[1.55 * inch, 1.75 * inch, 0.95 * inch, 0.75 * inch, 0.55 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f9")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    caption = Paragraph(
        "Table 1. Media-buzz regression coefficients for both targets, with and without a "
        "recency (last-10-game form) control &mdash; the robustness check ruling out hot-streak "
        "mean reversion as the explanation.", caption_style)
    story.append(KeepTogether([t, caption]))

    doc.build(story)
    print("wrote SSAC27_abstract.pdf")


if __name__ == "__main__":
    main()
