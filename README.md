# Pirate Galaxy Remnant Tracker

Privater Remnant-Träger-Tracker für Pirate Galaxy. Er meldet sich mit einem vorhandenen Spielkonto an, ruft die Trägerliste alle **180 Sekunden** ab und aktualisiert **dieselbe Discord-Nachricht**. Ein laufendes 3D-Spiel ist dafür nicht erforderlich. Der kleine Java-Collector läuft in einer eigenen Sandboxie-Box; Python speichert den Verlauf und veröffentlicht die Statuskarte.

## Stand

- Getestetes Profil: **Korell, Realm 2**, Protokollversion **1002132**, Windows und Azul Java 21.
- Der Testaccount hat `skullcarrierunlocked=false` und erhält trotzdem die serverseitige Trägerliste. Das ist ein beobachtetes Verhalten dieses Accounts und Servers, keine Zusage für alle Konten oder kommende Versionen.
- Normale Anmeldung und Spielsession bleiben erforderlich. Es handelt sich um den authentifizierten RPC des Spielprotokolls, nicht um eine öffentliche HTTP-API. Der Collector umgeht keine Freischaltung und führt keine Flug-, Kampf- oder Missionsaktionen aus.
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

`--dry-run` meldet sich am Spielserver an und schreibt `data/preview.json`, sendet aber nichts an Discord. Ein begrenzter Lauf markiert die Karte am Ende als gestoppt. `--config` muss vor dem Unterbefehl stehen.

## Installation auf einem anderen Windows-PC

Benötigt werden Python 3.11+, Sandboxie Plus, ein JDK 21 mit `javac.exe`, die lokal vorhandene getestete Java-21-Laufzeit und passende Client-JARs. Python hat keine zusätzlichen Laufzeitabhängigkeiten. Die Spiel- und Java-Binärdateien werden nicht in diesem Repository verteilt.

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

## Dateien und Datenschutz

| Datei | Zweck |
| --- | --- |
| `config.toml` | Lokale Pfade, Realm, Intervall und Discord-Anzeigename |
| `secrets.env` | Privater Webhook; nicht versioniert |
| `data/runtime/` | Lokal kopierte Clientbibliotheken und Java-Laufzeit |
| `data/history.sqlite3` | Verlauf und Discord-Nachrichten-ID |
| `data/status.json` | Letzter Betriebsstatus |
| `data/publications.jsonl` | Bestätigte Discord-POST/PATCH-Vorgänge ohne Webhook-Geheimnis |
| `data/runs/` und `data/sandbox/` | Lokale Collector-Läufe und Sandbox-Ausgaben |
| `data/tracker.log` | Rotierendes Betriebslog |

Zugangsdaten werden aus der externen Datei gelesen und dem Collector über seine Prozessumgebung übergeben. Sie stehen nicht in Befehlsargumenten oder eingecheckten Dateien. Der Discord-Webhook wird nicht an den Java-Collector weitergegeben. Lokale Prozessumgebung und Datendateien sind weiterhin durch die Windows-Kontorechte zu schützen. Verlauf, Spielbibliotheken, Zugangsdaten und Webhook gehören nicht ins Git-Repository. Der 30-Tage-Verlauf begrenzt die SQLite-Snapshots; alte Laufverzeichnisse werden nicht automatisch gelöscht.

## Aufbau und Grenzen

`collector/` implementiert normale Anmeldung, Realm-Wechsel, Session-Lebenszyklus und den wiederholten Aufruf `getSkullCarrierContainer()`. `src/pg_remnants/` validiert die Antworten, bildet Änderungen, speichert sie transaktional und publiziert die Discord-Karte. Das Intervall wird zwischen echten RPC-Aufrufen gemessen; ein lokal ablaufender Countdown allein gilt nicht als Aktualisierungsnachweis.

Die erste Veröffentlichung nutzt `POST ?wait=true`, weitere Aktualisierungen `PATCH /messages/{id}` gemäß der [Discord-Webhook-Dokumentation](https://docs.discord.com/developers/resources/webhook). Gelöschte Nachrichten werden neu erstellt. Ungültige Webhooks werden nicht durch neue Nachrichtenversuche kaschiert; 429-Antworten beachten `retry_after`. Mentions sind deaktiviert. Nach einer mehrdeutigen Netzwerkunterbrechung beim allerersten POST kann Discord eine Nachricht bereits angenommen haben, ohne dass ihre ID lokal ankommt; ein späterer Versuch kann dann eine zusätzliche Karte erzeugen.

Das Projekt ist eine erste getestete Implementierung. Dauerbetrieb über Wartungsfenster, AFK-Abmeldungen und mehrere Tage ist noch nicht nachgewiesen. Es benötigt eine laufende authentifizierte Session und die lokalen Bibliotheken. Das gleiche Konto parallel im Spiel zu verwenden, kann die Session verdrängen. Weitere Realms sind konfigurierbar, wurden aber nicht live geprüft. Es gibt derzeit keine Container-/Linux-Betriebsvariante und keinen Bot mit Discord-Befehlen.

## Entwicklung

```powershell
python -m unittest discover -s tests -v
```

Die Offline-Tests prüfen Validierung, unbekannte Werte, Verlauf, Wiederaufnahme der Nachrichten-ID, Discord-Fehlerfälle und den begrenzten Service-Lebenszyklus. GitHub Actions führt sie auf Windows und Linux mit Python 3.11 und 3.13 aus; der Live-Collector selbst wird nur lokal mit den privaten Laufzeitdateien geprüft. Die MIT-Lizenz betrifft den eigenen Quellcode dieses Repositorys, nicht die separat benötigten Spielbibliotheken.
