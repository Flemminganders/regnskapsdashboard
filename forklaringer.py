"""Enkle forklaringer av begreper og tall i dashboardet.

Brukes av «i»-knappene på kortene og av ordlisten nederst på siden.
Hver forklaring er (tittel, [avsnitt, ...]) – kort, i vanlig språk, uten fagsjargong.
Tekstene her er ren tekst; de escapes når de settes inn i HTML.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

Forklaring = Tuple[str, List[str]]

FORKLARINGER: Dict[str, Forklaring] = {
    # --- Valg og status ------------------------------------------------------
    "selskap_konsern": ("Selskap eller konsern?", [
        "Selskap er morselskapet alene, for eksempel Telenor ASA, slik det står i egne bøker.",
        "Konsern er hele gruppen: morselskapet og alle datterselskapene det eier, regnet som én enhet. "
        "Salg og lån mellom selskapene i gruppen er trukket ut, så du ser bare det gruppen gjør mot resten "
        "av verden.",
        "Er morselskapet et eierselskap, ligger driften i datterselskapene. Da forteller konsernet mest "
        "om forretningen, mens morselskapet mest viser utbytte og renter fra datterselskapene.",
    ]),
    "regnskapsaar": ("Regnskapsår", [
        "Velg hvilket år du vil se. Tallene sammenlignes alltid med året før, hvis det finnes.",
        "Brønnøysundregistrenes åpne API har tallene for de siste tre årene. Eldre år finnes som PDF av "
        "årsregnskapet nederst på siden.",
    ]),
    "status": ("Om merkene", [
        "Regnskapsår: perioden regnskapet gjelder, vanligvis 1. januar til 31. desember.",
        "Valuta: noen selskaper rapporterer i for eksempel USD. Da vises alle beløp i den valutaen.",
        "Regnskapsregler: IFRS er internasjonale regler som børsnoterte konsern må bruke. Regnskapsloven "
        "er de norske reglene. Forenklet IFRS er en blanding som mange morselskaper bruker.",
        "Balansen går opp: appen sjekker at det selskapet eier (eiendeler) er lik det som er finansiert med "
        "egenkapital og gjeld. Går det ikke opp, er noen tall trolig registrert feil.",
    ]),
    "selskapskort": ("Om selskapet", [
        "Organisasjonsnummer: selskapets unike nummer i Enhetsregisteret, ni siffer.",
        "Næring: hva selskapet driver med, etter den offisielle næringskoden (NACE).",
        "Ansatte: antall ansatte slik det er registrert i Aa-registeret (arbeidsgiverregisteret).",
        "Aksjekapital: pengene eierne skjøt inn da aksjene ble utstedt. Den sier lite om hva selskapet er "
        "verdt i dag.",
    ]),

    # --- Hovedtall -----------------------------------------------------------
    "sum_driftsinntekter": ("Driftsinntekter", [
        "Alt selskapet har tjent på det det driver med i løpet av året, mest salg av varer og tjenester. "
        "Ofte kalt omsetning.",
        "Utbytte og renter er ikke med. De er finansinntekter.",
    ]),
    "driftsresultat": ("Driftsresultat", [
        "Driftsinntekter minus driftskostnader: det selskapet tjener på selve driften, før renter og skatt.",
        "Driftskostnader er blant annet varekjøp, lønn, husleie og avskrivninger (verdifall på maskiner o.l.).",
    ]),
    "aarsresultat": ("Årsresultat", [
        "Det som er igjen til slutt, etter alle kostnader, renter og skatt. Ofte kalt overskudd (eller "
        "underskudd hvis negativt).",
        "Årsresultatet kan deles ut som utbytte til eierne eller holdes tilbake i selskapet.",
    ]),
    "sum_eiendeler": ("Sum eiendeler", [
        "Alt selskapet eier og har krav på ved årets slutt: bygg, maskiner, aksjer i andre selskaper, varer, "
        "penger som kunder skylder, og bankinnskudd.",
        "Kalles også totalkapital. Den er alltid lik egenkapital pluss gjeld.",
    ]),
    "egenkapital": ("Egenkapital", [
        "Den delen av eiendelene som tilhører eierne: det som ville vært igjen hvis all gjeld ble betalt.",
        "Den består av penger eierne har skutt inn og overskudd som er holdt tilbake i selskapet.",
    ]),

    # --- Nøkkeltallgrupper ---------------------------------------------------
    "lonnsomhet": ("Lønnsomhet", [
        "Hvor godt selskapet tjener penger, målt mot hvor mye det selger (marginer) eller hvor mye kapital "
        "det bruker (rentabilitet).",
        "Høyere er bedre. Sammenlign gjerne med selskaper i samme bransje, for normalt nivå varierer mye.",
    ]),
    "likviditet": ("Likviditet", [
        "Om selskapet har nok penger og lett omsettelige eiendeler til å betale regningene som forfaller det "
        "neste året.",
        "Dårlig likviditet kan gi problemer selv om selskapet tjener penger.",
    ]),
    "soliditet": ("Soliditet", [
        "Hvor godt selskapet tåler tap og dårlige tider, altså hvor mye av driften som er finansiert av "
        "eierne i stedet for med lån.",
        "Høy egenkapitalandel og lav gjeldsgrad betyr et solid selskap.",
        "Rentedekningsgraden viser om resultatet er stort nok til å betale rentene på gjelden. Den kan bare "
        "regnes ut når selskapet har oppgitt rentekostnadene sine.",
    ]),

    # --- Seksjoner -----------------------------------------------------------
    "drivere": ("Hva drev endringen?", [
        "Årsresultatet er driftsinntekter minus driftskostnader, pluss netto finans, minus skatt. Appen ser "
        "på hvor mye hver av disse postene endret seg fra året før, og hvor mye det flyttet årsresultatet.",
        "De tre postene som betydde mest vises. Grønt løftet resultatet, rødt trakk det ned. Sammen "
        "forklarer postene hele endringen.",
        "Tallene viser hva som endret seg, ikke hvorfor. Årsaken står ofte i årsrapporten.",
    ]),
    "balansedrivere": ("Hva endret seg i balansen?", [
        "Venstre side viser hvilke eiendeler som økte eller falt mest fra året før. Høyre side viser hvordan "
        "endringen er finansiert: med egenkapital, langsiktig gjeld eller kortsiktig gjeld.",
        "De to sidene endrer seg alltid like mye, fordi eiendelene er lik egenkapital pluss gjeld. Kjøper "
        "selskapet en maskin på lån, øker både anleggsmidlene og gjelden.",
        "Blå er økning og grå er nedgang. Det er ikke ment som godt eller dårlig.",
    ]),
    "sammenlign": ("Sammenlign selskaper", [
        "Viser hovedtall og nøkkeltall for to selskaper side om side. Appen bruker samme regnskapsår og samme "
        "regnskapstype (selskap eller konsern) når det finnes, så tallene blir så like som mulig.",
        "Det sterkeste nøkkeltallet er grønt. Beløp sier mest om størrelse, mens prosent og ganger er laget "
        "for å sammenligne selskaper av ulik størrelse.",
        "Sammenlign helst selskaper i samme bransje. Normale marginer og gjeldsnivåer varierer mye mellom bransjer.",
    ]),
    "hendelser": ("Hendelser i registrene", [
        "Datoer fra Enhetsregisteret for når styret, daglig leder eller revisor sist ble endret, og når "
        "kapital, vedtekter eller navn ble endret de siste to årene.",
        "Nyheter som oppkjøp og kontrakter finnes ikke i de offentlige registrene.",
    ]),
    "graf_balanse": ("Balansen", [
        "Venstre søyle viser hva selskapet eier (eiendeler). Høyre søyle viser hvordan det er betalt for "
        "(egenkapital og gjeld). De to søylene er alltid like høye.",
        "Anleggsmidler skal brukes lenge, som bygg og maskiner. Omløpsmidler blir raskt til penger, som varer, "
        "kundefordringer og bankinnskudd.",
        "Kortsiktig gjeld forfaller innen ett år. Langsiktig gjeld forfaller senere.",
    ]),
    "graf_resultat": ("Fra inntekter til årsresultat", [
        "Grafen går trinn for trinn fra driftsinntektene ned til årsresultatet.",
        "Grå søyler er summer slik de står i regnskapet. Blå søyler legger til, røde trekker fra.",
    ]),
    "utvikling": ("Utvikling", [
        "Viser hvordan inntekter, resultat og nøkkeltall har utviklet seg over årene som finnes i "
        "registeret. Det året du har valgt, er uthevet.",
        "Se etter trender: Vokser inntektene? Blir marginene bedre eller dårligere?",
    ]),
    "excel": ("Excel med formler", [
        "Fila har regnskapstallene og nøkkeltallene som ekte Excel-formler. Klikk på en celle for å se "
        "nøyaktig hvordan tallet er regnet ut, eller endre tallene og se hva som skjer.",
    ]),
    "pdf": ("Årsregnskap som PDF", [
        "Kopi av årsregnskapet slik selskapet sendte det inn til Brønnøysundregistrene, ofte med noter og "
        "årsberetning.",
        "Her finner du også årene før de tre som vises i appen.",
    ]),
}


def hent(nokkel: str) -> Forklaring:
    return FORKLARINGER[nokkel]


# Rekkefølgen i ordlisten nederst på siden.
ORDLISTE_REKKEFOLGE = [
    "selskap_konsern", "sum_driftsinntekter", "driftsresultat", "aarsresultat", "sum_eiendeler",
    "egenkapital", "lonnsomhet", "likviditet", "soliditet", "graf_balanse", "drivere", "balansedrivere",
    "sammenlign", "status",
]
