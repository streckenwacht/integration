# Changelog

Alle Änderungen an Streckenwacht, neueste zuerst. Die Einträge entsprechen den Release-Texten auf GitHub; was auf `dev` liegt und noch nicht veröffentlicht ist, steht unter „Unveröffentlicht“.

## 0.9.2 – 2026-10-30

### Verbessert
- **Weniger Rechenarbeit im Minutentakt:** Zustand und Attribute eines Sensors werden aus denselben Daten berechnet statt zweimal (beim Sensor „Reisezeitverlust“ bisher dreimal), und das Zusammenführen doppelter Meldungen läuft direkt nach dem Abruf statt beim Aktualisieren des ersten Sensors. Anlass war eine einmalige Warnung von Home Assistant („Updating state … took 0.668 seconds“). Zustand und Attribute beziehen sich jetzt außerdem garantiert auf denselben Zeitpunkt.
- HACS zeigt Streckenwacht auch Nutzern, die in HACS Luxemburg als Land eingestellt haben (Quelle Ponts et Chaussées).

### Intern
- `astral-sh/setup-uv` 10.3.2; Dependabot schlägt Aktualisierungen jetzt für `dev` vor statt für `main`.
- Entwicklungsumgebung: Pillow 13.0.0 per uv-Override (Dependabot-Warnungen aus dem HA-Pin).
- Entwicklerdoku: einheitlicher Release-Ablauf, GitHub-Einstellungen.

## 0.9.1 – 2026-10-26

### Verbessert
- **Weniger Schreiblast, z. B. für SD-Karten im Raspberry Pi:** Streckenwacht merkt sich, welche Meldungen schon angekündigt wurden. Diese Datei (bei einem großen Stadtbereich mehrere hundert KB) wurde bisher mit fast jedem Abruf neu geschrieben, mit Staus etwa alle 15 Minuten – jetzt höchstens einmal pro Stunde. Beim Herunterfahren und beim Neuladen wird sofort gespeichert; nur nach einem Stromausfall kann eine Meldung der letzten Stunde ein zweites Mal angekündigt werden.
- Die großen Listen-Attribute `events` (Sensor „Ereignisse“), `disruptions` („Störung aktiv“) und die Beschreibung des Kalender-Termins landen nicht mehr in der Verlaufsdatenbank. Für Automationen, Vorlagen und Karten sind sie unverändert da.

### Intern
- Der wöchentliche Quellen-Check startet nicht mehr bei jedem Release-Tag mit (Pfadfilter gelten für Tags nicht).

## 0.9.0 – 2026-10-26

### Neu
- **Reisezeitverlust je Fahrtrichtung:** Der Sensor „Reisezeitverlust“ bekommt das Attribut `by_direction` – der größte aktuelle Verlust je Fahrtrichtung („Start -> Ziel“), z. B. `{"Karlsruhe -> Heidelberg": 14, "Heidelberg -> Karlsruhe": 5}`. Ein Bereich enthält meist beide Richtungsfahrbahnen; der Zustand blieb bisher das Maximum über beide, und eine Automation konnte die eigene Richtung nicht herausgreifen. Angaben an Anschlussstellen und Staus ohne Richtung werden nicht aufgeführt (dieselbe Regel wie beim Richtungsfilter der Bereiche). Zustand und bisherige Attribute bleiben unverändert.
- **Blueprint „Stau-Benachrichtigung“ mit Fahrtrichtung:** Optional zählt nur noch der Stau in der eigenen Richtung (über `by_direction`); das Fahrtziel genügt, z. B. „Heidelberg“. Ohne Angabe verhält sich der Blueprint wie bisher. Wer ihn schon nutzt, holt die neue Fassung über *Blueprint erneut importieren*.

### Intern
- Entwicklungs- und Testumgebung auf Home Assistant 2026.10.4 angehoben (Testbibliothek 0.13.375), Abhängigkeiten in `uv.lock` aktualisiert – behebt 28 der 69 Dependabot-Warnungen der Entwicklungsumgebung; die übrigen 41 betreffen Pillow, das Home Assistant 2026.10.4 selbst auf 12.3.0 festlegt. Die Integration selbst bringt keine Abhängigkeiten mit.

### Doku
- Streckenwacht ist seit dem 24.10.2026 in der Standardliste von HACS: Die README beschreibt die Installation jetzt ohne benutzerdefiniertes Repository.

## 0.8.0 – 2026-10-20

### Neu
- **Kartenkarte fasst nahe Meldungen zusammen:** Beim Herauszoomen werden Meldungen, die dicht beieinander liegen, zu Kreisen mit ihrer Anzahl zusammengefasst – farbig nach der schwersten Meldung darin. Ein Tipp auf einen Kreis zoomt hinein, ab Straßenebene erscheint jede Meldung einzeln. Abschaltbar im Karten-Editor bzw. per `cluster: false`.

### Intern
- Versionsnummer in `pyproject.toml` wird mit angehoben (Test prüft, dass sie zu `manifest.json` und `const.py` passt).
- CI bricht veraltete Läufe ab, wenn ein neuerer Push auf denselben Branch kommt.

## 0.7.2 – 2026-10-20

Wartungsrelease – an der Integration selbst ändert sich nichts.

### Geändert
- **Installation über HACS aus einer Release-Datei:** HACS lädt die Integration jetzt als `streckenwacht.zip`, die an jedem Release hängt (auch an allen älteren). Für dich ändert sich dabei nichts; GitHub kann so zählen, wie oft Streckenwacht heruntergeladen wird.
- Hintergrund: Ein wöchentlicher automatischer Check prüft jetzt alle 23 Datenquellen und meldet, wenn sich eine Quelle ändert oder ausfällt.

## 0.7.1 – 2026-10-20

Fehlerbehebung für die Streckenwacht-Kartenkarte.

### Behoben
- **„Custom element not found“ statt Karte:** Die Karte erschien vor allem in der Companion App manchmal nicht, bis man den Frontend-Cache zurücksetzte. Ursache: Eine Seite, die geöffnet wurde, während Home Assistant noch startete, kannte die Karte nicht. Streckenwacht trägt die Karte jetzt selbst als Dashboard-Ressource ein (*Einstellungen → Dashboards → ⋮ → Ressourcen*) und hält den Eintrag bei Updates aktuell. Wer Ressourcen per YAML verwaltet, bekommt die Karte wie bisher.
- **Legende verdeckt nichts mehr:** Beim Ausrichten des Ausschnitts lässt die Karte unten Platz für die Legende.

## 0.7.0 – 2026-10-19

Die Streckenwacht-Kartenkarte zeigt jetzt mehrere Bereiche auf einmal.

### Neu
- **Mehrere Bereiche in einer Karte:** z. B. „Zuhause“ und den Arbeitsweg zusammen. Im Editor wählst du die Bereiche per Mehrfachauswahl, in YAML als Liste:
  ```yaml
  type: custom:streckenwacht-map-card
  entities:
    - sensor.streckenwacht_arbeitsweg_events
    - sensor.streckenwacht_zuhause_events
  ```
  Die Karte zeigt die Kreise aller Bereiche und passt den Ausschnitt an; eine Meldung, die in mehreren Bereichen liegt, erscheint nur einmal.
- Bestehende Karten mit `entity:` laufen unverändert weiter.

## 0.6.2 – 2026-10-19

Die Streckenwacht-Kartenkarte zeigt den Bereich jetzt passender.

### Verbessert
- Halbe Zoomstufen: Der Kreis des Bereichs füllt die Karte besser aus (vorher oft eine Stufe zu weit herausgezoomt).
- Der Ausschnitt folgt dem Bereich auch, wenn sich die Größe der Karte ändert (z. B. beim Laden des Dashboards oder Drehen des Handys) – bis du selbst verschiebst oder zoomst.

## 0.6.1 – 2026-10-19

Kleine Korrekturen am Editor der Streckenwacht-Kartenkarte.

### Behoben
- Die Beschriftungen im Karten-Editor erscheinen jetzt in der Sprache von Home Assistant (vorher immer Englisch).
- „Höhe“ ist ein Zahlenfeld mit Vorgabe 400 px statt eines leeren Schiebereglers.
- Beim Hinzufügen der Karte wird der Sensor „Ereignisse“ eines Bereichs vorausgewählt; ein Fehler in der Browser-Konsole beim Anlegen ist behoben.

## 0.6.0 – 2026-10-19

Eine eigene Karte für deine Bereiche – und doppelte Meldungen erscheinen nur noch einmal.

### Neu
- **Streckenwacht-Kartenkarte** (`custom:streckenwacht-map-card`): zeigt die Meldungen eines Bereichs mit ihrer echten Geometrie – Baustellen und Sperrungen als Linien oder Flächen entlang der Straße, farbig je Art. Was in den nächsten 14 Tagen beginnt, ist blass und gestrichelt; ein Tipp zeigt Zeitraum, Beschreibung und Quelle(n). Die Karte ist nach dem Update einfach da: *Karte hinzufügen* → „Streckenwacht“. Den Kartenhintergrund lädt sie über den Kachel-Proxy von Home Assistant (ab 2026.9) – dein Browser spricht nur mit Home Assistant.
- **Doppelte Meldungen zusammenfassen:** Melden mehrere Quellen dieselbe Baustelle (in Stuttgart etwa Landesmeldestelle und Stadt), erscheint sie einmal – mit allen Quellen in Beschreibung, Namensnennung und dem neuen Attribut `also_reported_by`. Benachrichtigt wird einmal. Die Regeln sind eng (gleiche Straße, höchstens 300 m, passender Zeitraum, nur Baustellen und Sperrungen); abschaltbar unter *Konfigurieren*.
- **README:** Beispiele für die eingebaute Kartenkarte mit Symbolen statt Namenskürzeln, ein Dashboard mit Reisezeitverlust und die Langzeitstatistik pro Woche/Monat.

### Hinweis zum Update

## 0.5.0 – 2026-10-18

Mehr für Baden-Württemberg: Verkehrsmeldungen aus dem Verkehrsfunk und Freiburg.

### Neu
- **Verkehrsmeldungen der Landesmeldestelle Baden-Württemberg** (über MobiData BW): Sperrungen mit Umleitung, Unfälle, Staus und Gefahren wie Ölspuren – außerhalb der Autobahnen (die kommen weiter über die Autobahn-API), vor allem im Raum Stuttgart. Erledigte Meldungen („Unfallstelle geräumt“) werden ausgeblendet. Ergänzt die Stadt Stuttgart, deren Dienst seit dem Umzug keine Sperrungen mehr ausweist.
- **Freiburg:** größere Baustellen auf den Hauptverkehrsstraßen.

Neue Quellen werden für Bereiche in der Nähe angeboten; bestehende Bereiche nimmst du über *Bereich ändern* dazu.

### Behoben
- Bei Luxemburg (und den neuen Verkehrsmeldungen) fehlte bei manchen Meldungen der Beginn, wenn die Quelle nur ein Ende angibt.

## 0.4.0 – 2026-10-18

Mehr Abdeckung: Luxemburg und vier weitere Städte – und eine Reparatur für Stuttgart.

### Neu
- **Luxemburg:** aktuelle und geplante Baustellen auf Luxemburgs Straßen (Ponts et Chaussées, CC0) – für Grenzpendler aus Trier, dem Saarland und der Eifel.
- **Region Karlsruhe:** Baustellen mit Sperrung oder Verkehrsbehinderung in Karlsruhe und der Technologieregion.
- **Rostock**, **Kiel** und **Ingolstadt:** Baustellen der Städte (in Rostock und Ingolstadt ohne reine Gehweg- und Fassadenarbeiten).

Die neuen Quellen werden in Bereichen in der Nähe automatisch angeboten; bestehende Bereiche nimmst du über *Bereich ändern* dazu.

### Behoben
- **Stadt Stuttgart nicht erreichbar:** Die Stadt hat ihren Kartendienst umgezogen, der alte Endpunkt antwortet nicht mehr. Streckenwacht nutzt jetzt den neuen. Der liefert allerdings keine Angabe zur Verkehrsauswirkung mehr – Stuttgarter Meldungen erscheinen deshalb vorerst alle als Baustelle, Vollsperrungen sind dort nicht mehr erkennbar.

### Hinweis zum Update
Weil die Stuttgarter Meldungen jetzt anders erkannt werden, gelten sie nach dem Update einmalig als „neu“ – eine Automation auf neue Meldungen kann dabei einmal auslösen.

## 0.3.0 – 2026-10-14

Vorwarnung vor Sperrungen, eine Karte und mehr Städte in NRW.

### Neu
- **Sensor „Nächste Sperrung“:** Beginn der nächsten geplanten Sperrung im Bereich (bis 14 Tage voraus) mit Titel, Straße und Ende.
- **Blueprint „Vorwarnung vor geplanter Sperrung“:** Push-Nachricht mit frei wählbarem Vorlauf (Standard 12 Stunden) – etwa am Vorabend einer Nachtsperrung. Import-Button in der README.
- **Karte:** alle aktuellen Meldungen deiner Bereiche als Punkte auf der Kartenkarte im Dashboard (`geo_location_sources: [streckenwacht]`, Beispiel in der README). Höchstens 150 Punkte, die schwersten und nächsten zuerst.
- **Meldungsarten pro Bereich:** im ersten Schritt des Bereichsdialogs wählbar (Baustellen, Sperrungen, Staus, Unfälle, Warnungen) – z. B. ohne normale Baustellen, damit Kalender, Karte und Benachrichtigungen in einer Stadt übersichtlich bleiben.
- **Neue Städte in NRW:** Aachen, Duisburg, Münster.

### Hinweis zum Update
Bestehende Bereiche zeigen weiterhin alle Meldungsarten. Ändern kannst du das über *Bereich ändern*.

## 0.2.1 – 2026-10-14

Datenquellen werden jetzt **pro Beobachtungsbereich** gewählt – passend zur Lage des Kreises.

### Geändert
- **Bereichsdialog in Schritten:** erst Name und Kreis, dann die Datenquellen. Angeboten werden die Autobahn und alle Quellen, deren Gebiet den Kreis berührt – alle vorausgewählt (z. B. Magdeburg: Autobahn und Sachsen-Anhalt). Gibt es nur die Autobahn, entfällt der Schritt.
- **Keine globale Quellenauswahl mehr:** Unter *Konfigurieren* stehen nur noch Abrufintervall und Staumeldungen. Abgefragt wird, was irgendein Bereich nutzt.
- „Stadt Stuttgart“ wird nur noch für Bereiche in Stuttgart angeboten.

### Behoben
- In 0.2.0 tauchten die neuen Quellen im Bereichsdialog erst auf, nachdem man sie unter *Konfigurieren* eingeschaltet hatte – und es wurden Quellen angeboten, die mit dem Bereich nichts zu tun haben.

### Hinweis zum Update
Bestehende Bereiche übernehmen automatisch die bisher eingeschalteten Quellen – am Verhalten ändert sich nichts. Neue Quellen fügst du über *Bereich ändern* hinzu. Beim ersten Start werden die bekannten Meldungen einmal still neu eingelesen (keine „neu“-Meldungen).

## 0.2.0 – 2026-10-14

Streckenwacht deckt jetzt deutlich mehr von Deutschland ab – und „Störung aktiv“ ist in Städten endlich aussagekräftig.

### Neue Datenquellen
- **Norddeutschland** (LBV.SH): Schleswig-Holstein mit allen Straßenklassen und aktuellen Verkehrsstörungen inkl. Unfällen, Hamburg, Mecklenburg-Vorpommern, Bundesstraßen in Niedersachsen
- **Berlin** (VIZ): Hauptstraßen inkl. Störungen
- **Brandenburg**: Bundes-, Landes- und Kreisstraßen
- **Sachsen-Anhalt**: alle Straßen (laut Anbieter nur nichtkommerzielle Nutzung)
- **Sachsen**: alle Straßen
- **Rheinland-Pfalz** (Mobilitätsatlas): alle Straßen
- **Städte:** München, Köln (Verkehrskalender), Frankfurt am Main, Dortmund

Beim Einrichten werden die Quellen für deinen Home-Assistant-Standort vorausgewählt. Bestehende Installationen: neue Quellen unter *Geräte & Dienste → Streckenwacht → Konfigurieren* aktivieren und im Beobachtungsbereich auswählen.

### Geändert
- **„Störung aktiv“** zählt Sperrungen, die länger als 30 Tage laufen, nur noch in ihrer ersten Woche. Vorher war der Sensor in Städten wegen monatelanger Sperrungen praktisch dauernd an (z. B. Stuttgart: 29 aktive Sperrungen im Umkreis von 10 km, jetzt zählen 3). Die Sperrungen bleiben im Kalender und im Sensor „Ereignisse“ sichtbar.

### Datenschutz
Für die großen Landesquellen ohne Änderungserkennung (Norddeutschland, Brandenburg) fragt Streckenwacht einen auf etwa 55 × 35 km gerundeten Kartenausschnitt ab – der Server erfährt nur die grobe Region. Alle anderen Quellen werden komplett geladen und lokal gefiltert.

## 0.1.0 – 2026-10-05

Erstes stabiles Release – nach fünf Testversionen (b1–b5).

Streckenwacht zeigt Baustellen, Sperrungen, Staus und Unfälle für selbst definierte Beobachtungsbereiche in Home Assistant – aus drei offenen Datenquellen: Autobahn GmbH, MobiData BW und Stadt Stuttgart. Pro Bereich: Kalender, „Störung aktiv“, Anzahl der Meldungen, Reisezeitverlust und ein Event bei neuen oder beendeten Meldungen. Details und Blueprints im [README](https://github.com/streckenwacht/integration#readme).

### Neu seit v0.1.0b5
- **Ruhigere Stau-Meldungen beim Event „neu/beendet“:**
  - Die Verkehrslage vergibt für denselben Stau oft eine neue Kennung (gemessen: rund ein Drittel aller „neuen“ Staus). Ein Stau, der im selben Abruf auf derselben Autobahn und Richtung höchstens 5 km neben einem verschwundenen auftaucht, gilt jetzt als derselbe Stau – kein „beendet“ plus „neu“ mehr.
  - Staus werden erst ab der **Stau-Schwelle des Bereichs** (Standard 10 Minuten Reisezeitverlust) als neu gemeldet, und nur solche Staus auch als beendet. Sperrungen, Unfälle und Baustellen sind nicht betroffen.
- README auch auf Englisch.

### Hinweis zum Update
Beim ersten Start nach dem Update liest jeder Bereich die aktuellen Meldungen einmal still neu ein – es kommen dabei keine „neu“-Meldungen.
