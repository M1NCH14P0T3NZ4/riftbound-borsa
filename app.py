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
    st.error("Configura i Secrets (URL e KEY) per connettere il database.")
    st.stop()

# --- CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def get_cards_list():
    """Recupera l'elenco completo delle carte"""
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    # Formattazione nome per distinguere le varianti
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

def get_card_history(card_id):
    """Recupera lo storico prezzi per una singola carta"""
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

@st.cache_data(ttl=3600)
def get_market_movers():
    """Recupera i dati della Vista SQL 'market_movers'"""
    try:
        res = supabase.table("market_movers").select("*").order("pct_change", desc=True).execute()
        return pd.DataFrame(res.data)
    except:
        return pd.DataFrame()

# --- AVVIO APP ---
df_cards = get_cards_list()
df_movers = get_market_movers()

# --- SIDEBAR ---
st.sidebar.title("🔍 Navigazione")
st.sidebar.divider()

# Filtro Set
set_list = ["Tutti"] + sorted(list(df_cards['set_code'].unique()))
selected_set = st.sidebar.selectbox("Filtra per Set", set_list)

# Filtro Carte in base al set
if selected_set != "Tutti":
    filtered_cards = df_cards[df_cards['set_code'] == selected_set]
else:
    filtered_cards = df_cards

card_options = sorted(filtered_cards['display_name'].unique())
selected_display = st.sidebar.selectbox("Cerca una carta", card_options)
langs = st.sidebar.multiselect("Mercati", ["EN", "CN"], default=["EN", "CN"])

st.sidebar.divider()
if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- HEADER: MARKET MOVERS ---
st.title("💹 Riftbound Market Intelligence")
st.markdown("Analisi dei prezzi e trend in tempo reale")

with st.expander("🚀 Visualizza i Top Movers delle ultime 24h", expanded=False):
    if not df_movers.empty:
        col_g, col_l = st.columns(2)
        with col_g:
            st.write("📈 **Top Gainers (Salite)**")
            for _, row in df_movers.head(3).iterrows():
                st.success(f"{row['name']} (+{row['pct_change']}%)")
        with col_l:
            st.write("📉 **Top Losers (Scese)**")
            for _, row in df_movers.tail(3).sort_values("pct_change").iterrows():
                st.error(f"{row['name']} ({row['pct_change']}%)")
    else:
        st.info("Esegui lo scraping per 2 giorni consecutivi per attivare i trend.")

st.divider()

# --- LAYOUT PRINCIPALE ---
col_left, col_right = st.columns([1, 2.5])

# Colonna sinistra: Immagine e Specs
with col_left:
    st.image(card_info['image_url'], use_container_width=True)
    
    st.subheader("📝 Info Carta")
    st.markdown(f"""
    - **ID:** `{card_id}`
    - **Rarità:** {card_info['rarity']}
    - **Set:** {card_info['set_code']}
    - **Might/Energy:** {card_info['might']} / {card_info['energy_cost']}
    """)
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

# Colonna destra: Grafico e Storico
with col_right:
    st.subheader(f"📊 Analisi: {selected_display}")
    
    prices_subset = get_card_history(card_id)
    if not prices_subset.empty:
        # Filtro lingua
        prices_subset = prices_subset[prices_subset['language'].isin(langs)]
        
        # Metrica ultimo prezzo
        last_en = prices_subset[prices_subset['language'] == 'EN']
        if not last_en.empty:
            p_val = last_en.iloc[-1]['price_low']
            delta = 0
            if len(last_en) > 1:
                delta = float(p_val) - float(last_en.iloc[-2]['price_low'])
            st.metric(label="Prezzo Attuale (EN)", value=f"{p_val} €", delta=f"{delta:.2f} €")

        # Grafico
        fig = px.line(
            prices_subset,
            x="recorded_at",
            y="price_low",
            color="language",
            markers=True,
            labels={"recorded_at": "Data", "price_low": "Prezzo (€)", "language": "Lingua"},
            template="plotly_dark",
            color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"}
        )
        fig.update_layout(hovermode="x unified", xaxis_title=None, yaxis_title="Prezzo (€)")
        st.plotly_chart(fig, use_container_width=True)

        # Tabella Grezza
        with st.expander("📄 Storico completo dati"):
            st.dataframe(
                prices_subset.sort_values('recorded_at', ascending=False)[['recorded_at', 'language', 'price_low']],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("Nessun dato di prezzo registrato per questa carta.")

st.divider()
st.caption("Dati estratti automaticamente da CardTrader. Sviluppato per la community di Riftbound.")
