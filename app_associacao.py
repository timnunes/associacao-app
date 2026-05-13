import streamlit as st
from supabase import create_client
from datetime import date, datetime
import pandas as pd
import urllib.parse

st.set_page_config(page_title="Controle de Associação", page_icon="🤝", layout="wide")

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

st.markdown("""
<style>
    .stButton > button { background-color:#0f766e; color:white; border-radius:8px; font-weight:bold; }
    .stButton > button:hover { background-color:#0d5e57; }
</style>""", unsafe_allow_html=True)

# ── Validação de CPF ──────────────────────────────────────────────────────────
def validar_cpf(cpf: str) -> bool:
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    if d1 != int(cpf[9]):
        return False
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    return d2 == int(cpf[10])

def fmt_cpf(cpf: str) -> str:
    cpf = ''.join(filter(str.isdigit, cpf))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

def fmt_data(d) -> str:
    if not d: return "—"
    try: return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(d)

def tel_com_ddi(tel):
    if not tel: return None
    t = ''.join(filter(str.isdigit, tel))
    return ("55" + t) if not t.startswith("55") else t

# ── Funções de banco ──────────────────────────────────────────────────────────
def buscar_associados():
    return db.table("assoc_associados").select("*").eq("ativo", True).order("nome").execute().data or []

def buscar_pagamentos_ano(ano):
    return db.table("assoc_pagamentos").select("*").eq("ano_referencia", ano).execute().data or []

def buscar_por_cpf(cpf):
    try:
        return db.table("assoc_associados").select("*").eq("cpf", ''.join(filter(str.isdigit, cpf))).single().execute().data
    except: return None

def link_wa(telefone, nome, ano, valor):
    tel = tel_com_ddi(telefone)
    msg = f"Olá {nome}, confirmamos sua anuidade {ano}. Valor: R$ {valor:.2f}. Obrigado! 🤝"
    return f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"

# ── Cabeçalho e métricas ──────────────────────────────────────────────────────
st.title("🤝 Controle de Associação")
st.caption(f"Ano de referência: **{ANO_ATUAL}**")

associados = buscar_associados()
pagamentos = buscar_pagamentos_ano(ANO_ATUAL)
ids_pagos  = {p["associado_id"] for p in pagamentos}

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 Total", len(associados))
c2.metric("✅ Pagaram", sum(1 for a in associados if a["id"] in ids_pagos))
c3.metric("❌ Inadimplentes", sum(1 for a in associados if a["id"] not in ids_pagos))
c4.metric("💰 Arrecadado", f"R$ {sum(p['valor'] for p in pagamentos):,.2f}")
st.markdown("---")

# ── Abas ─────────────────────────────────────────────────────────────────────
aba1, aba2, aba3, aba4 = st.tabs(["📋 Painel Geral","➕ Cadastrar Associado","💳 Registrar Pagamento","📊 Histórico"])

# ═══ ABA 1 — PAINEL GERAL ════════════════════════════════════════════════════
with aba1:
    st.subheader("Status de Anuidade")
    filtro = st.selectbox("Filtrar:", ["Todos","Pagos","Inadimplentes"])
    linhas = []
    for a in associados:
        pago = a["id"] in ids_pagos
        if filtro == "Pagos" and not pago: continue
        if filtro == "Inadimplentes" and pago: continue
        pg = next((p for p in pagamentos if p["associado_id"] == a["id"]), None)
        linhas.append({
            "Nome": a["nome"], "CPF": fmt_cpf(a["cpf"]),
            "Telefone": a.get("telefone") or "—",
            "Status": "✅ Pago" if pago else "❌ Pendente",
            "Valor Pago": f"R$ {pg['valor']:.2f}" if pg else "—",
            "Data": fmt_data(pg["data_pagamento"]) if pg else "—",
            "Forma": pg["forma"] if pg else "—",
            "_tel": tel_com_ddi(a.get("telefone")),
        })
    if not linhas:
        st.info("Nenhum resultado.")
    else:
        df = pd.DataFrame(linhas)
        st.dataframe(df.drop(columns=["_tel"]), use_container_width=True, hide_index=True)
        if filtro == "Inadimplentes":
            st.markdown("### 📲 Cobrar pelo WhatsApp")
            for r in linhas:
                if r["_tel"]:
                    msg = f"Olá {r['Nome']}, sua anuidade {ANO_ATUAL} está em aberto. Podemos acertar? 🤝"
                    st.markdown(f"[📲 {r['Nome']}](https://wa.me/{r['_tel']}?text={urllib.parse.quote(msg)})")
        csv = df.drop(columns=["_tel"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Exportar CSV", csv, f"associados_{ANO_ATUAL}.csv", "text/csv")

# ═══ ABA 2 — CADASTRAR ═══════════════════════════════════════════════════════
with aba2:
    st.subheader("Novo Associado")

    if st.session_state.get("cadastro_ok"):
        st.success(f"✅ **{st.session_state.get('ultimo_nome','')}** cadastrado com sucesso!")
        st.session_state.cadastro_ok = False

    with st.form("form_assoc", clear_on_submit=True):
        st.markdown("**Dados Pessoais**")
        ca1, ca2 = st.columns(2)
        with ca1:
            nome    = st.text_input("Nome completo *")
            cpf_in  = st.text_input("CPF * (somente números)")
            tel_in  = st.text_input("DDD + Telefone * (ex: 17999998888)")
        with ca2:
            nasc = st.date_input("Data de nascimento", value=None,
                                 min_value=date(1920,1,1), max_value=date.today(),
                                 format="DD/MM/YYYY")

        st.markdown("**Endereço**")
        ce1, ce2 = st.columns(2)
        with ce1:
            rua    = st.text_input("Rua / Avenida")
            bairro = st.text_input("Bairro")
        with ce2:
            cidade = st.text_input("Cidade")
            cuf, ccep = st.columns(2)
            with cuf:
                uf = st.selectbox("Estado", [
                    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
                    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"
                ], index=25)
            with ccep:
                cep = st.text_input("CEP")

        if st.form_submit_button("✅ Salvar Associado"):
            erros = []
            if not nome:               erros.append("Nome é obrigatório.")
            if not cpf_in:             erros.append("CPF é obrigatório.")
            elif not validar_cpf(cpf_in): erros.append("CPF inválido.")
            if not tel_in:             erros.append("Telefone é obrigatório.")
            if erros:
                for e in erros: st.error(e)
            else:
                partes = [x for x in [
                    rua.strip().title() if rua else None,
                    bairro.strip().title() if bairro else None,
                    cidade.strip().title() if cidade else None,
                    uf,
                    ("CEP " + ''.join(filter(str.isdigit, cep))) if cep else None
                ] if x]
                try:
                    db.table("assoc_associados").insert({
                        "nome":       nome.strip().title(),
                        "cpf":        ''.join(filter(str.isdigit, cpf_in)),
                        "telefone":   ''.join(filter(str.isdigit, tel_in)),
                        "nascimento": str(nasc) if nasc else None,
                        "endereco":   ", ".join(partes) if partes else None,
                    }).execute()
                    st.session_state.cadastro_ok  = True
                    st.session_state.ultimo_nome  = nome.strip().title()
                    st.rerun()
                except Exception as e:
                    if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                        st.error("⚠️ CPF já cadastrado.")
                    else:
                        st.error(f"Erro: {e}")

    st.markdown("---")
    st.subheader("🗂️ Associados Cadastrados")
    assoc_fresh = buscar_associados()
    if assoc_fresh:
        st.dataframe(pd.DataFrame([{
            "Nome":       a["nome"],
            "CPF":        fmt_cpf(a["cpf"]),
            "Telefone":   a.get("telefone") or "—",
            "Nascimento": fmt_data(a.get("nascimento")),
            "Endereço":   a.get("endereco") or "—",
        } for a in assoc_fresh]), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum associado cadastrado ainda.")

# ═══ ABA 3 — PAGAMENTO ═══════════════════════════════════════════════════════
with aba3:
    st.subheader("Registrar Pagamento de Anuidade")
    cpf_busca = st.text_input("CPF do associado (somente números)", key="cpf_pg")
    assoc_enc = None
    if cpf_busca:
        assoc_enc = buscar_por_cpf(cpf_busca)
        if assoc_enc:
            st.success(f"✅ Encontrado: **{assoc_enc['nome']}**")
            if assoc_enc["id"] in ids_pagos:
                pg = next((p for p in pagamentos if p["associado_id"] == assoc_enc["id"]), None)
                st.warning(f"⚠️ Já pagou em {fmt_data(pg['data_pagamento'])} — R$ {pg['valor']:.2f} via {pg['forma']}")
        else:
            st.error("❌ CPF não encontrado.")

    with st.form("form_pg", clear_on_submit=True):
        cp1, cp2 = st.columns(2)
        with cp1:
            ano_ref = st.number_input("Ano referência", 2020, 2030, ANO_ATUAL)
            valor   = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
        with cp2:
            forma   = st.selectbox("Forma", ["PIX","Dinheiro","Cartão","Transferência"])
            data_pg = st.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")
            obs     = st.text_input("Observação (opcional)")

        if st.form_submit_button("💳 Registrar Pagamento"):
            if not assoc_enc:
                st.error("Busque o CPF primeiro.")
            elif valor <= 0:
                st.error("Valor inválido.")
            else:
                db.table("assoc_pagamentos").insert({
                    "associado_id": assoc_enc["id"], "ano_referencia": int(ano_ref),
                    "valor": float(valor), "data_pagamento": str(data_pg),
                    "forma": forma, "observacao": obs or None,
                }).execute()
                st.success(f"✅ Pagamento registrado para **{assoc_enc['nome']}**!")
                if assoc_enc.get("telefone"):
                    st.markdown(f"[📲 Enviar confirmação WhatsApp]({link_wa(assoc_enc['telefone'], assoc_enc['nome'], ano_ref, valor)})")
                st.rerun()

# ═══ ABA 4 — HISTÓRICO ═══════════════════════════════════════════════════════
with aba4:
    st.subheader("Histórico de Pagamentos")
    ano_hist = st.selectbox("Ano:", list(range(ANO_ATUAL, 2019, -1)))
    pgs = db.table("assoc_pagamentos").select("*, assoc_associados(nome,cpf)").eq("ano_referencia", ano_hist).order("data_pagamento", desc=True).execute().data or []
    if pgs:
        df_h = pd.DataFrame([{
            "Nome":  (p.get("assoc_associados") or {}).get("nome","—"),
            "CPF":   fmt_cpf((p.get("assoc_associados") or {}).get("cpf","")),
            "Valor": f"R$ {p['valor']:.2f}",
            "Data":  fmt_data(p["data_pagamento"]),
            "Forma": p["forma"],
            "Obs":   p.get("observacao") or "—",
        } for p in pgs])
        st.dataframe(df_h, use_container_width=True, hide_index=True)
        st.metric("Total arrecadado", f"R$ {sum(p['valor'] for p in pgs):,.2f}")
        st.download_button(f"⬇️ Exportar {ano_hist}", df_h.to_csv(index=False).encode("utf-8"), f"pagamentos_{ano_hist}.csv", "text/csv")
    else:
        st.info(f"Nenhum pagamento em {ano_hist}.")
