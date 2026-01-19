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

# --- CONNESSIONE SUPABASE (SICUREZZA TRAMITE SECRETS) ---
# Queste variabili verranno lette dalle impostazioni di Streamlit Cloud
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except Exception as e:
    st.error("Errore: Chiavi di configurazione non trovate. Configura i 'Secrets' su Streamlit Cloud.")
    st.stop()

# --- 1. CARICAMENTO ANAGRAFICA (Cached) ---
@st.cache_data(ttl=600)
def get_cards_list():
    # Recuperiamo tutte le info delle carte
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    
    # Creazione nome visuale per il menu a tendina
    def format_name(row):
        base = row['name']
        if row.get('is_showcase'): 
            return f"{base} (✨ Showcase)"
        return base
    
    df['display_name'] = df.apply(format_name, axis=1)
    return df

# --- 2. CARICAMENTO STORICO PREZZI (Solo per la carta scelta) ---
def get_card_history(card_id):
    # Recupera i prezzi filtrando per ID e ordinandoli per data
    res = supabase.table("card_prices")\
        .select("*")\
        .eq("card_id", card_id)\
        .order("recorded_at", desc=False)\
        .execute()
    
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

# --- INTERFACCIA DASHBOARD ---
try:
    df_cards = get_cards_list()
except Exception as e:
    st.error(f"Errore nel caricamento del database: {e}")
    st.stop()

# --- SIDEBAR ---
st.sidebar.header("🔍 Navigazione Mercato")

# Selezione Set
set_options = ["Tutti"] + list(df_cards['set_code'].unique())
selected_set = st.sidebar.selectbox("Filtra per Set:", set_options)

# Filtro carte in base al set
if selected_set != "Tutti":
    available_cards = df_cards[df_cards['set_code'] == selected_set]
else:
    available_cards = df_cards

# Menu scelta carta
card_options = sorted(available_cards['display_name'].unique())
selected_display = st.sidebar.selectbox("Scegli una carta:", card_options)

# Scelta Lingua
langs = st.sidebar.multiselect("Mostra Mercati:", ["EN", "CN"], default=["EN", "CN"])

# Tasto Refresh manuale
if st.sidebar.button("🔄 Forza Aggiornamento"):
    st.cache_data.clear()
    st.rerun()

# --- RECUPERO DATI CARTA SELEZIONATA ---
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

with st.spinner('Caricamento dati borsa...'):
    prices_subset = get_card_history(card_id)

# Filtro lingua sui dati ricevuti
if not prices_subset.empty:
    prices_subset = prices_subset[prices_subset['language'].isin(langs)]

# --- LAYOUT DASHBOARD ---
st.title(f"📊 Borsa: {selected_display}")
st.caption(f"ID: {card_id} | Set: {card_info.get('set_code', 'Origins')}")
st.divider()

col_img, col_chart = st.columns([1, 2.5])

# COLONNA SINISTRA: Visualizzazione Carta
with col_img:
    if card_info['image_url']:
        st.image(card_info['image_url'], use_container_width=True)
    else:
        st.warning("Immagine non trovata")

    st.subheader("📝 Info Carta")
    st.markdown(f"""
    - **Rarità:** `{card_info['rarity']}`
    - **Dominio:** `{card_info['domain']}`
    - **Costo Energy:** `{card_info['energy_cost']}`
    - **Might:** `{card_info['might']}`
    """)
    
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

# COLONNA DESTRA: Grafico e Tabella
with col_chart:
    st.subheader("📈 Andamento Prezzo")
    
    if not prices_subset.empty:
        # Metrica ultimo prezzo (Inglese)
        en_data = prices_subset[prices_subset['language'] == 'EN']
        if not en_data.empty:
            last_p = en_data.iloc[-1]['price_low']
            # Calcolo delta se ci sono almeno 2 giorni
            delta = None
            if len(en_data) >= 2:
                delta = float(last_p) - float(en_data.iloc[-2]['price_low'])
            st.metric(label="Prezzo attuale (EN)", value=f"{last_p} €", delta=f"{delta:.2f} €" if delta else None)

        # Creazione grafico Plotly
        fig = px.line(
            prices_subset,
            x="recorded_at",
            y="price_low",
            color="language",
            markers=True,
            labels={"recorded_at": "Data", "price_low": "Prezzo (€)", "language": "Mercato"},
            template="plotly_dark",
            color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"}
        )
        
        fig.update_layout(
            hovermode="x unified",
            xaxis_title=None,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # Tabella Storica
        with st.expander("📄 Dati cronologici completi"):
            st.dataframe(
                prices_subset.sort_values('recorded_at', ascending=False)[['recorded_at', 'language', 'price_low']],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("⚠️ Nessun dato di prezzo trovato per questa carta.")
        st.info("Esegui lo scraper sul tuo PC per inviare i dati a Supabase.")

st.divider()
st.caption("Riftbound Analytics Dashboard | Dati forniti da CardTrader via Scraper Bot")