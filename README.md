# Pirate Galaxy Remnant Tracker

Ein eigenständiger Remnant-Träger-Tracker für Pirate Galaxy. Er liest die Trägerliste mit einem vorhandenen Spielkonto und aktualisiert standardmäßig alle **drei Minuten** eine PNG-Statuskarte in einem oder mehreren Discord-Kanälen. Pro Webhook bleibt dieselbe Nachricht erhalten, auch nach einem Neustart. Ein laufender 3D-Client ist nicht erforderlich.

Die Karte zeigt Systemtechnologie, Beute, Planet, HP, Spawnalter und verfügbare Abflugzeiten. Geschätzte Reveal-Countdowns werden aus dem eigenen Verlauf gelernt. Ein schlanker Java-Collector liest das Spielprotokoll; Python speichert die Beobachtungen in SQLite und erzeugt die Karte.

## Voraussetzungen

- Python **3.11 oder neuer**, ein **JDK 21** und Internetzugang zum Spielserver sowie Discord.
- Die eigenen, passenden Clientbibliotheken: `PirateGalaxy-test.jar`, `log4j/*.jar` und `mina/*.jar`. Spielbibliotheken und Java werden nicht mitgeliefert.
- Ein Spielkonto mit einem Piloten auf dem ausgewählten Realm sowie mindestens ein Discord-Webhook.
- **Windows:** Sandboxie Plus für den standardmäßigen isolierten Collector.
- **Linux:** ein normaler Benutzer für den Collector; `systemd` für Autostart und Neustarts. DejaVu Sans oder Liberation Sans verbessert die Darstellung der Bildkarte.

Das geprüfte Protokollprofil ist **1002132**. Der Client-JAR muss SHA-256 `6e31366238a3cea74ce8757abfc721a4d956145566ad12b29aeff2b65abc9e66` entsprechen. Andere Builds benötigen einen neuen Kompatibilitätstest. Keine `--add-opens`-Optionen hinzufügen: Sie verändern das Verhalten der alten Serialisierung.

Der Live-Abruf wurde auf Korell (Realm 2) mit einem Account ohne Remnant-Freischaltung bestätigt. Das ist keine Zusage für andere Konten, Realms oder kommende Spielversionen. Es handelt sich um den normalen authentifizierten Spiel-RPC, nicht um eine öffentliche HTTP-API. Der Collector führt keine Flug-, Kampf- oder Missionsaktionen aus.

## Installation

Das Repository kann in einem beliebigen Verzeichnis liegen. Befehle ohne anderen Hinweis werden im Checkout ausgeführt. Relative Pfade in `config.toml` beziehen sich auf das Verzeichnis dieser Konfiguration. Das Setup erzeugt lokale Pfade passend zur jeweiligen Installation; im Repository stehen keine produktiven Zugangsdaten oder Webhook-Adressen.

### Linux

Python und JDK 21 mit der Paketverwaltung der Distribution installieren. Danach:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
cp credentials.example.env credentials.env
cp secrets.example.env secrets.env
chmod 600 credentials.env secrets.env
```

`credentials.env` mit `Name:` und `PW:` ausfüllen. `secrets.env` erhält die Discord-Webhook-URL. Beide Dateien sind von Git ausgeschlossen. Alternativ kann die Kontodatei außerhalb des Checkouts liegen.

Die eigenen Clientdateien in einem Eingabeverzeichnis bereitstellen und dessen Pfad angeben:

```sh
.venv/bin/python scripts/setup_runtime.py --backend process --game ../client-inputs --credentials credentials.env
.venv/bin/python -m pg_remnants validate
.venv/bin/python -m pg_remnants run --cycles 1 --dry-run --max-seconds 120
```

`java` und `javac` werden aus `PATH` ermittelt. Mit `--java` und `--javac` lassen sich andere Installationen auswählen; `--jre` kopiert optional eine eigene passende Laufzeit. Windows-Laufzeiten sind auf Linux nicht verwendbar. Der Prozess-Backend nutzt die Rechte des gestarteten Benutzers und ist keine Sandboxie-Sandbox.

### Windows

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
Copy-Item credentials.example.env credentials.env
Copy-Item secrets.example.env secrets.env
```

Die beiden Dateien lokal ausfüllen. Anschließend die Pfade zu den eigenen Clientdateien, der Java-Laufzeit und dem Compiler übergeben:

```powershell
.venv\Scripts\python scripts/setup_runtime.py --game ..\client-inputs --jre ..\java-runtime --javac ..\jdk\bin\javac.exe --credentials credentials.env
.venv\Scripts\python -m pg_remnants validate
.venv\Scripts\python -m pg_remnants run --cycles 1 --dry-run --max-seconds 120
```

Das Setup findet Sandboxie Plus über `%ProgramFiles%`; mit `--sandboxie-dir` kann ein anderer Installationsort angegeben werden. Es legt eine eigene Box `PirateGalaxyRemnants` an und benötigt dafür Schreibzugriff auf die Sandboxie-Konfiguration. Bestehende Boxen, Konfigurationen und Laufzeitverzeichnisse werden nicht überschrieben. Eine Sicherung der vorherigen Sandboxie-Konfiguration bleibt lokal unter `data/`.

`START.CMD`, `STATUS.CMD` und `STOP.CMD` verwenden die lokale virtuelle Umgebung, falls vorhanden, sonst `python` aus `PATH`.

## Konfiguration und mehrere Discord-Kanäle

`config.example.toml` dokumentiert die Einstellungen. Das Setup erstellt daraus eine betriebsfähige lokale Konfiguration. `server` ist die Anzeige, `realm_id` der Spiel-Realm; der Standard ist Korell/2. Intervall und Verlaufslänge sind konfigurierbar, standardmäßig 180 Sekunden und 30 Tage.

Für zwei Kanäle in `config.toml`:

```toml
[discord]
username = "Remnant Tracker"
webhook_environments = ["DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK_SECONDARY_URL"]
```

Die zugehörigen Werte nur in der ignorierten `secrets.env` oder in der Prozessumgebung hinterlegen. Die Beispieladressen sind Platzhalter. Bereits gesetzte Umgebungsvariablen haben Vorrang. Die frühere Einstellung `webhook_environment` für ein einzelnes Ziel bleibt kompatibel.

Jeder Webhook hat seine eigene Nachrichten-ID, Fehleranzeige und Veröffentlichungshistorie. Netzwerkaufrufe laufen unabhängig voneinander; ein fehlerhafter Kanal verhindert die Veröffentlichung im anderen nicht. Identische Webhooks werden zusammengefasst. Mentions sind deaktiviert. Gelöschte Statusnachrichten werden neu angelegt; bei einem normalen Neustart wird die vorhandene Nachricht weiterverwendet.

## Betrieb und Autostart

```sh
python -m pg_remnants --config config.toml run
python -m pg_remnants --config config.toml status
python -m pg_remnants --config config.toml stop
```

`--config` steht vor dem Unterbefehl. `--dry-run` meldet sich am Spielserver an und schreibt eine Vorschau, sendet aber nichts an Discord. `--cycles` und `--max-seconds` begrenzen Testläufe. Ein geregelter Stopp markiert die Karten als gestoppt; bei Verbindungsfehlern bleibt der letzte bestätigte Stand sichtbar. `status` liest eine gespeicherte Momentaufnahme – nach einem harten Prozessabbruch ist der Datenzeitstempel entscheidend.

### Linux mit systemd

Als Benutzer installieren, unter dem der Tracker laufen soll:

```sh
.venv/bin/python scripts/install_systemd.py --config config.toml
sudo loginctl enable-linger "$(id -un)"
systemctl --user start pirate-galaxy-remnants.service
systemctl --user status pirate-galaxy-remnants.service
```

Der Installer aktiviert den Dienst für den Benutzer. **`Linger=yes` ist zusätzlich erforderlich**, damit er bereits beim Hochfahren ohne interaktive Anmeldung startet und nach dem Abmelden weiterläuft. Der Installer kann dies mit `--enable-linger` selbst anfordern, sofern die lokale Berechtigung dafür ausreicht. Mit `--output` lässt sich die erzeugte Unit vorab prüfen. Der Dienst läuft ohne Root-Rechte, mit restriktiven Dateirechten und verhindert Rechteerweiterungen. Er startet bei vorübergehenden Prozessfehlern erneut; bestätigte Anmelde-/Versionsfehler benötigen eine Korrektur.

```sh
loginctl show-user "$(id -un)" -p Linger
systemctl --user is-enabled pirate-galaxy-remnants.service
journalctl --user -u pirate-galaxy-remnants.service -n 50 --no-pager
systemctl --user restart pirate-galaxy-remnants.service
systemctl --user stop pirate-galaxy-remnants.service
```

Für Windows enthalten die CMD-Dateien einen manuellen Start; sie installieren keine Autostart-Aufgabe.

### Umzug auf einen anderen Rechner

Quellcode und passende Laufzeit auf dem Ziel vorbereiten. Den bisherigen Tracker vor der ersten Spielanmeldung auf dem Ziel stoppen, damit sich beide Prozesse nicht mit demselben Konto verdrängen. Danach `data/history.sqlite3` über die SQLite-Backup-Funktion oder nach vollständig beendetem Prozess übertragen. Sie enthält den Verlauf und die Discord-Nachrichten-IDs. Kontodatei und Webhooks separat und vertraulich übertragen. Das verhindert neue doppelte Karten und erhält die gelernten Reveal-Zeiten. Den Zielbetrieb und Autostart prüfen, bevor die alte Installation entfernt wird.

## Reveal-Angaben und Datenaktualität

- **Systemtechnologie:** laut [Spielupdate vom 8. Juli 2026](https://forum.pirategalaxy.com/threads/game-update-july-8-2026.39707/) ab Spawn verfügbar. Ein noch fehlender Wert bleibt als ausstehend markiert.
- **Beute und Planet:** der geprüfte Datensatz enthält keinen zukünftigen Reveal-Termin. Die Karte zeigt ausdrücklich **geschätzte** Countdowns aus dem Verlauf. Ohne passende Messung bleibt sie im Lernzustand. Ein Anschuss kann Informationen sofort offenlegen, wie in der [offiziellen Beschreibung](https://forum.pirategalaxy.com/threads/remnants-are-coming-game-update-july-1-2026.39667/) erläutert.
- **Erstmals erfasst / Reveal-Fenster:** bereits bekannte Informationen erhalten einen Beobachtungszeitpunkt; ein gemessener Wechsel von unbekannt zu bekannt erhält das Beobachtungsintervall. Daraus wird keine exakte serverseitige Reveal-Sekunde behauptet.
- **Schätzverfahren:** Median der Mittelpunkte gemessener Zeitfenster ab Spawn, getrennt nach Realm, SC/XC und Beute/Planet. Systeme werden innerhalb eines Trägertyps gemeinsam ausgewertet. Die Karte nennt Messzahl und beobachtete Altersspanne; weniger als fünf Messungen oder mehr als zehn Minuten Streuung werden als unsicher markiert. Das ist kein statistisches Konfidenzintervall.
- **Ausschlüsse:** bereits beim ersten Abruf bekannte Werte, veraltete Daten, lange Erfassungslücken und erkennbare Kampf-Reveals trainieren die Schätzung nicht. Sichtbare HP – auch 100 % – oder ein Abflugtimer schließen einen Träger vom weiteren Lernen aus. Nicht sichtbare Kampfereignisse lassen sich nicht vollständig ausschließen.
- **Abgelaufene Schätzung:** die Information bleibt unbekannt und die Karte meldet, dass die Schätzung verstrichen ist. Tatsächliche Serverdaten haben stets Vorrang. Countdowns auf dem PNG gelten zum angezeigten Datenstand und werden bei jedem Kartenupdate erneuert; die Anzeige verwendet Europe/Berlin.

Die normale Spielsession bleibt zwischen den Abrufen geöffnet. Vor einem neuen Abruf wird geprüft, dass der alte Remnant-Objektgraph aus dem lokalen Cache freigegeben wurde. Dadurch werden keine alten Details als frische Daten ausgegeben. Misslingt die Freigabe oder wird die Verbindung getrennt, erfolgt eine normale Neuanmeldung. Der Mechanismus ist auf den geprüften Clientbuild abgestimmt. Er verändert keine Kontorechte oder Spielfelder.

## Lokale Dateien

| Datei | Inhalt |
| --- | --- |
| `config.toml` | Lokale Pfade, Backend, Realm und Webhook-Variablennamen |
| `credentials.env` / externe Kontodatei | Spielzugang; niemals veröffentlichen |
| `secrets.env` | Webhook-Geheimnisse; niemals veröffentlichen |
| `data/runtime/` | Eigene Spielbibliotheken und Laufzeitmanifest |
| `data/history.sqlite3` | Beobachtungen und Nachrichten-ID pro Webhook |
| `data/status.json` | Betriebszustand und Veröffentlichungsstatus pro Ziel |
| `data/status-card.png` | Zuletzt erzeugte Karte |
| `data/publications.jsonl` | Bestätigte Veröffentlichungen ohne Webhook-Geheimnisse |
| `data/runs/`, `data/sandbox/` | Lokale Collector-Läufe bzw. Windows-Sandbox |

Zugangsdaten werden dem Collector über seine Prozessumgebung übergeben, nicht über Befehlsargumente. Webhooks werden nicht an Java weitergereicht. Der SQLite-Verlauf wird nach der konfigurierten Dauer bereinigt; alte Laufverzeichnisse werden nicht automatisch gelöscht. Spielbibliotheken, Logs, lokale Konfigurationen und Zugangsdaten gehören nicht ins Repository.

## Entwicklung und Grenzen

```sh
python -m unittest discover -s tests -v
```

GitHub Actions prüft Windows und Linux mit Python 3.11/3.13. Die Tests decken Datenvalidierung, Verlauf, Schätzungen, Karten, Discord-Uploads, mehrere Ziele und Prozessverwaltung ab. Für die authentifizierten Live-Tests sind eigene Laufzeitdateien und Zugangsdaten erforderlich; sie laufen nicht in öffentlicher CI. Langzeitbetrieb über mehrere Tage und alle möglichen Serverwartungen ist damit nicht zugesichert.

Die MIT-Lizenz gilt für den eigenen Quellcode, nicht für die separat benötigten Spielbibliotheken. Dieses Projekt ist ein unabhängiges Community-Werkzeug.
