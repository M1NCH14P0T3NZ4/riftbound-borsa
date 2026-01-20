import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Riftbound Borsa Carte", 
    page_icon="📈", 
    layout="wide"
)

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except Exception:
    st.error("Configura i Secrets su Streamlit Cloud (SUPABASE_URL e SUPABASE_KEY).")
    st.stop()

# --- 1. CARICAMENTO ANAGRAFICA ---
@st.cache_data(ttl=600)
def get_cards_list():
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    # Crea il nome per il menu a tendina
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

# --- 2. CARICAMENTO MOVERS (La parte che ti funzionava) ---
@st.cache_data(ttl=300)
def get_market_movers():
    try:
        # Interroga la Vista SQL che abbiamo creato insieme
        res = supabase.table("market_movers").select("*").order("pct_change", desc=True).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

# --- 3. CARICAMENTO STORICO (Solo per la carta scelta) ---
def get_card_history(card_id):
    # Query mirata per ID, ordinata per data
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

# --- ESECUZIONE CARICAMENTO ---
df_cards = get_cards_list()
df_movers = get_market_movers()

# --- SIDEBAR ---
st.sidebar.header("🔍 Filtri Borsa")
selected_set = st.sidebar.selectbox("Filtra per Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))

# Filtro carte in base al set
if selected_set != "Tutti":
    available_cards = df_cards[df_cards['set_code'] == selected_set]
else:
    available_cards = df_cards

card_list = sorted(available_cards['display_name'].unique())
selected_display = st.sidebar.selectbox("Seleziona una carta:", card_list)
selected_langs = st.sidebar.multiselect("Lingue:", ["EN", "CN"], default=["EN", "CN"])

if st.sidebar.button("🔄 Forza Aggiornamento"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- LAYOUT PRINCIPALE ---
st.title(f"📊 Borsa: {selected_display}")

# --- SEZIONE TREND (Market Movers) ---
with st.expander("🚀 Analisi Trend Ultime 24h (Tutte le carte)", expanded=False):
    if not df_movers.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("📈 **Top Gainers**")
            st.dataframe(df_movers.head(5)[['name', 'pct_change', 'current_price']], hide_index=True, width=None)
        with c2:
            st.write("📉 **Top Losers**")
            st.dataframe(df_movers.tail(5).sort_values('pct_change')[['name', 'pct_change', 'current_price']], hide_index=True, width=None)
    else:
        st.info("Dati insufficienti per calcolare i trend. Continua lo scraping giornaliero!")

st.divider()

col_left, col_right = st.columns([1, 2.5])

# --- COLONNA SINISTRA: Immagine e Specs ---
with col_left:
    if card_info['image_url']:
        st.image(card_info['image_url'], use_container_width=True)
    
    st.subheader("📝 Info Carta")
    st.markdown(f"""
    - **ID:** `{card_id}`
    - **Rarità:** {card_info['rarity']}
    - **Dominio:** {card_info['domain']}
    - **Set:** {card_info['set_code']}
    """)
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

# --- COLONNA DESTRA: Grafico e Storico ---
with col_right:
    st.subheader("📈 Andamento Prezzo")
    
    # Recuperiamo lo storico specifico
    df_history = get_card_history(card_id)
    
    if not df_history.empty:
        # Filtriamo per lingua scelta dall'utente
        df_plot = df_history[df_history['language'].isin(selected_langs)].copy()
        
        if not df_plot.empty:
            # Metrica Variazione (ultimo prezzo inserito)
            last_rec = df_plot.iloc[-1]
            st.metric(label=f"Ultimo Prezzo ({last_rec['language']})", value=f"{last_rec['price_low']} €")

            # Grafico a linee
            fig = px.line(
                df_plot, x="recorded_at", y="price_low", color="language",
                markers=True, template="plotly_dark",
                color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"},
                labels={"recorded_at": "Data", "price_low": "Prezzo (€)"}
            )
            fig.update_layout(hovermode="x unified", xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)

            # Tabella Dati
            with st.expander("📄 Storico Completo"):
                st.dataframe(df_plot.sort_values('recorded_at', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.warning("Seleziona una lingua nella sidebar per visualizzare i dati.")
    else:
        st.error(f"⚠️ Nessun dato trovato nel database per l'ID: {card_id}")
        st.info("Verifica che lo scraper stia usando l'ID corretto o clicca su 'Aggiorna Dati'.")

st.divider()
st.caption("Riftbound Card Market Dashboard | Powered by Supabase")
