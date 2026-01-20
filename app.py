import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Riftbound Borsa", page_icon="📈", layout="wide")

# Nascondi menu Streamlit per un look più pulito
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def load_data():
    # Carica anagrafica
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    
    # Carica prezzi (Tutti i record per calcolare i movers e mostrare il grafico)
    p_res = supabase.table("card_prices").select("*").order("recorded_at", desc=False).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty:
        df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
        # Creiamo una data semplificata (senza ore/secondi) per raggruppare i giorni nel grafico
        df_p['date'] = df_p['recorded_at'].dt.strftime('%Y-%m-%d')
    return df_c, df_p

df_cards, df_all_prices = load_data()

# --- SIDEBAR ---
st.sidebar.title("🔍 Filtri")
selected_set = st.sidebar.selectbox("Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
filtered_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]

selected_display = st.sidebar.selectbox("Cerca Carta:", sorted(filtered_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Mercati:", ["EN", "CN"], default=["EN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# --- LOGICA CALCOLO MOVERS (Solo se utili) ---
def get_top_expensive(df_p, df_c):
    # Prende l'ultimo prezzo registrato per ogni carta e ordina per valore decrescente
    latest_prices = df_p.sort_values('recorded_at').groupby(['card_id', 'language']).last().reset_index()
    top_5 = latest_prices.sort_values('price_low', ascending=False).head(5)
    return pd.merge(top_5, df_c[['card_id', 'name']], on='card_id')

# --- LAYOUT PRINCIPALE ---
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']
df_history = df_all_prices[(df_all_prices['card_id'] == card_id) & (df_all_prices['language'].isin(selected_langs))]

st.title(f"📊 {selected_display}")
st.caption(f"Espansione: {card_info['set_code']} | ID: {card_id}")

# --- METRICHE IN ALTO ---
if not df_history.empty:
    m1, m2, m3 = st.columns(3)
    last_p = df_history.iloc[-1]['price_low']
    first_p = df_history.iloc[0]['price_low']
    diff = float(last_p) - float(first_p)
    
    m1.metric("Prezzo Attuale", f"{last_p} €")
    m2.metric("Variazione Totale", f"{round(diff, 2)} €", delta=f"{round(diff, 2)} €")
    m3.metric("Rarità", card_info['rarity'])

st.divider()

# --- GRAFICO E IMMAGINE ---
col_img, col_chart = st.columns([1, 2.5])

with col_img:
    st.image(card_info['image_url'], width='stretch')
    with st.expander("📝 Descrizione Abilità"):
        st.write(card_info['ability'] if card_info['ability'] else "Nessun testo abilità presente.")

with col_chart:
    if not df_history.empty:
        # GRAFICO OTTIMIZZATO
        fig = px.line(
            df_history, 
            x="recorded_at", 
            y="price_low", 
            color="language",
            markers=True,
            title="Andamento Storico (Prezzo Minimo)",
            template="plotly_dark",
            color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"}
        )
        
        # Forza il grafico a mostrare i giorni in modo lineare
        fig.update_layout(
            hovermode="x unified",
            xaxis_title=None,
            yaxis_title="Euro (€)",
            margin=dict(l=0, r=0, t=40, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nessun dato storico per questa carta.")

# --- TABELLA RIEPILOGATIVA ---
st.subheader("📋 Storico Rilevazioni")
if not df_history.empty:
    st.dataframe(
        df_history.sort_values('recorded_at', ascending=False)[['recorded_at', 'language', 'price_low']],
        use_container_width=True,
        hide_index=True
    )

# --- SEZIONE CARTE PIÙ COSTOSE (CORRETTA) ---
st.divider()
st.subheader("💎 Carte più preziose del set (Mercato EN)")
df_top = get_top_expensive(df_all_prices[df_all_prices['language']=='EN'], df_cards)
cols = st.columns(5)
for i, (_, row) in enumerate(df_top.iterrows()):
    cols[i].metric(row['name'], f"{row['price_low']} €")
