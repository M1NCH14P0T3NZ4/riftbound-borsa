import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
import re

# --- CONFIGURAZIONE PAGINA ---
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

# --- FUNZIONI DI SUPPORTO ---
def get_ct_url_slug(name, set_code, is_sh):
    """Genera lo slug per il link CardTrader"""
    clean = re.sub(r'[^a-z0-9\s-]', '', name.lower().replace("'", "-"))
    slug = clean.replace(" ", "-")
    while "--" in slug: slug = slug.replace("--", "-")
    suffix = "-alternate-art" if is_sh else ""
    return f"https://www.cardtrader.com/en/cards/{slug.strip('-')}{suffix}-{set_code.lower()}"

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def get_all_base_data():
    # 1. Carte
    c_res = supabase.table("cards").select("*").execute()
    df_c = pd.DataFrame(c_res.data)
    df_c['display_name'] = df_c.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    
    # 2. Prezzi (Ultimi 2000 per analisi globale)
    p_res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(2000).execute()
    df_p = pd.DataFrame(p_res.data)
    if not df_p.empty:
        df_p['recorded_at'] = pd.to_datetime(df_p['recorded_at'])
    
    return df_c, df_p

def get_single_card_history(card_id):
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

# --- INIZIALIZZAZIONE ---
df_cards, df_all_prices = get_all_base_data()

# --- SIDEBAR ---
st.sidebar.title("📊 Navigazione")
selected_set = st.sidebar.selectbox("Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
filtered_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]

selected_display = st.sidebar.selectbox("Cerca Carta:", sorted(filtered_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Lingue:", ["EN", "CN"], default=["EN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero dati carta
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']
df_history = get_single_card_history(card_id)

# --- LAYOUT DASHBOARD ---
st.title("💹 Riftbound Market Intelligence")

tab1, tab2, tab3 = st.tabs(["🔍 Dettaglio Carta", "🌍 Analisi Mercato", "🎒 Il mio Portfolio"])

# --- TAB 1: DETTAGLIO CARTA ---
with tab1:
    col_img, col_chart = st.columns([1, 2.5])
    with col_img:
        st.image(card_info['image_url'], width='stretch')
        # Tasto Acquisto
        ct_link = get_ct_url_slug(card_info['name'], card_info['set_code'], card_info['is_showcase'])
        st.link_button("🛒 Comprala su CardTrader", ct_link, use_container_width=True)
        
        st.subheader("📝 Specifiche")
        st.write(f"**Rarità:** {card_info['rarity']} | **Set:** {card_info['set_code']}")
        if card_info['ability']:
            with st.expander("Vedi Abilità"):
                st.write(card_info['ability'])
    
    with col_chart:
        if not df_history.empty:
            plot_df = df_history[df_history['language'].isin(selected_langs)]
            if not plot_df.empty:
                last_p = float(plot_df.iloc[-1]['price_low'])
                delta_val = 0
                if len(plot_df) > 1:
                    delta_val = last_p - float(plot_df.iloc[-2]['price_low'])
                
                st.metric("Ultimo Prezzo Rilevato", f"{last_p} €", delta=f"{round(delta_val, 2)} €")

                fig = px.line(plot_df, x="recorded_at", y="price_low", color="language",
                             markers=True, template="plotly_dark",
                             color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"})
                fig.update_layout(hovermode="x unified", xaxis_title=None, margin=dict(t=10))
                st.plotly_chart(fig, width='stretch')
            else:
                st.warning("Seleziona una lingua.")
        else:
            st.error("Storico non trovato per questa carta.")

# --- TAB 2: ANALISI MERCATO ---
with tab2:
    st.header("🌍 Panoramica Origins & Spiritforged")
    
    if not df_all_prices.empty:
        # 1. Calcolo Valore Totale Set (Solo EN)
        latest_market = df_all_prices[df_all_prices['language'] == 'EN'].sort_values('recorded_at').groupby('card_id').last().reset_index()
        total_set_value = latest_market['price_low'].sum()
        
        # 2. Calcolo Gainers/Losers (confronto ultimi 2 giorni)
        movers_list = []
        for cid in latest_market['card_id'].unique():
            history = df_all_prices[(df_all_prices['card_id'] == cid) & (df_all_prices['language'] == 'EN')].sort_values('recorded_at', ascending=False)
            if len(history) >= 2:
                curr = float(history.iloc[0]['price_low'])
                prev = float(history.iloc[1]['price_low'])
                if prev > 0:
                    pct = round(((curr - prev) / prev) * 100, 2)
                    name = df_cards[df_cards['card_id'] == cid]['name'].values[0]
                    movers_list.append({'Carta': name, 'Variazione': pct, 'Prezzo': curr})
        
        df_movers = pd.DataFrame(movers_list)

        # UI Stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Valore Totale Set (1x)", f"{round(total_set_value, 2)} €")
        
        if not df_movers.empty:
            with st.container():
                col_g, col_l = st.columns(2)
                with col_g:
                    st.success("📈 Top Gainers (EN)")
                    st.dataframe(df_movers.sort_values('Variazione', ascending=False).head(5), hide_index=True, width='stretch')
                with col_l:
                    st.error("📉 Top Losers (EN)")
                    st.dataframe(df_movers.sort_values('Variazione', ascending=True).head(5), hide_index=True, width='stretch')
    else:
        st.info("Attendi che lo scraper accumuli più dati per l'analisi dei trend.")

# --- TAB 3: PORTFOLIO ---
with tab3:
    st.header("🎒 Il mio Raccoglitore")
    st.write("Gestisci le tue carte e monitora il valore del tuo investimento.")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        qty = st.number_input(f"Quante copie hai di '{selected_display}'?", min_value=0, step=1)
        buy_price = st.number_input("Prezzo medio di acquisto (€)", min_value=0.0)
    
    if qty > 0 and not df_history.empty:
        current_p = float(df_history.iloc[-1]['price_low'])
        invested = qty * buy_price
        current_val = qty * current_p
        profit = current_val - invested
        
        with col_p2:
            st.metric("Valore Attuale", f"{round(current_val, 2)} €", delta=f"{round(profit, 2)} € Profitto")
            st.progress(min(max(current_val / (invested if invested > 0 else 1), 0.0), 1.0), text="Rendimento rispetto all'acquisto")

st.divider()
st.caption("Riftbound Card Market Dashboard | Real-time prices via Scraper Bot")
