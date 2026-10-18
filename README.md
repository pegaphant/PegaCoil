# PegaCoil

Fusion-360-Add-in, das die **Stator-Leiterplatte eines PCB-Motors** auslegt: 3-phasiger Axialfluss-Motor,
die Spulen sind Leiterbahnen auf mehreren Lagen, der Rotor trägt die Magnete.

Du gibst vor: **Außen- und Innendurchmesser, Leistung, Spannung** – optional Lagen, Spulenzahl und Kupferdicke
(sonst automatisch). PegaCoil rechnet Spulenzahl, Windungen, Bahnbreite, Widerstand, Strom, Drehmoment,
Leerlaufdrehzahl, Erwärmung und die passenden Magnete aus, zeichnet die Lagen in Fusion und speichert eine
**KiCad-Platine** (daraus in KiCad die Gerber-Dateien für die Fertigung).

## Installation

1. Ordner `PegaCoil` nach `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` kopieren
   (oder in Fusion: *Dienstprogramme → Add-Ins → Skripte und Zusatzmodule → Zusatzmodule → +* und diesen Ordner wählen).
2. In der Liste **PegaCoil** ausführen (Häkchen „Beim Start ausführen“ setzen).
3. Der Knopf **PegaCoil** liegt unter *Dienstprogramme → Zusatzmodule*.

## Bedienung

1. Maße, Leistung (W) und Spannung (V) eingeben, **Berechnen** drücken – das Ergebnis erscheint im Fenster,
   samt Vergleich der Lagenzahlen.
2. **OK**: zeichnet die Platine in Fusion (eigene Komponente, eine Skizze je Lage mit den Bahnmitten) und speichert
   auf Wunsch die `.kicad_pcb` und einen Bericht `_Auslegung.txt`.
3. In KiCad öffnen → *Datei → Fertigungsdateien → Gerber* (Lagen F.Cu, In*.Cu, B.Cu, Masken, Edge.Cuts) und Bohrdatei.

## Wie gerechnet wird

- **Wicklung** 3 Spulen : 2 Magnetpole (z. B. 12 Spulen / 8 Pole), Spulen U V W U V W …, alle Spulen einer Phase
  in Reihe. Anschlüsse U1/U2, V1/V2, W1/W2 – Stern (U2+V2+W2 verbinden) oder Dreieck beim Anlöten.
- **Spule**: Sektor-Spirale, Lagen 1, 3, 5 … nach innen, 2, 4, 6 … gespiegelt wieder nach außen
  (Strom kreist überall gleich herum). Lagenpaare über Durchkontaktierungen in der Spulenmitte bzw. in einer
  Reihe über der Spule verbunden. Die Phasen sind außen über Bögen auf der Unterseite verkettet.
- **Fertigungsregeln** (vorsichtig, JLCPCB-tauglich): 1 oz → 0,127 / 0,127 mm, 2 oz → 0,2 / 0,2 mm,
  Via 0,3 / 0,6 mm. Innenlagen standardmäßig 0,5 oz (Vorgabe bei 4/6/8 Lagen).
- **Auslegung**: Ziel-Widerstand zwischen zwei Anschlüssen = U² / P (Anlaufstrom = P / U). Für jede Kombination aus
  Lagen, Kupfer, Spulenzahl und Innenradius sucht PegaCoil die Windungszahl mit der breitesten passenden Bahn und
  nimmt die mit dem größten Anlaufmoment. Ist der Widerstand kleiner als das Ziel, muss der Treiber den Strom
  begrenzen (wird angezeigt).
- **Automatisch** = die günstigste Variante (Lagen, 2 oz kostet extra) mit mindestens 80 % des besten Drehmoments.
- **Drehmoment** (Schätzung): Kt = 2 · (Spulen/3) · 0,866 · B · Σ (r_außen² − r_innen²) aller radialen Leiter.
  B = Flussdichte im Luftspalt (Vorgabe 0,3 T: N52-Magnete, ~1 mm Spalt, mit Rückschluss eher 0,4–0,5 T).
- **Wärme**: ruhende Luft, beide Seiten, h ≈ 12 W/(m²·K). Die angegebene Leistung fällt beim Anlauf komplett als
  Wärme an – Dauerleistung steht im Ergebnis.
- **Abstandsprüfung**: eigene Prüfung jeder Lage (auch zwischen Windungen derselben Spule – KiCad sieht das nicht,
  weil eine Spule ein Netz ist).

## Ohne Fusion

```
python -m pegacoil --od 60 --id 10 --power 10 --volt 12 --out stator.kicad_pcb
python -m unittest discover tests
```

## Grenzen (Version 0.1)

- Nur Reihenschaltung der Spulen einer Phase, nur 3:2-Wicklung.
- Eine einzelne Durchkontaktierung je Lagenwechsel (≈ 1 A dauernd) – bei mehr Strom gibt es eine Warnung.
- In Fusion werden die Bahnmitten als Skizzen gezeichnet, nicht als 3D-Kupfer.
- Drehmoment und Erwärmung sind Schätzungen – am Prototyp nachmessen.
