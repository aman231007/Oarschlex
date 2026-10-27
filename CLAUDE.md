# Oarschlex – Anleitung für KI-Agenten

Wir lösen **More than a Hack 2027, Phase 1**: Für jeden der 199.319 Frames eines Spiels
(Barça–Athletic) sagen, wer den Ball hat (`H`/`A`), ob er tot ist (`D`) oder `X`.
Gewertet nach **spellF1** (ganze Ballbesitzphasen). Abgabe **17.11.2026**.

Mehrere Personen arbeiten parallel, jede mit eigenem Agenten. **GitHub-Issues sind unser
gemeinsames Gedächtnis.** Lies vor jeder Arbeit:

1. dieses Dokument,
2. [docs/PLAN.md](docs/PLAN.md) – Architektur, Schnittstellen, Arbeitspakete,
3. [docs/EDGE_CASES.md](docs/EDGE_CASES.md) – die Spezifikation (EC-IDs),
4. das Issue, an dem du arbeitest, **mit allen Kommentaren**.

Offizielle Regeln: README.md, CHALLENGE.md, EVALUATION.md, RULES.md, FAQ.md (vom Upstream).

---

## Harte Regeln – nie brechen

1. **Keine Matchdaten lesen.** Nichts unter `data/` öffnen, ausgeben, mit `@` anhängen oder
   durch Skripte laufen lassen, deren Ausgabe Werte daraus zeigt. Die Teilnahmebedingungen
   verbieten, Daten oder Auszüge an ein Cloud-LLM zu geben – Verstoß = Disqualifikation.
   Wir entwickeln mit **synthetischen Szenen** (`possession/synth.py`) und **Fremdspielen**.
   Auf echten Daten startet ein **Mensch** die Skripte; zurück kommen nur Kennzahlen (Scores,
   Anzahlen, Dauern), die der Mensch freigibt. Braucht eine Aufgabe das, Label `braucht-mensch`.
2. **Keine Handlabels und kein Training auf BAR-ATH.** Auch nicht "nur zur Validierung" oder
   zum Wählen von Parametern (Upstream-Issue #10), und auch nicht mit dem gelieferten Tracking
   als automatischen Labels (Upstream #2). Video ansehen, um Regeln zu *verstehen*, ist ok
   (Upstream #14) – aber keine Konstanten oder Regeln, die an bestimmte Frames gebunden sind.
3. **Tunen nur auf Fremdspielen** (IDSSE, Metrica-Sample). Die öffentlichen 5 Minuten nur zum
   Prüfen, ob die Pipeline korrekt ist.
4. **Bitgenau reproduzierbar** (Upstream #11): CPU, gepinnte Versionen
   (`requirements-dev.txt`), feste Seeds, keine Abhängigkeit von Dict-/Set-Reihenfolge, Zeit
   oder Hash. Trainierte Gewichte und Zwischenergebnisse dürfen committet werden, mit dem
   Skript, das sie erzeugt (Upstream #14).
5. **`gh` nur gegen `aman231007/Oarschlex`.** Der Klon hat auch `upstream` =
   `metrica-sports/more-than-a-hack-2027` (öffentlich!). Dort nie Issues, PRs oder Kommentare
   anlegen. Einmal pro Klon: `gh repo set-default aman231007/Oarschlex`.
6. **`data/` nie committen.** Vor jedem Commit `git status` prüfen.
7. **Fremddaten zitieren.** IDSSE ist CC BY 4.0 – Zitat in README und technischem Dokument.

---

## Arbeitsablauf

Eine Person schreibt dir zum Beispiel:

- **"Nimm Issue #12"** → genau dieses Issue.
- **"Nimm das nächste freie Issue"** → wähle so:
  `gh issue list --label status:bereit --search "no:assignee" --json number,title,labels,milestone`
  Nimm das mit dem frühesten Meilenstein, darin `prio:hoch` zuerst, dann die kleinste Nummer.
  Prüfe "Hängt ab von": Ist ein genanntes Issue noch offen, nimm ein anderes.
- **"Was ist der Stand?"** → fasse offene/laufende Issues und PRs zusammen.

Dann:

1. **Übernehmen**
   `gh issue edit N --add-assignee @me --remove-label status:bereit --add-label status:in-arbeit`
   und Kommentar: wer übernimmt, welcher Branch.
2. **Branch** `issue-N-kurzname` vom aktuellen `main` (`git pull` vorher).
3. **TDD**: Ändert sich Verhalten, zuerst `docs/EDGE_CASES.md` anpassen. Dann Tests schreiben
   und rot sehen, dann Code bis grün. Testnamen und Docstrings nennen die EC-IDs.
4. **Prüfen**: `.venv/Scripts/python -m pytest -q` grün. Danach einen Review-Agenten über den
   Diff laufen lassen und Befunde einarbeiten oder als Issue anlegen.
5. **PR** mit `Closes #N`, kurzer Zusammenfassung, Testergebnis. Issue-Label auf
   `status:review`. Nicht selbst mergen, außer die Person sagt es.
6. **Alles, was dir auffällt, wird ein Issue** – nicht nur im Chat erwähnen:
   Bug → `typ:bug`, fehlender Test → `typ:test`, Erkenntnis → `typ:erkenntnis`,
   Frage an Menschen → `typ:frage` + `braucht-mensch`. Immer `bereich:*` setzen und auf
   verwandte Issues verlinken. Vorher suchen, ob es schon eins gibt (`gh issue list --search`).
7. **Ergebnisse von Läufen auf echten Daten** (nur freigegebene Kennzahlen) als Kommentar ins
   passende Issue. So sieht jeder Agent sie später.

Wenn du blockiert bist: Kommentar ins Issue, Label `status:blockiert`, Person informieren.

---

## Labels

| Gruppe | Labels |
|---|---|
| Typ | `typ:feature` `typ:bug` `typ:test` `typ:erkenntnis` `typ:frage` `typ:epic` |
| Bereich | `bereich:fundament` `bereich:daten` `bereich:validierung` `bereich:totball` `bereich:ballbesitz` `bereich:decoder` `bereich:abgabe` |
| Status | `status:bereit` `status:in-arbeit` `status:review` `status:blockiert` |
| Sonstiges | `braucht-mensch` `prio:hoch` `prio:optional` |

Meilensteine: **Woche 1 – Fundament** (bis 03.11.), **Woche 2 – Ballbesitz** (bis 10.11.),
**Woche 3 – Abgabe** (bis 17.11.).

---

## Befehle

```bash
py -3.14 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python evaluation/validate_submission.py <datei>.csv   # vor jeder Abgabe
```

## Konventionen

- Code, Kommentare, Docstrings: Englisch. Doku und Issues: Deutsch.
- Paket `possession/`, Tests `tests/test_<modul>.py`. numpy zuerst, keine neuen Abhängigkeiten
  ohne Issue.
- Einheiten: Meter, Sekunden, Frames (25 fps). Koordinaten wie in `possession/types.py`.
- Alle Schwellenwerte als benannte Parameter mit Startwert (siehe EDGE_CASES.md), nie als
  Zahl mitten im Code.
- Jedes Modul nennt im Docstring die EC-IDs, die es behandelt.
