# app.py
import io
import json
import math
from datetime import datetime, timezone

import pandas as pd
import pytz
import requests
import streamlit as st
from dateutil import parser as dtparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ------------------ Konstanter ------------------
STHLM_TZ = pytz.timezone("Europe/Stockholm")
SMHI_ENDPOINT = (
    "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2/"
    "geotype/point/lon/{lon}/lat/{lat}/data.json"
)

DEFAULT_PRESETS = [
    ("Stockholm", 59.3293, 18.0686),
    ("Göteborg", 57.7089, 11.9746),
    ("Malmö", 55.60498, 13.00382),
    ("Umeå", 63.8258, 20.2630),
    ("Östersund", 63.1792, 14.6357),
]

# ------------------ Hjälpare ------------------
def _requests_session():
    """Session med retry och vettig User-Agent."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({
        "User-Agent": "streamlit-smhi/1.0 (+example@example.com)"
    })
    return s

def _safe_get_param(param_list, name, default=math.nan):
    for p in param_list:
        if p.get("name") == name:
            vals = p.get("values") or []
            return vals[0] if vals else default
    return default

def _utc_to_local(ts_iso: str) -> datetime:
    dt = dtparser.isoparse(ts_iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(STHLM_TZ)

def _deg_to_cardinal(deg: float) -> str:
    if math.isnan(deg):
        return "—"
    dirs = ["N","NNO","NO","ONO","O","OSO","SO","SSO","S","SSV","SV","VSV","V","VNV","NV","NNV"]
    ix = int((deg + 11.25) // 22.5) % 16
    return dirs[ix]

@st.cache_data(ttl=600, show_spinner=False)
def fetch_smhi(lat: float, lon: float) -> dict:
    """Hämta SMHI JSON med robust felhantering."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Ogiltiga koordinater: lat={lat}, lon={lon}")

    url = SMHI_ENDPOINT.format(lat=f"{lat:.6f}", lon=f"{lon:.6f}")
    s = _requests_session()
    r = s.get(url, timeout=15)

    # Statuskod
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        sample = (r.text or "")[:200].replace("\n", " ")
        raise RuntimeError(f"SMHI HTTP {r.status_code}: {e}. Svar (början): {sample!r}")

    # Content-Type kontrolleras
    ct = r.headers.get("Content-Type", "")
    if "application/json" not in ct:
        sample = (r.text or "")[:200].replace("\n", " ")
        raise RuntimeError(f"SMHI svarade inte med JSON (Content-Type={ct!r}). Svar (början): {sample!r}")

    # JSON-dekodning
    try:
        return r.json()
    except (json.JSONDecodeError, ValueError) as e:
        sample = (r.text or "")[:200].replace("\n", " ")
        raise RuntimeError(f"Kunde inte tolka JSON från SMHI: {e}. Svar (början): {sample!r}")

def smhi_to_df(payload: dict) -> pd.DataFrame:
    """Konvertera SMHI payload -> DataFrame i lokal tid."""
    ts = payload.get("timeSeries", []) or []
    rows = []
    for item in ts:
        valid_time = _utc_to_local(item["validTime"])
        params = item.get("parameters", [])
        rows.append(
            {
                "time": valid_time,
                "temp_C": _safe_get_param(params, "t"),
                "wind_ms": _safe_get_param(params, "ws"),
                "gust_ms": _safe_get_param(params, "gust"),
                "precip_mm_h": _safe_get_param(params, "pmean", 0.0),
                "cloud_okta": _safe_get_param(params, "tcc_mean"),
                "msl_hPa": _safe_get_param(params, "msl"),
                "rh_pct": _safe_get_param(params, "r"),
                "wind_deg": _safe_get_param(params, "wd"),
            }
        )
    df = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
    # Fyll ev. saknade nederbördsvärden med 0 (SMHI saknar ibland pmean)
    if "precip_mm_h" in df:
        df["precip_mm_h"] = df["precip_mm_h"].fillna(0.0)
    return df

def pick_current_row(df: pd.DataFrame) -> pd.Series:
    """Närmaste tidssteg till nu."""
    now = datetime.now(STHLM_TZ)
    idx = (df["time"] - now).abs().idxmin()
    return df.loc[idx]

# ------------------ UI ------------------
st.set_page_config(page_title="SMHI Väder", page_icon="🌦️", layout="wide")

st.sidebar.title("Inställningar")
st.sidebar.caption("Data: SMHI metfcst (pmp3g/version/2).")

preset_names = [f"{n} ({lat:.4f}, {lon:.4f})" for n, lat, lon in DEFAULT_PRESETS] + ["Egen position…"]
preset = st.sidebar.selectbox("Snabbval plats", preset_names)

if preset != "Egen position…":
    i = preset_names.index(preset)
    name, lat, lon = DEFAULT_PRESETS[i]
else:
    c1, c2 = st.sidebar.columns(2)
    lat = c1.number_input("Lat", value=59.329300, format="%.6f")
    lon = c2.number_input("Lon", value=18.068600, format="%.6f")
    name = f"{lat:.4f},{lon:.4f}"

hours_ahead = st.sidebar.slider("Visa timmar framåt", min_value=12, max_value=72, value=48, step=12)
refresh = st.sidebar.button("🔄 Hämta igen", use_container_width=True)
if refresh:
    fetch_smhi.clear()

error_container = st.empty()
debug = st.expander("Teknisk felsökning", expanded=False)

# ------------------ Fetch ------------------
try:
    payload = fetch_smhi(lat, lon)
except Exception as e:
    error_container.error(f"Misslyckades att läsa SMHI-data: {e}")
    with debug:
        st.code(SMHI_ENDPOINT.format(lat=f"{lat:.6f}", lon=f"{lon:.6f}"))
        st.write("Tips: prova igen, testa annan plats, eller kontrollera proxy/brandvägg.")
    st.stop()

df = smhi_to_df(payload)
if df.empty:
    error_container.warning("Fick inget tidsseriedata från SMHI.")
    st.stop()

now_local = datetime.now(STHLM_TZ)
df_window = df[(df["time"] >= now_local) & (df["time"] <= now_local + pd.Timedelta(hours=hours_ahead))]

# ------------------ Header ------------------
st.title("🌦️ SMHI Väder (Streamlit)")
approved = payload.get("approvedTime")
approved_local = _utc_to_local(approved).strftime("%Y-%m-%d %H:%M") if approved else "okänd"
st.caption(f"Plats: **{name}** • Koordinater: **{lat:.4f}, {lon:.4f}** • Godkänd prognos: {approved_local} ({STHLM_TZ})")

# ------------------ Nuvarande läge ------------------
cur = pick_current_row(df)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Temperatur (°C)", f"{cur['temp_C']:.1f}")
m2.metric("Vind (m/s)", f"{cur['wind_ms']:.1f}")
m3.metric("Byvind (m/s)", f"{cur['gust_ms']:.1f}")
m4.metric("Nederbörd (mm/h)", f"{cur['precip_mm_h']:.2f}")
m5.metric("Moln (0–8 okta)", "—" if math.isnan(cur["cloud_okta"]) else f"{cur['cloud_okta']:.0f}")
m6.metric("Vindriktning", f"{_deg_to_cardinal(cur['wind_deg'])} ({cur['wind_deg']:.0f}°)" if not math.isnan(cur["wind_deg"]) else "—")

# ------------------ Grafer ------------------
st.subheader("Prognos")
tab1, tab2, tab3 = st.tabs(["🌡️ Temperatur", "💨 Vind", "🌧️ Nederbörd"])

with tab1:
    st.line_chart(df_window.set_index("time")[["temp_C"]])

with tab2:
    st.line_chart(df_window.set_index("time")[["wind_ms", "gust_ms"]])

with tab3:
    st.bar_chart(df_window.set_index("time")[["precip_mm_h"]])

# ------------------ Tabell + export ------------------
st.subheader("Detaljer (tabell)")
show_cols = [
    "time", "temp_C", "wind_ms", "gust_ms", "wind_deg",
    "precip_mm_h", "cloud_okta", "msl_hPa", "rh_pct"
]
nice = (
    df_window[show_cols]
    .rename(columns={
        "time": "Tid (lokal)",
        "temp_C": "Temp (°C)",
        "wind_ms": "Vind (m/s)",
        "gust_ms": "Byvind (m/s)",
        "wind_deg": "Vindriktning (°)",
        "precip_mm_h": "Nederbörd (mm/h)",
        "cloud_okta": "Moln (0–8)",
        "msl_hPa": "Tryck (hPa)",
        "rh_pct": "RF (%)",
    })
)

# Visa även kardinalriktning
if "Vindriktning (°)" in nice.columns:
    nice["Vind"] = nice["Vindriktning (°)"].apply(_deg_to_cardinal)

st.dataframe(nice, use_container_width=True, hide_index=True)

csv = nice.to_csv(index=False).encode("utf-8")
st.download_button(
    "Ladda ner som CSV",
    data=csv,
    file_name=f"smhi_forecast_{lat:.4f}_{lon:.4f}.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption("Källa: SMHI öppna data (pmp3g). Tider i Europe/Stockholm.")