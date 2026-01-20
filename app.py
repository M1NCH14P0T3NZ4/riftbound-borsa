import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Borsa", page_icon="📈", layout="wide")

# --- CONNESSIONE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Errore Secrets!")
    st.stop()

# --- CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def get_all_data():
    # Carichiamo anagrafica
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    
    # Carichiamo TUTTI i prezzi per calcolare i Market Movers (Guerilla Mode)
    p_res = supabase.table("card_prices").select("card_id, price_low, recorded_at, language").order("recorded_at", desc=True).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty:
        df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    
    return df_c, df_p

# --- LOGICA MARKET MOVERS ---
def calculate_movers(df_prices, df_cards):
    if df_prices.empty: return pd.DataFrame(), pd.DataFrame()
    
    # Prendiamo solo mercato EN per i trend globali
    df_en = df_prices[df_prices['language'] == 'EN'].copy()
    
    # Per ogni carta, prendiamo l'ultimo e il penultimo prezzo
    movers = []
    for cid in df_en['card_id'].unique():
        card_history = df_en[df_en['card_id'] == cid].sort_values('recorded_at', ascending=False)
        if len(card_history) >= 2:
            current = card_history.iloc[0]['price_low']
            previous = card_history.iloc[1]['price_low']
            change = ((float(current) - float(previous)) / float(previous)) * 100
            
            name = df_cards[df_cards['card_id'] == cid]['name'].values[0]
            movers.append({'name': name, 'change': round(change, 2), 'price': current})
    
    df_m = pd.DataFrame(movers)
    if df_m.empty: return pd.DataFrame(), pd.DataFrame()
    
    gainers = df_m[df_m['change'] > 0].sort_values('change', ascending=False).head(5)
    losers = df_m[df_m['change'] < 0].sort_values('change', ascending=True).head(5)
    return gainers, losers

# --- ESECUZIONE ---
df_cards, df_all_prices = get_all_data()
df_gainers, df_losers = calculate_movers(df_all_prices, df_cards)

# --- SIDEBAR ---
st.sidebar.title("🔍 Mercato Riftbound")
selected_set = st.sidebar.selectbox("Set:", ["Tutti"] + list(df_cards['set_code'].unique()))
filtered_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]

selected_display = st.sidebar.selectbox("Cerca Carta:", sorted(filtered_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Lingue:", ["EN", "CN"], default=["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Dati"):
    st.cache_data.clear()
    st.rerun()

# --- LAYOUT DASHBOARD ---
st.title("📊 Riftbound Market Intelligence")

# --- SEZIONE 1: MARKET OVERVIEW ---
col_stats1, col_stats2, col_stats3 = st.columns(3)

with col_stats1:
    st.subheader("📈 Top Gainers (24h)")
    if not df_gainers.empty:
        for _, r in df_gainers.iterrows():
            st.write(f"**{r['name']}** : green[+{r['change']}%] ({r['price']}€)")
    else: st.caption("Nessuna variazione rilevante")

with col_stats2:
    st.subheader("📉 Top Losers (24h)")
    if not df_losers.empty:
        for _, r in df_losers.iterrows():
            st.write(f"**{r['name']}** : red[{r['change']}%] ({r['price']}€)")
    else: st.caption("Nessuna variazione rilevante")

with col_stats3:
    st.subheader("💎 Most Valuable")
    # Prende le 3 carte più costose in assoluto dall'ultimo rilvamento
    top_expensive = df_all_prices.sort_values(['recorded_at', 'price_low'], ascending=[False, False]).drop_duplicates('card_id').head(3)
    for _, r in top_expensive.iterrows():
        name = df_cards[df_cards['card_id'] == r['card_id']]['name'].values[0]
        st.write(f"**{name}**: {r['price_low']}€")

st.divider()

# --- SEZIONE 2: DETTAGLIO CARTA ---
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

col_img, col_chart = st.columns([1, 2.5])

with col_img:
    st.image(card_info['image_url'], use_container_width=True)
    st.subheader("📝 Specifiche")
    st.markdown(f"""
    - **ID:** `{card_id}`
    - **Rarità:** {card_info['rarity']}
    - **Set:** {card_info['set_code']}
    """)
    if card_info['ability']:
        st.info(f"**Abilità:**\n\n{card_info['ability']}")

with col_chart:
    st.subheader(f"📈 Storico Prezzi: {selected_display}")
    
    # Filtriamo i prezzi per questa carta specifica
    df_history = df_all_prices[df_all_prices['card_id'] == card_id]
    
    if not df_history.empty:
        plot_df = df_history[df_history['language'].isin(selected_langs)].sort_values('recorded_at')
        
        # Grafico
        fig = px.line(
            plot_df, x="recorded_at", y="price_low", color="language",
            markers=True, template="plotly_dark",
            color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"},
            labels={"recorded_at": "Data", "price_low": "Prezzo (€)"}
        )
        fig.update_layout(hovermode="x unified", xaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

        # Metrica veloce
        if len(plot_df) > 1:
            last_p = plot_df.iloc[-1]['price_low']
            prev_p = plot_df.iloc[-2]['price_low']
            st.metric("Ultimo Prezzo", f"{last_p} €", f"{round(float(last_p)-float(prev_p), 2)} €")

        with st.expander("📄 Dati Grezzi"):
            st.dataframe(plot_df.sort_values('recorded_at', ascending=False), use_container_width=True, hide_index=True)
    else:
        st.warning("Dati non ancora disponibili per questa carta.")

st.divider()
st.caption("Riftbound Borsa v3.0 | Dati aggiornati automaticamente tramite GitHub Actions.")
