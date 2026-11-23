# Puffco Peak Pro für Home Assistant

Inoffizielle Home-Assistant-Integration für den **Puffco Peak Pro** über Bluetooth LE (Lorax-Protokoll). Läuft lokal über den Bluetooth-Adapter von Home Assistant, ohne Cloud.

> Nicht mit Puffco verbunden. Das Protokoll ist nachgebaut – ein Firmware-Update kann die Integration jederzeit brechen. Nutzung auf eigene Gefahr.

## Was sie kann

| Typ | Entitäten |
|---|---|
| Sensoren | Akku, Ladestatus, Kammertemperatur, Status, Session-Restzeit, aktives Profil, Profil-Temperatur/-Dauer, Dabs gesamt, Dabs pro Tag, Dabs bis Akku leer, Kammer-Typ |
| Binärsensoren | Heizt, Lädt, Erreichbar |
| Steuerung | Heizen starten (mit gewähltem Startprofil), Heizen stoppen, Stimmungslicht an/aus, Startprofil-Auswahl, Jetzt abfragen |

Der Puffco erlaubt nur **eine** Bluetooth-Verbindung gleichzeitig. Die Integration verbindet sich deshalb nur kurz zum Abfragen (Standard alle 5 Minuten, während einer Session alle 15 Sekunden) und trennt danach wieder, damit die Puffco-App weiter nutzbar bleibt.

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/tomstroer-dev/ha-puffco`, Typ **Integration**.
2. „Puffco Peak Pro“ herunterladen, Home Assistant neu starten.
3. Puffco-App auf dem Handy schließen, am Puffco den Knopf halten, bis das Logo **blau** leuchtet.
4. Einstellungen → Geräte & Dienste: Der Puffco wird meist automatisch gefunden. Sonst **Integration hinzufügen → Puffco Peak Pro**.

Das Abfrageintervall lässt sich unter **Konfigurieren** ändern.

## Danke

Protokoll-Details aus öffentlicher Reverse-Engineering-Arbeit:
[Fr0st3h/PuffcoBLE](https://github.com/Fr0st3h/PuffcoBLE) (MIT),
[magikh0e/puffco-lorax-decode](https://github.com/magikh0e/puffco-lorax-decode),
[barrynewman1997-sys/puffco-remote](https://github.com/barrynewman1997-sys/puffco-remote).
