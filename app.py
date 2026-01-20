import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Borsa Carte", page_icon="📈", layout="wide")

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except Exception:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def get_cards_list():
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    # Formattazione per menu a tendina
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

def get_card_history(card_id):
    # Recupera i dati ordinati per tempo
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

@st.cache_data(ttl=300)
def get_market_movers():
    try:
        res = supabase.table("market_movers").select("*").order("pct_change", desc=True).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

# --- AVVIO APP ---
df_cards = get_cards_list()
df_movers = get_market_movers()

# --- SIDEBAR ---
st.sidebar.title("🔍 Filtri Borsa")
selected_set = st.sidebar.selectbox("Filtra per Set", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))

# Filtro carte
if selected_set != "Tutti":
    available_cards = df_cards[df_cards['set_code'] == selected_set]
else:
    available_cards = df_cards

selected_display = st.sidebar.selectbox("Seleziona Carta:", sorted(available_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Lingue:", ["EN", "CN"], default=["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Dati"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- HEADER MOVERS ---
st.title(f"📊 Borsa: {selected_display}")
with st.expander("🚀 Analisi Trend Ultime 24h (Tutte le carte)"):
    if not df_movers.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("📈 **Top Gainers**")
            st.dataframe(df_movers.head(5)[['name', 'pct_change', 'current_price']], hide_index=True, use_container_width=True)
        with c2:
            st.write("📉 **Top Losers**")
            st.dataframe(df_movers.tail(5).sort_values('pct_change')[['name', 'pct_change', 'current_price']], hide_index=True, use_container_width=True)
    else:
        st.info("Dati insufficienti per i trend. Continua lo scraping giornaliero!")

st.divider()

# --- LAYOUT PRINCIPALE ---
col_left, col_right = st.columns([1, 2.5])

with col_left:
    # Immagine
    st.image(card_info['image_url'], use_container_width=True)
    
    # Specifiche
    st.subheader("📝 Info")
    st.markdown(f"""
    - **ID:** `{card_id}`
    - **Rarità:** {card_info['rarity']}
    - **Might/Energy:** {card_info['might']}/{card_info['energy_cost']}
    """)
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

with col_right:
    # RECUPERO PREZZI (Logica rinforzata)
    df_history = get_card_history(card_id)
    
    if not df_history.empty:
        # Applichiamo il filtro lingua
        if selected_langs:
            df_plot = df_history[df_history['language'].isin(selected_langs)].copy()
        else:
            df_plot = df_history.copy()

        if not df_plot.empty:
            # Metrica Variazione
            last_rec = df_plot.iloc[-1]
            st.metric(label=f"Ultimo Prezzo ({last_rec['language']})", value=f"{last_rec['price_low']} €")

            # Grafico
            fig = px.line(
                df_plot, x="recorded_at", y="price_low", color="language",
                markers=True, template="plotly_dark",
                color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"},
                labels={"recorded_at": "Data", "price_low": "Prezzo (€)"}
            )
            fig.update_layout(hovermode="x unified", xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

            # Tabella
            with st.expander("📄 Storico Completo dei Prezzi"):
                st.dataframe(df_plot.sort_values('recorded_at', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.warning("Seleziona almeno una lingua nella sidebar per vedere il grafico.")
    else:
        st.error(f"⚠️ Nessun dato trovato nel database per l'ID: {card_id}")
        st.info("Verifica che lo scraper stia usando l'ID corretto per questa carta.")

st.divider()
st.caption("Riftbound Borsa v2.1")
