import streamlit as st
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

st.set_page_config(page_title="Sports Betting AI", page_icon="🏆", layout="wide")

st.title("🏆 Sports Betting AI")
st.caption("MLB • NFL • NBA • NHL • UFC | Noticias • lesiones • cuotas • análisis")

st.warning("⚠️ Esto es una herramienta de análisis. Las probabilidades son estimaciones y no garantizan ganancias.")

SPORTS = {
    "MLB": {
        "espn": "baseball/mlb",
        "odds": "baseball_mlb",
    },
    "NFL": {
        "espn": "football/nfl",
        "odds": "americanfootball_nfl",
    },
    "NBA": {
        "espn": "basketball/nba",
        "odds": "basketball_nba",
    },
    "NHL": {
        "espn": "hockey/nhl",
        "odds": "icehockey_nhl",
    },
    "UFC": {
        "espn": "mma/ufc",
        "odds": "mma_mixed_martial_arts",
    },
}

ODDS_API_KEY = st.secrets.get("ODDS_API_KEY", "")

def get_json(url, params=None):
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=120)
def get_games(sport):
    data = get_json(
        f"https://site.api.espn.com/apis/site/v2/sports/{SPORTS[sport]['espn']}/scoreboard"
    )
    return (data or {}).get("events", [])

@st.cache_data(ttl=300)
def get_news(query):
    try:
        r = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            timeout=15,
        )
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:10]:
            out.append({
                "title": item.findtext("title") or "",
                "link": item.findtext("link") or "",
                "date": item.findtext("pubDate") or "",
            })
        return out
    except Exception:
        return []

@st.cache_data(ttl=120)
def get_odds(sport):
    if not ODDS_API_KEY:
        return []
    data = get_json(
        f"https://api.the-odds-api.com/v4/sports/{SPORTS[sport]['odds']}/odds",
        {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
        },
    )
    return data or []

def american_to_prob(price):
    try:
        p = float(price)
        return (-p / (-p + 100)) if p < 0 else (100 / (p + 100))
    except Exception:
        return 0.0

def extract_match(event):
    try:
        comps = event["competitions"][0]["competitors"]
        home = next(x for x in comps if x.get("homeAway") == "home")
        away = next(x for x in comps if x.get("homeAway") == "away")
        return (
            home["team"]["displayName"],
            away["team"]["displayName"],
            event.get("date", ""),
            event.get("status", {}).get("type", {}).get("detail", ""),
        )
    except Exception:
        return None

def confidence_score(home, away):
    # Modelo inicial transparente: 53% local / 47% visitante.
    # Se añadirán estadísticas, lesiones y movimiento de línea en módulos posteriores.
    return 53.0, 47.0

def risk_label(p):
    if p >= 65:
        return "🔥 ALTA"
    if p >= 57:
        return "🟢 MODERADA"
    if p >= 52:
        return "🟡 LEVE"
    return "⚪ SIN VENTAJA"

sport = st.sidebar.selectbox("Deporte", list(SPORTS.keys()))
st.sidebar.info("Actualización automática de datos: ~2–5 min según la fuente.")
if st.sidebar.button("🔄 Actualizar"):
    st.cache_data.clear()
    st.rerun()

tab_games, tab_news, tab_odds, tab_model = st.tabs(
    ["🏟️ Juegos", "📰 Noticias", "💰 Cuotas", "🤖 Modelo"]
)

with tab_games:
    st.subheader(f"Juegos de {sport}")
    events = get_games(sport)

    if not events:
        st.info("No hay juegos disponibles ahora mismo o ESPN no respondió.")
    else:
        for event in events:
            match = extract_match(event)
            if not match:
                continue

            home, away, event_date, detail = match
            hp, ap = confidence_score(home, away)
            pick = home if hp >= ap else away
            pick_prob = max(hp, ap)

            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"### {away} vs {home}")
                if detail:
                    st.caption(detail)
                st.write(f"🏠 {home}: **{hp:.1f}%**")
                st.write(f"✈️ {away}: **{ap:.1f}%**")
            with c2:
                st.metric("AI Pick", pick)
                st.metric("Probabilidad", f"{pick_prob:.1f}%")
                st.write(risk_label(pick_prob))

            st.divider()

with tab_news:
    st.subheader("📰 Noticias recientes")
    query = st.text_input("Equipo, jugador o pelea", placeholder="Ej: Yankees, Chiefs, Lakers, UFC")
    if query:
        articles = get_news(query)
        if not articles:
            st.info("No se encontraron noticias.")
        for a in articles:
            st.markdown(f"**{a['title']}**")
            if a["date"]:
                st.caption(a["date"])
            if a["link"]:
                st.markdown(f"[Leer noticia]({a['link']})")
            st.divider()

with tab_odds:
    st.subheader("💰 Cuotas")
    odds = get_odds(sport)
    if not ODDS_API_KEY:
        st.info("Para activar cuotas reales, agrega ODDS_API_KEY en Streamlit Secrets.")
    elif not odds:
        st.warning("No se pudieron obtener cuotas en este momento.")
    else:
        rows = []
        for game in odds:
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            for book in game.get("bookmakers", []):
                for market in book.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for out in market.get("outcomes", []):
                        price = out.get("price")
                        rows.append({
                            "Juego": f"{away} vs {home}",
                            "Casa": book.get("title", ""),
                            "Selección": out.get("name", ""),
                            "Cuota": price,
                            "Prob. implícita": round(american_to_prob(price) * 100, 1),
                        })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

with tab_model:
    st.subheader("🤖 Cómo decide el sistema")
    st.markdown("""
**Objetivo del modelo completo:**
- 📊 rendimiento reciente
- 🏠 ventaja de localía
- 🚑 lesiones y jugadores descartados
- 📰 noticias recientes
- 😴 descanso y calendario
- 📈 movimiento de las líneas
- 💰 comparación entre probabilidad estimada y cuota
- 🧮 cálculo de valor esperado (EV)
- ⚠️ nivel de riesgo

**Importante:** esta primera versión ya funciona como dashboard, pero el porcentaje mostrado
en la sección de juegos es un **modelo base**, no una predicción profesional. No debe usarse
como señal automática para apostar dinero real.
""")

st.divider()
st.caption(f"Última actualización local: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
