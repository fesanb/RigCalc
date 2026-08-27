# RigCalc

[![Tests](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml/badge.svg)](https://github.com/fesanb/RigCalc/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

RigCalc leser riggegeometri fra Vectorworks Spotlight og bygger en vanlig,
inspiserbar Python-modell av trusskonstruksjoner, støtter og laster.

Prosjektet er foreløpig i **geometrifasen**. Det beregner ikke reaksjonskrefter
og skriver ikke laster tilbake til hoistfeltene ennå.

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

En vellykket kjøring skriver uten å åpne Notepad:

```text
RigCalc/output/rigcalc_geometry.txt
RigCalc/output/rigcalc_geometry.json
```

TXT-filen er beregnet for rask menneskelig kontroll. JSON-filen inneholder den
detaljerte modellen som kan analyseres og brukes i tester.

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
Vectorworks -> vw/scanner -> intern modell -> topology -> report
```

## Kjøre tester

Fra `RigCalc`-mappen, med Python-runtime som følger Vectorworks 2026:

```powershell
& 'C:\Program Files\Vectorworks 2026\Python39\python.exe' -B -m unittest discover -s tests -v
```

`-B` hindrer at testen oppretter `__pycache__`-filer i repoet.

## Bidrag og sikkerhet

Se [CONTRIBUTING.md](CONTRIBUTING.md) før du foreslår større endringer. Ikke
publiser sårbarheter eller sensitiv prosjektinformasjon i en offentlig issue;
følg i stedet [SECURITY.md](SECURITY.md).

## Lisens

RigCalc distribueres under [MIT-lisensen](LICENSE).
