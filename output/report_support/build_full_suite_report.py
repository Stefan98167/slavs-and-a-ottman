"""Build the task's PDF from preserved results; no network or policy calls."""

import json
import statistics
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/pdf/system-and-13-run-review.pdf"
BEFORE = ROOT / "output/validation/full-suite-10-hosted"
AFTER = ROOT / "output/validation/full-suite-followup-3-hosted"

for name, filename in (("Open", "OpenSans-Regular.ttf"), ("OpenB", "OpenSans-Bold.ttf"),
                       ("OpenI", "OpenSans-Italic.ttf")):
    pdfmetrics.registerFont(TTFont(name, f"/usr/share/fonts/open-sans/{filename}"))
pdfmetrics.registerFontFamily("Open", normal="Open", bold="OpenB", italic="OpenI", boldItalic="OpenB")

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#216FA5")
TEAL = colors.HexColor("#147A6C")
AMBER = colors.HexColor("#A36614")
INK = colors.HexColor("#253746")
GRAY = colors.HexColor("#566775")
PALE = colors.HexColor("#F0F4F7")
LINE = colors.HexColor("#CAD5DD")
WHITE = colors.white


def records(folder):
    return {r["case_id"].split(":")[-1]: r for path in sorted(folder.glob("unified-*.json"))
            if (r := json.loads(path.read_text()))}


B, F = records(BEFORE), records(AFTER)
assert len(B) == 10 and len(F) == 3, "All thirteen results are required before publication"
MB, MF = json.loads((BEFORE / "run.json").read_text()), json.loads((AFTER / "run.json").read_text())
assert MB.get("finished_at") and MF.get("finished_at")
assert len({r["session_id"] for r in [*B.values(), *F.values()]}) == 13


def score(record):
    return 100 * record["result"]["score"]


MEAN_B = statistics.mean(map(score, B.values()))
MEAN_F = statistics.mean(map(score, F.values()))
MATCH_B = statistics.mean(score(B[key]) for key in F)
MEAN_13 = statistics.mean(map(score, [*B.values(), *F.values()]))


def euros(value):
    return f"EUR {value:,.2f}"


def timeouts(records_):
    return sum(len(thread.get("timeouts") or []) for record in records_.values()
               for thread in record.get("threads", {}).values())


def error_count(records_):
    return sum(bool(r.get("run_error") or r.get("audit_errors")) for r in records_.values())


OUT.parent.mkdir(parents=True, exist_ok=True)
C = canvas.Canvas(str(OUT), pagesize=A4, pageCompression=1)
C.setTitle("How our negotiation system works | 13-run review")
C.setAuthor("Slavs and an Ottoman | Engineering review")
C.setSubject("System architecture, full-suite benchmark, reflection and three random follow-ups")
PAGE = 0
W, H = A4


def text(value, x, y, width, *, size=10.5, color=INK, bold=False, leading=None, align=0):
    style = ParagraphStyle("body", fontName="OpenB" if bold else "Open", fontSize=size,
                           leading=leading or size * 1.44, textColor=color, alignment=align,
                           spaceBefore=0, spaceAfter=0)
    paragraph = Paragraph(value, style)
    _, height = paragraph.wrap(width, 2000)
    assert y - height > 43, f"Page {PAGE} overflows: {value[:85]}"
    paragraph.drawOn(C, x, y - height)
    return y - height


def page(kicker, title, subtitle="", *, wide=False):
    global PAGE, W, H
    if PAGE:
        C.showPage()
    PAGE += 1
    W, H = landscape(A4) if wide else A4
    C.setPageSize((W, H))
    C.setFillColor(NAVY)
    C.rect(0, H - 9, W, 9, fill=1, stroke=0)
    text(kicker.upper(), 44, H - 34, W - 88, size=9, color=TEAL, bold=True)
    y = text(title, 44, H - 57, W - 88, size=23, color=NAVY, bold=True, leading=29)
    if subtitle:
        y = text(subtitle, 44, y - 12, W - 88, size=10, color=GRAY)
    C.setStrokeColor(LINE)
    C.line(44, 38, W - 44, 38)
    C.setFont("Open", 8)
    C.setFillColor(GRAY)
    C.drawString(44, 24, "Slavs and an Ottoman | Tacto Arena | 10 October 2026")
    C.drawRightString(W - 44, 24, f"{PAGE:02d}")
    return y - 25


def section(title, body, y):
    y = text(title, 44, y, W - 88, size=13, bold=True, color=NAVY)
    return text(body, 44, y - 7, W - 88) - 21


def callout(title, body, y, *, fill=PALE, color=TEAL):
    width = W - 88
    style = ParagraphStyle("measure", fontName="Open", fontSize=10.5, leading=15.12)
    p = Paragraph(body, style)
    _, body_h = p.wrap(width - 30, 2000)
    height = 48 + body_h
    C.setFillColor(fill)
    C.roundRect(44, y - height, width, height, 8, fill=1, stroke=0)
    text(title, 59, y - 12, width - 30, size=12, color=color, bold=True)
    text(body, 59, y - 36, width - 30)
    return y - height - 22


def table(headers, rows, widths, y, *, size=9.4, min_height=30):
    x0 = 44
    C.setFillColor(NAVY)
    C.rect(x0, y - 30, sum(widths), 30, fill=1, stroke=0)
    x = x0
    for label, width in zip(headers, widths):
        text(label, x + 8, y - 6, width - 16, size=size, color=WHITE, bold=True)
        x += width
    y -= 30
    for index, row in enumerate(rows):
        heights = []
        for value, width in zip(row, widths):
            p = Paragraph(str(value), ParagraphStyle("measure", fontName="Open", fontSize=size, leading=size*1.4))
            heights.append(p.wrap(width - 16, 2000)[1])
        height = max(min_height, max(heights) + 15)
        assert y - height > 50, f"Table overflow page {PAGE}: {row}"
        if index % 2 == 0:
            C.setFillColor(PALE)
            C.rect(x0, y - height, sum(widths), height, fill=1, stroke=0)
        x = x0
        for value, width in zip(row, widths):
            text(str(value), x + 8, y - 6, width - 16, size=size)
            x += width
        C.setStrokeColor(LINE)
        C.line(x0, y - height, x0 + sum(widths), y - height)
        y -= height
    return y - 18


def arrow(points, label=None):
    C.setStrokeColor(GRAY)
    C.setFillColor(GRAY)
    C.setLineWidth(1)
    p = C.beginPath()
    p.moveTo(*points[0])
    for point in points[1:]:
        p.lineTo(*point)
    C.drawPath(p)
    x, y = points[-1]
    a, b = points[-2]
    dx, dy = x - a, y - b
    length = max((dx * dx + dy * dy) ** .5, 1)
    dx, dy = dx / length, dy / length
    p = C.beginPath()
    p.moveTo(x, y)
    p.lineTo(x - 6 * dx + 3 * dy, y - 6 * dy - 3 * dx)
    p.lineTo(x - 6 * dx - 3 * dy, y - 6 * dy + 3 * dx)
    p.close()
    C.drawPath(p, fill=1, stroke=0)
    if label:
        lx, ly, value = label
        text(value, lx, ly, 140, size=8.5, color=GRAY)


def box(x, y, width, height, title, detail, *, caution=False):
    C.setFillColor(colors.HexColor("#FFF3DE") if caution else colors.HexColor("#E6F3EF"))
    C.setStrokeColor(AMBER if caution else TEAL)
    C.setLineWidth(.8)
    C.roundRect(x, y, width, height, 7, fill=1, stroke=1)
    text(title, x + 8, y + height - 8, width - 16, size=10.1, bold=True, align=TA_CENTER, leading=12.5)
    if detail:
        text(detail.replace("\n", "<br/>"), x + 8, y + height - 25, width - 16,
             size=8.3, color=GRAY, align=TA_CENTER, leading=10.2)


# 1. Executive explanation.
y = page("Read this first", "An automated buyer, not a price bot",
         "What we built, what thirteen real practice negotiations revealed, and what to improve next.")
y = section("The idea in one minute", "Imagine a pump manufacturer buying metal parts. A supplier asks for a higher "
            "price. Our software reads the quote, checks what the factory needs, proposes a trade, reads the reply, "
            "and either agrees a safe deal or walks away. It compares the <b>whole cost of supplying the factory</b>, "
            "not just the number printed next to one part.", y)
y = table(["Experiment", "Average /100", "What this tells us"], [
    ["All 10 hosted problems", f"<b>{MEAN_B:.2f}</b>", "Broad baseline: one attempt at every available problem, same code."],
    ["3 random follow-ups", f"<b>{MEAN_F:.2f}</b>", "After reflection and fixes; compare with the same three earlier cases."],
    ["Same 3 before fixes", f"{MATCH_B:.2f}", "The fairer comparison, though still only one observation per version."],
], [165, 92, W - 88 - 257], y, size=9.6)
y = callout("The system is connected. Its performance is uneven.",
            "All 13 sessions produced valid deals. The architecture is working end to end, but that is not the same "
            "as consistently finding a strong deal. The full set averages 50.30, with especially weak index-linked cases. "
            "Some financial effects remain unobservable, and idle RFQ threads can time out.", y)
y = section("What changed during this task", "We finished bounded clarification and offer recovery, ran all ten cases, "
            "read every conversation, then added a request to restore a better earlier quote, stricter invitation recognition, "
            "evidence answers during questions, and a fresh server-state check before closing. Final local gate: "
            "<b>305 passed, 1 skipped, 15 subtests passed</b>.", y)
text("Reading guide: pages 2-7 explain the system; pages 8-10 explain the experiment and reflection; "
     "pages 11-12 support the next decision and reproduce the evidence. No merge, commit, push or default-agent change was made.",
     44, y, W-88, size=9.5, color=GRAY)

# 2. The game and its score.
y = page("The hackathon", "What are we trying to win?", "The supplier is simulated. The negotiation and accepted contract are real API interactions.")
y = section("Our role", "The fictional buyer is Hollerau Pumpenwerke, a German pump maker. A case gives us a part, "
            "required quantity, purchasing period, hard requirements and an alternative. One to three supplier bots respond "
            "by email. They can move prices and terms, refuse requests or stop negotiating. A <b>must-have</b> is a hard "
            "requirement, such as delivery within 42 days, that a lower price cannot override.", y)
y = section("What counts as a deal", "The structured term sheet is binding; email prose alone is not. We must accept the "
            "supplier's <b>current primary offer ID</b>. A cheaper alternative mentioned in a reply must first be confirmed "
            "as that standing offer. Missing terms may fall back to the supplier's quote PDF, not our preferred defaults.", y)
y = callout("Score = share of the available whole-cost saving", "<b>(opening cost - accepted cost) / "
            "(opening cost - hidden best cost)</b>, limited to 0-100%. A broken must-have scores zero. No deal takes the "
            "alternative's score, or zero without an alternative. A valid but unchanged opening offer can still score zero.", y)
y = table(["Simple example from the brief", "Whole cost"], [
    ["Opening: EUR 43.20, payment after 30 days", "EUR 347,904"],
    ["Deal: EUR 41.60, payment after 60 days", "EUR 332,800"],
    ["Illustrative hidden best", "EUR 324,224"],
    ["Saving 15,104 / available saving 23,680", "63.78 /100"],
], [W-88-130, 130], y)
y = section("Constraints that shape the software", "Up to three complete packages per email, ten rounds by default, "
            "and 60 seconds to respond after each supplier reply. The final has five waves with an eight-minute cap each. "
            "The runner must be unattended; it must not read final leaderboards or event feeds. The score rewards cost, "
            "not the number of citations or the length of our messages.", y)
text("Rules source: bundled brief/brief.md, brief/api.md and brief/submission.md. Server-provided practice quota is authoritative; "
     "this benchmark observed a 450-session limit, while the bundled brief says 200.", 44, y, W-88, size=9, color=GRAY)

# 3. Recognizable original architecture, with accurate status.
page("Architecture map", "The original loop, now connected", wide=True)
text("Green = implemented and exercised. Amber = implemented with important limits. Arrows show the running flow, not a new proposed architecture.",
     44, 493, W-88, size=9, color=GRAY)
box(191, 427, 150, 39, "Case opens", "Buyer need + supplier quotes")
box(165, 357, 200, 48, "Read case and documents", "PDF / CSV / email / scoped archive", caution=True)
box(38, 265, 190, 63, "Buyer-cost engine", "Cost, must-haves, alternative\nPrivate supplier health is unknown", caution=True)
box(307, 265, 190, 63, "Supplier profile", "Cash / capacity / quality / rigidity\nSourced likely, otherwise unknown", caution=True)
box(38, 176, 190, 63, "Generate valid packages", "Allowed terms + evidence-backed trades\nAll candidates checked by code")
box(307, 176, 190, 63, "Rank trade hypotheses", "Concrete give/get where supported\nNarrow rules, not mind-reading", caution=True)
box(187, 102, 165, 48, "Choose one proposal", "Original plan allowed up to three\nAlternatives now kept internally")
box(187, 50, 165, 39, "Send concise email", "Exact terms + relevant evidence")
box(563, 50, 225, 45, "Supplier responds", "Price / terms / status / documents")
box(578, 124, 195, 46, "Update evidence + history", "Never infer a hidden cost floor")
box(553, 210, 235, 65, "Another useful, safe move?", "Re-package / clarify / hold / restore\nUse cost, response and remaining moves", caution=True)
box(566, 326, 210, 61, "Accept best valid offer", "Or walk if none is safe\nOnly a fresh current standing ID")
box(559, 424, 221, 42, "RFQ: parallel supplier loops", "One global closing decision", caution=True)
arrow([(266,427),(266,405)])
arrow([(215,357),(215,343),(133,343),(133,328)])
arrow([(316,357),(316,343),(402,343),(402,328)])
arrow([(133,265),(133,239)])
arrow([(402,265),(402,239)])
arrow([(133,176),(133,163),(228,163),(228,150)])
arrow([(402,176),(402,163),(312,163),(312,150)])
arrow([(269,102),(269,89)])
arrow([(352,69),(563,69)])
arrow([(675,95),(675,124)])
arrow([(675,170),(675,210)])
arrow([(553,242),(525,242),(525,126),(352,126)], (415,146,"Yes: another move"))
arrow([(672,275),(672,326)], (685,308,"Stop / final / deadline"))
arrow([(669,424),(669,387)])

# 4. Evidence boundaries.
y = page("Components 1-3", "Read facts without inventing motives", "The profile is a small, source-linked set of hypotheses, not a psychological model.")
y = table(["Input", "What it is used for", "What it must not become"], [
    ["Supplier emails, quote PDFs, CSVs and relevant supplier letters", "Quoted terms and explicit supplier statements, with source IDs.", "A guessed cost floor, financing rate or unstated guarantee."],
    ["Buyer case and published rates", "Need, hard limits, permitted terms, total cost and reservation.", "Evidence that the supplier needs cash or has spare capacity."],
    ["Eligible buyer purchase orders / reference quotes", "An honest price-history argument when relevant and requested.", "Proof of today's supplier cost or identical commercial terms."],
], [155, 179, W-88-334], y)
y = table(["Profile dimension", "Supported example", "Policy response"], [
    ["Cash sensitive", "Supplier explicitly requests earlier payment.", "Offer earlier payment only for a lower proposed price."],
    ["Capacity sensitive", "Supplier asks for binding volume / commitment.", "Test commitment within buyer need and horizon."],
    ["Quality sensitive", "Supplier provides a numeric quality guarantee. PPM means defects per million units.", "Use permitted guaranteed terms; never invent a stricter promise."],
    ["Price rigid", "Sourced fixed-price or refusal language.", "Consider another term, not an imaginary price floor."],
], [110, 205, W-88-315], y)
y = callout("Unknown is a useful answer", "A profile field is either <b>likely</b>, with a source, or <b>unknown</b>. "
            "Unknown values keep conservative opening terms. Repairing a buyer must-have or buying needed coverage is "
            "allowed separately; neither claims to know the supplier's motivation.", y)
text("Code: arena_kit/docs.py and quote_extract.py read documents; negotiator/supplier_evidence.py and intelligence.py "
     "normalize them; supplier_profile.py applies explicit-statement rules; case_evidence.py scopes archived letters by author, "
     "supplier, part and date. Rules are mostly English. Broad OCR/locale robustness is not complete.",
     44, y, W-88, size=9.4, color=GRAY)

# 5. Economics and package generation.
y = page("Components 4-6", "A slightly higher price can be cheaper", "A package is the price plus payment, quantity, duration, delivery and other contractual terms.")
y = section("The cost engine", "The calculator adds purchase spend, uncovered need and fallback risk, financing, freight, "
            "late delivery, defects and chargebacks, tooling, index movement and index risk. It then checks every hard buyer "
            "requirement. For some strategic cases, Arena also adds a supplier-health penalty that needs private economics "
            "we do not have. Our estimate is therefore not universally exact.", y)
y = table(["Observed P03 package", "Quoted price", "Actual / modeled whole cost"], [
    ["24 months, 4,580 units/year, 30-day payment", "EUR 430.15", "EUR 3,968,442.37 before the payment trade"],
    ["Same coverage, 90-day payment", "EUR 433.08", "EUR 3,942,826.22 accepted by Arena"],
    ["Net effect", "Price rose", "Actual cost fell by EUR 25,616.15"],
], [219, 90, W-88-309], y)
y = section("How candidate packages are created", "The policy starts from the current quote, tests a few bounded opening "
            "prices, and keeps other terms unchanged unless a supported trade, buyer requirement or coverage benefit justifies a change. "
            "The generator evaluates allowed combinations. The safety selector sends only <b>one</b> complete, useful package "
            "and records the alternatives privately.", y)
y = callout("Three gates before a proposal leaves", "<b>1.</b> Every required field is present and allowed. "
            "<b>2.</b> Every buyer must-have holds. <b>3.</b> Modeled total cost stays below the reservation and available "
            "safe-offer ceiling. Previously sent exact packages are filtered. These gates do not guarantee the supplier "
            "will accept or preserve its previous offer.", y)
y = section("Two useful definitions", "<b>Reservation</b> is our maximum acceptable whole cost, derived from the buyer's "
            "alternative or fallback. <b>Index clause</b> means the price follows a named market index. Its <b>deadband</b> "
            "is the movement ignored before an adjustment applies; a larger band can reduce the buyer's price exposure.", y)
text("Code: arena_kit/cost.py is the published starter-kit arithmetic; negotiator/evaluator.py adds validation and explanations; "
     "package_policy.py chooses permitted changes; packages.py enumerates candidates; proposal_safety.py applies final limits. "
     "Unknown relationship cost remains a limitation even when every modeled gate passes.", 44, y, W-88, size=9.4, color=GRAY)

# 6. Decision loop and specialist modules.
y = page("Components 7-10", "What happens after each reply?", "The unified agent coordinates small modules; it does not ask a language model to calculate the deal.")
y = table(["Situation", "Action in plain language", "Main component"], [
    ["Terms incomplete or contradictory", "Ask a specific question. Do not guess missing values or silently waive a requirement.", "dialogue_recovery / unified"],
    ["A useful valid package exists", "Send one explicit conditional proposal, priced by total cost.", "package_policy / packages"],
    ["Supplier changes the terms after our ask", "Cost the entire change. A bounded premium can buy a useful term back.", "term_repair"],
    ["Price stalls or supplier invites a trade", "Try one costed non-price exchange, retaining at least half the modeled benefit.", "response_signal / response_trades"],
    ["A cheaper current secondary sheet exists", "Repeat its exact terms and request a primary standing offer; do not accept its secondary ID.", "supplier_alternatives"],
    ["An experiment made the offer worse", "Request the earlier quoted package once. Ask for fresh standing confirmation.", "offer_restoration<br/>(new)"],
    ["Supplier requests support for our argument", "Send eligible evidence or honestly say the ask is commercial. No invented benchmark.", "buyer_arguments"],
    ["Little benefit remains, final, or no moves", "Accept the cheapest valid current offer under reservation, or walk away.", "unified + runner"],
], [122, 239, W-88-361], y, size=9.4)
text("The opening aspiration stays anchored to the original quote, not later concessions. Threshold-based stopping normally "
     "waits for two buyer messages. Final/deadline handling overrides exploration. These are deterministic heuristics, not "
     "proven optimal settings. Clarification is capped at two recovery/trade questions per thread.", 44, y, W-88, size=10, color=GRAY)

# 7. Infrastructure and RFQ timing.
y = page("Components 11-13", "The plumbing matters as much as the strategy", "An RFQ means several suppliers competing for one contract. Only one global acceptance closes it.")
y = table(["Layer", "Responsibility", "Important boundary"], [
    ["CLI / agent factory", "Load configuration and choose unified or a comparison agent.", "supplier remains the default; unified is explicit."],
    ["HTTP client", "Authenticate, pace calls, use 180-second HTTP timeout and retry the same move ID.", "A network retry must not create a second move/session."],
    ["Runner", "Download attachments, send supplier messages concurrently and close before the wave cap.", "Parallel sends do not automatically keep idle rivals alive."],
    ["Validation harness", "Freeze source, save selection/seed, run local or hosted cases, preserve decisions and results.", "No replacement runs or score-based case filtering."],
], [97, 236, W-88-333], y)
y = callout("A real failure in the full benchmark", "In P05 one supplier agreed early while another kept negotiating. "
            "The early supplier accumulated two timeouts; an uncompetitive third supplier accumulated three and withdrew. "
            "The winning thread had none. <b>Five timeouts is not an error-free run</b>, even though the final deal was valid.", y, color=AMBER)
y = section("What the new closing check fixes", "Immediately before closing, unified fetches current server state, including "
            "timeout-generated offer IDs, and re-evaluates the deal. It cannot simply attach an old price to a new ID. "
            "An unknown or over-budget updated offer is rejected. The original unsent closing decision is marked superseded.", y)
y = section("What it does not fix", "Reading state does not reset a supplier's 60-second clock. A full per-thread scheduler "
            "and an explicit policy for retiring uncompetitive suppliers are still needed. The API does not offer a documented "
            "'park this supplier' action. Repeated keepalive emails would also consume rounds and affect the negotiation.", y)
text("Code: arena_kit/cli.py, client.py and play.py; scripts/validate_mvp.py. The starter kit supplies much of the protocol "
     "and final-wave infrastructure; our contribution is its integration with the evidence-and-cost policy.",
     44, y, W-88, size=9.4, color=GRAY)

# 8. Complete fixed-version benchmark, not the practice-best leaderboard.
y = page("Experiment A", "All ten problems: 50.30 /100", "One attempt per hosted case. Same frozen source. No replacement runs, no best-score selection.")
chart_top = y - 12
left, bar_x, bar_w = 44, 113, W-88-125
for tick in (0,25,50,75,100):
    tx = bar_x + bar_w * tick / 100
    C.setStrokeColor(LINE)
    C.line(tx, chart_top - 354, tx, chart_top + 1)
    text(str(tick), tx - 10, chart_top - 365, 30, size=9, color=GRAY)
for i,(key,record) in enumerate(B.items()):
    yy = chart_top - i*35
    text(key, left, yy, 55, bold=True)
    C.setFillColor(BLUE)
    C.rect(bar_x, yy-18, bar_w*score(record)/100, 18, fill=1, stroke=0)
    text(f"{score(record):.2f}", bar_x + bar_w*score(record)/100 + 6, yy+1, 49, size=9.7, bold=True)
text("Arena score /100 (higher is better)", bar_x, chart_top-389, bar_w, size=9, color=GRAY)
y = chart_top - 420
y = callout("Coverage is stronger than the earlier random averages", "This is a complete ten-case development benchmark. "
            "It includes the weaker cases that were absent from some earlier random batches. Do not compare 50.30 directly "
            "with a previous nine-run mean from a different mix and call the difference a regression or improvement.", y)
text(f"10/10 deals met must-haves and actual reservation. Runner/contract-audit errors: {error_count(B)}. "
     f"Recorded timeouts: {timeouts(B)}, all in P05's inactive rivals. Modeled accepted cost matched Arena to the cent in "
     "8/10 cases; the exceptions were P02 and P03's relationship component.", 44, y, W-88, size=10)

# 9. Complete conversation review.
y = page("What every conversation showed", "Successes and weaknesses, side by side", "These are observed mechanisms and limitations, not reconstructed supplier motives.")
notes = {
    "P01": "Sourced 14-day payment exchange led to 133.80. One purchase-order argument verified; acknowledgements no longer caused repeated evidence disclosure.",
    "P02": "Clarification produced a complete copper-index alternative at 348.03. Confirmation worked, but unmodeled supplier-health cost added EUR 115,648.66.",
    "P03": "A bounded higher-price / 90-day-payment exchange lowered actual cost. The oversized alternative was not chosen. Health-cost gap: EUR 259.63.",
    "P04": "The 24-month package cut cost. Price history verified but did not move the supplier further. It made a final offer at 4.88; we accepted.",
    "P05": "A 52-day quote failed the delivery limit; 42 days was repaired. Later payment raised price too far. Five idle-rival timeouts exposed stale-state risk.",
    "P07": "24-month coverage and a reciprocal counter reached 5.49. Supplier explicitly agreed; clean closing without further probing.",
    "P08": "Supplier required indexation for 24 months. Its 5% deadband alternative at 5.72 was cheaper overall than the lower-price 0% deadband offer.",
    "P10": "Opening volume was below the minimum. The sourced commitment package restored full coverage; final 31.80 / 56 days met the hard limits.",
    "P11": "Quality improved from 6,400 to 1,500 ppm. Price ended at 46.00, worse than the earlier 45.50 outcome. More generous feasibility credit needs study.",
    "P18": "The supplier insisted on indexation. It rejected a higher-price / better-deadband exchange, then made a final offer. We did not force the clause.",
}
y = table(["Case / score", "What happened and what it means"],
          [[f"<b>{key}</b><br/>{score(B[key]):.2f}", value] for key,value in notes.items()],
          [80, W-88-80], y, size=9.7, min_height=42)
text("All returned buyer and supplier messages, structured offers, statuses and argument results were reviewed, including "
     "all three P05 suppliers and their separate timeout records. A verified citation is useful evidence hygiene, not an automatic reward.",
     44, y, W-88, size=9.5, color=GRAY)

# 10. Changes and matched random results.
y = page("Experiment B", "Reflect, change, test, then run three", "The three cases were selected uniformly without replacement after the second local gate.")
y = table(["Case", "Before /100", "After /100", "Change"], [
    [key, f"{score(B[key]):.2f}", f"{score(F[key]):.2f}", f"{score(F[key])-score(B[key]):+.2f}"] for key in F
] + [["Mean", f"{MATCH_B:.2f}", f"{MEAN_F:.2f}", f"{MEAN_F-MATCH_B:+.2f}"]],
          [110, 132, 132, W-88-374], y, size=10)
y = section("Changes before these three runs", "<b>Recovery:</b> one request to renew a better prior primary quote after an "
            "unhelpful experiment; no stale-ID acceptance. <b>Language:</b> only first-hand prospective trade invitations; "
            "quoted or negated requests cannot trigger document disclosure. <b>Responsiveness:</b> answer genuine evidence "
            "requests even when our move is a question. <b>Closing:</b> fetch current remote state, then recheck safety.", y)
followup_text_path = ROOT / "output/report_support/followup_analysis.json"
assert followup_text_path.exists(), "Read all final conversations and supply analysis before publishing"
FOLLOWUP = json.loads(followup_text_path.read_text())
for key in F:
    y = section(f"{key}: {score(F[key]):.2f} /100", escape(FOLLOWUP[key]), y)
text(f"Follow-up runner/contract-audit errors: {error_count(F)}; recorded timeouts: {timeouts(F)}. "
     f"The mixed 13-run mean is {MEAN_13:.2f}, but it combines versions and repeats three cases, so it is not the headline "
     "benchmark. Practice cases are not an unseen holdout; three observations cannot establish a general causal improvement.",
     44, y, W-88, size=9.5, color=GRAY)

# 11. Decisions and operational readiness.
y = page("Next decisions", "Protect what works. Test what is uncertain.", "Do not confuse architectural completion, commercial strength and final-event readiness.")
y = table(["Priority", "Next action", "Why / proof required"], [
    ["1 - Reliability", "Add independent per-thread deadline handling and deliberate RFQ retirement/closing decisions.", "A ten-case run exposed five idle-rival timeouts. Stress-test slow and uneven replies; fresh closing alone is not enough."],
    ["2 - Strategy", "Run a predeclared matched comparison of concession / feasibility-credit settings.", "P11 regressed. Freeze one change per arm, keep every outcome, use varied synthetic inputs, never fit hidden best prices."],
    ["3 - Model limits", "Expose uncertain relationship cost in decision diagnostics; use genuine disclosed economics only.", "P02's missing component is material. Do not reverse-engineer private costs from scores or claim a guaranteed true-cost ceiling."],
    ["4 - Evidence", "Harden mixed/scanned PDFs, locale ambiguity and conflict handling in an isolated module.", "Current parsing and mostly English rules are narrow. Add fixtures and failure diagnostics before broadening inference."],
    ["5 - Deployment", "Rehearse wave deadlines and resume behavior on the final machine; prepare release data and submission.", "A good practice score does not prove eight-minute wave readiness or satisfy the repo/hash/slide submission requirements."],
], [95, 205, W-88-300], y, size=9.7)
y = callout("Keep these protections", "Unknown means unknown. No case-ID tactics or learned supplier floors. "
            "One clear proposal, complete terms, hard buyer limits, costed reciprocal trades and exact standing-offer acceptance. "
            "Keep supplier, packages and advanced runnable; do not make unified the default from these thirteen observations.", y)
text("The optional language-model (LLM) agent and evidence-priority adapter remain separate. The evaluated unified path is deterministic: "
     "it uses no LLM calls. Final-event operations described in the bundled submission guide were not executed by this task.",
     44, y, W-88, size=9.5, color=GRAY)

# 12. Evidence and reproducibility.
y = page("Audit trail", "Thirteen sessions, two frozen versions", "Replay links open the actual hosted conversations. Local files retain the complete decisions and cost audits.")
rows=[]
for phase,records_ in (("10-case",B),("Follow-up",F)):
    for key,r in records_.items():
        url=f"https://arena.tacto.ai/replay/{r['session_id']}"
        rows.append([f"{phase} / {key}", f"{score(r):.2f}", f'<link href="{url}" color="#216FA5">{r["session_id"]}</link>'])
y = table(["Run", "Score /100", "Replay ID (clickable)"],rows,[132,90,W-88-222],y,size=9.3,min_height=24)
y = text("<b>Source fingerprints</b> (working-tree versions, not committed releases)",44,y,W-88,size=10)
for label,m in (("Ten-case",MB),("Follow-up",MF)):
    y=text(f"{label}: {m['source_sha256']}",44,y-5,W-88,size=8.1,leading=11)-2
y=text(f"Git base: {MB['head']}<br/>Random follow-up seed: {MF['seed']}. "
       "Selected before opening sessions; no replacement runs.<br/>Local tests: 288 before benchmark; 305 before follow-ups; "
       "each with 1 skipped and 15 subtests passed. All four agents' S01-S03 scores stayed unchanged. "
       "Advanced remains stronger on those scripted cases; they do not model real supplier behavior.",44,y-7,W-88,size=9.1)-12
text("<b>Sources and files:</b> bundled brief/brief.md, brief/api.md, brief/submission.md; README.md, MVP_INTELLIGENCE.md, "
     "MVP_EVALUATOR.md, MVP_ROUND3_REPORT.md, MVP_CORE_CHARACTERISTICS.md; inspected implementation and tests. "
     "Run evidence: output/validation/full-suite-10-hosted/ and full-suite-followup-3-hosted/. Plan: MVP_FULL_SUITE_PLAN.md. "
     "A source hash is not a dependency or server-behavior lock. Secrets are not included in this report.",
     44,y,W-88,size=8.7,color=GRAY)
C.save()
print(f"Created {OUT} ({PAGE} pages)")
