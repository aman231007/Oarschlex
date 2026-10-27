# Plan: Überblick, Architektur, Arbeitspakete

Stand 27.10.2026. Der Plan ist die Landkarte, die Issues sind die Aufgaben. Ändert sich der
Plan, wird diese Datei per PR angepasst und das Roadmap-Issue #1 aktualisiert.

## Was wir wissen

- **Metrik:** spellF1 zählt ganze Ballbesitzphasen (IoU 0,3–0,7). 1 s Versatz kostet ca. 35 %.
  `D` trennt Phasen, Unterbrechungen sind also genauso wichtig wie das Team.
- **`X`:** wird für spellF1 mit dem letzten Label aufgefüllt. Mitten in einer Phase gratis,
  an Übergängen teuer.
- **Daten:** Ball fehlt in 41 % der bewerteten Frames, Tracks ohne Identität, 46 Slots.
- **Offline erlaubt** (Upstream #15): Zukünftige Frames dürfen genutzt werden. Wir
  rückdatieren Wechsel auf den ersten Kontakt.
- **Fremddaten:** IDSSE (7 Bundesliga-Spiele, CC BY 4.0, Hugging Face `pysport/idsse-data`)
  ist vom Veranstalter ausdrücklich erlaubt (Upstream #16). Ihr Tracking hat pro Frame
  BallStatus und BallPossession – derselbe Mechanismus, aus dem unsere Ground Truth stammt.
  Dazu Metrica-Sample-Daten (gleiches EPTS-Format wie unsere ATD).
- **Verboten:** Handlabels oder Training auf BAR-ATH, Tunen auf den 5 öffentlichen Minuten.

## Architektur

```
 ATD (.txt/.xml) ─► io_atd ─┐
 Smart Tagging ──► io_tagging ─┐
 Fremdspiele ──► external/* ─► degrade ─┐   (nur für Tests/Tuning)
                            │  │        │
                            ▼  │        ▼
                         Match (types.py)  ◄── synth.py (Testszenen)
                            │
                  ball.py (Bereinigung, kurze Lücken)
                            │
                  features.py (Abstände, Gedränge, Teamtempo, Form …)
                            │
        ┌───────────────────┼───────────────────────┐
        ▼                   ▼                       ▼
  evidence/dead_ball   evidence/control      evidence/tagging, pitch_control, shape
        └───────────────────┼───────────────────────┘
                            ▼
                   Evidence (types.py)
                            │
                  decoder.py (HSMM/Viterbi, 5 Zustände: H, H~, A, A~, D)
                            │
                  refine.py (Grenzen rückdatieren, X-Politik)
                            │
                  make_submission.py ─► CSV ─► validate_submission.py
```

`H~`/`A~` sind "umkämpft, zuletzt H/A": Sie geben das bisherige Team oder `X` aus und bilden
die Hysterese aus EC-01/EC-04 ab.

## Schnittstellen (Vertrag für paralleles Arbeiten)

Definiert in `possession/types.py` (Issue #2). Wer ein Modul baut, hält sich daran; Änderungen
nur per Issue.

- **`Match`**: `fps`, `pitch=(Länge, Breite)` in m, `ball` `(n, 2)` m mit NaN für fehlend,
  `players` `(n, k, 2)` m mit NaN, `team` `(k,)` int8 (0 Heim, 1 Auswärts, -1 sonst),
  `halves` `((halbzeit, erster, letzter Frame), …)`. Ursprung: Eckpunkt, x entlang der Länge.
- **Labels**: `np.ndarray` mit `"H" "A" "D" "X"`, Länge `n`.
- **`Evidence`**: benannte Kanäle, jeweils `(n,)` float, NaN = keine Aussage:
  `dead` (P(Ball tot)), `home` (P(Heim hat Ball | Ball lebt)); dazu Ereigniskanäle `(n,)` int8:
  `control` (Team, dessen bestätigte Kontrolle in diesem Frame beginnt, sonst -1) und
  `touch` (Team, das in diesem Frame den Ball berührt, sonst -1). Weitere Kanäle per Issue.
- **Testszenen**: `synth` liefert `SyntheticCase(match, expected, care, note)`. `care` markiert
  Frames, die bewertet werden; Frames nahe einer Grenze dürfen tolerant sein.

## Arbeitspakete und parallele Spuren

Nach #2 und #3 laufen fünf Spuren unabhängig. Jede Spur kann ein eigener Agent übernehmen.

| Spur | Issues | Ergebnis |
|---|---|---|
| **0 Fundament** | #2 Datenmodell, #3 Szenen-Generator | Vertrag + Testdaten für alle |
| **A Daten** | #6 ATD-Loader, #7 Smart-Tagging-Loader | echte Daten als `Match` |
| **B Validierung** | #8 IDSSE, #9 Metrica, #10 Degradierung, #11 Tuning-Harness | Testfeld zum Tunen |
| **C Totball** | #13 Features, #14 Totball-Belege, #12 Ballbereinigung | `Evidence.dead` |
| **D Ballbesitz** | #15 Kontrolle, #19 Pitch Control, #20 Form ohne Ball, #21 Tagging | `Evidence.home/control` |
| **E Decoder** | #16 HSMM, #17 Grenzen + X, #18 Pipeline | Labels + CSV |
| **Menschen** | #4 Daten + Baseline, #5 Fragen F1–F7, #25 Abgabe | Daten, Antworten, Upload |
| **Abschluss** | #22 Pfiff (optional), #23 Broadcast (optional), #24 Doku | Ausbau, Dokument |

Abhängigkeiten stehen in jedem Issue unter "Hängt ab von".

## Zeitplan

| Meilenstein | Zeitraum | Ziel |
|---|---|---|
| Woche 1 – Fundament | 28.10.–03.11. | #2–#11, #13, #14, #16, erste Version #18: **erste gültige Abgabe** |
| Woche 2 – Ballbesitz | 04.11.–10.11. | #12, #15, #17, #19–#21, Tuning auf Fremdspielen |
| Woche 3 – Abgabe | 11.11.–17.11. | Ablationen, #22–#24, **Code-Freeze 15.11.**, #25 Abgabe am 16.11. |

## Für Menschen: so startet ihr einen Agenten

Öffnet Claude Code im Repo-Ordner und schreibt einfach:

> Nimm das nächste freie Issue.

oder

> Nimm Issue #14.

Der Agent liest CLAUDE.md, übernimmt das Issue, arbeitet testgetrieben, öffnet einen PR und
legt alles, was ihm auffällt, als neues Issue an. Issues mit `braucht-mensch` sind für euch:
Sie brauchen die echten Daten oder eine Entscheidung.
