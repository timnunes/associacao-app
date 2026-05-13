import streamlit as st
from supabase import create_client
from datetime import date, datetime
import pandas as pd
import urllib.parse

# ─────────────────────────────────────────────
#  CONFIGURAÇÃO
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Controle de Associação",
    page_icon="🤝",
    layout="wide"
)

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
except Exception:
    st.error("❌ Secrets não encontrados. Configure SUPABASE_URL e SUPABASE_KEY.")
    st.stop()

try:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Erro ao conectar no Supabase: {e}")
    st.stop()
ANO_ATUAL = datetime.now().year

# ─────────────────────────────────────────────
#  CSS CUSTOMIZADO
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f0f4f8; }
    .stButton > button {
        background-color: #0f766e;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    .stButton > button:hover {
        background-color: #0d5e57;
    }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .pago { color: #16a34a; font-weight: bold; }
    .pendente { color: #dc2626; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────
def buscar_associados():
    res = db.table("assoc_associados").select("*").eq("ativo", True).order("nome").execute()
    return res.data or []

def buscar_pagamentos_ano(ano):
    res = db.table("assoc_pagamentos").select("*").eq("ano_referencia", ano).execute()
    return res.data or []

def buscar_associado_por_cpf(cpf):
    cpf_limpo = cpf.replace(".", "").replace("-", "")
    res = db.table("assoc_associados").select("*").eq("cpf", cpf_limpo).single().execute()
    return res.data

def link_whatsapp(telefone, nome, ano, valor):
    msg = f"Olá {nome}, confirmamos o recebimento da sua anuidade {ano}. Valor: R$ {valor:.2f}. Obrigado pela parceria! 🤝"
    encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{telefone}?text={encoded}"

def status_badge(status):
    if status == "Pago":
        return "✅ Pago"
    return "❌ Pendente"

# ─────────────────────────────────────────────
#  CABEÇALHO
# ─────────────────────────────────────────────
st.title("🤝 Controle de Associação")
st.caption(f"Ano de referência: **{ANO_ATUAL}**")

# ─────────────────────────────────────────────
#  MÉTRICAS DO DASHBOARD
# ─────────────────────────────────────────────
associados = buscar_associados()
pagamentos = buscar_pagamentos_ano(ANO_ATUAL)

ids_pagos = {p["associado_id"] for p in pagamentos}
total = len(associados)
pagos = sum(1 for a in associados if a["id"] in ids_pagos)
inadimplentes = total - pagos
valor_arrecadado = sum(p["valor"] for p in pagamentos)

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Total de Associados", total)
col2.metric("✅ Pagaram", pagos)
col3.metric("❌ Inadimplentes", inadimplentes)
col4.metric("💰 Arrecadado", f"R$ {valor_arrecadado:,.2f}")

st.markdown("---")

# ─────────────────────────────────────────────
#  ABAS PRINCIPAIS
# ─────────────────────────────────────────────
aba1, aba2, aba3, aba4 = st.tabs([
    "📋 Painel Geral",
    "➕ Cadastrar Associado",
    "💳 Registrar Pagamento",
    "📊 Histórico de Pagamentos"
])

# ══════════════════════════════════════════════
# ABA 1 — PAINEL GERAL (lista com status)
# ══════════════════════════════════════════════
with aba1:
    st.subheader("Status de Anuidade — Todos os Associados")

    filtro = st.selectbox("Filtrar por:", ["Todos", "Pagos", "Inadimplentes"])

    linhas = []
    for a in associados:
        pago = a["id"] in ids_pagos
        pg = next((p for p in pagamentos if p["associado_id"] == a["id"]), None)
        linhas.append({
            "Nome": a["nome"],
            "CPF": a["cpf"],
            "Telefone": a["telefone"],
            "Status": "Pago" if pago else "Pendente",
            "Valor Pago": f"R$ {pg['valor']:.2f}" if pg else "—",
            "Data Pagamento": pg["data_pagamento"] if pg else "—",
            "Forma": pg["forma"] if pg else "—",
            "WhatsApp": a["telefone"],
            "_id": a["id"],
        })

    df = pd.DataFrame(linhas)

    if filtro == "Pagos":
        df = df[df["Status"] == "Pago"]
    elif filtro == "Inadimplentes":
        df = df[df["Status"] == "Pendente"]

    if df.empty:
        st.info("Nenhum resultado encontrado.")
    else:
        for _, row in df.iterrows():
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
                c1.write(f"**{row['Nome']}**")
                c2.write(row["CPF"])
                badge = "✅ Pago" if row["Status"] == "Pago" else "❌ Pendente"
                c3.write(badge)
                c4.write(row["Valor Pago"])
                if row["Telefone"]:
                    c5.markdown(f"[📲 WhatsApp](https://wa.me/{row['Telefone']})", unsafe_allow_html=True)

    # Botão para exportar CSV
    if not df.empty:
        csv = df.drop(columns=["WhatsApp", "_id"]).to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Exportar lista CSV",
            data=csv,
            file_name=f"associados_{ANO_ATUAL}.csv",
            mime="text/csv"
        )

# ══════════════════════════════════════════════
# ABA 2 — CADASTRAR ASSOCIADO
# ══════════════════════════════════════════════
with aba2:
    st.subheader("Novo Associado")

    with st.form("form_associado"):
        col_a, col_b = st.columns(2)
        with col_a:
            nome = st.text_input("Nome completo *")
            cpf  = st.text_input("CPF * (somente números)")
            telefone = st.text_input("Telefone (com DDI 55, ex: 55179XXXXXXXX)")
        with col_b:
            nascimento = st.date_input("Data de nascimento", value=None, min_value=date(1920,1,1))
            endereco = st.text_input("Endereço")

        salvar = st.form_submit_button("✅ Salvar Associado")

        if salvar:
            if not nome or not cpf:
                st.error("Nome e CPF são obrigatórios.")
            else:
                cpf_limpo  = ''.join(filter(str.isdigit, cpf))
                nome_fmt   = nome.strip().title()
                tel_fmt    = ''.join(filter(str.isdigit, telefone)) if telefone else None
                end_fmt    = endereco.strip().title() if endereco else None
                try:
                    db.table("assoc_associados").insert({
                        "nome":       nome_fmt,
                        "cpf":        cpf_limpo,
                        "telefone":   tel_fmt,
                        "nascimento": str(nascimento) if nascimento else None,
                        "endereco":   end_fmt,
                    }).execute()
                    st.success(f"✅ Associado **{nome_fmt}** cadastrado com sucesso!")
                    st.cache_resource.clear()
                except Exception as e:
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        st.error("⚠️ CPF já cadastrado.")
                    else:
                        st.error(f"Erro: {e}")

    st.markdown("---")
    st.subheader("🗂️ Associados Cadastrados")
    if associados:
        df_cad = pd.DataFrame(associados)[["nome","cpf","telefone","nascimento","endereco"]]
        df_cad.columns = ["Nome","CPF","Telefone","Nascimento","Endereço"]
        st.dataframe(df_cad, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum associado cadastrado ainda.")

# ══════════════════════════════════════════════
# ABA 3 — REGISTRAR PAGAMENTO
# ══════════════════════════════════════════════
with aba3:
    st.subheader("Registrar Pagamento de Anuidade")

    cpf_busca = st.text_input("Digite o CPF do associado (somente números)")

    assoc_encontrado = None
    if cpf_busca:
        assoc_encontrado = buscar_associado_por_cpf(cpf_busca)
        if assoc_encontrado:
            st.success(f"✅ Associado encontrado: **{assoc_encontrado['nome']}**")
            # Verificar se já pagou
            ja_pagou = assoc_encontrado["id"] in ids_pagos
            if ja_pagou:
                pg = next((p for p in pagamentos if p["associado_id"] == assoc_encontrado["id"]), None)
                st.warning(f"⚠️ Este associado já registrou pagamento em {pg['data_pagamento']} — R$ {pg['valor']:.2f} via {pg['forma']}")
        else:
            st.error("❌ CPF não encontrado. Cadastre o associado primeiro.")

    with st.form("form_pagamento"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            ano_ref = st.number_input("Ano de referência", min_value=2020, max_value=2030, value=ANO_ATUAL)
            valor   = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
        with col_p2:
            forma   = st.selectbox("Forma de pagamento", ["PIX", "Dinheiro", "Cartão", "Transferência"])
            obs     = st.text_input("Observação (opcional)")
            data_pg = st.date_input("Data do pagamento", value=date.today())

        registrar = st.form_submit_button("💳 Registrar Pagamento")

        if registrar:
            if not assoc_encontrado:
                st.error("Busque e confirme o CPF do associado primeiro.")
            elif valor <= 0:
                st.error("Informe um valor válido.")
            else:
                db.table("assoc_pagamentos").insert({
                    "associado_id": assoc_encontrado["id"],
                    "ano_referencia": int(ano_ref),
                    "valor": float(valor),
                    "data_pagamento": str(data_pg),
                    "forma": forma,
                    "observacao": obs or None
                }).execute()
                st.success(f"✅ Pagamento registrado para **{assoc_encontrado['nome']}**!")

                # Link WhatsApp automático
                if assoc_encontrado.get("telefone"):
                    link_wa = link_whatsapp(assoc_encontrado["telefone"], assoc_encontrado["nome"], ano_ref, valor)
                    st.markdown(f"[📲 Enviar confirmação pelo WhatsApp]({link_wa})", unsafe_allow_html=True)

                st.cache_resource.clear()

# ══════════════════════════════════════════════
# ABA 4 — HISTÓRICO DE PAGAMENTOS
# ══════════════════════════════════════════════
with aba4:
    st.subheader("Histórico Completo de Pagamentos")

    ano_hist = st.selectbox("Selecionar ano:", list(range(ANO_ATUAL, 2019, -1)))
    pgs_hist = db.table("assoc_pagamentos")\
        .select("*, assoc_associados(nome, cpf)")\
        .eq("ano_referencia", ano_hist)\
        .order("data_pagamento", desc=True)\
        .execute().data or []

    if pgs_hist:
        linhas_hist = []
        for p in pgs_hist:
            assoc_info = p.get("assoc_associados") or {}
            linhas_hist.append({
                "Nome": assoc_info.get("nome", "—"),
                "CPF": assoc_info.get("cpf", "—"),
                "Ano": p["ano_referencia"],
                "Valor": f"R$ {p['valor']:.2f}",
                "Data": p["data_pagamento"],
                "Forma": p["forma"],
                "Observação": p.get("observacao") or "—"
            })
        df_hist = pd.DataFrame(linhas_hist)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

        total_hist = sum(p["valor"] for p in pgs_hist)
        st.metric("Total arrecadado", f"R$ {total_hist:,.2f}")

        csv_hist = df_hist.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"⬇️ Exportar {ano_hist} CSV",
            data=csv_hist,
            file_name=f"pagamentos_{ano_hist}.csv",
            mime="text/csv"
        )
    else:
        st.info(f"Nenhum pagamento registrado em {ano_hist}.")
