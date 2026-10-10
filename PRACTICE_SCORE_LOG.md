# Practice score log

This log deliberately separates **local controlled simulation** from hosted
Arena practice.  A local score is not a Hackathon score, and a missing replay
URL must remain missing rather than being invented.

## Current controlled batch

Agent version for every row: `b56b7ff+dirty`, `StrategicAgent` with default
settings.  Runs were executed on 2026-10-10 using the in-process local
`SimTable`; no network or hosted Arena session was opened.

| Environment | Case / scenario | Agent version | Deal | Score | Selected supplier | Key reason / outcome | Replay link | Fact review | Give/get + CTA review |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| Local simulation | `case:S01` — price increase | `b56b7ff+dirty`, strategic-default | Deal | 1.0000 | `sup:70270` | Default scripted supplier accepted the €15.72 / 90-day package. | Not persisted; rerun locally | Pass: OTD 84.6% matches `sc:70270@2026Q3` | Fail: body does not name the actual terms/trade. |
| Local simulation | `case:S02` — two-supplier RFQ | `b56b7ff+dirty`, strategic-default | Deal | 0.9901 | `sup:70340` | Final same-price package closed at €15.49 with 90-day payment and 21-day lead time. | Not persisted; rerun locally | Pass: reviewed OTD values match both scorecards. | Fail: “confirm” describes a counter-offer, not an acceptance. |
| Local simulation | `case:S03` — framework renewal | `b56b7ff+dirty`, strategic-default | Deal | 1.0000 | `sup:70520` | Default scripted supplier accepted the €215.60 package. | Not persisted; rerun locally | Pass: OTD 81.1% matches `sc:70520@2026Q3` | Fail: body does not state the exact give/get. |

### Batch result

- Controlled local score requirement: **passed** (three non-zero deals).
- Hosted-practice requirement: **not evidenced** (no credentials, session,
  replay URL, or score record is present).
- Highest-impact failure to tune next: outbound wording is generated from a
  template/profile rather than the actual differences between the attached
  term sheets.  See [QUALITY_GATE.md](QUALITY_GATE.md).

## Hosted-practice row template

Add a row immediately after each hosted case closes.  Record a replay URL only
when the Arena returned one; never place credentials or secret headers here.

| Timestamp UTC | Environment | Case / type | Agent and version | Session ID | Deal / no-deal | Score | Selected supplier | Key supplier reason | Replay URL | Fact review | Give/get + CTA review | Highest-impact failure | Next single change |
| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| _pending hosted run_ | Hosted practice |  |  |  |  |  |  |  |  |  |  |  |  |

## Reproduction command for the controlled batch

```powershell
& .\.runtime-venv\Scripts\python.exe -m arena_kit.cli simulate case:S01 --agent strategic
& .\.runtime-venv\Scripts\python.exe -m arena_kit.cli simulate case:S02 --agent strategic
& .\.runtime-venv\Scripts\python.exe -m arena_kit.cli simulate case:S03 --agent strategic
```

The local simulator's supplier is deliberately scripted.  Use it for contract
and regression checks only; inspect hosted replays for supplier reasoning and
real practice performance.
