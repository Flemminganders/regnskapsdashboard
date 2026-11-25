"""Utseende i Apple-stil: fargetokens, CSS og små HTML-byggesteiner.

Samme visuelle språk som Fondsdashboard: Apple-grå flater, kort med 22 px
radius, systemfonten med størrelsesavhengig tracking, tabelltall og myke,
kritisk dempede overganger. Respekterer redusert bevegelse, redusert
gjennomsiktighet og økt kontrast.

All tekst som kommer fra API-et sendes gjennom ``e()`` (HTML-escaping).
"""
from __future__ import annotations

from html import escape
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

FONT = '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif'

TOKENS: Dict[str, Dict[str, str]] = {
    "light": {
        "page": "#fbfbfd", "surface": "#ffffff", "ink": "#1d1d1f", "ink-2": "#424245",
        "muted": "#6e6e73", "grid": "#e8e8ed", "axis": "#d2d2d7", "line": "rgba(0,0,0,0.07)",
        "fill": "rgba(118,118,128,0.12)", "fill-2": "rgba(118,118,128,0.08)",
        "card-shadow": "0 0 0 1px rgba(0,0,0,0.045), 0 1px 2px rgba(0,0,0,0.03), 0 8px 24px rgba(0,0,0,0.045)",
        "thumb": "#ffffff", "thumb-shadow": "0 3px 8px rgba(0,0,0,0.12), 0 1px 1px rgba(0,0,0,0.04)",
        "accent": "#0071e3", "up": "#248a3d", "down": "#d70015", "warn": "#b25000",
        "up-bg": "rgba(52,199,89,0.14)", "down-bg": "rgba(255,59,48,0.12)", "warn-bg": "rgba(255,149,0,0.16)",
        "bar": "rgba(251,251,253,0.72)", "elev": "rgba(255,255,255,0.86)",
    },
    "dark": {
        "page": "#000000", "surface": "#1c1c1e", "ink": "#f5f5f7", "ink-2": "#c7c7cc",
        "muted": "#98989d", "grid": "#2c2c2e", "axis": "#3a3a3c", "line": "rgba(255,255,255,0.08)",
        "fill": "rgba(118,118,128,0.24)", "fill-2": "rgba(118,118,128,0.16)",
        "card-shadow": "none",
        "thumb": "#636366", "thumb-shadow": "0 3px 8px rgba(0,0,0,0.3)",
        "accent": "#0a84ff", "up": "#30d158", "down": "#ff453a", "warn": "#ff9f0a",
        "up-bg": "rgba(48,209,88,0.16)", "down-bg": "rgba(255,69,58,0.16)", "warn-bg": "rgba(255,159,10,0.18)",
        "bar": "rgba(0,0,0,0.7)", "elev": "rgba(44,44,46,0.86)",
    },
}

# Grafpalett (fargeblind-validert), egne steg for lys og mørk modus.
GRAF = {
    "light": {"serie": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
              "opp": "#2a78d6", "ned": "#e34948"},
    "dark": {"serie": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
             "opp": "#3987e5", "ned": "#e66767"},
}

# Kritisk dempet fjær (damping 1.0, response ~0.4 s) som CSS-easing – samme som Fondsdashboard.
SPRING = ("linear(0, 0.075, 0.227, 0.390, 0.536, 0.656, 0.750, 0.821, 0.873, 0.911, 0.938, "
          "0.957, 0.971, 0.980, 0.986, 0.991, 0.994, 0.996, 0.997, 0.998, 1)")


def e(tekst: object) -> str:
    return escape("" if tekst is None else str(tekst))


def graffarger(modus: str) -> Dict[str, object]:
    t, g = TOKENS[modus], GRAF[modus]
    return {**g, "tekst": t["ink"], "dempet": t["muted"], "rutenett": t["grid"],
            "akse": t["axis"], "flate": t["surface"], "sum": t["ink-2"], "font": FONT}


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def css(modus: str) -> str:
    t = TOKENS[modus]
    vars_ = "\n".join(f"  --{k}: {v};" for k, v in t.items())
    return f"""<style>
:root {{
{vars_}
  --font-ui: {FONT};
  --spring: {SPRING};
  --spring-t: 500ms;
  color-scheme: {modus};
}}

/* ---------- Flate og typografi ---------- */
.stApp {{ background: var(--page); color: var(--ink); }}
.stApp a {{ color: var(--accent); }}
.stSpinner i, [data-testid="stSpinner"] i {{ border-top-color: var(--accent) !important; }}
.stApp, .stApp button, .stApp input, .stApp textarea {{
  font-family: var(--font-ui);
  -webkit-font-smoothing: antialiased;
}}
.stApp :is(p, label, li, summary, input, button, h1, h2, h3, h4, td, th) {{ font-family: var(--font-ui); }}
.stApp p, .stApp li {{ letter-spacing: -0.003em; }}
.block-container {{ max-width: 1180px; padding-top: 4.25rem; padding-bottom: 5rem; }}
@media (max-width: 760px) {{ .block-container {{ padding-left: 16px; padding-right: 16px; padding-top: 3.5rem; }} }}

/* Gjennomskinnelig verktøylinje øverst (materiale over innholdet) */
header[data-testid="stHeader"] {{
  background: var(--bar);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  box-shadow: 0 0.5px 0 var(--line);
}}

/* ---------- Toppfelt ---------- */
.rd-brand {{ display: flex; align-items: center; gap: 10px; color: var(--ink);
  font-size: 1rem; font-weight: 600; letter-spacing: -0.012em; }}
.rd-brand img {{ width: 28px; height: 28px; border-radius: 7px; box-shadow: 0 1px 2px rgba(0,0,0,.12); }}
.rd-h1 {{ margin: 18px 0 6px; font-size: clamp(2rem, 4.4vw, 2.75rem); line-height: 1.05; font-weight: 700;
  letter-spacing: -0.03em; color: var(--ink); text-wrap: balance; }}
.rd-lede {{ margin: 0 0 22px; color: var(--muted); font-size: 1.0625rem; line-height: 1.45;
  letter-spacing: -0.01em; max-width: 46rem; }}

/* ---------- Søkefelt (Spotlight-pille) ---------- */
.st-key-sok {{ margin-bottom: 4px; }}
.st-key-sok [data-testid="stTextInput"] label {{ display: none; }}
.st-key-sok div[data-baseweb="input"], .st-key-sok div[data-baseweb="base-input"] {{
  background: var(--surface) !important; border: none !important; border-radius: 980px !important;
}}
.st-key-sok div[data-baseweb="input"] {{
  height: 52px; align-items: center;
  box-shadow: var(--card-shadow), 0 0 0 1px var(--line);
  transition: box-shadow 200ms var(--spring);
}}
.st-key-sok div[data-baseweb="input"]:focus-within {{
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 28%, transparent), 0 0 0 1px var(--accent);
}}
.st-key-sok input {{
  height: 52px; padding-left: 50px !important; font-size: 1.0625rem; color: var(--ink);
  letter-spacing: -0.01em; font-variant-numeric: tabular-nums;
  background: transparent url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%238e8e93' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='10.5' cy='10.5' r='6.5'/%3E%3Cpath d='M15.5 15.5 20 20'/%3E%3C/svg%3E") no-repeat 20px 50% / 19px;
}}
.st-key-sok input::placeholder {{ color: var(--muted); opacity: 1; }}
/* Søkefeltet er en egen komponent (iframe); luften rundt fokusringen ligger inne i den */
.st-key-sok iframe, .st-key-kort-sammenlign iframe[title*="sokefelt"] {{ display: block; }}
.st-key-sok {{ margin-left: -5px; margin-right: -5px; }}
[class*="st-key-flere"] {{ margin-top: 4px; }}

/* ---------- Knapper ---------- */
.stApp button[kind] {{
  border-radius: 980px; font-weight: 500; letter-spacing: -0.01em;
  transition: transform 100ms ease-out, background-color 150ms ease, box-shadow 150ms ease;
}}
.stApp button[kind]:active {{ transform: scale(0.97); }}
.stApp button[kind="primary"], .stApp button[kind="primaryFormSubmit"] {{
  background: var(--accent); border-color: var(--accent); color: #fff;
}}
.stApp button[kind="primary"]:hover, .stApp button[kind="primaryFormSubmit"]:hover {{
  background: color-mix(in srgb, var(--accent) 88%, black); border-color: transparent; color: #fff;
}}
.st-key-sok button[kind="primaryFormSubmit"] {{ height: 52px; font-size: 1.0625rem; font-weight: 600; }}

/* Forslag-chips */
.rd-forslag-tittel {{ margin: 26px 0 10px; color: var(--muted); font-size: .75rem; font-weight: 600;
  letter-spacing: .06em; text-transform: uppercase; }}
[class*="st-key-eks"] button {{
  background: var(--surface); border: none; color: var(--ink); min-height: 40px; padding: 0 16px;
  box-shadow: var(--card-shadow), 0 0 0 1px var(--line);
}}
[class*="st-key-eks"] button:hover {{ background: var(--surface); color: var(--accent); border: none; }}
[class*="st-key-eks"] button p {{ font-size: .9375rem; white-space: nowrap; }}

/* ---------- Segmentert kontroll (Selskap / Konsern) ---------- */
:is(.st-key-typevalg, .st-key-aarvalg) [data-testid="stButtonGroup"] > div {{
  background: var(--fill); padding: 2px; border-radius: 980px; gap: 0; width: fit-content;
}}
:is(.st-key-typevalg, .st-key-aarvalg) [data-testid="stButtonGroup"] button {{
  border: none !important; background: transparent; border-radius: 980px !important;
  min-height: 32px; padding: 0 16px; color: var(--ink); box-shadow: none;
  transition: background-color 250ms var(--spring), box-shadow 250ms var(--spring), transform 100ms ease-out;
}}
:is(.st-key-typevalg, .st-key-aarvalg) [data-testid="stButtonGroup"] button[kind$="Active"] {{
  background: var(--thumb); box-shadow: var(--thumb-shadow); color: var(--ink);
}}
:is(.st-key-typevalg, .st-key-aarvalg) [data-testid="stButtonGroup"] button p {{ font-size: .875rem; font-weight: 500; }}
:is(.st-key-typevalg, .st-key-aarvalg) label {{ display: none; }}
.st-key-valg {{ justify-content: flex-start; flex-wrap: wrap; gap: 10px 14px; }}
.st-key-valg > div {{ flex: 0 0 auto !important; width: auto !important; min-width: 0; }}

/* ---------- Kort ---------- */
.rd-kort, [class*="st-key-kort"] {{
  background: var(--surface); border-radius: 22px; box-shadow: var(--card-shadow);
  border: 1px solid transparent;
}}
[class*="st-key-kort"] {{ padding: 22px 24px 14px; }}
.rd-kort {{ padding: 24px; }}
@media (max-width: 760px) {{ .rd-kort, [class*="st-key-kort"] {{ padding: 18px; border-radius: 18px; }} }}

.rd-seksjon {{ margin: 40px 0 14px; }}
.rd-seksjon h2 {{ margin: 0; font-size: 1.5rem; line-height: 1.15; font-weight: 700; letter-spacing: -0.022em; color: var(--ink); }}
.rd-seksjon p {{ margin: 4px 0 0; color: var(--muted); font-size: .9375rem; }}
.rd-korttittel {{ margin: 0 0 2px; font-size: 1.0625rem; font-weight: 600; letter-spacing: -0.012em; color: var(--ink); }}
.rd-kortundertittel {{ margin: 0; color: var(--muted); font-size: .8125rem; }}

/* ---------- Selskapskort ---------- */
.rd-selskap {{ display: grid; grid-template-columns: auto 1fr auto; gap: 18px; align-items: center; }}
.rd-selskap > .rd-info {{ align-self: start; }}
.rd-monogram {{
  width: 64px; height: 64px; border-radius: 16px; display: grid; place-items: center;
  color: #fff; font-size: 1.5rem; font-weight: 600; letter-spacing: -0.02em;
  background: linear-gradient(160deg, #6a7df2, #2a2f9e); box-shadow: 0 2px 6px rgba(42,47,158,.25);
}}
.rd-navn {{ margin: 0; font-size: 1.75rem; line-height: 1.1; font-weight: 700; letter-spacing: -0.025em; color: var(--ink); }}
.rd-undertittel {{ margin: 4px 0 0; color: var(--muted); font-size: .9375rem; letter-spacing: -0.005em; }}
.rd-fakta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 18px 24px;
  margin: 22px 0 0; padding-top: 20px; border-top: 1px solid var(--line); }}
.rd-fakta dt {{ color: var(--muted); font-size: .75rem; font-weight: 500; letter-spacing: .01em; margin-bottom: 3px; }}
.rd-fakta dd {{ margin: 0; color: var(--ink); font-size: .9375rem; font-weight: 500; letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }}
.rd-fakta a {{ color: var(--accent); text-decoration: none; }}
.rd-fakta a:hover {{ text-decoration: underline; }}
.rd-mangler {{ color: var(--muted) !important; font-weight: 400 !important; font-style: italic; }}

/* ---------- Piller (status) ---------- */
.rd-piller {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 18px 0 0; }}
.rd-pille {{ display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px;
  border-radius: 980px; background: var(--fill-2); color: var(--ink-2); font-size: .8125rem; font-weight: 500;
  letter-spacing: -0.005em; white-space: nowrap; }}
.rd-pille[class*=" i-"]::before {{ content: ""; width: 14px; height: 14px; flex: none; background: currentColor;
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; -webkit-mask-size: contain; mask-size: contain; }}
{ikon_css()}
.rd-pille.ok {{ background: var(--up-bg); color: var(--up); }}
.rd-pille.feil {{ background: var(--down-bg); color: var(--down); }}
.rd-pille.adv {{ background: var(--warn-bg); color: var(--warn); }}
.rd-varsel {{ margin-top: 14px; }}

/* ---------- Hovedtall ---------- */
.rd-kpier {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }}
@media (max-width: 520px) {{ .rd-kpier {{ grid-template-columns: 1fr 1fr; gap: 10px; }}
  .rd-kpi {{ padding: 16px; border-radius: 18px; }} .rd-kpi .big {{ font-size: 1.5rem; }}
  .rd-kpi .big .unit {{ display: block; margin: 4px 0 0; font-size: .8125rem; }} }}
.rd-kpi {{ background: var(--surface); border-radius: 22px; box-shadow: var(--card-shadow); padding: 20px 22px 18px; }}
.rd-kpi .lbl {{ color: var(--muted); font-size: .8125rem; font-weight: 500; letter-spacing: -0.003em; }}
.rd-kpi .big {{ margin-top: 8px; font-size: 2rem; line-height: 1.05; font-weight: 600; letter-spacing: -0.03em;
  color: var(--ink); font-variant-numeric: tabular-nums; white-space: nowrap; }}
.rd-kpi .big .unit {{ color: var(--muted); font-size: .9375rem; font-weight: 500; letter-spacing: 0; margin-left: .2em; }}
.rd-kpi .delta {{ margin-top: 12px; display: flex; flex-wrap: wrap; row-gap: 4px; align-items: center; gap: 6px; font-size: .8125rem; color: var(--muted); }}
.rd-kpi .delta b {{ white-space: nowrap; font-weight: 600; font-variant-numeric: tabular-nums; padding: 2px 8px; border-radius: 980px; }}
.rd-kpi .delta b.opp {{ color: var(--up); background: var(--up-bg); }}
.rd-kpi .delta b.ned {{ color: var(--down); background: var(--down-bg); }}

/* ---------- Nøkkeltall ---------- */
.rd-grupper {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; align-items: start; }}
.rd-gruppe {{ background: var(--surface); border-radius: 22px; box-shadow: var(--card-shadow); padding: 10px 8px 8px; }}
.rd-gruppe h3 {{ margin: 8px 16px 6px; color: var(--muted); font-size: .75rem; font-weight: 600;
  letter-spacing: .06em; text-transform: uppercase; }}
.rd-nt {{ border-radius: 14px; }}
.rd-nt + .rd-nt {{ border-top: 1px solid var(--line); }}
.rd-nt[open] + .rd-nt, .rd-nt:has(+ .rd-nt[open]) {{ border-top-color: transparent; }}
.rd-nt summary {{ list-style: none; cursor: pointer; display: grid; grid-template-columns: 1fr auto 14px;
  gap: 10px; align-items: center; padding: 14px 16px; border-radius: 14px;
  transition: background-color 150ms ease, transform 100ms ease-out; -webkit-tap-highlight-color: transparent; }}
.rd-nt summary::-webkit-details-marker {{ display: none; }}
.rd-nt summary:hover {{ background: var(--fill-2); }}
.rd-nt summary:active {{ transform: scale(0.985); background: var(--fill); }}
.rd-nt summary:focus-visible {{ outline: 3px solid color-mix(in srgb, var(--accent) 45%, transparent); outline-offset: -2px; }}
.rd-nt .navn {{ color: var(--ink); font-size: .9375rem; font-weight: 500; letter-spacing: -0.01em; }}
.rd-nt .forrige {{ display: block; color: var(--muted); font-size: .75rem; font-weight: 400; margin-top: 2px;
  font-variant-numeric: tabular-nums; }}
.rd-nt .verdi {{ color: var(--ink); font-size: 1.375rem; font-weight: 600; letter-spacing: -0.025em;
  font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}
.rd-nt .verdi small {{ margin-left: .25em; color: var(--muted); font-size: .8125rem; font-weight: 500; letter-spacing: 0; }}
.rd-nt .verdi.mangler {{ color: var(--muted); font-size: .9375rem; font-weight: 500; font-style: italic; letter-spacing: 0; }}
.rd-nt .innhold {{ padding: 0 16px 16px; color: var(--ink-2); font-size: .875rem; line-height: 1.5;
  animation: rd-inn 320ms var(--spring) both; }}
@keyframes rd-inn {{ from {{ opacity: 0; transform: translateY(-4px); }} to {{ opacity: 1; transform: none; }} }}
.rd-formel {{ display: inline-block; margin: 2px 0 10px; padding: 6px 12px; border-radius: 10px; background: var(--fill-2);
  color: var(--ink); font-size: .8125rem; font-weight: 500; letter-spacing: -0.005em; }}
.rd-inndata {{ margin: 10px 0 0; display: grid; grid-template-columns: 1fr auto; gap: 4px 12px; font-size: .8125rem; }}
.rd-inndata dt {{ color: var(--muted); }}
.rd-inndata dd {{ margin: 0; text-align: right; font-variant-numeric: tabular-nums; color: var(--ink); }}
.rd-merknad {{ margin: 10px 0 0; color: var(--muted); font-size: .8125rem; }}

/* ---------- Ekspandere, varsler, tabeller ---------- */
[data-testid="stExpander"] details {{
  border: none; border-radius: 18px; background: var(--surface); box-shadow: var(--card-shadow);
}}
[data-testid="stExpander"] summary {{ padding: 14px 20px; border-radius: 18px; }}
[data-testid="stExpander"] summary:hover {{ color: var(--accent); }}
[data-testid="stExpander"] summary p {{ font-weight: 500; letter-spacing: -0.01em; }}
[data-testid="stAlert"] > div {{ border-radius: 16px; }}
[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
[data-testid="stPlotlyChart"] {{ margin-top: 4px; }}
[data-testid="stCaptionContainer"] {{ color: var(--muted); }}

/* ---------- Drivere ---------- */
.rd-drivere-topp {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; margin: 0 0 18px; }}
.rd-drivere-topp .fra-til {{ font-size: 1.375rem; font-weight: 600; letter-spacing: -0.025em; color: var(--ink);
  font-variant-numeric: tabular-nums; }}
.rd-drivere-topp .fra-til span {{ color: var(--muted); font-weight: 500; }}
.rd-driver {{ display: grid; grid-template-columns: 28px 1fr auto; gap: 4px 14px; align-items: center;
  padding: 14px 0; border-top: 1px solid var(--line); }}
.rd-driver .nr {{ grid-row: span 2; width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center;
  background: var(--fill-2); color: var(--ink-2); font-size: .8125rem; font-weight: 600; }}
.rd-driver .tittel {{ color: var(--ink); font-size: .9375rem; font-weight: 600; letter-spacing: -0.01em; }}
.rd-driver .effekt {{ font-size: .9375rem; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap;
  padding: 3px 10px; border-radius: 980px; }}
.rd-driver .effekt.opp {{ color: var(--up); background: var(--up-bg); }}
.rd-driver .effekt.ned {{ color: var(--down); background: var(--down-bg); }}
.rd-driver .tekst {{ grid-column: 2 / 4; color: var(--muted); font-size: .8125rem; line-height: 1.45; }}
.rd-driver .stav {{ grid-column: 2 / 4; height: 6px; border-radius: 3px; background: var(--fill-2); overflow: hidden; margin-top: 4px; }}
.rd-driver .stav i {{ display: block; height: 100%; border-radius: 3px; transform-origin: left;
  animation: rd-stav 700ms var(--spring) both; }}
.rd-driver .stav i.opp {{ background: var(--up); }}
.rd-driver .stav i.ned {{ background: var(--down); }}
.rd-driver .effekt.pluss {{ color: var(--accent); background: var(--fill-2); }}
.rd-driver .effekt.minus {{ color: var(--ink-2); background: var(--fill-2); }}
.rd-driver .stav i.pluss {{ background: var(--accent); }}
.rd-driver .stav i.minus {{ background: var(--muted); }}
.rd-balsider {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 32px; }}
@media (max-width: 860px) {{ .rd-balsider {{ grid-template-columns: 1fr; }} }}
.rd-balside h4 {{ margin: 0 0 10px; display: flex; flex-direction: column; gap: 2px;
  color: var(--ink); font-size: 1rem; font-weight: 600; letter-spacing: -0.015em; }}
.rd-balside h4 span {{ color: var(--muted); font-size: .8125rem; font-weight: 500; font-variant-numeric: tabular-nums; }}
.rd-tabell td.sterkest {{ font-weight: 600; color: var(--up); }}
@keyframes rd-stav {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
.rd-merk {{ margin: 12px 0 0; color: var(--muted); font-size: .75rem; line-height: 1.45; }}

/* ---------- Hendelser ---------- */
.rd-hendelse {{ display: grid; grid-template-columns: 96px 1fr; gap: 2px 14px; padding: 12px 0; border-top: 1px solid var(--line); }}
.rd-hendelse .dato {{ grid-row: span 2; white-space: nowrap; color: var(--muted); font-size: .8125rem; font-weight: 500;
  font-variant-numeric: tabular-nums; padding-top: 1px; }}
.rd-hendelse .tittel {{ color: var(--ink); font-size: .9375rem; font-weight: 600; letter-spacing: -0.01em; }}
.rd-hendelse .detalj {{ color: var(--muted); font-size: .8125rem; }}
.rd-tom {{ color: var(--muted); font-size: .875rem; padding: 12px 0; border-top: 1px solid var(--line); margin: 0; }}

.rd-to {{ display: grid; grid-template-columns: 1.35fr 1fr; gap: 14px; align-items: start; }}
@media (max-width: 860px) {{ .rd-to {{ grid-template-columns: 1fr; }} }}

/* ---------- Utvikling (tabell over år) ---------- */
.rd-tabell {{ width: 100%; border-collapse: collapse; font-size: .875rem; }}
.rd-tabell th {{ text-align: right; color: var(--muted); font-size: .75rem; font-weight: 600; letter-spacing: .02em;
  padding: 0 0 8px 12px; font-variant-numeric: tabular-nums; }}
.rd-tabell th:first-child, .rd-tabell td:first-child {{ text-align: left; padding-left: 0; }}
.rd-tabell td {{ text-align: right; padding: 9px 0 9px 12px; border-top: 1px solid var(--line); color: var(--ink);
  font-variant-numeric: tabular-nums; white-space: nowrap; }}
.rd-tabell td:first-child {{ color: var(--ink-2); white-space: normal; }}
.rd-tabell td.valgt, .rd-tabell th.valgt {{ font-weight: 600; color: var(--ink); }}
.rd-tabell td.mangler {{ color: var(--muted); font-style: italic; }}
.rd-tabell tr.gruppe td {{ color: var(--muted); font-size: .6875rem; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; padding-top: 16px; border-top: none; }}
.rd-tabell-rull {{ overflow-x: auto; }}

/* ---------- PDF-lenker ---------- */
.rd-pdf {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }}
.rd-pdf a {{ display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 14px; border-radius: 980px;
  background: var(--fill-2); color: var(--ink); text-decoration: none; font-size: .875rem; font-weight: 500;
  font-variant-numeric: tabular-nums; transition: background-color 150ms ease, transform 100ms ease-out; }}
.rd-pdf a:hover {{ background: var(--fill); color: var(--accent); }}
.rd-pdf a:active {{ transform: scale(0.96); }}
.rd-pdf a::before {{ content: ""; width: 13px; height: 13px; background: currentColor;
  -webkit-mask: {_maske(_SVG["dok"])} no-repeat center / contain; mask: {_maske(_SVG["dok"])} no-repeat center / contain; }}

/* ---------- Forklaringer («i»-knapp med boble) ---------- */
.rd-tittelrad {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }}
.rd-kpi .lbl {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
.rd-gruppe h3 {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
.rd-info {{ position: relative; display: inline-block; flex: none; text-transform: none; letter-spacing: 0; }}
.rd-info > summary {{
  list-style: none; cursor: pointer; width: 20px; height: 20px; border-radius: 50%;
  display: grid; place-items: center; background: var(--fill-2); color: var(--muted);
  font: 600 12px/1 var(--font-ui); font-style: normal; user-select: none; -webkit-tap-highlight-color: transparent;
  transition: background-color 150ms ease, color 150ms ease, transform 100ms ease-out;
}}
.rd-info > summary::-webkit-details-marker {{ display: none; }}
.rd-info > summary::after {{ content: ""; position: absolute; inset: -10px; }}   /* større trykkflate */
.rd-info > summary:hover {{ background: var(--fill); color: var(--accent); }}
.rd-info > summary:active {{ transform: scale(0.9); }}
.rd-info > summary:focus-visible {{ outline: 3px solid color-mix(in srgb, var(--accent) 45%, transparent); outline-offset: 2px; }}
.rd-info[open] > summary {{ background: var(--accent); color: #fff; }}
.rd-boble {{
  position: absolute; top: calc(100% + 8px); right: -6px; z-index: 1000; width: min(320px, 78vw);
  padding: 14px 16px; border-radius: 14px; text-align: left;
  background: var(--elev); backdrop-filter: blur(24px) saturate(180%); -webkit-backdrop-filter: blur(24px) saturate(180%);
  box-shadow: 0 0 0 1px var(--line), 0 14px 36px rgba(0,0,0,.16), 0 2px 6px rgba(0,0,0,.06);
  color: var(--ink-2); font-size: .8125rem; font-weight: 400; line-height: 1.5; white-space: normal;
  transform-origin: top right; animation: rd-boble 280ms var(--spring) both;
}}
.rd-info.venstre .rd-boble {{ right: auto; left: -6px; transform-origin: top left; }}
.rd-boble b {{ display: block; margin-bottom: 6px; color: var(--ink); font-size: .875rem; font-weight: 600; letter-spacing: -0.01em; }}
.stApp .rd-boble p, .stApp .rd-ord dd p {{ margin: 0 0 8px; font-size: .8125rem; line-height: 1.5; }}
.rd-boble p:last-child {{ margin-bottom: 0; }}
@keyframes rd-boble {{ from {{ opacity: 0; transform: scale(.94) translateY(-4px); }} to {{ opacity: 1; transform: none; }} }}
/* Mobil: boblen blir et lite ark nederst på skjermen (alltid innenfor skjermen) */
@media (max-width: 600px) {{
  .rd-boble, .rd-info.venstre .rd-boble {{
    position: fixed; top: auto; left: 12px; right: 12px; bottom: max(12px, env(safe-area-inset-bottom));
    width: auto; max-height: 60vh; overflow-y: auto; padding: 16px 18px; border-radius: 18px;
    font-size: .875rem; transform-origin: bottom center; animation: rd-ark 360ms var(--spring) both;
  }}
  .rd-boble b {{ font-size: .9375rem; }}
  .stApp .rd-boble p {{ font-size: .875rem; }}
}}
@keyframes rd-ark {{ from {{ opacity: 0; transform: translateY(24px); }} to {{ opacity: 1; transform: none; }} }}
/* Streamlit-beholdere må ikke klippe boblen */
[data-testid="stHtml"], [data-testid="stElementContainer"]:has(.rd-info) {{ overflow: visible !important; }}
.st-key-valg .rd-info {{ margin-left: -4px; }}

/* Ordliste */
.rd-ordliste {{ margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 4px 28px; }}
.rd-ord {{ padding: 12px 0; border-top: 1px solid var(--line); }}
.rd-ord dt {{ color: var(--ink); font-size: .9375rem; font-weight: 600; letter-spacing: -0.01em; margin-bottom: 4px; }}
.rd-ord dd {{ margin: 0; color: var(--ink-2); font-size: .8125rem; line-height: 1.5; }}
.rd-ord dd p {{ margin: 0 0 6px; }}

/* ---------- Bunntekst ---------- */
.rd-bunn {{ margin-top: 48px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--muted);
  font-size: .75rem; line-height: 1.5; }}

/* ---------- Tilgjengelighet ---------- */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation-duration: 1ms !important; transition-duration: 1ms !important; }}
  .stApp button[kind]:active, .rd-nt summary:active, .rd-pdf a:active {{ transform: none; }}
}}
@media (prefers-reduced-transparency: reduce) {{
  .rd-boble {{ background: var(--surface); backdrop-filter: none; -webkit-backdrop-filter: none; }}
  header[data-testid="stHeader"] {{ background: var(--page); backdrop-filter: none; -webkit-backdrop-filter: none; }}
}}
@media (prefers-contrast: more) {{
  .rd-kort, .rd-kpi, .rd-gruppe, [class*="st-key-kort"], [data-testid="stExpander"] details {{
    border: 1px solid var(--ink-2); box-shadow: none; }}
  .rd-nt + .rd-nt {{ border-top-color: var(--ink-2); }}
}}
</style>"""


# ---------------------------------------------------------------------------
# HTML-byggesteiner
# ---------------------------------------------------------------------------
# Ikoner tegnes som CSS-masker (st.html fjerner innebygd <svg>), så de arver tekstfargen.
_SVG = {
    "sjekk": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3.5 8.5 6.5 11.5 12.5 4.5'/></svg>",
    "kryss": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'><path d='M4 4l8 8M12 4l-8 8'/></svg>",
    "utrop": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'><path d='M8 3.5v5.5'/><circle cx='8' cy='12.25' r='.9' fill='black' stroke='none'/></svg>",
    "kalender": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.6' stroke-linecap='round'><rect x='2.5' y='3.5' width='11' height='10' rx='2'/><path d='M2.5 6.5h11M5.5 2v3M10.5 2v3'/></svg>",
    "valuta": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.6' stroke-linecap='round'><circle cx='8' cy='8' r='5.75'/><path d='M8 4.5v7M9.9 6.1c-.4-.6-1.1-.9-1.9-.9-1 0-1.8.6-1.8 1.4 0 1.9 3.8 1 3.8 2.8 0 .8-.8 1.4-1.9 1.4-.8 0-1.6-.4-2-1'/></svg>",
    "bok": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round'><path d='M3 3.5c1.7-.6 3.4-.4 5 .8v9c-1.6-1.2-3.3-1.4-5-.8zM13 3.5c-1.7-.6-3.4-.4-5 .8v9c1.6-1.2 3.3-1.4 5-.8z'/></svg>",
    "dok": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='1.6' stroke-linejoin='round' stroke-linecap='round'><path d='M4 1.75h5.25L12.5 5v9.25H4z'/><path d='M9 1.75V5.25h3.5M6.25 8.5h4M6.25 11h4'/></svg>",
    "chev": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M6 3.5 10.5 8 6 12.5'/></svg>",
}


def _maske(svg: str) -> str:
    return f'url("data:image/svg+xml,{quote(svg)}")'


def ikon_css() -> str:
    regler = [f".i-{navn}::before {{ -webkit-mask-image: {_maske(svg)}; mask-image: {_maske(svg)}; }}"
              for navn, svg in _SVG.items() if navn not in ("chev", "dok")]
    chev = _maske(_SVG["chev"])
    regler.append(
        f".rd-nt summary::after {{ content: ''; width: 14px; height: 14px; background: var(--muted);"
        f" -webkit-mask: {chev} no-repeat center / contain; mask: {chev} no-repeat center / contain;"
        f" transition: transform var(--spring-t) var(--spring); }}")
    regler.append(".rd-nt[open] summary::after { transform: rotate(90deg); }")
    return "\n".join(regler)


def topp() -> str:
    return ('<div class="rd-brand"><img src="app/static/favicon.png" alt="">Regnskap</div>'
            '<h1 class="rd-h1">Regnskapsdashboard</h1>'
            '<p class="rd-lede">Søk opp et selskap på Oslo Børs, eller skriv inn et hvilket som helst org.nr, og se nøkkeltallene fra siste årsregnskap. '
            'Data rett fra Brønnøysundregistrene.</p>')


def seksjon(tittel: str, undertekst: Optional[str] = None) -> str:
    u = f"<p>{e(undertekst)}</p>" if undertekst else ""
    return f'<div class="rd-seksjon"><h2>{e(tittel)}</h2>{u}</div>'


def pille(tekst: str, klasse: str = "", ikon: Optional[str] = None, tittel: Optional[str] = None) -> str:
    i = f" i-{ikon}" if ikon else ""
    t = f' title="{e(tittel)}"' if tittel else ""
    return f'<span class="rd-pille {klasse}{i}"{t}>{e(tekst)}</span>'


def monogram(navn: Optional[str]) -> str:
    ord_ = [o for o in (navn or "?").replace("-", " ").split()
            if o.upper() not in {"AS", "ASA", "SA", "DA", "ANS", "BA", "NUF", "&", "OG"}]
    return "".join(o[0] for o in ord_[:2]).upper() or "?"


def pent_navn(navn: Optional[str]) -> str:
    """«EQUINOR ASA» -> «Equinor ASA». Navn som allerede har små bokstaver beholdes."""
    if not navn:
        return "Ukjent navn"
    if navn != navn.upper():
        return navn
    behold = {"AS", "ASA", "SA", "DA", "ANS", "BA", "NUF", "IKS", "KF", "SE"}

    def ord_(o: str) -> str:
        # Forkortelser uten vokaler (DNB, BW, LPG) beholdes; ellers stor forbokstav, også etter bindestrek.
        if o in behold or (o.isalpha() and not any(v in o for v in "AEIOUYÆØÅ")):
            return o
        return "-".join(d.capitalize() for d in o.split("-"))
    return " ".join(ord_(o) for o in navn.split())


def fakta(par: Iterable[Tuple[str, Optional[str], bool]]) -> str:
    """(etikett, verdi-html, er_html). Verdi None -> «mangler»."""
    rader = []
    for etikett, verdi, er_html in par:
        if verdi in (None, ""):
            dd = '<dd class="rd-mangler">mangler</dd>'
        else:
            dd = f"<dd>{verdi if er_html else e(verdi)}</dd>"
        rader.append(f"<div><dt>{e(etikett)}</dt>{dd}</div>")
    return f'<dl class="rd-fakta">{"".join(rader)}</dl>'


def kpi(etikett: str, tall: str, enhet: str, delta: Optional[Tuple[float, str]], tittel: str,
        info_html: str = "") -> str:
    if tall == "mangler":
        big = '<div class="big" style="color:var(--muted);font-size:1.25rem;font-style:italic">mangler</div>'
    else:
        big = f'<div class="big">{e(tall)}<span class="unit">{e(enhet)}</span></div>'
    if delta is not None:
        pst, aar = delta
        klasse = "opp" if pst >= 0 else "ned"
        pil = "▲" if pst >= 0 else "▼"
        tekst = f"{pil} {abs(pst):.1f} %".replace(".", ",")
        d = f'<div class="delta"><b class="{klasse}">{tekst}</b>fra {e(aar)}</div>'
    else:
        d = '<div class="delta">&nbsp;</div>'
    big = big.replace('<div class="big"', f'<div class="big" title="{e(tittel)}"', 1)
    return f'<div class="rd-kpi"><div class="lbl"><span>{e(etikett)}</span>{info_html}</div>{big}{d}</div>'


def nokkeltall_rad(navn: str, verdi: str, forrige: Optional[str], formel: str,
                   forklaring: str, inndata: List[Tuple[str, str]], merknad: Optional[str],
                   enhet: str = "") -> str:
    mangler = verdi in ("mangler", "ikke meningsfull")
    f = f'<span class="forrige">{e(forrige)}</span>' if forrige else ""
    inn = "".join(f"<dt>{e(a)}</dt><dd>{e(b)}</dd>" for a, b in inndata)
    m = f'<p class="rd-merknad">{e(merknad)}</p>' if merknad else ""
    return (f'<details class="rd-nt"><summary>'
            f'<span class="navn">{e(navn)}{f}</span>'
            f'<span class="verdi{" mangler" if mangler else ""}">{e(verdi)}'
            f'{f"<small>{e(enhet)}</small>" if enhet and not mangler else ""}</span>'
            f'</summary><div class="innhold"><span class="rd-formel">{e(formel)}</span>'
            f'<div>{e(forklaring)}</div><dl class="rd-inndata">{inn}</dl>{m}</div></details>')


def gruppe(tittel: str, rader: List[str], info_html: str = "") -> str:
    return f'<section class="rd-gruppe"><h3><span>{e(tittel)}</span>{info_html}</h3>{"".join(rader)}</section>'

def info(tittel: str, avsnitt: List[str], side: str = "hoyre") -> str:
    """Liten «i»-knapp som åpner en kort forklaring. ``side`` = hvilken side boblen henger fra
    («hoyre» for knapper i høyre hjørne av et kort, «venstre» for knapper langt til venstre)."""
    tekst = "".join(f"<p>{e(a)}</p>" for a in avsnitt)
    return (f'<details class="rd-info {side}"><summary aria-label="Forklaring: {e(tittel)}" '
            f'title="Hva betyr dette?">i</summary>'
            f'<div class="rd-boble" role="note"><b>{e(tittel)}</b>{tekst}</div></details>')


def tittelrad(tittel: str, undertittel: Optional[str] = None, info_html: str = "",
              luft_under: bool = False) -> str:
    """Korttittel (+ undertittel) med i-knappen i høyre hjørne."""
    u = f'<p class="rd-kortundertittel">{e(undertittel)}</p>' if undertittel else ""
    stil_ = ' style="margin-bottom:14px"' if luft_under else ""
    return (f'<div class="rd-tittelrad"{stil_}><div><p class="rd-korttittel">{e(tittel)}</p>{u}</div>'
            f'{info_html}</div>')


def ordliste(innslag: List[Tuple[str, List[str]]]) -> str:
    rader = "".join(f'<div class="rd-ord"><dt>{e(t)}</dt><dd>{"".join(f"<p>{e(a)}</p>" for a in avsnitt)}</dd></div>'
                    for t, avsnitt in innslag)
    return f'<dl class="rd-ordliste">{rader}</dl>'


def bunn() -> str:
    return ('<div class="rd-bunn">Kilde: Enhetsregisteret og Regnskapsregisteret (data.brreg.no), lisens NLOD. '
            'Tallene er slik selskapet har rapportert dem. Nøkkeltallene er forenklede og regnet på balansen '
            'ved årets slutt. Appen bruker ingen KI.</div>')


def driver_rad(nr: int, tittel: str, tekst: str, effekt: str, opp: bool, bredde: float,
               noytral: bool = False) -> str:
    """Én driver-rad. ``noytral`` gir blå/grå i stedet for grønn/rød – for balanseposter,
    der en økning (f.eks. i gjeld) verken er god eller dårlig i seg selv."""
    retning = ("pluss" if opp else "minus") if noytral else ("opp" if opp else "ned")
    b = max(2.0, min(100.0, bredde))
    return (f'<div class="rd-driver"><span class="nr">{nr}</span>'
            f'<span class="tittel">{e(tittel)}</span><span class="effekt {retning}">{e(effekt)}</span>'
            f'<span class="tekst">{e(tekst)}</span>'
            f'<span class="stav"><i class="{retning}" style="width:{b:.1f}%"></i></span></div>')


def hendelse_rad(dato: str, tittel: str, detalj: Optional[str]) -> str:
    d = f'<span class="detalj">{e(detalj)}</span>' if detalj else '<span class="detalj"></span>'
    return f'<div class="rd-hendelse"><span class="dato">{e(dato)}</span><span class="tittel">{e(tittel)}</span>{d}</div>'


def tabell(overskrift: List[str], rader: List[List[str]], valgt_kol: Optional[int] = None,
           grupperader: Iterable[int] = (), sterke: Iterable[Tuple[int, int]] = ()) -> str:
    """Enkel tabell. Celler med teksten «mangler» får egen stil. ``valgt_kol`` uthever valgt år,
    ``sterke`` er (rad, kolonne) for celler som skal merkes som sterkest."""
    grupper = set(grupperader)
    sterk = set(sterke)
    def kl(i: int, tekst: str, n: int = -1) -> str:
        k = []
        if (n, i) in sterk:
            k.append("sterkest")
        if i == valgt_kol:
            k.append("valgt")
        if tekst in ("mangler", "ikke meningsfull"):
            k.append("mangler")
        return f' class="{" ".join(k)}"' if k else ""
    hode = "".join(f"<th{kl(i, '')}>{e(h)}</th>" for i, h in enumerate(overskrift))
    kropp = []
    for n, rad in enumerate(rader):
        if n in grupper:
            kropp.append(f'<tr class="gruppe"><td colspan="{len(overskrift)}">{e(rad[0])}</td></tr>')
        else:
            kropp.append("<tr>" + "".join(f"<td{kl(i, c, n)}>{e(c)}</td>" for i, c in enumerate(rad)) + "</tr>")
    return (f'<div class="rd-tabell-rull"><table class="rd-tabell"><thead><tr>{hode}</tr></thead>'
            f'<tbody>{"".join(kropp)}</tbody></table></div>')


def pdf_lenker(lenker: List[Tuple[int, str]]) -> str:
    return '<div class="rd-pdf">' + "".join(
        f'<a href="{e(url)}" target="_blank" rel="noopener" title="Årsregnskap {aar} (PDF)">{aar}</a>'
        for aar, url in lenker) + "</div>"
