"""
Sistema de códigos promocionais.

Tipos suportados:
- VIP: ativa/estende VIP por N dias
- SALDO: adiciona dinheiro ao saldo
- COINS: adiciona Coins
- GEMAS: adiciona Gemas

Tudo é persistido no SQLite existente. Nenhum usuário/indicação é apagado.
"""
import secrets
import string
from datetime import datetime
from telebot import types

from database import conn, cursor
from utils import eh_admin, data_atual, dinheiro, adicionar_saldo, registrar_historico, registrar_movimentacao, criar_notificacao
from avancado import add_coins, add_gemas
from vip import preparar_vip, vip_ativo

estados_criacao = {}
estados_resgate = {}


def preparar_codigos():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codigos_promocionais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            limite_resgates INTEGER NOT NULL DEFAULT 1,
            resgates INTEGER NOT NULL DEFAULT 0,
            validade TEXT,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_por INTEGER NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codigos_resgates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            resgatado_em TEXT NOT NULL,
            UNIQUE(codigo_id, usuario_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_codigos_codigo ON codigos_promocionais(codigo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resgates_codigo ON codigos_resgates(codigo_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resgates_usuario ON codigos_resgates(usuario_id)")
    conn.commit()


def _codigo():
    chars = string.ascii_uppercase + string.digits
    while True:
        valor = "VIP-" + "".join(secrets.choice(chars) for _ in range(8))
        cursor.execute("SELECT 1 FROM codigos_promocionais WHERE codigo=?", (valor,))
        if not cursor.fetchone():
            return valor


def criar_codigo(tipo, valor, limite, validade, admin_id):
    preparar_codigos()
    tipo = tipo.upper().strip()
    if tipo not in ("VIP", "SALDO", "COINS", "GEMAS"):
        return False, "Tipo inválido."
    valor = float(valor)
    limite = int(limite)
    if valor <= 0 or limite <= 0:
        return False, "Valor e limite devem ser maiores que zero."
    if validade:
        try:
            datetime.fromisoformat(validade)
        except ValueError:
            return False, "Validade inválida. Use AAAA-MM-DD."
    codigo = _codigo()
    cursor.execute("""
        INSERT INTO codigos_promocionais
        (codigo,tipo,valor,limite_resgates,resgates,validade,ativo,criado_por,criado_em)
        VALUES(?,?,?,?,0,?,1,?,?)
    """, (codigo, tipo, valor, limite, validade or None, admin_id, data_atual()))
    conn.commit()
    return True, codigo


def _buscar(codigo):
    preparar_codigos()
    cursor.execute("""
        SELECT id,codigo,tipo,valor,limite_resgates,resgates,validade,ativo
        FROM codigos_promocionais
        WHERE codigo=?
    """, (codigo.upper().strip(),))
    return cursor.fetchone()


def resgatar_codigo(usuario_id, codigo):
    preparar_codigos()
    codigo = codigo.strip().upper()
    row = _buscar(codigo)
    if not row:
        return False, "❌ Código não encontrado."
    cid, code, tipo, valor, limite, resgates, validade, ativo = row

    if not ativo:
        return False, "❌ Este código está desativado."
    if resgates >= limite:
        return False, "❌ Este código já atingiu o limite de resgates."

    if validade:
        try:
            if datetime.fromisoformat(validade).date() < datetime.now().date():
                cursor.execute("UPDATE codigos_promocionais SET ativo=0 WHERE id=?", (cid,))
                conn.commit()
                return False, "❌ Este código está expirado."
        except ValueError:
            return False, "❌ Este código possui uma validade inválida."

    cursor.execute("SELECT 1 FROM codigos_resgates WHERE codigo_id=? AND usuario_id=?", (cid, usuario_id))
    if cursor.fetchone():
        return False, "❌ Você já resgatou este código."

    try:
        # Registro do resgate e benefício são feitos na mesma transação.
        cursor.execute(
            "INSERT INTO codigos_resgates(codigo_id,usuario_id,resgatado_em) VALUES(?,?,?)",
            (cid, usuario_id, data_atual())
        )
        cursor.execute(
            "UPDATE codigos_promocionais SET resgates=resgates+1 WHERE id=? AND ativo=1 AND resgates<limite_resgates",
            (cid,)
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return False, "❌ Este código acabou de atingir o limite de resgates."

        if tipo == "VIP":
            preparar_vip()
            from vip import _agora, _parse_dt, cfg
            dias = max(1, int(valor))
            cursor.execute("""
                SELECT id,expiracao FROM vip_assinaturas
                WHERE usuario_id=? AND status='ATIVO'
                ORDER BY expiracao DESC LIMIT 1
            """, (usuario_id,))
            atual = cursor.fetchone()
            inicio = _agora()
            if atual:
                exp = _parse_dt(atual[1])
                base = exp if exp and exp > inicio else inicio
                nova_exp = base
                nova_exp = nova_exp.replace(microsecond=0)
                from datetime import timedelta
                nova_exp = nova_exp + timedelta(days=dias)
                cursor.execute("UPDATE vip_assinaturas SET expiracao=?, status='ATIVO' WHERE id=?", (nova_exp.isoformat(timespec="seconds"), atual[0]))
            else:
                from datetime import timedelta
                exp = inicio + timedelta(days=dias)
                cursor.execute("""
                    INSERT INTO vip_assinaturas(usuario_id,plano,preco_stars,inicio,expiracao,status,charge_id,payload,criado_em)
                    VALUES(?,?,0,?,?,'ATIVO',NULL,NULL,?)
                """, (usuario_id, cfg("vip_nome","VIP Premium"), inicio.isoformat(timespec="seconds"), exp.isoformat(timespec="seconds"), data_atual()))
            texto = f"💎 <b>VIP ativado!</b>\n\n⏳ +{dias} dias de VIP."
            registrar_historico(usuario_id, "CODIGO_VIP", f"Código {code}: +{dias} dias", 0)

        elif tipo == "SALDO":
            adicionar_saldo(usuario_id, float(valor))
            texto = f"💰 <b>Saldo recebido!</b>\n\n+{dinheiro(valor)}"
            registrar_historico(usuario_id, "CODIGO_SALDO", f"Código {code}", float(valor))

        elif tipo == "COINS":
            add_coins(usuario_id, int(valor))
            texto = f"🪙 <b>Coins recebidos!</b>\n\n+{int(valor)} Coins"
            registrar_historico(usuario_id, "CODIGO_COINS", f"Código {code}", 0)

        else:
            add_gemas(usuario_id, int(valor))
            texto = f"💎 <b>Gemas recebidas!</b>\n\n+{int(valor)} Gemas"
            registrar_historico(usuario_id, "CODIGO_GEMAS", f"Código {code}", 0)

        conn.commit()
        criar_notificacao(usuario_id, "🎁 Código promocional", f"Código {code} resgatado.")
        return True, texto

    except Exception as erro:
        conn.rollback()
        print(f"ERRO AO RESGATAR CÓDIGO: {erro}")
        return False, "❌ Não foi possível resgatar o código agora. Tente novamente."



def abrir_painel_admin_codigos(bot, chat_id):
    preparar_codigos()
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("➕ Criar código", callback_data="promo_criar"))
    kb.row(types.InlineKeyboardButton("📋 Ver códigos", callback_data="promo_listar"))
    bot.send_message(
        chat_id,
        "🎟️ <b>CÓDIGOS PROMOCIONAIS</b>\n\nEscolha uma opção:",
        parse_mode="HTML",
        reply_markup=kb
    )

def registrar(bot):
    preparar_codigos()

    @bot.message_handler(func=lambda m: m.text == "🎟️ Código Promocional")
    def iniciar_resgate(message):
        estados_resgate[message.from_user.id] = True
        bot.send_message(message.chat.id, "🎟️ <b>RESGATAR CÓDIGO</b>\n\nDigite seu código promocional:", parse_mode="HTML")

    @bot.message_handler(func=lambda m: estados_resgate.get(m.from_user.id, False))
    def receber_resgate(message):
        uid = message.from_user.id
        estados_resgate.pop(uid, None)
        ok, texto = resgatar_codigo(uid, message.text or "")
        bot.send_message(message.chat.id, texto, parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🎟️ Códigos" and eh_admin(m.from_user.id))
    def menu_codigos_admin(message):
        abrir_painel_admin_codigos(bot, message.chat.id)

    @bot.callback_query_handler(func=lambda c: c.data == "promo_criar" and eh_admin(c.from_user.id))
    def iniciar_criacao(call):
        estados_criacao[call.from_user.id] = {"etapa": "tipo"}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            "➕ <b>CRIAR CÓDIGO</b>\n\n"
            "Tipo da recompensa:\n"
            "VIP = dias de VIP\n"
            "SALDO = valor em R$\n"
            "COINS = quantidade de Coins\n"
            "GEMAS = quantidade de Gemas\n\n"
            "Digite: VIP, SALDO, COINS ou GEMAS", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.from_user.id in estados_criacao and eh_admin(m.from_user.id))
    def criar_passo(message):
        uid = message.from_user.id
        estado = estados_criacao[uid]
        valor = (message.text or "").strip()

        if estado["etapa"] == "tipo":
            tipo = valor.upper()
            if tipo not in ("VIP", "SALDO", "COINS", "GEMAS"):
                bot.send_message(message.chat.id, "❌ Tipo inválido. Use VIP, SALDO, COINS ou GEMAS.")
                return
            estado.update(tipo=tipo, etapa="valor")
            bot.send_message(message.chat.id, f"💰 Digite o valor de {tipo}.\n\nExemplo: 30 para 30 dias de VIP ou 100 para 100 Coins.")
            return

        if estado["etapa"] == "valor":
            try:
                n = float(valor.replace(",", "."))
                if n <= 0 or (estado["tipo"] in ("VIP","COINS","GEMAS") and n != int(n)):
                    raise ValueError
                estado.update(valor=n, etapa="limite")
                bot.send_message(message.chat.id, "👥 Quantas pessoas poderão resgatar?\n\nExemplo: 100")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Valor inválido.")
            return

        if estado["etapa"] == "limite":
            try:
                limite = int(valor)
                if limite <= 0: raise ValueError
                estado.update(limite=limite, etapa="validade")
                bot.send_message(message.chat.id, "📅 Validade do código?\n\nDigite AAAA-MM-DD ou 0 para sem validade.")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Digite um número inteiro maior que zero.")
            return

        if estado["etapa"] == "validade":
            validade = None if valor == "0" else valor
            ok, resultado = criar_codigo(estado["tipo"], estado["valor"], estado["limite"], validade, uid)
            estados_criacao.pop(uid, None)
            if not ok:
                bot.send_message(message.chat.id, f"❌ {resultado}")
                return
            bot.send_message(message.chat.id,
                f"🎉 <b>CÓDIGO CRIADO</b>\n\n"
                f"🎟️ Código: <code>{resultado}</code>\n"
                f"🎁 Tipo: {estado['tipo']}\n"
                f"💰 Valor: {estado['valor']:g}\n"
                f"👥 Limite: {estado['limite']}\n"
                f"📅 Validade: {validade or 'Sem validade'}\n\n"
                f"📋 Envie este código para as pessoas que poderão resgatá-lo.",
                parse_mode="HTML")

    @bot.callback_query_handler(func=lambda c: c.data == "promo_listar" and eh_admin(c.from_user.id))
    def listar(call):
        cursor.execute("""
            SELECT codigo,tipo,valor,limite_resgates,resgates,validade,ativo
            FROM codigos_promocionais ORDER BY id DESC LIMIT 30
        """)
        rows = cursor.fetchall()
        if not rows:
            texto = "📋 Nenhum código criado."
        else:
            linhas = ["🎟️ <b>ÚLTIMOS CÓDIGOS</b>"]
            for code,tipo,valor,limite,resgates,validade,ativo in rows:
                linhas.append(f"\n<code>{code}</code> — {tipo} {valor:g}\n👥 {resgates}/{limite} | {'🟢' if ativo else '🔴'} | 📅 {validade or 'sem validade'}")
            texto = "\n".join(linhas)
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, texto, parse_mode="HTML")


    @bot.message_handler(commands=["codigo"])
    def codigo_comando(message):
        partes = (message.text or "").split(maxsplit=1)
        if len(partes) < 2:
            bot.reply_to(message, "Uso: /codigo SEU_CODIGO")
            return
        ok, texto = resgatar_codigo(message.from_user.id, partes[1])
        bot.send_message(message.chat.id, texto, parse_mode="HTML")
