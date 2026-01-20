import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Borsa", page_icon="📈", layout="wide")

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except Exception as e:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- 1. CARICAMENTO CARTE (Tutte) ---
@st.cache_data(ttl=600)
def get_cards_list():
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    # Distinguiamo le Showcase nel menu
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

# --- 2. CARICAMENTO PREZZI (Solo per la carta scelta - Risolve il limite 1000) ---
def get_card_history(card_id):
    res = supabase.table("card_prices")\
        .select("*")\
        .eq("card_id", card_id)\
        .order("recorded_at", desc=False)\
        .execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

# --- INTERFACCIA ---
df_cards = get_cards_list()

st.sidebar.header("🔍 Navigazione")
card_options = sorted(df_cards['display_name'].unique())
selected_display = st.sidebar.selectbox("Scegli una carta:", card_options)
langs = st.sidebar.multiselect("Mercati:", ["EN", "CN"], default=["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Dati"):
    st.cache_data.clear()
    st.rerun()

# Recupero dati della carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# Recupero lo storico (solo per questa carta)
prices_subset = get_card_history(card_id)

# --- LAYOUT DASHBOARD ---
st.title(f"📊 Borsa: {selected_display}")
st.divider()

col_img, col_chart = st.columns([1, 2])

with col_img:
    # Mostra l'immagine (usiamo use_container_width che è il più compatibile)
    if card_info['image_url']:
        st.image(card_info['image_url'], use_container_width=True)
    
    st.subheader("📝 Info")
    st.write(f"**ID:** `{card_id}`")
    st.write(f"**Rarità:** {card_info['rarity']}")
    st.write(f"**Set:** {card_info.get('set_code', 'Origins')}")
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

with col_chart:
    st.subheader("📈 Andamento Prezzo")
    
    if not prices_subset.empty:
        # Applichiamo il filtro lingua scelto dall'utente
        plot_data = prices_subset[prices_subset['language'].isin(langs)]
        
        if not plot_data.empty:
            # Grafico
            fig = px.line(
                plot_data,
                x="recorded_at",
                y="price_low",
                color="language",
                markers=True,
                labels={"recorded_at": "Data", "price_low": "Prezzo (€)"},
                template="plotly_dark",
                color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"}
            )
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # Tabella
            st.subheader("🕒 Storico Record")
            st.dataframe(plot_data.sort_values('recorded_at', ascending=False), use_container_width=True)
        else:
            st.warning("Seleziona una lingua per vedere il grafico.")
    else:
        st.error(f"Nessun prezzo trovato per {card_id}. Hai runnato lo scraper?")

st.divider()
st.caption("Riftbound Borsa - Dati CardTrader")
