# RigCalc

[![Tests](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml/badge.svg)](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RigCalc leser riggegeometri fra Vectorworks Spotlight, bygger en inspiserbar
Python-modell og utfører foreløpige statiske analyser av trusskonstruksjoner.
Programmet beregner reaksjoner, deformasjoner og snittkrefter med både en
lineær bjelkemodell og en korotasjonell 3D-modell. Validerte resultater kan
skrives tilbake til Hoist- og Truss Cross-objekter i Vectorworks.

> [!WARNING]
> RigCalc er eksperimentell programvare. Resultater må ikke brukes som eneste
> grunnlag for sikkerhetskritiske rigg- eller løftebeslutninger. Beregninger og
> forutsetninger må kontrolleres av kvalifisert personell.

## Migrering fra LoadCalc

Produktmappen og Python-pakken er omdøpt:

```text
LoadCalc/          -> RigCalc/
loadcalc/          -> rigcalc/
loadcalc_geometry  -> rigcalc_geometry
```

En gammel Vectorworks-loader vil ikke fungere etter denne endringen. Kopier
hele den nye `RigCalc/loader.py` inn i Vectorworks-scriptet og kontroller at
`RIGCALC_REPO_DIR` peker på den nye `RigCalc`-mappen. Dette må gjøres én gang.

## Filen som skal inn i Vectorworks

Den komplette loaderen ligger i:

```text
RigCalc/loader.py
```

Dette er den eneste prosjektfilen som skal kopieres inn i Vectorworks Resource
Manager. Selve RigCalc-koden skal fortsatt ligge eksternt i Git-repoet.

### Installere loaderen

1. Åpne `RigCalc/loader.py` i en teksteditor.
2. Kopier **hele filinnholdet**.
3. Opprett eller åpne en Python Script-resource i Vectorworks Resource Manager.
4. Erstatt gammelt scriptinnhold med loaderen og lagre.
5. Endre `RIGCALC_REPO_DIR` øverst i loaderen dersom repoet ligger et annet
   sted på maskinen.

Eksempel:

```python
RIGCALC_REPO_DIR = (
    r"C:\Path\To\RigCalc"
)
```

Stien skal peke på mappen som inneholder både `rigcalc/`, `loader.py` og denne
README-filen:

```text
VWDEV/
└── RigCalc/                  <-- RIGCALC_REPO_DIR peker hit
    ├── loader.py
    ├── README.md
    ├── rigcalc/
    │   └── __init__.py
    ├── output/
    └── tests/
```

Ikke sett stien til bare `VWDEV`, og ikke sett den til
`RigCalc/rigcalc`. Loaderen kontrollerer stien og viser en forståelig feil
dersom `rigcalc/__init__.py` ikke finnes.

## Normal utviklingsflyt

Etter at loaderen er installert én gang:

1. Rediger filene under `RigCalc/rigcalc/` i VS Code.
2. Lagre endringene.
3. Kjør RigCalc-scriptet fra Vectorworks.
4. Loaderen tømmer import-cachen og kjører siste lagrede kode.

Vectorworks trenger normalt ikke startes på nytt, og loaderen trenger ikke
kopieres inn på nytt ved vanlige kodeendringer. Den må bare oppdateres dersom
selve `loader.py` eller repo-stien endres.

## Output

Før rapportene skrives viser RigCalc en dialog med beregningsrelevante
designlag. Bare valgte lag tas med i geometrimodellen. Velg derfor lag som
inneholder hengende konstruksjon og utstyr, og la gulv-, lager- og
presentasjonslag være avslått. Siste valg huskes som forslag til neste
kjøring, men dialogen vises alltid.

En vellykket kjøring skriver uten å åpne Notepad:

```text
RigCalc/output/rigcalc_geometry.txt
RigCalc/output/rigcalc_geometry.json
RigCalc/output/rigcalc_cross_sections.json
RigCalc/output/rigcalc_calculation.txt
RigCalc/output/rigcalc_calculation.json
RigCalc/output/rigcalc_nonlinear_calculation.txt
RigCalc/output/rigcalc_nonlinear_calculation.json
RigCalc/output/rigcalc_solver_comparison.txt
RigCalc/output/rigcalc_solver_comparison.json
RigCalc/output/rigcalc_primary_calculation.txt
RigCalc/output/rigcalc_primary_calculation.json
RigCalc/output/rigcalc_hoist_ids.json
RigCalc/output/rigcalc_writeback.json
RigCalc/output/rigcalc_truss_cross_writeback.json
RigCalc/output/rigcalc_notifications.json
RigCalc/output/rigcalc_notification_writeback.json
RigCalc/output/rigcalc_run_summary.json
```

TXT-filen er beregnet for rask menneskelig kontroll. JSON-filen inneholder den
detaljerte modellen som kan analyseres og brukes i tester.

Når utviklingsdiagnostikk er aktivert, skrives også
`rigcalc_inventory.json` og `rigcalc_normalized.json`.
`rigcalc_inventory.json` er en skrivebeskyttet diagnostisk inventering av alle
plug-in-objekter (`T=86`), med plug-in-type, lag, klasse, posisjon og alle
tilknyttede records og felt. Den brukes til å kartlegge Spotlight-objekter før
de tas inn i lastmodellen, og endrer ikke Vectorworks-dokumentet.

`rigcalc_normalized.json` er den stabile, kalkulasjonsrettede datakontrakten.
Hver masse og kobling beholder kildefelt, originalverdi og eventuelle
datakvalitetsvarsler. Ukjente tall uten eksplisitt enhet blir ikke antatt å
være kilogram.

Full inventar- og normaliseringsdiagnostikk er deaktivert i standardkjøringen
fordi den leser alle records og nested objekter og ikke er nødvendig for
beregningen. Sett `WRITE_DEVELOPMENT_INVENTORY = True` i `rigcalc/config.py`
når disse rapportene skal regenereres. Standardkjøringen bruker en lett
lagindeks og detaljleser bare valgte beregningsobjekter og Hanging Positions.

Under kjøring viser Vectorworks fremdrift for lagindeks, modellbygging,
lineær analyse og ikke-lineær analyse. Den ikke-lineære fasen viser
konstruksjon, lastprosent og Newton-iterasjon.

Etter kjøringen viser Vectorworks et sammendrag med antall objekter,
beregnede konstruksjoner, writeback-resultater, frigjorte motorstøtter og
objekter som ikke kunne behandles.

Genererte TXT- og JSON-rapporter ignoreres av Git. `output/.gitkeep` sørger for
at selve output-mappen finnes etter kloning.

## Feilsøking

En feil i loaderen eller RigCalc skriver full traceback til:

```text
%TEMP%\VWDEV\rigcalc_error.txt
```

Vectorworks viser bare en kort feilmelding med plasseringen til denne filen.
Kontroller først at `RIGCALC_REPO_DIR` peker på riktig `RigCalc`-mappe.

## Arkitekturregel

Bare `rigcalc/vw/` skal kjenne til Vectorworks API. Modell-, topologi- og
rapportmodulene skal kunne importeres og testes uten Vectorworks.

Flyten er:

```text
Vectorworks -> vw/scanner -> intern modell -> topology -> solver -> report/writeback
```

Solverne og rapportmodulene er rene Python-moduler og kan testes uten
Vectorworks. `rigcalc/vw/` håndterer skanning, dialoger, fremdrift og alle
endringer i det åpne Vectorworks-dokumentet.

## Beregning og writeback

RigCalc grupperer sammenhengende truss til konstruksjoner og knytter motorer,
dead hangs, punktlaster, fordelte laster og Truss Cross-objekter til dem.
Mekaniske tverrsnitt leses fra Vectorworks-data og konverteres til SI-enheter.
Konstruksjoner uten tilstrekkelige tverrsnittsdata eller entydig geometri blir
rapportert, men får ikke resultater skrevet tilbake.

Den lineære og den korotasjonelle analysen sammenlignes før et primærresultat
velges. Ikke-konvergerte ikke-lineære resultater forkastes. Motorstøtter som
ville kreve en negativ reaksjon, frigis og systemet løses på nytt. Godkjente
motorreaksjoner skrives til High Hook-feltene, og krefter i strukturelle
Truss Cross-koblinger skrives tilbake i newton.

Writeback skjer automatisk som del av en normal kjøring. Arbeid derfor i en
kopi eller et versjonskontrollert Vectorworks-dokument når nye datasett
valideres.

## Lastvarsler i tegningen

Etter at primærberegningen er valgt, kontrollerer RigCalc reaksjonslasten ved
hver motor mot motorens kapasitet. En reaksjonslast over kapasiteten oppretter
en rød tekstmarkør med hvit tekst ved motoren i klassen `RigCalc-Load`.
Markøren er ett enkelt tekstobjekt uten tekstbryting eller Tight Fill. Fyll,
fyllmønster og pennfarge står til By Class. Når varslingsklassene opprettes
første gang, får de standardfarge og hvit penn; eksisterende klasser endres
aldri av RigCalc.
Markøren viser varseltype, motor-ID og kapasitetsutnyttelse på tre linjer.
Kapasiteten sammenlignes
med lasten ved lower hook; motor- og kjedevekt i High Hook-verdien inngår ikke
i denne kapasitetskontrollen.

RigCalc gir genererte markører et internt objektnavn. Ved neste kjøring
slettes og regenereres alle disse tekstobjektene. Andre objekter brukeren har
lagt i `RigCalc-Load`, blir ikke endret eller slettet. Varslingsdata og resultatet av
skrivingen lagres i henholdsvis `rigcalc_notifications.json` og
`rigcalc_notification_writeback.json` i output-mappen.

Beregningsrapportene inneholder også vertikal defleksjon i midten av hvert
spenn mellom aktive oppheng, maksimal beregnet defleksjon i hvert spenn og
maksimal defleksjon for hele konstruksjonen. Hvert spenn får en informativ
oransje tekstmarkør i `RigCalc-Deflection`. Det settes foreløpig ikke en
feilgrense fordi tillatt defleksjon må fastsettes per prosjekt eller system.

Interne elementkrefter kontrolleres komponentvis mot `MaxNx`, `MaxVy`,
`MaxVz`, `MaxMt`, `MaxMby` og `MaxMbz` fra Braceworks cross-section-XML.
Verdien null behandles som manglende kapasitet. Overskridelser samles per
snitt og vises som blå tekstmarkører i `RigCalc-Internal`. Kontrollen antar
ikke en interaksjonsformel mellom aksialkraft og moment.

## Kjøre tester

Fra `RigCalc`-mappen, med Python-runtime som følger Vectorworks 2026:

```powershell
& 'C:\Program Files\Vectorworks 2026\Python39\python.exe' -B -m unittest discover -s tests -v
```

`-B` hindrer at testen oppretter `__pycache__`-filer i repoet.

## Bidrag og sikkerhet

Se [CHANGELOG.md](CHANGELOG.md) for vesentlige endringer og
[CONTRIBUTING.md](CONTRIBUTING.md) før du foreslår større endringer. Ikke
publiser sårbarheter eller sensitiv prosjektinformasjon i en offentlig issue;
følg i stedet [SECURITY.md](SECURITY.md).

## Lisens

RigCalc distribueres under [MIT-lisensen](LICENSE).
