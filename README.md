# Pirate Galaxy Remnant Tracker

Privater Remnant-Träger-Tracker für Pirate Galaxy. Er meldet sich mit einem vorhandenen Spielkonto an, ruft die Trägerliste alle **180 Sekunden** ab und aktualisiert **dieselbe Discord-Nachricht** mit einer eigenen PNG-Karte im Stil des Remnant-Fensters. Ein laufendes 3D-Spiel ist dafür nicht erforderlich. Der kleine Java-Collector läuft in einer eigenen Sandboxie-Box; Python speichert den Verlauf und veröffentlicht die Statuskarte.

## Stand

- Getestetes Profil: **Korell, Realm 2**, Protokollversion **1002132**, Windows und Azul Java 21.
- Der Testaccount hat `skullcarrierunlocked=false` und erhält trotzdem die serverseitige Trägerliste. Das ist ein beobachtetes Verhalten dieses Accounts und Servers, keine Zusage für alle Konten oder kommende Versionen.
- Für jeden Abruf wird eine neue normale Spielsession geöffnet und danach geschlossen. Es handelt sich um den authentifizierten RPC des Spielprotokolls, nicht um eine öffentliche HTTP-API. Der Collector umgeht keine Freischaltung und führt keine Flug-, Kampf- oder Missionsaktionen aus.
- HP, Planet und Abflug bleiben **unbekannt**, wenn der Server sie nicht liefert. Ein verschwundener Eintrag heißt „nicht mehr gelistet“, nicht automatisch „zerstört“.
- SQLite speichert vollständige Snapshots und Änderungen für standardmäßig 30 Tage. Die Discord-Karte zeigt bis zu 15 Träger; eine Kürzung wird angezeigt.
- Bei Verbindungsproblemen oder einem geregelten Stopp bleibt der letzte bestätigte Stand sichtbar und wird entsprechend markiert. Vorübergehende Verbindungsfehler führen zu erneuter Anmeldung mit Wartezeit; Anmelde- und Versionsfehler stoppen den Collector.

## Auf dem eingerichteten PC

Checkout: `D:\PirateGalaxyRemnantTracker`.

- **`START.CMD`**: dauerhaft starten; das Terminal offen lassen.
- **`STATUS.CMD`**: zuletzt gespeicherten Betriebsstatus anzeigen.
- **`STOP.CMD`**: laufenden Tracker geordnet stoppen und die Discord-Karte kennzeichnen.

Es wird keine Autostart-Aufgabe installiert. Für Dauerbetrieb muss der PC laufen und der Prozess gestartet sein. `STATUS.CMD` zeigt eine gespeicherte Momentaufnahme; nach einem harten Prozessabbruch kann diese veraltet sein. Der sichtbare Datenstand in Discord bleibt deshalb immer mit Zeitstempel versehen. Die Nachricht wird beim Neustart anhand ihrer lokal gespeicherten ID weiterverwendet.

```powershell
python scripts/tracker.py validate
python scripts/tracker.py run --cycles 1 --dry-run --max-seconds 120
python scripts/tracker.py run --cycles 2 --max-seconds 480
python scripts/tracker.py run
python scripts/tracker.py stop
```

`--dry-run` meldet sich am Spielserver an und schreibt `data/preview.json` sowie `data/status-card.png`, sendet aber nichts an Discord. Ein begrenzter Lauf markiert die Karte am Ende als gestoppt. `--config` muss vor dem Unterbefehl stehen.

## Installation auf einem anderen Windows-PC

Benötigt werden Python 3.11+, Sandboxie Plus, ein JDK 21 mit `javac.exe`, die lokal vorhandene getestete Java-21-Laufzeit und passende Client-JARs. Die Bildkarte benötigt Pillow 12.2.0; `tzdata` liefert die Zeitzone Europe/Berlin. Installiere die Python-Abhängigkeiten mit `python -m pip install -e .`. Die Spiel- und Java-Binärdateien werden nicht in diesem Repository verteilt.

1. Repository auschecken. Das Client-Eingabeverzeichnis muss `PirateGalaxy-test.jar` sowie die Verzeichnisse `log4j/` und `mina/` mit den zugehörigen JARs enthalten.
2. Zugangsdaten außerhalb des Repositorys in einer Datei mit `Name:` und `PW:` hinterlegen.
3. Einmalig die lokale Laufzeit und die dedizierte Sandbox vorbereiten:

```powershell
python scripts/setup_runtime.py --game 'C:\private\pg-inputs' --jre 'C:\private\zulu21-jre' --javac 'C:\private\jdk21\bin\javac.exe' --credentials 'C:\private\PG Cred.txt'
```

Das Setup kopiert diese lokalen Eingaben nach `data/runtime`, legt die Box `PirateGalaxyRemnants` an und schreibt `config.toml`. Dafür muss die Sandboxie-Konfiguration schreibbar sein. Bestehende Sandbox-Abschnitte werden auf unveränderten Inhalt geprüft; eine Sicherung liegt anschließend unter `data/Sandboxie-before.ini`. Das Setup ist für eine neue Installation gedacht und verweigert das Ersetzen einer vorhandenen Java-Laufzeit oder Box. Nach einem abgebrochenen Setup zuerst den vorhandenen Zustand prüfen.

4. `secrets.example.env` nach `secrets.env` kopieren und dort den eigenen Discord-Webhook eintragen. Alternativ die Umgebungsvariable `DISCORD_WEBHOOK_URL` setzen; ein bereits gesetzter Wert hat Vorrang.
5. Serverbezeichnung, Realm und Pfade in `config.toml` prüfen, `validate` ausführen und einen begrenzten Test starten.

**Kompatibilität:** Der getestete Client-JAR hat SHA-256 `6e31366238a3cea74ce8757abfc721a4d956145566ad12b29aeff2b65abc9e66`. Andere Builds erfordern Anpassung und einen erneuten Protokolltest. Keine `--add-opens`-Optionen ergänzen: Sie verändern das Verhalten der alten Serialisierung. Der Collector startet weder den Spieleinstiegspunkt noch die native Grafik-Engine.

## Bildkarte und Reveal-Zeiten

Die Karte zeigt Träger nach Spawn sortiert, goldene SC- und violette XC-Markierungen, Systemtechnologie, Beute, Planet, HP-Balken sowie Spawnalter und gegebenenfalls Abflugzeit. PNG-Anhänge werden bei jeder Aktualisierung ausgetauscht; die Nachrichten-ID bleibt erhalten. Ein Zeitstempel im Dateinamen verhindert, dass Discord eine alte Bildversion aus seinem Cache anzeigt. Alle Bildzeiten gelten für Europe/Berlin; eingebrannte Countdowns gelten zum angegebenen Datenstand, nicht als sekundengenau laufende Uhr.

Für die Reveal-Angaben werden Daten und Beobachtung getrennt:

- **Systemtechnologie:** laut [Spielupdate vom 8. Juli 2026](https://forum.pirategalaxy.com/threads/game-update-july-8-2026.39707/) ab Spawn verfügbar. Wenn der aktuelle Abruf noch keinen Wert enthält, steht dort „Meldung ausstehend“; es wird keine eigene Systemzuordnung geraten.
- **Beute und Planet:** der geprüfte `aiq`/`ait`-Datensatz enthält keinen zukünftigen Reveal-Termin. Die Karte zeigt aus dem Verlauf gelernte, ausdrücklich geschätzte Countdowns. Ohne passenden Messwert steht dort „Lerne Reveal-Zeit · noch keine Messung“. Die [offizielle Beschreibung](https://forum.pirategalaxy.com/threads/remnants-are-coming-game-update-july-1-2026.39667/) beschreibt auch automatische Informationsfreigaben und das sofortige Offenlegen aller Informationen beim Anschuss. „Beute nach Anschuss“ ist die vertraute Forge-Beschriftung, keine Behauptung, dass es ausschließlich diesen Auslöser gibt.
- **Erstmals erfasst:** Zeitpunkt, an dem der Tracker einen Wert erstmals beobachtet hat. Bereits vorhandene Informationen werden nicht rückwirkend als frischer Reveal ausgegeben.
- **Reveal-Zeitfenster:** nur wenn ein verlässlicher frischer Abruf vorher keinen Wert hatte und ein späterer ihn enthält, wird das Beobachtungsintervall angezeigt. Das Intervall kann bei Ausfällen länger als drei Minuten sein. Es ist keine exakte serverseitige Reveal-Sekunde.

### Lernen aus dem Verlauf (0.3.0)

Die Schätzung ist der Median der Mittelpunkte gemessener Reveal-Fenster relativ zum Spawn. Die zusätzliche Zeile zeigt Anzahl `n` und die gesamte beobachtete Altersspanne. Unter fünf Messungen oder bei mehr als zehn Minuten Streuung steht ausdrücklich „unsicher“. Das ist eine Heuristik mit kleinem Datensatz, kein statistisches Konfidenzintervall und kein bestätigter Spieltimer.

Beute und Planet sowie SC und XC werden getrennt gelernt, ebenso die Realms. Systeme werden innerhalb eines Trägertyps gemeinsam ausgewertet; mögliche Systemunterschiede sind mit dem bisherigen Verlauf nicht geklärt. Nur Übergänge von unbekannt zu bekannt zwischen zwei nachweislich frischen Abrufen zählen. Beim 3-Minuten-Takt darf das Fenster höchstens 6,5 Minuten umfassen. Bereits beim ersten Beobachten bekannte Informationen, verschwundene Träger, alte Cache-Abrufe und erkennbare Kampf-Reveals zählen nicht: Sobald bei einem Träger HP (auch 100 %) oder ein Abflugtimer sichtbar waren, lernt er keine automatischen Reveal-Zeiten mehr. Nicht sichtbare Kampfereignisse lassen sich damit nicht vollständig ausschließen.

Neue bestätigte Daten haben immer Vorrang. Nach Ablauf einer Schätzung steht „Schätzung … verstrichen · offen“; der Tracker erfindet keine Beute und keinen Planeten und verschiebt die Frist nicht künstlich. Bei Verbindungsproblemen wird nur die geschätzte Uhrzeit mit „letzter Stand“ ausgegeben. Die Schätzungen werden nach jedem Abruf erneuert, nach Neustarts aus dem gespeicherten Verlauf rekonstruiert und auf die konfigurierte Aufbewahrungsdauer begrenzt.

### Sitzung behalten und frische Daten abrufen (0.3.0)

In 0.2.0 war eine normale Neuanmeldung pro Abruf der nachgewiesene Weg zu frischen Details. Innerhalb einer Sitzung hatte die Clientbibliothek registrierte Remnant-Objekte wiederverwendet; für den getesteten Account ohne Freischaltung kamen nicht alle Detailänderungen an. Reine RPC- und Discord-Zeitstempel waren deshalb kein Beleg für frische Felder. Alte Cache-Abrufe werden weiterhin nicht als verlässliche untere Reveal-Grenzen oder Lernwerte behandelt.

Der Collector behält jetzt die normale Anmeldung. Er kopiert nach jedem RPC nur die erlaubten einfachen Datenwerte und hält vom Remnant-Objektgraphen anschließend ausschließlich schwache Referenzen. Vor dem nächsten Abruf lässt er die vorhandenen Bibliotheksroutinen abgelaufene Serialisierungsreferenzen (20 Sekunden) und freigegebene Objekte bereinigen. Er prüft **alle** zugehörigen Remotes auf tatsächliche Freigabe und die Entfernung ihrer IDs aus der lokalen Registry. Es werden keine Registry-Einträge manuell gelöscht, keine Spielfelder verändert und keine zusätzlichen Kontorechte angefordert.

Nur ein neuer Login oder die geprüfte Freigabe des alten Graphen erlaubt einen als frisch markierten Snapshot. Wenn die Freigabe misslingt, folgt eine normale Neuanmeldung als Rückfall. Verbindungsabbrüche führen ebenfalls zu einem neuen Login; technische Fehler nutzen den bestehenden verzögerten Wiederholungsablauf. Die Bereinigung ist auf die geprüfte Clientversion zugeschnitten und wird zusammen mit deren Hash überprüft. Es laufen weder Renderer noch 3D-Client.

Bei störungsfreiem Dauerbetrieb entfällt dadurch die Anmeldung alle drei Minuten. Der vorherige Ablauf bedeutete 480 Anmeldezyklen pro Tag und wegen Bootstrap plus Realm bis zu 960 `credentialLogin`-Aufrufe. Weiterhin nötig sind ein Remnant-RPC alle drei Minuten und der normale Verbindungsverkehr. Die tatsächliche Serverlast oder Kosten pro Anfrage sind nicht messbar; eine Aussage über eine Überlastung wäre unbelegt.

## Dateien und Datenschutz

| Datei | Zweck |
| --- | --- |
| `config.toml` | Lokale Pfade, Realm, Intervall und Discord-Anzeigename |
| `secrets.env` | Privater Webhook; nicht versioniert |
| `data/runtime/` | Lokal kopierte Clientbibliotheken und Java-Laufzeit |
| `data/history.sqlite3` | Verlauf und Discord-Nachrichten-ID |
| `data/status.json` | Letzter Betriebsstatus |
| `data/status-card.png` | Zuletzt erzeugte Discord-Bildkarte |
| `data/publications.jsonl` | Bestätigte Discord-POST/PATCH-Vorgänge ohne Webhook-Geheimnis |
| `data/runs/` und `data/sandbox/` | Lokale Collector-Läufe und Sandbox-Ausgaben |
| `data/tracker.log` | Rotierendes Betriebslog |

Zugangsdaten werden aus der externen Datei gelesen und dem Collector über seine Prozessumgebung übergeben. Sie stehen nicht in Befehlsargumenten oder eingecheckten Dateien. Der Discord-Webhook wird nicht an den Java-Collector weitergegeben. Lokale Prozessumgebung und Datendateien sind weiterhin durch die Windows-Kontorechte zu schützen. Verlauf, Spielbibliotheken, Zugangsdaten und Webhook gehören nicht ins Git-Repository. Der 30-Tage-Verlauf begrenzt die SQLite-Snapshots; alte Laufverzeichnisse werden nicht automatisch gelöscht.

## Aufbau und Grenzen

`collector/` implementiert normale Anmeldung, Realm-Wechsel, Session-Lebenszyklus und den Aufruf `getSkullCarrierContainer()` in einer wiederverwendeten Session mit geprüftem frischem Remnant-Objektgraphen. `src/pg_remnants/` validiert die Antworten, bildet Änderungen, speichert sie transaktional und publiziert die Discord-Karte. Das Intervall wird zwischen echten RPC-Aufrufen gemessen; ein lokal ablaufender Countdown allein gilt nicht als Aktualisierungsnachweis.

Die erste Veröffentlichung nutzt `POST ?wait=true`, weitere Aktualisierungen `PATCH /messages/{id}` gemäß der [Discord-Webhook-Dokumentation](https://docs.discord.com/developers/resources/webhook). Gelöschte Nachrichten werden neu erstellt. Ungültige Webhooks werden nicht durch neue Nachrichtenversuche kaschiert; 429-Antworten beachten `retry_after`. Mentions sind deaktiviert. Nach einer mehrdeutigen Netzwerkunterbrechung beim allerersten POST kann Discord eine Nachricht bereits angenommen haben, ohne dass ihre ID lokal ankommt; ein späterer Versuch kann dann eine zusätzliche Karte erzeugen.

Das Projekt ist eine erste getestete Implementierung. Dauerbetrieb über Wartungsfenster, AFK-Abmeldungen und mehrere Tage ist noch nicht nachgewiesen. Es benötigt die lokalen Bibliotheken; neue Anmeldungen bleiben für den Start, Verbindungsabbrüche und den Cache-Rückfall erforderlich. Das gleiche Konto parallel im Spiel zu verwenden, kann die Session verdrängen. Weitere Realms sind konfigurierbar, wurden aber nicht live geprüft. Es gibt derzeit keine Container-/Linux-Betriebsvariante und keinen Bot mit Discord-Befehlen.

## Entwicklung

```powershell
python -m unittest discover -s tests -v
```

Die Offline-Tests prüfen Validierung, unbekannte Werte, Verlauf und dessen Migration, Reveal-Beobachtungen, Zeitzonen, PNG-Erzeugung, binären Multipart-Upload, Austausch des Bildanhangs, Wiederaufnahme der Nachrichten-ID, Discord-Fehlerfälle und den begrenzten Service-Lebenszyklus. GitHub Actions führt sie auf Windows und Linux mit Python 3.11 und 3.13 aus; der Live-Collector selbst wird nur lokal mit den privaten Laufzeitdateien geprüft. Die MIT-Lizenz betrifft den eigenen Quellcode dieses Repositorys, nicht die separat benötigten Spielbibliotheken.
