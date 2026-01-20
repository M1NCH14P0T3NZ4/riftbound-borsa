import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Riftbound Borsa AI", 
    page_icon="📈", 
    layout="wide"
)

# Nascondi menu Streamlit per un look pulito
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud (SUPABASE_URL e SUPABASE_KEY).")
    st.stop()

# --- CARICAMENTO DATI ---

@st.cache_data(ttl=600)
def get_cards_list():
    """Recupera l'anagrafica delle carte"""
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    # Crea il nome per il menu a tendina
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

def get_card_history(card_id):
    """Recupera lo storico prezzi specifico (ID puntuale)"""
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

# --- INTERFACCIA SIDEBAR ---
df_cards = get_cards_list()

st.sidebar.title("📊 Analisi Decisionale")
st.sidebar.divider()

# Filtro Set
set_list = ["Tutti"] + sorted(list(df_cards['set_code'].unique()))
selected_set = st.sidebar.selectbox("Filtra per Set:", set_list)

# Filtro Carte
if selected_set != "Tutti":
    available_cards = df_cards[df_cards['set_code'] == selected_set]
else:
    available_cards = df_cards

selected_display = st.sidebar.selectbox("Seleziona una carta:", sorted(available_cards['display_name'].unique()))

# Fondamentale: scegliamo una lingua alla volta per confrontare prezzo e media correttamente
selected_lang = st.sidebar.radio("Mercato di riferimento:", ["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- LAYOUT PRINCIPALE ---
st.title(f"📊 Borsa: {selected_display}")
st.caption(f"Supporto Decisionale basato su Media Mobile a 7 giorni (SMA)")
st.divider()

col_img, col_chart = st.columns([1, 2.5])

# Caricamento storico
df_history = get_card_history(card_id)

with col_img:
    # Immagine carta
    st.image(card_info['image_url'], use_container_width=True)
    
    # Specifiche
    st.subheader("📝 Specifiche")
    st.write(f"**ID:** `{card_id}`")
    st.write(f"**Rarità:** {card_info['rarity']} | **Set:** {card_info['set_code']}")
    
    # --- LOGICA SEGNALE IA ---
    if not df_history.empty:
        df_lang = df_history[df_history['language'] == selected_lang]
        if not df_lang.empty:
            last_price = float(df_lang.iloc[-1]['price_low'])
            last_trend = float(df_lang.iloc[-1]['price_trend'])
            
            st.subheader("🤖 Segnale IA")
            # Se il prezzo è più alto del 15% rispetto alla media mobile
            if last_price > last_trend * 1.15:
                st.warning(f"⚠️ **SOPRAVALUTATA**\nIl prezzo è del {round(((last_price/last_trend)-1)*100)}% sopra la media. Attendi una discesa.")
            # Se il prezzo è più basso del 15% rispetto alla media mobile
            elif last_price < last_trend * 0.85:
                st.success(f"🔥 **OCCASIONE**\nIl prezzo è del {round((1-(last_price/last_trend))*100)}% sotto la media. Ottimo momento per comprare!")
            else:
                st.info("⚖️ **STABILE**\nIl prezzo è in linea con il valore reale della settimana.")

with col_chart:
    if not df_history.empty:
        df_plot = df_history[df_history['language'] == selected_lang].copy()
        
        if not df_plot.empty:
            # Creazione del grafico con due linee
            # Trasformiamo i dati per avere una riga per ogni punto di ogni linea (Melt)
            df_melted = df_plot.melt(
                id_vars=['recorded_at'], 
                value_vars=['price_low', 'price_trend'],
                var_name='Tipo', value_name='Euro'
            )
            
            # Rinominiamo i tipi per la legenda
            df_melted['Tipo'] = df_melted['Tipo'].map({
                'price_low': 'Prezzo di Mercato',
                'price_trend': 'Media Mobile (Trend 7gg)'
            })

            fig = px.line(
                df_melted, 
                x="recorded_at", 
                y="Prezzo (Euro)", 
                color="Tipo",
                markers=True,
                labels={"recorded_at": "Data", "Prezzo (Euro)": "Prezzo (€)"},
                template="plotly_dark",
                color_discrete_map={
                    'Prezzo di Mercato': "#00CC96",      # Verde
                    'Media Mobile (Trend 7gg)': "#FFA15A" # Arancione
                }
            )
            
            fig.update_layout(
                hovermode="x unified",
                xaxis_title=None,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Metrica di confronto
            st.metric(
                label=f"Ultimo Prezzo ({selected_lang})", 
                value=f"{last_price} €", 
                delta=f"{round(last_price - last_trend, 2)} € rispetto alla media"
            )

            # Storico record
            with st.expander("📄 Visualizza tutti i record"):
                st.dataframe(df_plot.sort_values('recorded_at', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.warning(f"Nessun dato registrato per il mercato {selected_lang}.")
    else:
        st.info("Esegui lo scraper per generare i primi dati.")

st.divider()
st.caption("Riftbound Intelligence Dashboard • Dati analizzati in tempo reale")
