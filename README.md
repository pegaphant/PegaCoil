# PegaCoil

Fusion-360-Add-in, das die **Stator-Leiterplatte eines PCB-Motors** auslegt: 3-phasiger Axialfluss-Motor,
die Spulen sind Leiterbahnen auf mehreren Lagen, der Rotor trägt die Magnete.

Du gibst vor: **Außen- und Innendurchmesser und Spannung** – optional Leistung, Lagen, Spulenzahl und Kupferdicke
(sonst automatisch). Bei jeder Änderung zeigt das Fenster sofort, wie viel Watt auf diese Größe passen. PegaCoil rechnet Spulenzahl, Windungen, Bahnbreite, Widerstand, Strom, Drehmoment,
Leerlaufdrehzahl, Erwärmung und die passenden Magnete aus, zeichnet die Lagen in Fusion und speichert eine
**KiCad-Platine** (daraus in KiCad die Gerber-Dateien für die Fertigung).

## Installation

1. Ordner `PegaCoil` nach `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` kopieren
   (oder in Fusion: *Dienstprogramme → Add-Ins → Skripte und Zusatzmodule → Zusatzmodule → +* und diesen Ordner wählen).
2. In der Liste **PegaCoil** ausführen (Häkchen „Beim Start ausführen“ setzen).
3. Der Knopf **PegaCoil** liegt unter *Dienstprogramme → Zusatzmodule*.

## Roboter-Antriebe

Vorgabe ist eine **Nenndrehzahl** (z. B. 1500 U/min): PegaCoil sucht das größte **Dauer-Drehmoment** bei dieser
Drehzahl (Spannung muss die Gegenspannung bei der Nenndrehzahl noch überwinden) und nennt das **Spitzenmoment**
(Strom U/R im Stillstand, nur Sekunden – der Treiber begrenzt meist darunter). PCB-Motoren haben kein Rastmoment
und laufen dadurch völlig ruckfrei. Nenndrehzahl 0 = höchste Leistung (mit Mindestwirkungsgrad, Vorgabe 80 %).
Gerechnet wird im Hintergrund – das Fenster bleibt bedienbar, nur die letzte Eingabe zählt.

## Updates

PegaCoil schaut bei jedem Fusion-Start im Hintergrund auf GitHub nach einer neuen Version und holt sie selbst
(der Add-in-Ordner ist ein git-Klon von `pegaphant/PegaCoil`). Lokale Änderungen werden nie überschrieben – dann
wird nur angezeigt, dass es eine neue Version gibt. Oben im Fenster steht die Version (Datum des letzten Commits)
und der Stand; Rechnung und Export laufen nach einem Update sofort mit dem neuen Stand, Änderungen am Fenster
selbst nach dem nächsten Fusion-Neustart.

## Bedienung

1. Maße, Spannung und Lagen eingeben – alles rechnet sofort mit (Enter/Tab übernimmt einen Wert):
   - **Größe/Lagen/Spannung geändert** → im Feld *Motorleistung* steht, was diese Platine dauerhaft an der Welle
     schafft; darunter Aufnahme (W, A), Drehmoment, Drehzahl und das ganze Ergebnis.
   - **Motorleistung geändert** → der Außendurchmesser stellt sich auf die kleinste passende Größe ein.
2. **OK**: die Platine wird als **EAGLE-Platine** (`.brd`) ins aktive Fusion-Projekt (Ordner *PegaCoil*) geladen und
   in **Fusion Electronics** als PCB geöffnet – dort *CAM-Prozessor → Gerber*. Optional zusätzlich 3D-Skizzen ins
   aktuelle Design (geht auch in „Part Design“-Dokumenten) und eine KiCad-Datei.

## Rotor und Stapel

Mit **„Rotor & Stapel als 3D-Baugruppe“** legt PegaCoil ein neues Design an: je Rotorscheibe eine Komponente
(Träger, Magnete als einzelne Körper mit Magnetisierung im Namen, ggf. Stahlrückschluss), die Statoren als
Platzhalter-Scheiben mit Anschlussbohrungen – bei 3 Platinen schon um den Einbauwinkel verdreht – und die Welle.
Farben: rot = ↑ axial / N oben, blau = ↓ axial / S oben, gelb = tangential (Halbach).

- **Halbach**: Außenscheiben eine Lage auf 2 mm unmagnetischem Boden, innere Scheiben zwei Lagen Rücken an Rücken
  (Halbach ist nur einseitig stark). Unten ↑ → ↓ ←, oben ↑ ← ↓ → – axial gleich, tangential gegensinnig, damit
  sich beide Seiten im Spalt addieren.
- **Stahlrückschluss**: Außenscheiben 3 mm Stahl + Magnete, innere Scheiben Magnete durchgehend; alle N/S gleich.

## Wie gerechnet wird

- **Wicklung** 3 Spulen : 2 Magnetpole (z. B. 12 Spulen / 8 Pole), Spulen U V W U V W …, alle Spulen einer Phase
  in Reihe. Anschlüsse U1/U2, V1/V2, W1/W2 – Stern (U2+V2+W2 verbinden) oder Dreieck beim Anlöten.
- **Spule**: Sektor-Spirale, Lagen 1, 3, 5 … nach innen, 2, 4, 6 … gespiegelt wieder nach außen
  (Strom kreist überall gleich herum). Lagenpaare über Durchkontaktierungen in der Spulenmitte bzw. in einer
  Reihe über der Spule verbunden. Die Phasen sind außen über Bögen auf der Unterseite verkettet.
- **Kupfer** bis 13 oz (Heavy Copper, z. B. PCBWay). Mindestbahn/-abstand je Dicke (vorsichtig angenommen):
  1 oz 0,127 · 2 oz 0,2 · 3 oz 0,25 · 4 oz 0,3 · 6 oz 0,4 · 8 oz 0,5 · 10 oz 0,6 · 13 oz 0,75 mm – vor der Bestellung
  mit den Fertigerregeln abgleichen (überschreibbar unter *Erweitert*). Die Platine wird bei viel Kupfer dicker
  (Kupfer + 0,2 mm Isolierung je Lagenabstand). Innenkupfer automatisch so dick wie außen (höchstens 6 oz):
  die Lagen einer Spule liegen in Reihe, dünnes Innenkupfer kostet viel Widerstand. Via 0,3 / 0,6 mm.
- **Dauerstrom**: höchstens so viel, dass die Kupferverluste (warm) die Platine um höchstens *Max. Erwärmung*
  (40 K) erwärmen, und nie mehr als U / R.
- **Motorleistung** (an der Welle) = I · (U − I · R_warm) = Drehmoment × Drehzahl unter Last;
  **Aufnahme** = U · I (Differenz = Wärme im Kupfer).
- **Auslegung**: Für jede Kombination aus Lagen, Kupfer, Spulenzahl und Innenradius sucht PegaCoil die Windungszahl
  mit der breitesten passenden Bahn: zuerst die, die die gewünschte Leistung dauerhaft schafft, dann das größte
  Drehmoment. An der Wärmegrenze ist das Drehmoment fast unabhängig von der Windungszahl – weniger Windungen heißt
  mehr Strom und Drehzahl, also mehr Watt („höchstens … W“, begrenzt durch *Max. Leerlaufdrehzahl*, 10 000 U/min).
  Ist der Widerstand kleiner als U / Dauerstrom, muss der Treiber den Strom begrenzen (wird angezeigt).
- **Automatisch** = die Variante mit der höchsten Dauerleistung an der Welle (Lagen und Kupfer werden durchprobiert);
  schaffen mehrere die Leistung, die günstigste mit mindestens 80 % des besten Drehmoments.
- **Aufbau**: *3 Platinen (je Phase eine)* – jede Platine trägt nur eine Phase, eine Spule je Pol, Nachbarn
  gegensinnig in Reihe (Wicklungsfaktor 1), dreimal Kupfer und Kühlfläche; die 3 gleichen Platinen werden um
  240°/Spulenzahl verdreht gestapelt. Oder *1 Platine* mit allen 3 Phasen (3 Spulen : 2 Pole, Faktor 0,866).
- **Magnetfeld** aus den Magneten: Halbach beidseitig (B1 = 0,85 · 2 Br · sin(π/4)/(π/4) · (1 − e^(−k·hm)) ·
  e^(−k·g/2)) oder Magnete auf Stahlrückschluss (B1 = 4/π · Br · sin(α·π/2) · sinh(k·hm)/sinh(k·(hm + g/2))),
  k = π/Polteilung, g = Platinendicke + 2 × Luft. Mehr Pole = kürzere Polteilung = mehr Streufeld; die Polzahl
  wird mitgesucht. Gerechnet wird mit dem Mittel 2/π · B1.
- **Drehmoment**: Kt = 2 · m · k_w · B · Σ (r_außen² − r_innen²) aller radialen Leiter (m Spulen je Phase).
- **Wärme**: Wärmeübergang je Platinenseite nach *Kühlung*: ruhende Luft 12, drehende Rotorscheiben 25,
  Fahrtwind 50, Lüfter 80, Öl ruhend 100, Öl umgewälzt 300 W/(m²·K) (Richtwerte; Öl: Planschverluste nicht
  gerechnet, Wärme muss übers Gehäuse weg). Zulässiger Kupferverlust = h · 2 · Fläche · Erwärmung je Platine.
- **Lagen** werden in Gruppen geschaltet: Paare einer Gruppe parallel, Gruppen in Reihe (automatisch die beste
  Aufteilung). Parallel = mehr Querschnitt bei gleicher Windungszahl; sonst brächten mehr Lagen nur mehr Windungen.
- **Abstandsprüfung**: eigene Prüfung jeder Lage (auch zwischen Windungen derselben Spule – KiCad sieht das nicht,
  weil eine Spule ein Netz ist).

## Ohne Fusion

```
python -m pegacoil --od 60 --id 10 --volt 12 --out stator.kicad_pcb   # --power 0 = automatisch
python -m unittest discover tests
```

## Grenzen (Version 0.1)

- Nur Reihenschaltung der Spulen einer Phase, nur 3:2-Wicklung.
- Eine einzelne Durchkontaktierung je Lagenwechsel (≈ 1 A dauernd) – bei mehr Strom gibt es eine Warnung.
- In Fusion werden die Bahnmitten als Skizzen gezeichnet, nicht als 3D-Kupfer.
- Drehmoment und Erwärmung sind Schätzungen – am Prototyp nachmessen.
