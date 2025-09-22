import streamlit as st
import sqlite3
import pandas as pd
import traceback

# ---------------------------
# CONFIGURAÇÃO INICIAL
# ---------------------------
players = [
    "Necrod", "Mayara", "Cabo", "Cronos", "Ramos",
    "Diogo", "Senju", "Erick", "Magnata", "Vanahein"
]

# ---------------------------
# BANCO DE DADOS
# ---------------------------
def init_db():
    conn = sqlite3.connect("liga.db")
    c = conn.cursor()

    # Tabela de jogadores
    c.execute('''CREATE TABLE IF NOT EXISTS jogadores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT UNIQUE,
                    vitorias INTEGER DEFAULT 0,
                    estrelas_ataque INTEGER DEFAULT 0,
                    estrelas_defesa INTEGER DEFAULT 0,
                    porc_ataque REAL DEFAULT 0,
                    porc_defesa REAL DEFAULT 0,
                    tempo_ataque REAL DEFAULT 0,
                    tempo_defesa REAL DEFAULT 0
                )''')

    # Tabela de rodadas
    c.execute('''CREATE TABLE IF NOT EXISTS rodadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rodada INTEGER,
                    jogador1 TEXT,
                    jogador2 TEXT,
                    estrelas_j1 INTEGER,
                    estrelas_j2 INTEGER,
                    porc_j1 REAL,
                    porc_j2 REAL,
                    tempo_j1 REAL,
                    tempo_j2 REAL
                )''')

    conn.commit()
    return conn

# ---------------------------
# FUNÇÕES AUXILIARES
# ---------------------------
def get_jogadores(conn):
    return pd.read_sql("SELECT * FROM jogadores", conn)

def get_rodadas(conn):
    return pd.read_sql("SELECT * FROM rodadas", conn)

def inicializar_jogadores(conn):
    for nome in players:
        try:
            conn.execute("INSERT INTO jogadores (nome) VALUES (?)", (nome,))
        except:
            pass
    conn.commit()

def gerar_rodadas(conn):
    existentes = pd.read_sql("SELECT COUNT(*) as qtd FROM rodadas", conn).iloc[0]["qtd"]
    if existentes > 0:
        return
    
    n = len(players)
    lista = players.copy()
    if n % 2 != 0:
        lista.append("BYE")
        n += 1
    
    rodadas = []
    for i in range(n - 1):
        pares = []
        for j in range(n // 2):
            p1 = lista[j]
            p2 = lista[n - 1 - j]
            if p1 != "BYE" and p2 != "BYE":
                pares.append((p1, p2))
        rodadas.append(pares)
        lista.insert(1, lista.pop())
    
    for r, jogos in enumerate(rodadas, start=1):
        for j1, j2 in jogos:
            conn.execute("""INSERT INTO rodadas 
                            (rodada, jogador1, jogador2, estrelas_j1, estrelas_j2, porc_j1, porc_j2, tempo_j1, tempo_j2)
                            VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0)""",
                         (r, j1, j2))
    conn.commit()

def registrar_resultado(conn, rodada, j1, j2, e1, e2, p1, p2, t1, t2):
    conn.execute("""UPDATE rodadas SET 
                        estrelas_j1=?, estrelas_j2=?, 
                        porc_j1=?, porc_j2=?, 
                        tempo_j1=?, tempo_j2=?
                    WHERE rodada=? AND jogador1=? AND jogador2=?""",
                 (e1, e2, p1, p2, t1, t2, rodada, j1, j2))
    conn.commit()
    atualizar_classificacao(conn, j1, j2, e1, e2, p1, p2, t1, t2)

def atualizar_classificacao(conn, j1, j2, e1, e2, p1, p2, t1, t2):
    if e1 > e2:
        conn.execute("UPDATE jogadores SET vitorias = vitorias + 1 WHERE nome = ?", (j1,))
    elif e2 > e1:
        conn.execute("UPDATE jogadores SET vitorias = vitorias + 1 WHERE nome = ?", (j2,))

    conn.execute("UPDATE jogadores SET estrelas_ataque = estrelas_ataque + ? WHERE nome = ?", (e1, j1))
    conn.execute("UPDATE jogadores SET estrelas_ataque = estrelas_ataque + ? WHERE nome = ?", (e2, j2))

    conn.execute("UPDATE jogadores SET estrelas_defesa = estrelas_defesa + ? WHERE nome = ?", (e2, j1))
    conn.execute("UPDATE jogadores SET estrelas_defesa = estrelas_defesa + ? WHERE nome = ?", (e1, j2))

    conn.execute("UPDATE jogadores SET porc_ataque = porc_ataque + ?, porc_defesa = porc_defesa + ? WHERE nome = ?", (p1, p2, j1))
    conn.execute("UPDATE jogadores SET porc_ataque = porc_ataque + ?, porc_defesa = porc_defesa + ? WHERE nome = ?", (p2, p1, j2))

    conn.execute("UPDATE jogadores SET tempo_ataque = tempo_ataque + ?, tempo_defesa = tempo_defesa + ? WHERE nome = ?", (t1, t2, j1))
    conn.execute("UPDATE jogadores SET tempo_ataque = tempo_ataque + ?, tempo_defesa = tempo_defesa + ? WHERE nome = ?", (t2, t1, j2))

    conn.commit()

# ---------------------------
# ESTILO VISUAL BÁSICO
# ---------------------------
# Cores suaves (ajustáveis)
TOP_GREEN_1 = '#d9f5df'
TOP_GREEN_2 = '#c2ebc8'
BOTTOM_RED_1 = '#ffd6d6'
BOTTOM_RED_2 = '#ffb3b3'

# ---------------------------
# APP STREAMLIT
# ---------------------------
st.set_page_config(page_title="Liga do 13°", layout="wide")
st.title("🏆 Liga do 13° – Temporada 1")

conn = init_db()
inicializar_jogadores(conn)
gerar_rodadas(conn)

menu = st.sidebar.radio("Navegação", ["Classificação", "Rodadas", "Cadastrar Resultados"])

# DEBUG
try:
    df_tmp = get_jogadores(conn)
    st.write(f"DEBUG: jogadores cadastrados = {len(df_tmp)}")
except Exception:
    st.write("DEBUG: erro ao obter jogadores do DB")
    st.text(traceback.format_exc())

# ---------------------------
# CLASSIFICAÇÃO
# ---------------------------
if menu == "Classificação":
    st.subheader("📊 Tabela de Classificação")

    try:
        df = get_jogadores(conn)
        if df.empty:
            st.info("Nenhum jogador cadastrado. Inicialize jogadores ou verifique o banco de dados.")
        else:
            # remove coluna id para não aparecer
            df = df.drop(columns=['id'], errors='ignore')

            # ordenação — mantém a lógica anterior
            df = df.sort_values(
                by=["vitorias", "estrelas_ataque", "estrelas_defesa", 
                    "porc_ataque", "porc_defesa", "tempo_ataque", "tempo_defesa"],
                ascending=[False, False, True, False, True, True, True]
            ).reset_index(drop=True)

            # posição com base na ordenação (1,2,3...)
            df["Posição"] = range(1, len(df) + 1)

            # renomear colunas para exibir bonito
            df = df.rename(columns={
                "nome": "Nome",
                "vitorias": "Vitórias",
                "estrelas_ataque": "⭐ Atk",
                "estrelas_defesa": "⭐ Def",
                "porc_ataque": "% Atk",
                "porc_defesa": "% Def",
                "tempo_ataque": "⏱ Atk",
                "tempo_defesa": "⏱ Def"
            })

            # adicionar medalhas NO FINAL do nome (ex.: "Nome 🥇")
            def add_medal_end(nome, pos):
                if pos == 1:
                    return f"{nome} 🥇"
                elif pos == 2:
                    return f"{nome} 🥈"
                elif pos == 3:
                    return f"{nome} 🥉"
                else:
                    return nome

            df['Nome'] = df.apply(lambda row: add_medal_end(row['Nome'], row['Posição']), axis=1)

            # preparar cópia para exibição e formatação
            df_display = df.copy()

            # Formatar tempos (segundos -> MM:SS ou H:MM:SS)
            def format_time_seconds(val):
                try:
                    s = int(round(float(val)))
                except:
                    return '' if pd.isna(val) else str(val)
                h = s // 3600
                m = (s % 3600) // 60
                sec = s % 60
                if h > 0:
                    return f"{h}:{m:02d}:{sec:02d}"
                else:
                    return f"{m:02d}:{sec:02d}"

            for c in ['⏱ Atk', '⏱ Def']:
                if c in df_display.columns:
                    df_display[c] = df_display[c].apply(format_time_seconds)

            # Formatar porcentagens como barra visual (HTML) — usar escape=False no to_html
            def pct_to_bar(v):
                try:
                    pct = max(0, min(100, int(round(float(v)))))
                except:
                    return ''
                return (f"<div class='pbar' title='{pct}%'>"
                        f"<div class='pbar-fill' style='width:{pct}%;'></div>"
                        f"<div class='pbar-label'>{pct}%</div>"
                        f"</div>")

            for c in ['% Atk', '% Def']:
                if c in df_display.columns:
                    df_display[c] = df_display[c].apply(pct_to_bar)

            # garantir inteiros nas colunas inteiras
            for c in ['Posição', 'Vitórias', '⭐ Atk', '⭐ Def']:
                if c in df_display.columns:
                    df_display[c] = df_display[c].apply(lambda v: (str(int(v)) if pd.notna(v) and str(v) != '' else ''))

            # gerar HTML com to_html sem índice e permitindo HTML nas células
            html_table = df_display.to_html(index=False, escape=False, classes='classtable', border=0)

            # CSS + estilo para a barra de porcentagem
            css = """
            <style>
            .classtable{font-family:Inter, Roboto, Arial; border-collapse:collapse; width:100%; box-shadow: 0 6px 20px rgba(0,0,0,0.25); border-radius:8px; overflow:hidden;}
            .classtable thead th{background:#0f1724; color:#e6eef3; padding:10px 14px; text-align:left; font-weight:700; border-bottom:1px solid rgba(255,255,255,0.04);}
            .classtable td{padding:10px 14px; vertical-align:middle; color:#071014;}
            .classtable tr:hover{filter:brightness(0.98);} 
            .classtable td.name{ font-weight:500; }
            .classtable td.pos{ width:64px; text-align:center; font-weight:700; }
            .pbar{ background: rgba(0,0,0,0.04); border-radius:8px; position:relative; height:18px; width:100px; display:inline-block; vertical-align:middle; margin-right:6px;}
            .pbar-fill{ background:linear-gradient(90deg,#6ee7b7,#34d399); height:100%; border-radius:8px;}
            .pbar-label{ position:absolute; right:6px; top:1px; font-size:12px; color:#073; font-weight:700;}
            .classtable td .pbar{ margin:0 auto; display:block; }
            </style>
            """

            st.markdown(css + html_table, unsafe_allow_html=True)

    except Exception:
        st.error("Erro ao carregar dados de classificação. Veja o log abaixo:")
        st.text(traceback.format_exc())

# ---------------------------
# RODADAS
# ---------------------------
elif menu == "Rodadas":
    st.subheader("📅 Rodadas")
    rodadas = get_rodadas(conn)
    if rodadas.empty:
        st.info("Nenhum confronto registrado ainda.")
    else:
        for r in sorted(rodadas["rodada"].unique()):
            st.markdown(f"### Rodada {r}")
            st.dataframe(
                rodadas[rodadas["rodada"] == r][["jogador1", "jogador2", "estrelas_j1", "estrelas_j2"]],
                use_container_width=True
            )

# ---------------------------
# CADASTRAR RESULTADOS
# ---------------------------
elif menu == "Cadastrar Resultados":
    st.subheader("✍️ Registrar Resultado")

    rodadas = get_rodadas(conn)
    rodada = st.selectbox("Rodada", sorted(rodadas["rodada"].unique()))
    jogos = rodadas[rodadas["rodada"] == rodada][["jogador1", "jogador2"]].values.tolist()

    jogo = st.selectbox("Confronto", [f"{j1} vs {j2}" for j1, j2 in jogos])
    j1, j2 = jogo.split(" vs ")

    e1 = st.number_input(f"⭐ Estrelas {j1}", 0, 3, step=1)
    e2 = st.number_input(f"⭐ Estrelas {j2}", 0, 3, step=1)
    p1 = st.number_input(f"% Ataque {j1}", 0.0, 100.0, step=0.1)
    p2 = st.number_input(f"% Ataque {j2}", 0.0, 100.0, step=0.1)
    t1 = st.number_input(f"⏱️ Tempo {j1} (segundos)", 0.0, 300.0, step=1.0)
    t2 = st.number_input(f"⏱️ Tempo {j2} (segundos)", 0.0, 300.0, step=1.0)

    if st.button("Salvar Resultado"):
        registrar_resultado(conn, rodada, j1, j2, e1, e2, p1, p2, t1, t2)
        st.success("Resultado registrado com sucesso ✅")
