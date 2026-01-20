import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Riftbound Borsa", page_icon="📈", layout="wide")

# Nascondi menu Streamlit
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- 1. CARICAMENTO ANAGRAFICA (Cached) ---
@st.cache_data(ttl=600)
def get_cards_list():
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

# --- 2. CARICAMENTO STORICO (Specifico per carta - SOLUZIONE AL LIMITE 1000) ---
def get_card_history(card_id):
    # Chiediamo SOLO i prezzi per questo ID specifico. 
    # Questo evita di scaricare migliaia di righe inutili e risolve i giorni mancanti.
    res = supabase.table("card_prices")\
        .select("*")\
        .eq("card_id", card_id)\
        .order("recorded_at", desc=False)\
        .execute()
    
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        # Normalizziamo le date a "Giorno/Mese/Anno" per raggruppare eventuali rilevazioni multiple
        df['data_visuale'] = df['recorded_at'].dt.date
    return df

# --- 3. LOGICA TOP CARTE (Semplificata e funzionante) ---
@st.cache_data(ttl=3600)
def get_market_summary():
    # Prende gli ultimi 2000 prezzi inseriti per avere una panoramica (qui il limite va bene)
    res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(1000).execute()
    return pd.DataFrame(res.data)

# --- AVVIO APP ---
df_cards = get_cards_list()

# --- SIDEBAR ---
st.sidebar.title("🔍 Navigazione")
selected_set = st.sidebar.selectbox("Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
filtered_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]

selected_display = st.sidebar.selectbox("Cerca Carta:", sorted(filtered_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Mercati:", ["EN", "CN"], default=["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- CARICAMENTO PREZZI (SOLO PER QUESTA CARTA) ---
with st.spinner('Recupero storico completo...'):
    df_history = get_card_history(card_id)

# --- LAYOUT PRINCIPALE ---
st.title(f"📊 {selected_display}")
st.caption(f"Set: {card_info['set_code']} | ID: {card_id}")
st.divider()

col_img, col_chart = st.columns([1, 2.5])

with col_img:
    st.image(card_info['image_url'], width='stretch')
    st.subheader("📝 Info")
    st.write(f"**Rarità:** {card_info['rarity']}")
    st.write(f"**Dominio:** {card_info['domain']}")
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

with col_chart:
    if not df_history.empty:
        # Filtriamo per lingua
        plot_df = df_history[df_history['language'].isin(selected_langs)]
        
        if not plot_df.empty:
            # Metrica Ultimo Prezzo
            last_p = plot_df.iloc[-1]['price_low']
            st.metric("Ultimo Prezzo Rilevato", f"{last_p} €")

            # GRAFICO COMPLETO
            fig = px.line(
                plot_df, 
                x="recorded_at", 
                y="price_low", 
                color="language",
                markers=True,
                labels={"recorded_at": "Data", "price_low": "Prezzo (€)"},
                template="plotly_dark",
                color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"}
            )
            fig.update_layout(hovermode="x unified", xaxis_title=None)
            st.plotly_chart(fig, width='stretch')

            # TABELLA STORICA (Mostra TUTTI i giorni ora)
            st.subheader("📋 Storico Rilevazioni")
            st.dataframe(
                plot_df.sort_values('recorded_at', ascending=False)[['recorded_at', 'language', 'price_low']],
                width='stretch',
                hide_index=True
            )
        else:
            st.warning("Seleziona una lingua (EN o CN) per visualizzare il grafico.")
    else:
        st.error(f"⚠️ Nessun dato trovato per {card_id}.")
        st.info("Assicurati di aver runnato lo scraper per questa carta.")

st.divider()
st.caption("Riftbound Borsa - Sistema di monitoraggio storico completo.")
