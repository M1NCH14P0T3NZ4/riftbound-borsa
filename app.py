import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Borsa AI", page_icon="📈", layout="wide")

# Nascondi menu Streamlit
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def get_all_base_data():
    # 1. Recupero anagrafica carte
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    
    # 2. Recupero ultimi prezzi globali per i Movers (EN)
    # Prendiamo gli ultimi 2000 record per avere abbastanza storico per i confronti
    p_res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty:
        df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    
    return df_c, df_p

def get_card_history(card_id):
    """Recupera lo storico completo per la carta selezionata"""
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

# --- INIZIALIZZAZIONE DATI ---
df_cards, df_all_prices = get_all_base_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Navigazione")
st.sidebar.divider()

selected_set = st.sidebar.selectbox("Filtra per Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
filtered_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]

selected_display = st.sidebar.selectbox("Seleziona una carta:", sorted(filtered_cards['display_name'].unique()))
selected_lang = st.sidebar.radio("Mercato:", ["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']
df_history = get_card_history(card_id)

# --- LAYOUT PRINCIPALE CON TABS ---
st.title("💹 Riftbound Market Intelligence")
tab1, tab2, tab3 = st.tabs(["🔍 Dettaglio & IA", "🌍 Analisi Mercato", "🎒 Il mio Portfolio"])

# --- TAB 1: DETTAGLIO CARTA (Con Media Mobile) ---
with tab1:
    col_img, col_chart = st.columns([1, 2.5])
    
    with col_img:
        st.image(card_info['image_url'], use_container_width=True)
        st.subheader("📝 Specifiche")
        st.write(f"**ID:** `{card_id}` | **Rarità:** {card_info['rarity']}")
        if card_info['ability']:
            with st.expander("Vedi Abilità"):
                st.write(card_info['ability'])
        
        # LOGICA SEGNALE IA
        df_lang = df_history[df_history['language'] == selected_lang]
        if not df_lang.empty:
            last_p = float(df_lang.iloc[-1]['price_low'])
            last_t = float(df_lang.iloc[-1]['price_trend'])
            st.subheader("🤖 Segnale IA")
            if last_p > last_t * 1.15: st.warning(f"⚠️ SOPRAVALUTATA (+{round(((last_p/last_t)-1)*100)}%)")
            elif last_p < last_t * 0.85: st.success(f"🔥 OCCASIONE (-{round((1-(last_p/last_t))*100)}%)")
            else: st.info("⚖️ MERCATO STABILE")

    with col_chart:
        if not df_lang.empty:
            # Grafico a doppia linea (Melted)
            temp_df = df_lang[['recorded_at', 'price_low', 'price_trend']].copy()
            df_melted = temp_df.melt(id_vars=['recorded_at'], value_vars=['price_low', 'price_trend'],
                                     var_name='Legenda', value_name='Prezzo')
            df_melted['Legenda'] = df_melted['Legenda'].map({'price_low': 'Prezzo Real', 'price_trend': 'Media Mobile'})

            fig = px.line(df_melted, x="recorded_at", y="Prezzo", color="Legenda",
                         markers=True, template="plotly_dark",
                         color_discrete_map={'Prezzo Real': "#00CC96", 'Media Mobile': "#FFA15A"})
            fig.update_layout(hovermode="x unified", xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
            
            st.metric("Valore Attuale", f"{last_p} €", f"{round(last_p - last_t, 2)} € vs Media")
        else:
            st.warning("Nessun dato per questa lingua.")

# --- TAB 2: ANALISI MERCATO (Gainers, Losers & Value) ---
with tab2:
    st.header("🌍 Panoramica Mercato (EN)")
    
    if not df_all_prices.empty:
        # Calcolo Movers
        df_en = df_all_prices[df_all_prices['language'] == 'EN'].copy()
        latest_market = df_en.sort_values('recorded_at').groupby('card_id').last().reset_index()
        
        # Valore Totale
        total_val = latest_market['price_low'].sum()
        st.metric("Valore Totale Set Origins (1x)", f"{round(total_val, 2)} €")
        
        # Calcolo variazioni %
        movers = []
        for cid in latest_market['card_id'].unique():
            h = df_en[df_en['card_id'] == cid].sort_values('recorded_at', ascending=False)
            if len(h) >= 2:
                curr, prev = float(h.iloc[0]['price_low']), float(h.iloc[1]['price_low'])
                if prev > 0:
                    movers.append({'Carta': df_cards[df_cards['card_id']==cid]['name'].values[0], 
                                   'Variazione %': round(((curr-prev)/prev)*100, 2), 'Prezzo': curr})
        
        df_m = pd.DataFrame(movers)
        col_g, col_l = st.columns(2)
        with col_g:
            st.success("📈 Top Gainers (24h)")
            st.dataframe(df_m.sort_values('Variazione %', ascending=False).head(5), hide_index=True, use_container_width=True)
        with col_l:
            st.error("📉 Top Losers (24h)")
            st.dataframe(df_m.sort_values('Variazione %', ascending=True).head(5), hide_index=True, use_container_width=True)

# --- TAB 3: PORTFOLIO (Il tuo Raccoglitore) ---
with tab3:
    st.header("🎒 Gestione Collezione")
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        qty = st.number_input(f"Copie possedute di '{card_info['name']}'", min_value=0, step=1)
        buy_p = st.number_input("Prezzo di acquisto unitario (€)", min_value=0.0)
    
    if qty > 0 and not df_lang.empty:
        current_v = last_p * qty
        profit = current_v - (buy_p * qty)
        with c_p2:
            st.subheader("Risultato")
            st.metric("Valore Attuale", f"{round(current_v, 2)} €", f"{round(profit, 2)} € Profitto")
            if profit > 0: st.balloons()

st.divider()
st.caption("Riftbound Borsa v4.0 - All Rights Reserved")
