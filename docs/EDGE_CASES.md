# Edge-Case-Katalog (Spezifikation)

Dieses Dokument ist die Spezifikation, aus der die Tests entstehen. Jeder Fall hat eine ID
(`EC-xx`). Jeder Test in `tests/` nennt die ID, die er absichert, und jedes Modul nennt die IDs,
die es behandelt. Ändert sich eine Regel, ändert sich zuerst dieses Dokument, dann der Test,
dann der Code.

**Maßgeblich ist die Ground Truth.** Widerspricht eine Regel hier der öffentlichen 5-Minuten-GT,
wird die Regel angepasst (CHALLENGE.md: "if your reading of the definition disagrees with it,
the ground truth is right"). Die GT dient nur zum Verstehen der Definition, nie zum Tunen.

**Regel-Grenze (RULES.md):** Keine Konstanten oder Regeln, die an bestimmte Frames des
Barça-Spiels gebunden sind. Alle Schwellenwerte unten sind Parameter, die auf Fremdspielen
(Metrica-Sample-Daten, ggf. DFL/IDSSE) getunt werden.

---

## Grundbegriffe

| Begriff | Bedeutung |
|---|---|
| **Zustände** | `H`, `A`, `D` pro Frame. `X` nur als Ausgabe ("keine Aussage"), nie als Zustand. |
| **Ballbesitzphase** | maximale Folge von `H` oder von `A`. `D` trennt Phasen immer. |
| **Kontakt** | Ball innerhalb `R_TOUCH` eines Spielers bei lokalem Abstandsminimum oder Richtungs-/Tempowechsel des Balls. |
| **Kontrolle** | Team T kontrolliert den Ball, wenn (a) ein T-Spieler ihn mind. `T_CTRL` innerhalb `R_CTRL` führt, **oder** (b) ein T-Spieler ihn erfolgreich zu einem T-Mitspieler spielt, **oder** (c) der Torwart von T ihn aufnimmt (EC-13). |
| **Wechsel** | Ballbesitz geht nur bei bestätigter **Kontrolle** des anderen Teams über. Lose Bälle, Abpraller, Ablenkungen und Duelle ohne Kontrolle ändern nichts (CHALLENGE.md). |
| **Rückdatierung** | Ist ein Wechsel bestätigt, beginnt die neue Phase beim **ersten Kontakt** der Kontrollsequenz, nicht beim Bestätigungszeitpunkt. Wir rechnen offline über das ganze Spiel. |
| **Restart** | Ende einer `D`-Phase: der erste Frame, in dem der ruhende Ball durch den Ausführenden in Bewegung kommt (Ausnahme Einwurf: EC-05). |

### Startparameter (werden auf Fremdspielen getunt)

| Parameter | Start | Bedeutung |
|---|---|---|
| `R_TOUCH` | 1,0 m | Ballabstand für einen Kontakt |
| `R_CTRL` | 1,5 m | Ballabstand für Ballführung |
| `T_CTRL` | 0,4 s (10 Frames) | Mindestdauer Ballführung für Kontrolle |
| `V_FLIGHT` | 12 m/s | Ballgeschwindigkeit, ab der ein Ball "unterwegs" ist (Pass, Schuss, Flugball) |
| `R_CROWD` / `N_CROWD` | 3 m / 4 Spieler | Gedränge: mind. `N_CROWD` Spieler beider Teams im Radius |
| `V_STILL` / `T_STILL` | 1,0 m/s / 2 s | mittlere Spielergeschwindigkeit, unter der eine Unterbrechung wahrscheinlich ist |
| `OUT_MARGIN` | 0,5 m | Ball muss so weit hinter der Linie sein, um als "aus" zu gelten (Rauschen) |
| `T_GAP_X` | 0,5 s | Ballverlust innerhalb einer Phase, ab dem wir `X` statt einer Schätzung ausgeben |

---

## A. Von euch genannt

### EC-01 Gedränge bei Standards (Ecke, Freistoß in Tornähe)

- **Situation:** Viele Spieler an einer Stelle. Der Ball ist weder klar kontrolliert noch klar
  frei, der nächste Spieler wechselt ständig.
- **Signale:** Gedränge-Index (Spieler beider Teams in `R_CROWD`), vorangehender Restart
  (EC-06), Smart Tagging `SET PIECES` mit `Type` Corner/Free Kick, `PLAYERS IN THE BOX`.
- **Soll:** Ballbesitz bleibt beim **ausführenden Team**, bis das andere Team **Kontrolle**
  zeigt. Während des Gedränges keine Wechsel aus "nächster Spieler". Bei Unsicherheit `X`
  (kostet auf spellF1 innerhalb einer Phase nichts).
- **Grenze:** Klärender Kopfball ist kein Wechsel. Geht er ins Aus: `D` (EC-22). Sichert der
  Verteidiger danach den Ball: Wechsel, rückdatiert auf seinen ersten Kontakt.
- **Testszene:** Ecke von H, 8 Spieler im Fünfer, Ball pendelt zwischen H- und A-Spielern
  ohne Ballführung, dann (a) H köpft aufs Tor ins Aus, (b) A klärt, A-Spieler nimmt an und
  dribbelt.

### EC-02 Lange Pässe, Abschläge, Flanken

- **Situation:** Ball 1–4 s in der Luft, oft nicht getrackt. Unter der Flugbahn steht
  zufällig ein Gegner, der "nächste Spieler" ist also falsch.
- **Signale:** Abspielgeschwindigkeit > `V_FLIGHT`, kein Spieler in `R_TOUCH`, Ball verschwindet
  kurz nach dem Abspiel, Smart Tagging `LONG BALL`.
- **Soll:** Während der Flugphase bleibt der Ball beim **abspielenden Team**. Entschieden wird
  bei der Annahme: Annahme durch Mitspieler, keine Änderung. Kontrolle durch Gegner, Wechsel ab
  dessen erstem Kontakt. Kopfballduell ohne anschließende Kontrolle, kein Wechsel
  (CHALLENGE.md).
- **Grenze:** Torwart-Abstoß ist zuerst ein Restart (EC-06), dann ein langer Ball.
- **Testszene:** H spielt 40-m-Ball, Ball fehlt 2 s, A-Spieler unter der Flugbahn, (a) H-Spieler
  nimmt an, (b) A-Spieler köpft weg ohne Kontrolle, H sichert, (c) A nimmt an und spielt Pass.

### EC-03 Schüsse

- **Situation:** Schneller Ball Richtung Tor, danach Tor, Aus, Parade, Block oder Abpraller.
- **Signale:** Ballgeschwindigkeit > `V_FLIGHT` mit Richtung Torraum, Ballposition hinter der
  Torlinie, Torwartposition (Torwart = Spieler, der sich im eigenen Strafraum am nächsten zum Tor
  aufhält; keine IDs vorhanden).
- **Soll:**
  - Tor: `D` ab Überqueren der Linie bis Anstoß (EC-09).
  - Ins Aus (Abstoß/Ecke): `D` ab Überqueren der Linie.
  - Torwart fängt: Wechsel (Kontrolle), rückdatiert auf den Fang.
  - Parade oder Block ohne Kontrolle: kein Wechsel. Wer den Abpraller kontrolliert, bekommt
    den Ball.
- **Testszene:** Schuss von H, (a) Tor, (b) neben das Tor, (c) Torwart fängt, (d) Torwart
  pariert, H staubt ab, (e) Verteidiger blockt, A sichert.

### EC-04 Zweikämpfe

- **Situation:** Spieler beider Teams sehr nah am Ball, der nächste Spieler wechselt im
  Frametakt.
- **Signale:** zwei Teams in `R_TOUCH`, Ballgeschwindigkeit niedrig, schnelle Wechsel des
  nächsten Spielers.
- **Soll:** Hysterese, Ballbesitz bleibt beim bisherigen Team, bis das andere Team Kontrolle
  zeigt (wegdribbeln oder Pass zum Mitspieler). Während des Duells `X`.
- **Grenze:** Foul im Duell, Pfiff: `D` (EC-07). Ball geht ins Aus: `D` (EC-22).
- **Testszene:** H dribbelt, A attackiert, 1,5 s Gerangel, (a) H behauptet sich, (b) A erobert
  und spielt ab, (c) Ball springt ins Aus.

### EC-05 Einwurf

- **Situation:** Ball über der Seitenlinie, Einwerfer steht an der Linie.
- **Soll (eure Regel):** `D` bis der Ball **wieder im Spielfeld** ist, dann das Team des
  Einwerfenden. Smart Tagging hat hier immer `Team = N/A`, das Team kommt also aus dem
  Tracking: Spieler, der direkt an der Linie beim Ball steht. Fallback: Team des ersten
  Ballkontakts im Feld.
- **Grenze:** Einwurf direkt zum Gegner: kurze Phase des Einwerfers, dann Wechsel bei
  Kontrolle durch Gegner.
- **Testszene:** Ball geht bei y < 0 ins Aus, 8 s Stillstand, H-Spieler an der Linie, Ball
  kommt ins Feld, H-Mitspieler nimmt an.
- **Offen (Frage F1):** Endet `D` in der GT beim Wiedereintritt oder schon beim Abwurf? Kann
  sich das wegen Tracking-Rauschen an der Linie unterscheiden?

---

## B. Weitere Fälle

### Toter Ball

#### EC-06 Restarts: Ecke, Freistoß, Abstoß, Anstoß, Elfmeter
- **Soll:** `D` endet, wenn der ruhende Ball in Bewegung kommt. Das Team ist das des
  Ausführenden. Smart Tagging `SET PIECES` liefert Typ und Team (außer Einwurf) als Beleg,
  nicht als Antwort.
- **Testszene:** Ball liegt 6 s still an der Eckfahne, ein H-Spieler daneben, dann Flanke.

#### EC-07 Pfiff ohne Aus (Foul, Abseits, Verletzung, Handspiel)
- **Situation:** Ball bleibt im Feld, ist aber tot. Das schwierigste `D`.
- **Signale:** Mittlere Spielergeschwindigkeit fällt unter `V_STILL` für mind. `T_STILL`, Ball
  langsam oder ruhend, danach ein Restart-Muster (Ball ruht an einer Stelle, ein Spieler daneben,
  Mauer bei Freistoß).
- **Soll:** `D` ab dem Moment, in dem die Verlangsamung beginnt, bis zum Restart.
- **Grenze:** Den genauen Pfiff-Frame kennen wir nicht. Wir nehmen den Beginn der kollektiven
  Verlangsamung. **Offen (Frage F2):** Wann beginnt `D` in der GT bei einem Foul?
- **Testszene:** Spiel läuft, alle 22 Spieler bremsen innerhalb 1 s auf < 1 m/s, Ball ruht 15 s,
  dann Freistoß.

#### EC-08 Vorteil
- **Soll:** Kein `D`, wenn nach einer kurzen Verlangsamung das Spiel ohne ruhenden Ball
  weiterläuft. Unterscheidung zu EC-07: kein Restart-Muster, Ball bleibt in Bewegung.
- **Testszene:** Kurzes Abbremsen von 4 Spielern, Ball rollt weiter, H spielt weiter.

#### EC-09 Tor
- **Soll:** `D` ab Überqueren der Torlinie bis zum Anstoß (Ball am Mittelpunkt, Teams in den
  eigenen Hälften). Jubel und Rückweg sind Teil der `D`-Phase.

#### EC-10 Lange Unterbrechungen (Wechsel, VAR, Verletzung, Trinkpause)
- **Soll:** `D` über die gesamte Pause. Fehlender Ball über lange Zeit plus Stillstand ist hier
  ein starkes Signal, kein Rauschen.

#### EC-11 Halbzeitbeginn
- **Soll:** Die bewerteten Frames der 2. Halbzeit beginnen vor dem Anstoß. Alles bis zum
  Anstoß ist `D`. Den Anstoß erkennen wir **algorithmisch** (Ball am Mittelpunkt, Teams getrennt
  in ihren Hälften, dann Ball in Bewegung), nicht über eine feste Framezahl.

#### EC-12 Zweiter Ball, Ball neben dem Feld
- **Situation:** Das Tracking sieht einen Ball außerhalb des Felds, während gespielt wird
  (Balljunge, Ersatzball), oder springt zwischen zwei Bällen.
- **Soll:** Ballpositionen weit außerhalb des Felds mit unplausiblem Sprung (Geschwindigkeit
  > physikalisch möglich) werden verworfen, nicht als Aus gewertet.

#### EC-22 Ball über der Linie, Rauschen an der Linie
- **Soll:** Aus erst, wenn der Ball mindestens `OUT_MARGIN` hinter der Linie ist oder dort
  verschwindet und danach ein Restart-Muster folgt. Zurückdatieren auf den Linienübertritt.
- **Testszene:** Ball rollt entlang der Seitenlinie mit ±0,3 m Rauschen, bleibt im Spiel.

### Ballbesitz

#### EC-13 Torwart hält den Ball
- **Soll:** Kontrolle des Torwart-Teams, auch wenn Gegner in der Nähe stehen. Der Ball ruht
  nahe dem Torwart, Gegner ziehen sich zurück.

#### EC-14 Abfangen mit Direktpass
- **Soll:** Ein Kontakt eines B-Spielers, danach direkter Pass zu einem B-Mitspieler, ist ein
  Wechsel (Kontrolle über Variante (b)), obwohl `T_CTRL` nicht erreicht wird.
- **Testszene:** H-Pass, A-Spieler fängt ab, spielt sofort zu A-Mitspieler.

#### EC-15 Ball in der Luft über einem Spieler
- **Soll:** Liegt der Ball in einer Flugphase (EC-02), zählt die Nähe zu Spielern nicht als
  Kontakt, solange Ballgeschwindigkeit und -richtung sich nicht ändern.

#### EC-16 Abgefälschter Pass, der ankommt
- **Soll:** Kein Wechsel. Kurzer Kontakt des Gegners ohne Kontrolle ändert nichts.

#### EC-17 Schiedsrichterball, Ball trifft Schiedsrichter
- **Soll:** Schiedsrichterball wie Restart (EC-06). Ball prallt vom Schiedsrichter ab: Behandlung
  wie loser Ball. Schiedsrichter sind evtl. als Track enthalten (EC-19).

### Tracking-Probleme

#### EC-18 Ball fehlt lange während eines Übergangs
- **Soll:** Bei Lücken innerhalb einer klaren Phase `X` (wird auf spellF1 mit dem letzten Label
  gefüllt). Bei Lücken mit Wechsel-Indizien (Teamformation dreht von Angriff auf Verteidigung)
  muss der Decoder den Wechsel **in** der Lücke platzieren, am wahrscheinlichsten Punkt.
- **Kollektive Signale ohne Ball:** Ausdehnung beider Teams, Bewegungsrichtung der
  Teamschwerpunkte, Pressing-Muster.

#### EC-19 Tracking-Artefakte
- **Situationen:** doppelte Tracks, Slot mit falscher Teamzuordnung, Schiedsrichter oder
  sich aufwärmende Spieler als Track, mehr als 22 Objekte.
- **Soll:** Robuste Features, also keine Entscheidung an einem einzelnen Track. Tracks
  außerhalb des Felds ignorieren. Duplikate (zwei Tracks < 0,5 m, gleiches Team) zusammenfassen.

### Metrik

#### EC-20 Sehr kurze echte Ballbesitzphasen
- **Bewusster Kompromiss:** Die Hysterese verschluckt Phasen unter ca. 1 s. Eine erfundene
  Phase kostet Precision, eine verpasste Recall. Auf Fremdspielen messen, was sich lohnt.

#### EC-21 Halbzeitränder und X-Füllung
- **Soll:** Am Anfang einer Halbzeit wird `X` **rückwärts** gefüllt. Der erste Frame jeder
  Halbzeit bekommt daher immer ein echtes Label (`D` vor dem Anstoß). Phasen laufen nie über
  die Halbzeitpause.

---

## Fragen an euch

Bitte in den öffentlichen 5 Minuten bzw. in den Metadaten nachsehen und mir **nur die Antwort**
schicken, keine Daten-Auszüge.

| # | Frage |
|---|---|
| F1 | Einwurf: Endet `D` in der GT beim Wiedereintritt des Balls ins Feld oder schon beim Abwurf? |
| F2 | Foul ohne Aus: Beginnt `D` beim Pfiff bzw. Abbremsen oder erst, wenn der Ball zur Ruhe kommt? |
| F3 | Gibt es in den 5 Minuten Phasen unter 1 s (z. B. kurzer Ballgewinn, sofort verloren)? Wie viele ungefähr? |
| F4 | Kippt das GT-Label bei Duellen oder Abprallern kurz zum anderen Team, oder bleibt es stabil? |
| F5 | ATD-Format: Wie viele Werte hat die Ball-Gruppe pro Zeile (nur x,y,Geschwindigkeit oder auch Höhe/Status/Besitzer)? Welche Kanäle nennt die Metadaten-XML? |
| F6 | Sind Schiedsrichter oder Ersatzspieler als Track enthalten (Slots, die keinem der beiden Teams gehören)? |

Für F5 und F6 schreibe ich ein kleines Skript, das nur die **Struktur** ausgibt (Feldanzahlen,
Kanalnamen), keine Werte.
