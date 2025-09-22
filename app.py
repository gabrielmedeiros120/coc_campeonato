import streamlit as st
import sqlite3
import pandas as pd

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
# ESTILO VISUAL (NOVA LÓGICA)
# ---------------------------
# Cores suaves verdes para top 5 (com zebra) e vermelhos para os 5 últimos
TOP_GREEN_1 = '#e6f9e6'
TOP_GREEN_2 = '#dff0e6'
BOTTOM_RED_1 = '#fdecec'
BOTTOM_RED_2 = '#f9d6d6'

# Função que aplica estilo por linha usando o índice da linha (após ordenação)
def style_row(row):
    n = styled_row_count  # variável global definida onde o Styler é aplicado
    idx = row.name  # 0-based index da linha após o sort/reset
    styles = [''] * len(row)

    # Top 5 (tons de verde, zebra)
    if idx < 5:
        shade = TOP_GREEN_1 if idx % 2 == 0 else TOP_GREEN_2
        styles = [f'background-color: {shade};' for _ in row]
        # destaque um pouco a posição e nome
        try:
            pos_i = list(row.index).index('Posição')
            styles[pos_i] += ' font-weight: bold;'
        except ValueError:
            pass

    # Bottom 5 (tons de vermelho, zebra)
    elif idx >= max(0, n - 5):
        shade = BOTTOM_RED_1 if idx % 2 == 0 else BOTTOM_RED_2
        styles = [f'background-color: {shade};' for _ in row]

    return styles

# ---------------------------
# APP STREAMLIT
# ---------------------------
st.set_page_config(page_title="Liga do 13°", layout="wide")
st.title("🏆 Liga do 13° – Temporada 1")

conn = init_db()
inicializar_jogadores(conn)
gerar_rodadas(conn)

menu = st.sidebar.radio("Navegação", ["Classificação", "Rodadas", "Cadastrar Resultados"])

# ---------------------------
# CLASSIFICAÇÃO
# ---------------------------
if menu == "Classificação":
    st.subheader("📊 Tabela de Classificação")

    df = get_jogadores(conn)
    if not df.empty:
        # remove coluna id para não aparecer
        df = df.drop(columns=['id'], errors='ignore')

        # ordenação — mantém a lógica anterior, mas agora transformamos a posição em ordem absoluta
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

        # adicionar medalhas ao lado do nome para top3 (sem criar coluna separada)
        def add_medal(nome, pos):
            if pos == 1:
                return '🥇 ' + nome
            elif pos == 2:
                return '🥈 ' + nome
            elif pos == 3:
                return '🥉 ' + nome
            else:
                return nome

        df['Nome'] = df.apply(lambda row: add_medal(row['Nome'], row['Posição']), axis=1)

        # reordenar colunas: Posicao, Nome, ...
        cols = [c for c in df.columns if c != 'Posição']
        cols = ['Posição'] + cols
        df = df[cols]

        # Preparar e renderizar uma tabela HTML personalizada (remove totalmente a primeira coluna de índice)
        styled_row_count = len(df)

        # cores menos "brancas" — tons mais saturados para melhor contraste
        TOP_GREEN_1 = '#b7eac7'
        TOP_GREEN_2 = '#9fe2b0'
        BOTTOM_RED_1 = '#ffb3b3'
        BOTTOM_RED_2 = '#ff9a9a'

        def row_bg_color(idx, n):
            if idx < 5:
                return TOP_GREEN_1 if idx % 2 == 0 else TOP_GREEN_2
            elif idx >= max(0, n - 5):
                return BOTTOM_RED_1 if idx % 2 == 0 else BOTTOM_RED_2
            else:
                return 'transparent'

        # construir HTML da tabela manualmente (index removido)
        n = len(df)
        table_html = '''
        <style>
        .classtable{font-family:Roboto, "Helvetica Neue", Arial; border-collapse:collapse; width:100%;}
        .classtable th{background:#1f2933; color:#e5e7eb; padding:12px; text-align:left; border-top-left-radius:8px;}
        .classtable th:last-child{border-top-right-radius:8px}
        .classtable td{padding:10px;}
        .classtable tr{transition: background 0.15s ease}
        .classtable thead th{font-weight:600}
        </style>
        <table class="classtable">
            <thead>
                <tr>'''

        for col in df.columns:
            table_html += f"<th>{col}</th>"
        table_html += "</tr>
            </thead>
            <tbody>
"

        for idx, row in df.reset_index(drop=True).iterrows():
            bg = row_bg_color(idx, n)
            # texto em cor escura para melhor contraste sobre fundo claro
            table_html += f"<tr style='background:{bg}; color:#0b0b0b;'>"
            for col in df.columns:
                val = row[col]
                table_html += f"<td>{val}</td>"
            table_html += "</tr>
"

        table_html += "</tbody>
</table>"

        st.markdown(table_html, unsafe_allow_html=True)


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
