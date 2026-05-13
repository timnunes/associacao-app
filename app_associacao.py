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
    st.error("❌ Secrets não encontrados.")
    st.stop()

try:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"❌ Erro ao conectar: {e}")
    st.stop()

ANO_ATUAL = datetime.now().year

st.markdown("""
<style>
    .stButton > button { background-color:#0f766e; color:white; border-radius:8px; font-weight:bold; }
    .stButton > button:hover { background-color:#0d5e57; }
</style>""", unsafe_allow_html=True)

# ── Utilitários ───────────────────────────────────────────────────────────────
def validar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0]*11: return False
    soma = sum(int(cpf[i])*(10-i) for i in range(9))
    if (soma*10%11)%10 != int(cpf[9]): return False
    soma = sum(int(cpf[i])*(11-i) for i in range(10))
    return (soma*10%11)%10 == int(cpf[10])

def fmt_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf or ""))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf)==11 else cpf

def fmt_data(d):
    if not d: return "—"
    try: return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d/%m/%Y")
    except: return str(d)

def tel_com_ddi(tel):
    if not tel: return None
    t = ''.join(filter(str.isdigit, tel))
    return ("55"+t) if not t.startswith("55") else t

def wa_link(telefone, msg):
    tel = tel_com_ddi(telefone)
    if not tel: return None
    return f"https://wa.me/{tel}?text={urllib.parse.quote(msg)}"

# ── Banco ─────────────────────────────────────────────────────────────────────
def buscar_associados():
    return db.table("assoc_associados").select("*").eq("ativo",True).order("nome").execute().data or []

def buscar_lancamentos_ano(ano):
    """Retorna TODOS os lançamentos do ano (pendentes e pagos)"""
    return db.table("assoc_pagamentos").select("*").eq("ano_referencia",ano).execute().data or []

def buscar_por_nome(termo):
    return db.table("assoc_associados").select("*").eq("ativo",True).ilike("nome",f"%{termo}%").order("nome").execute().data or []

# ── Dados globais ─────────────────────────────────────────────────────────────
associados    = buscar_associados()
lancamentos   = buscar_lancamentos_ano(ANO_ATUAL)

# Separa por status
ids_pagos     = {p["associado_id"] for p in lancamentos if p.get("status") == "pago"}
ids_pendentes = {p["associado_id"] for p in lancamentos if p.get("status") == "pendente"}
ids_lancados  = ids_pagos | ids_pendentes  # todos que têm lançamento

total         = len(associados)
n_pagos       = len([a for a in associados if a["id"] in ids_pagos])
n_pendentes   = len([a for a in associados if a["id"] in ids_pendentes])
n_sem_lanc    = len([a for a in associados if a["id"] not in ids_lancados])
arrecadado    = sum(p["valor"] for p in lancamentos if p.get("status") == "pago")
valor_ref     = next((p["valor"] for p in lancamentos), 0.0)
em_aberto     = sum(p["valor"] for p in lancamentos if p.get("status") == "pendente")

# ── Cabeçalho + Métricas ──────────────────────────────────────────────────────
st.title("🤝 Controle de Associação")
st.caption(f"Ano de referência: **{ANO_ATUAL}**")

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("👥 Associados",    total)
c2.metric("✅ Pagaram",       n_pagos)
c3.metric("⏳ Pendentes",     n_pendentes)
c4.metric("💰 Arrecadado",   f"R$ {arrecadado:,.2f}")
c5.metric("📋 Em Aberto",    f"R$ {em_aberto:,.2f}")
st.markdown("---")

# ── Abas ──────────────────────────────────────────────────────────────────────
aba1,aba2,aba3,aba4,aba5,aba6 = st.tabs([
    "📋 Painel Geral",
    "➕ Cadastrar Associado",
    "🚀 Gerar Anuidade",
    "💳 Registrar Pagamento",
    "📊 Relatórios",
    "🗂️ Histórico",
])

# ═══ ABA 1 — PAINEL GERAL ════════════════════════════════════════════════════
with aba1:
    st.subheader("Status de Anuidade")
    col_f1, col_f2 = st.columns([2,1])
    with col_f1:
        filtro = st.selectbox("Filtrar:", ["Todos","✅ Pagos","⏳ Pendentes","❌ Sem lançamento"])
    with col_f2:
        busca_painel = st.text_input("🔍 Buscar por nome", key="busca_painel")

    linhas = []
    for a in associados:
        pago     = a["id"] in ids_pagos
        pendente = a["id"] in ids_pendentes
        sem_lanc = a["id"] not in ids_lancados

        if filtro == "✅ Pagos"           and not pago:     continue
        if filtro == "⏳ Pendentes"        and not pendente: continue
        if filtro == "❌ Sem lançamento"   and not sem_lanc: continue
        if busca_painel and busca_painel.lower() not in a["nome"].lower(): continue

        lanc = next((p for p in lancamentos if p["associado_id"]==a["id"]), None)

        if pago:
            status_label = "✅ Pago"
        elif pendente:
            status_label = "⏳ Pendente"
        else:
            status_label = "❌ Sem lançamento"

        linhas.append({
            "Nome":       a["nome"],
            "CPF":        fmt_cpf(a["cpf"]),
            "Telefone":   a.get("telefone") or "—",
            "Status":     status_label,
            "Valor":      f"R$ {lanc['valor']:.2f}" if lanc else "—",
            "Vencimento": fmt_data(lanc["data_pagamento"]) if lanc and not pago else "—",
            "Pago em":    fmt_data(lanc["data_pagamento"]) if pago else "—",
            "Forma":      lanc["forma"] if pago and lanc else "—",
            "_tel":       tel_com_ddi(a.get("telefone")),
            "_nome":      a["nome"],
        })

    if not linhas:
        st.info("Nenhum resultado.")
    else:
        df = pd.DataFrame(linhas)
        st.dataframe(df.drop(columns=["_tel","_nome"]), use_container_width=True, hide_index=True)

        if filtro == "⏳ Pendentes":
            st.markdown("### 📲 Cobrar pelo WhatsApp")
            for r in linhas:
                if r["_tel"]:
                    msg = f"Olá {r['_nome']}, sua anuidade {ANO_ATUAL} está pendente. Podemos acertar? 🤝"
                    st.markdown(f"[📲 {r['_nome']}](https://wa.me/{r['_tel']}?text={urllib.parse.quote(msg)})")

        csv = df.drop(columns=["_tel","_nome"]).to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Exportar CSV", csv, f"status_{ANO_ATUAL}.csv", "text/csv")

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
            nome   = st.text_input("Nome completo *")
            cpf_in = st.text_input("CPF * (somente números)")
            tel_in = st.text_input("DDD + Telefone * (ex: 17999998888)")
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
                uf = st.selectbox("Estado",[
                    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG",
                    "PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"
                ], index=25)
            with ccep:
                cep = st.text_input("CEP")

        if st.form_submit_button("✅ Salvar Associado"):
            erros = []
            if not nome:                  erros.append("Nome é obrigatório.")
            if not cpf_in:                erros.append("CPF é obrigatório.")
            elif not validar_cpf(cpf_in): erros.append("CPF inválido.")
            if not tel_in:                erros.append("Telefone é obrigatório.")
            if erros:
                for e in erros: st.error(e)
            else:
                partes = [x for x in [
                    rua.strip().title() if rua else None,
                    bairro.strip().title() if bairro else None,
                    cidade.strip().title() if cidade else None,
                    uf,
                    ("CEP "+''.join(filter(str.isdigit,cep))) if cep else None
                ] if x]
                try:
                    db.table("assoc_associados").insert({
                        "nome":       nome.strip().title(),
                        "cpf":        ''.join(filter(str.isdigit,cpf_in)),
                        "telefone":   ''.join(filter(str.isdigit,tel_in)),
                        "nascimento": str(nasc) if nasc else None,
                        "endereco":   ", ".join(partes) if partes else None,
                    }).execute()
                    st.session_state.cadastro_ok = True
                    st.session_state.ultimo_nome = nome.strip().title()
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

# ═══ ABA 3 — GERAR ANUIDADE ══════════════════════════════════════════════════
with aba3:
    st.subheader("🚀 Gerar Anuidade para Todos os Associados")
    st.info(
        "Gera a **cobrança de anuidade** para todos os associados ativos. "
        "O status fica como **Pendente** até você registrar o pagamento de cada um. "
        "Quem já tiver lançamento no ano selecionado é ignorado."
    )

    with st.form("form_gerar"):
        cg1,cg2,cg3 = st.columns(3)
        with cg1: ano_gerar   = st.number_input("Ano", 2020, 2030, ANO_ATUAL)
        with cg2: valor_anuid = st.number_input("Valor (R$)", min_value=0.01, step=0.01, format="%.2f")
        with cg3: vencimento  = st.date_input("Vencimento", value=date(ANO_ATUAL,12,31), format="DD/MM/YYYY")
        enviar_wa = st.checkbox("📲 Mostrar links WhatsApp para notificar")

        if st.form_submit_button("🚀 Gerar Cobranças"):
            if valor_anuid <= 0:
                st.error("Informe um valor válido.")
            else:
                lanc_ano     = buscar_lancamentos_ano(int(ano_gerar))
                ids_lancados_ano = {p["associado_id"] for p in lanc_ano}
                todos        = buscar_associados()
                pendentes    = [a for a in todos if a["id"] not in ids_lancados_ano]

                if not pendentes:
                    st.warning(f"Todos os associados já têm lançamento para {int(ano_gerar)}.")
                else:
                    try:
                        db.table("assoc_pagamentos").insert([{
                            "associado_id":   a["id"],
                            "ano_referencia": int(ano_gerar),
                            "valor":          float(valor_anuid),
                            "data_pagamento": str(vencimento),
                            "forma":          "PIX",
                            "status":         "pendente",   # ← PENDENTE até pagar
                            "observacao":     f"Anuidade {int(ano_gerar)} — lançamento em lote",
                        } for a in pendentes]).execute()

                        st.success(f"✅ Cobrança gerada para **{len(pendentes)} associados** — status: ⏳ Pendente")
                        st.dataframe(pd.DataFrame([{
                            "Nome":     a["nome"],
                            "CPF":      fmt_cpf(a["cpf"]),
                            "Telefone": a.get("telefone") or "—",
                            "Status":   "⏳ Pendente",
                            "Valor":    f"R$ {valor_anuid:.2f}",
                            "Vencimento": vencimento.strftime("%d/%m/%Y"),
                        } for a in pendentes]), use_container_width=True, hide_index=True)

                        if enviar_wa:
                            st.markdown("### 📲 Notificar pelo WhatsApp")
                            for a in pendentes:
                                if a.get("telefone"):
                                    msg = (f"Olá {a['nome']}, sua anuidade {int(ano_gerar)} foi gerada. "
                                           f"Valor: R$ {valor_anuid:.2f}. "
                                           f"Vencimento: {vencimento.strftime('%d/%m/%Y')}. Obrigado! 🤝")
                                    tel = tel_com_ddi(a["telefone"])
                                    st.markdown(f"[📲 {a['nome']}](https://wa.me/{tel}?text={urllib.parse.quote(msg)})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")

    st.markdown("---")
    st.subheader(f"Situação atual — {ANO_ATUAL}")
    lanc_atual   = buscar_lancamentos_ano(ANO_ATUAL)
    todos_ativos = buscar_associados()
    ids_lanc_at  = {p["associado_id"] for p in lanc_atual}
    ids_pg_at    = {p["associado_id"] for p in lanc_atual if p.get("status")=="pago"}
    ids_pend_at  = {p["associado_id"] for p in lanc_atual if p.get("status")=="pendente"}

    cr1,cr2,cr3,cr4 = st.columns(4)
    cr1.metric("Total de associados",  len(todos_ativos))
    cr2.metric("✅ Pagos",             len(ids_pg_at))
    cr3.metric("⏳ Pendentes",         len(ids_pend_at))
    cr4.metric("❌ Sem lançamento",    len(todos_ativos)-len(ids_lanc_at))

# ═══ ABA 4 — REGISTRAR PAGAMENTO ═════════════════════════════════════════════
with aba4:
    st.subheader("💳 Registrar Pagamento de Anuidade")
    st.caption("Busque o associado pelo nome e confirme o recebimento.")

    termo_pg = st.text_input("🔍 Digite o nome do associado", key="busca_pg")
    assoc_enc = None

    if termo_pg and len(termo_pg) >= 2:
        resultados = buscar_por_nome(termo_pg)
        if resultados:
            opcoes = {f"{a['nome']} — CPF: {fmt_cpf(a['cpf'])}": a for a in resultados}
            escolha = st.radio("Selecione o associado:", list(opcoes.keys()), key="radio_pg")
            assoc_enc = opcoes[escolha]

            # Verifica lançamento existente
            lanc_assoc = next((p for p in lancamentos if p["associado_id"]==assoc_enc["id"]), None)

            if lanc_assoc:
                if lanc_assoc.get("status") == "pago":
                    st.success(f"✅ Já pagou em {fmt_data(lanc_assoc['data_pagamento'])} — R$ {lanc_assoc['valor']:.2f} via {lanc_assoc['forma']}")
                else:
                    st.warning(f"⏳ Anuidade {ANO_ATUAL} pendente — Valor: R$ {lanc_assoc['valor']:.2f} | Vencimento: {fmt_data(lanc_assoc['data_pagamento'])}")
            else:
                st.info(f"📌 Sem lançamento para {ANO_ATUAL}. Preencha abaixo para registrar o pagamento diretamente.")
        else:
            st.error("Nenhum associado encontrado.")

    if assoc_enc:
        lanc_assoc = next((p for p in lancamentos if p["associado_id"]==assoc_enc["id"]), None)
        ja_pago    = lanc_assoc and lanc_assoc.get("status") == "pago"

        if not ja_pago:
            with st.form("form_pg", clear_on_submit=True):
                cp1,cp2 = st.columns(2)
                with cp1:
                    ano_ref    = st.number_input("Ano referência", 2020, 2030, ANO_ATUAL)
                    valor_pago = st.number_input("Valor recebido (R$)",
                                                 min_value=0.01, step=0.01, format="%.2f",
                                                 value=float(lanc_assoc["valor"]) if lanc_assoc else 0.01)
                with cp2:
                    forma   = st.selectbox("Forma de pagamento", ["PIX","Dinheiro","Cartão","Transferência"])
                    data_pg = st.date_input("Data do recebimento", value=date.today(), format="DD/MM/YYYY")
                    obs     = st.text_input("Observação (opcional)")

                if st.form_submit_button("💳 Confirmar Pagamento"):
                    if valor_pago <= 0:
                        st.error("Valor inválido.")
                    else:
                        try:
                            if lanc_assoc:
                                # Atualiza o lançamento existente para PAGO
                                db.table("assoc_pagamentos").update({
                                    "status":          "pago",
                                    "valor":           float(valor_pago),
                                    "data_pagamento":  str(data_pg),
                                    "forma":           forma,
                                    "observacao":      obs or lanc_assoc.get("observacao"),
                                }).eq("id", lanc_assoc["id"]).execute()
                            else:
                                # Sem lançamento prévio — insere diretamente como pago
                                db.table("assoc_pagamentos").insert({
                                    "associado_id":   assoc_enc["id"],
                                    "ano_referencia": int(ano_ref),
                                    "valor":          float(valor_pago),
                                    "data_pagamento": str(data_pg),
                                    "forma":          forma,
                                    "status":         "pago",
                                    "observacao":     obs or None,
                                }).execute()

                            st.success(f"✅ Pagamento de **{assoc_enc['nome']}** confirmado!")
                            if assoc_enc.get("telefone"):
                                msg = (f"Olá {assoc_enc['nome']}, confirmamos o recebimento da sua "
                                       f"anuidade {int(ano_ref)}. Valor: R$ {valor_pago:.2f} via {forma}. Obrigado! 🤝")
                                link = wa_link(assoc_enc["telefone"], msg)
                                if link: st.markdown(f"[📲 Enviar confirmação WhatsApp]({link})")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

# ═══ ABA 5 — RELATÓRIOS ══════════════════════════════════════════════════════
with aba5:
    st.subheader("📊 Relatórios")

    ano_rel   = st.selectbox("Ano do relatório:", list(range(ANO_ATUAL, 2019, -1)), key="ano_rel")
    assoc_rel = buscar_associados()
    lanc_rel  = buscar_lancamentos_ano(ano_rel)

    ids_pg_rel   = {p["associado_id"] for p in lanc_rel if p.get("status")=="pago"}
    ids_pend_rel = {p["associado_id"] for p in lanc_rel if p.get("status")=="pendente"}
    ids_sem_rel  = {a["id"] for a in assoc_rel if a["id"] not in ids_pg_rel and a["id"] not in ids_pend_rel}

    pagos_rel    = [a for a in assoc_rel if a["id"] in ids_pg_rel]
    pend_rel     = [a for a in assoc_rel if a["id"] in ids_pend_rel]
    sem_lanc_rel = [a for a in assoc_rel if a["id"] in ids_sem_rel]

    total_arrecad = sum(p["valor"] for p in lanc_rel if p.get("status")=="pago")
    total_pend    = sum(p["valor"] for p in lanc_rel if p.get("status")=="pendente")

    st.markdown(f"### Resumo — {ano_rel}")
    r1,r2,r3,r4 = st.columns(4)
    r1.metric("👥 Total associados",  len(assoc_rel))
    r2.metric("✅ Pagos",             len(pagos_rel))
    r3.metric("⏳ Pendentes",         len(pend_rel))
    r4.metric("❌ Sem lançamento",    len(sem_lanc_rel))

    r5,r6,r7,r8 = st.columns(4)
    r5.metric("💰 Arrecadado",       f"R$ {total_arrecad:,.2f}")
    r6.metric("📋 A receber",        f"R$ {total_pend:,.2f}")
    r7.metric("📈 % Adimplência",    f"{(len(pagos_rel)/len(assoc_rel)*100):.1f}%" if assoc_rel else "—")
    r8.metric("📉 % Inadimplência",  f"{((len(pend_rel)+len(sem_lanc_rel))/len(assoc_rel)*100):.1f}%" if assoc_rel else "—")

    # Por forma de pagamento
    if lanc_rel:
        pgs_efetuados = [p for p in lanc_rel if p.get("status")=="pago"]
        if pgs_efetuados:
            st.markdown("---")
            st.markdown("### 💳 Arrecadação por Forma de Pagamento")
            df_forma = pd.DataFrame(pgs_efetuados).groupby("forma")["valor"].agg(["sum","count"]).reset_index()
            df_forma.columns = ["Forma","Total (R$)","Qtd"]
            df_forma["Total (R$)"] = df_forma["Total (R$)"].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(df_forma, use_container_width=True, hide_index=True)

    st.markdown("---")
    tab_pg, tab_pend, tab_sem = st.tabs(["✅ Pagos","⏳ Pendentes","❌ Sem lançamento"])

    with tab_pg:
        if pagos_rel:
            df_pg = pd.DataFrame([{
                "Nome":  a["nome"],
                "CPF":   fmt_cpf(a["cpf"]),
                "Valor": f"R$ {next((p['valor'] for p in lanc_rel if p['associado_id']==a['id']),0):.2f}",
                "Pago em": fmt_data(next((p['data_pagamento'] for p in lanc_rel if p['associado_id']==a['id'] and p.get('status')=='pago'),None)),
                "Forma": next((p['forma'] for p in lanc_rel if p['associado_id']==a['id'] and p.get('status')=='pago'),"—"),
            } for a in pagos_rel])
            st.dataframe(df_pg, use_container_width=True, hide_index=True)
            st.download_button(f"⬇️ Exportar pagos {ano_rel}", df_pg.to_csv(index=False).encode("utf-8"), f"pagos_{ano_rel}.csv","text/csv")
        else:
            st.info(f"Nenhum pagamento confirmado em {ano_rel}.")

    with tab_pend:
        if pend_rel:
            df_pend = pd.DataFrame([{
                "Nome":       a["nome"],
                "CPF":        fmt_cpf(a["cpf"]),
                "Telefone":   a.get("telefone") or "—",
                "Valor":      f"R$ {next((p['valor'] for p in lanc_rel if p['associado_id']==a['id']),0):.2f}",
                "Vencimento": fmt_data(next((p['data_pagamento'] for p in lanc_rel if p['associado_id']==a['id']),None)),
            } for a in pend_rel])
            st.dataframe(df_pend, use_container_width=True, hide_index=True)
            st.markdown("### 📲 Cobrar pelo WhatsApp")
            for a in pend_rel:
                if a.get("telefone"):
                    val = next((p['valor'] for p in lanc_rel if p['associado_id']==a['id']),0)
                    msg = f"Olá {a['nome']}, sua anuidade {ano_rel} de R$ {val:.2f} está pendente. Podemos acertar? 🤝"
                    tel = tel_com_ddi(a["telefone"])
                    st.markdown(f"[📲 {a['nome']}](https://wa.me/{tel}?text={urllib.parse.quote(msg)})")
            st.download_button(f"⬇️ Exportar pendentes {ano_rel}", df_pend.to_csv(index=False).encode("utf-8"), f"pendentes_{ano_rel}.csv","text/csv")
        else:
            st.success(f"🎉 Nenhuma anuidade pendente em {ano_rel}!")

    with tab_sem:
        if sem_lanc_rel:
            df_sem = pd.DataFrame([{
                "Nome":     a["nome"],
                "CPF":      fmt_cpf(a["cpf"]),
                "Telefone": a.get("telefone") or "—",
            } for a in sem_lanc_rel])
            st.dataframe(df_sem, use_container_width=True, hide_index=True)
            st.download_button(f"⬇️ Exportar sem lançamento {ano_rel}", df_sem.to_csv(index=False).encode("utf-8"), f"sem_lancamento_{ano_rel}.csv","text/csv")
        else:
            st.success(f"🎉 Todos os associados têm lançamento em {ano_rel}!")

# ═══ ABA 6 — HISTÓRICO ═══════════════════════════════════════════════════════
with aba6:
    st.subheader("🗂️ Histórico Completo")
    ano_hist = st.selectbox("Ano:", list(range(ANO_ATUAL, 2019, -1)), key="ano_hist")
    pgs = db.table("assoc_pagamentos").select("*, assoc_associados(nome,cpf)").eq("ano_referencia",ano_hist).order("data_pagamento",desc=True).execute().data or []
    if pgs:
        df_h = pd.DataFrame([{
            "Nome":   (p.get("assoc_associados") or {}).get("nome","—"),
            "CPF":    fmt_cpf((p.get("assoc_associados") or {}).get("cpf","")),
            "Status": "✅ Pago" if p.get("status")=="pago" else "⏳ Pendente",
            "Valor":  f"R$ {p['valor']:.2f}",
            "Data":   fmt_data(p["data_pagamento"]),
            "Forma":  p["forma"] if p.get("status")=="pago" else "—",
            "Obs":    p.get("observacao") or "—",
        } for p in pgs])
        st.dataframe(df_h, use_container_width=True, hide_index=True)
        col_h1, col_h2 = st.columns(2)
        col_h1.metric("Total arrecadado", f"R$ {sum(p['valor'] for p in pgs if p.get('status')=='pago'):,.2f}")
        col_h2.metric("Total pendente",   f"R$ {sum(p['valor'] for p in pgs if p.get('status')=='pendente'):,.2f}")
        st.download_button(f"⬇️ Exportar {ano_hist}", df_h.to_csv(index=False).encode("utf-8"), f"historico_{ano_hist}.csv","text/csv")
    else:
        st.info(f"Nenhum registro em {ano_hist}.")
