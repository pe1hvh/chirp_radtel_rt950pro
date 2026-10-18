# RT-950 Pro — CHIRP-driver: geheugenkaart en status (bijgewerkt 18-10-2026)

Radio: Radtel RT-950 Pro, firmware 0.29 (10 x 99 zones). Vendor CPS: RT-950PRO_CPS v1.3.3 (20260622).
Basis: experimentele driver van 2E0NBS (NathanBarguss/Chirp_Radtel-RT-950-Pro @254d2cd, MIT), aangepast.

## Eigen repo
- Naam: `chirp-radtel-rt950pro`, één schone eerste commit (0.1.0), auteur PE1HVH, MIT met copyright Nathan Barguss 2025 + PE1HVH 2026. Geen Claude-regels in de commit.
- Inhoud: radtel_rt950pro.py (één bestand), LICENSE, README (Engels), CHANGELOG, docs/memory-map.md, docs/protocol.md, tools/ (find_zone_names, make_sample_image, chirp_list_left), tests/ (neutrale testset: VHF-LOCAL en UHF-LOCAL).
- Installatie in README: (1) Help → Load module from issue 12180 (per sessie, alleen zolang issue open, waarschuwing "not a recognized CHIRP developer"); (2) kopiëren naar `~/.local/share/pipx/venvs/chirp/lib/python3.*/site-packages/chirp/drivers/` (kan weg zijn na herinstallatie/nieuwe Python-versie; niet voor Windows-installer).
- Geen dependencies behalve CHIRP (met pyserial); pytest alleen voor tests; Python ≥ 3.10.

## Codekwaliteit (18-10-2026)
- pylint 10.00/10 (standaardinstellingen, max 100 tekens), pydocstyle Google-conventie schoon, pydoc werkt met en zonder CHIRP en zonder pyserial.
- Eén `__all__` met de hele publieke API (eerder overschreef de laatste `__all__ = ["RT950ProRadio"]` de rest, waardoor pydoc alleen die klasse toonde).
- Docstrings in Google-stijl voor alle klassen, functies (ook private en geneste) en module-constanten.
- Gedrag aantoonbaar ongewijzigd: AST-diff zonder docstrings toont alleen bedoelde wijzigingen; old/new-vergelijking via echte CHIRP (lezen, memories, set_memory, zones, settings, write-plan) byte-identiek.
- Opgeloste latente fout: `get_logger` bestond niet (NameError bij transport zonder logger).
- CHIRP's eigen stijlcheck (tools/cpep8.py, pep8/flake8) gebruikt 79 tekens; voor een PR nog herformatteren.

## Op de echte radio bevestigd (Hans)
| Adres / cmd | Inhoud | Lezen | Schrijven |
|---|---|---|---|
| 0x52/0x57 0x0000–0x7BBF | 990 kanalen x 32 bytes = 10 zones x 99 (zone n kanaal k = plek (n-1)*99+k) | ok | ok |
| 0x52/0x57 0x8000, 0x9000, 0xA000, 0xB000, 0xD000 | VFO, functie, DTMF, modulatie | ok | ok |
| 0x52/0x57 0xC000–0xC09F | 10 zonenamen x 16 bytes (NoodNetOv op 0xC000 … ZoneTen op 0xC090) | ok | ok |
| 0x54/0x58 0x0000 | APRS (128 bytes) | ok | ok met 0x58 (geschreven en teruggelezen); 0x55 geeft GEEN ACK |

0xC800 (zonenamen bij de RT-920) is NIET het adres bij de RT-950 Pro.
Op Hans' radio is 0x7800–0x7FFF volledig 0xFF (lege kanalen 961–990).
DCS-lijst in de driver: 210 codes; index 1–105 = N, 106–210 = I (polariteit "I", niet CHIRP's "R").

## Uit de CPS-changelog (RT-950PRO_CPS, primaire bron: startmelding CPS v1.3.3)
- v1.0.5 (20250916): "channel division" toegevoegd; v1.2.0 (20251114): zonenamen bewerken + CHIRP-CSV-export; v1.1.0/1.1.1 (okt 2025): CHIRP-CSV-import.
- v1.2.1 (20251129): kanaalgeheugen van 960 (15 zones x 64) naar 990 (10 zones x 99). Zones bestonden dus al vóór 0.24, alleen als 15 x 64.
- v1.2.2 (20251203): opslagstructuur gewijzigd; CPS-bestanden van vóór 1.2.2 openen niet meer.
- v1.3.0 (20260209) en v1.3.3 (20260622): nieuwe instellingen (rx interruption, breathing light, NOAA alarm, backlight, power-on delay, VFO scan range; APRS working channel, channel mute, tx data reporting, beacon pop-up time). Liggen vermoedelijk in de functie-/APRS-blokken; offsets onbekend.

## Uit andere bronnen
- NeonPlug (infamy/NeonPlug PR #197, gemerged 10-10-2026): eerste melding APRS-write 0x58; ACK-wachttijd tot 30 s.
- NeonPlug: 0x7800–0x7FFF en ≥0xE000 nooit schrijven — bij één eigenaar calibratie-achtige data (waarschijnlijk 960-kanaal-firmware). Niet door Hans geverifieerd.
- Fork Dadud/Chirp_Radtel-RT-950-Pro (Kyle Brockman, dec 2025): CHANNEL_COUNT 990 maar leest nog 0x0000–0x7800 → indeling inconsistent; geen zones; APRS nog 0x55.
- CHIRP issue #12180: open (status New), geen driver gemerged; FW 0.24 (251201) hoort bij de overgang naar 10 x 99.

## Risico
- Radio's met oude 960-kanaal-firmware (15 x 64): 960 x 32 = 0x7800, dus kanalen eindigen op 0x77FF. Een driver die 990 kanalen (tot 0x7BBF) schrijft, overschrijft daar 0x7800–0x7BBF — precies het gebied waar NeonPlug calibratie-achtige data zag. Driver moet firmware/indeling detecteren en bij 960-kanaal-firmware weigeren te schrijven (of alleen tot 0x77FF). Afleiding, niet getest.
- Nieuwe instellingen uit CPS 1.3.x: driver moet instellingenblokken read-modify-write behandelen, nooit uit standaardwaarden opbouwen.

## Bekende fouten (gevonden bij de review van 18-10-2026, nog niet opgelost)
1. VFO-band wordt 0 bij elke settings-apply: `_apply_vfo_freq_band` leest een lijstwaarde met `_value_as_int`; CHIRP geeft de labeltekst terug → 0. Getest: band 2 → 0, byte 0x8012 wordt 0x00. Oplossing: `_value_as_index` + `_VFO_BAND_CHOICES` (zoals bij step).
2. DCS-polariteit: radio gebruikt "I", CHIRP "R". Inverted DCS van de radio geeft CHIRP-polariteit "IN"/"NI" (ongeldig); "R" uit CHIRP geeft bij encoderen `ValueError: Unsupported DCS code D023R`. Oplossing: I↔R vertalen in `_apply_tones` en `_update_tones_from_memory`.
3. Tonen zonder CHIRP-"Cross": alleen-RX-toon en gemengde CTCSS/DCS gaan verloren bij bewerken van zo'n kanaal.
4. Settings-apply zet "niet ingesteld" (0xFF) om in een standaardwaarde (bv. APRS → write_aprs wordt True na alleen openen en toepassen).
5. `_ToneInfo` is ongebruikt.

## Route naar officiële CHIRP
- PR op kk7ds/chirp: tests slagen, rebased, `Fixes/Related to #12180`, testimage `tests/images/Radtel_RT-950_Pro.img`, MemoryMapBytes, bestanden GPLv3 of zonder licentietekst.
- Huidige driver (MIT, eigen architectuur) past niet; voorstel: RT-950 Pro als subklasse van de RT-920-driver (radtel_rt900.py), zoals Fred Trimble eerder voorstelde.
- "Developer"-rol op chirpmyradio.com (bepaalt waarschuwing bij Load module from issue) wordt door de beheerder (Dan Smith, KK7DS) toegekend; geen vaste criteria gevonden.
- Voorstel in het Engels opgesteld voor issue #12180 (vragen: subklasse gewenst?, review door Fred?, testimage met neutrale kanalen ok?).

## Open
- Bekende fouten 1–4 hierboven oplossen (eigen commit, met test).
- Handshake (PROGRAMBT9000U + XOR) vergelijken met RT-920-protocol.
- Maximale lengte zonenaam (slot 16 bytes, driver schrijft max 10).
- Firmware-/indelingsdetectie (960 vs 990) toevoegen vóór schrijven.
- Reactie maintainers op voorstel in #12180 afwachten.
