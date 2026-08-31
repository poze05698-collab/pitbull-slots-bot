"""VIP pago por Telegram Stars.

O VIP é um produto digital dentro do Telegram. O pagamento usa XTR (Telegram
Stars), conforme a API oficial do Telegram. O acesso só é liberado depois de
successful_payment; o charge_id é guardado com UNIQUE para impedir crédito
duplicado. Nenhum dado do database.db existente é apagado.
"""
from datetime import datetime, timedelta
from telebot import types
from database import conn, cursor
from utils import eh_admin, data_atual, dinheiro, registrar_historico, registrar_movimentacao, criar_notificacao
from config import MERCADOPAGO_VIP_ATIVO
from mercadopago_vip import preparar_pagamentos_mp, criar_pix, iniciar_monitoramento

DEFAULTS = {
    "vip_ativo": "1",
    "vip_preco_stars": "100",
    "vip_duracao_dias": "30",
    "vip_giros_roleta": "2",
    "vip_raspadinhas": "2",
    "vip_chance_mult": "1.5",
    "vip_xp_mult": "2",
    "vip_coins_bonus": "0",
    "vip_gemas_bonus": "0",
    "vip_nome": "VIP Premium",
        "vip_preco_reais": "9.99",
    "vip_pagamento_online": "1",
}


def preparar_vip():
    cursor.execute("""CREATE TABLE IF NOT EXISTS vip_config (
        chave TEXT PRIMARY KEY, valor TEXT NOT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS vip_assinaturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        plano TEXT NOT NULL,
        preco_stars INTEGER NOT NULL,
        inicio TEXT NOT NULL,
        expiracao TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ATIVO',
        charge_id TEXT UNIQUE,
        payload TEXT UNIQUE,
        criado_em TEXT NOT NULL
    )""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS vip_pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        payload TEXT NOT NULL UNIQUE,
        charge_id TEXT NOT NULL UNIQUE,
        valor_stars INTEGER NOT NULL,
        data TEXT NOT NULL
    )""")
    for k, v in DEFAULTS.items():
        cursor.execute("INSERT OR IGNORE INTO vip_config(chave,valor) VALUES(?,?)", (k, v))
    conn.commit()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vip_assinaturas_usuario_status ON vip_assinaturas(usuario_id, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vip_pagamentos_charge ON vip_pagamentos(charge_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vip_pagamentos_payload ON vip_pagamentos(payload)")
    conn.commit()


def cfg(chave, default=None):
    cursor.execute("SELECT valor FROM vip_config WHERE chave=?", (chave,))
    row = cursor.fetchone()
    return row[0] if row else default


def set_cfg(chave, valor):
    cursor.execute("INSERT OR REPLACE INTO vip_config(chave,valor) VALUES(?,?)", (chave, str(valor)))
    conn.commit()


def _agora():
    return datetime.now()


def _parse_dt(valor):
    try:
        return datetime.fromisoformat(valor)
    except Exception:
        return None


def vip_ativo(usuario_id):
    preparar_vip()
    cursor.execute("""SELECT id, expiracao FROM vip_assinaturas
                     WHERE usuario_id=? AND status='ATIVO'
                     ORDER BY expiracao DESC LIMIT 1""", (usuario_id,))
    row = cursor.fetchone()
    if not row:
        return False
    exp = _parse_dt(row[1])
    if not exp or exp <= _agora():
        cursor.execute("UPDATE vip_assinaturas SET status='EXPIRADO' WHERE id=?", (row[0],))
        conn.commit()
        return False
    return True


def beneficios_vip(usuario_id):
    ativo = vip_ativo(usuario_id)
    if not ativo:
        return {
            "ativo": False,
            "roleta": 1,
            "raspadinha": 1,
            "chance": 1.0,
            "xp": 1.0,
            "coins": 0,
            "gemas": 0,
        }
    return {
        "ativo": True,
        "roleta": max(1, int(cfg("vip_giros_roleta", 2))),
        "raspadinha": max(1, int(cfg("vip_raspadinhas", 2))),
        "chance": max(1.0, float(cfg("vip_chance_mult", 1.5))),
        "xp": max(1.0, float(cfg("vip_xp_mult", 2))),
        "coins": max(0, int(cfg("vip_coins_bonus", 0))),
        "gemas": max(0, int(cfg("vip_gemas_bonus", 0))),
    }


def enviar_area_vip(bot, chat_id):
    preparar_vip()

    ativo = vip_ativo(chat_id)
    nome = cfg("vip_nome", "VIP Premium")
    dias = max(1, int(cfg("vip_duracao_dias", 30)))
    preco_reais = float(cfg("vip_preco_reais", "9.99"))

    # Esta tela é EXCLUSIVAMENTE para o usuário:
    # benefícios + duração + adquirir/renovar.
    texto = (
        f"💎 <b>{nome}</b>\n\n"
        "<b>Benefícios do VIP:</b>\n\n"
        f"🎰 {int(cfg('vip_giros_roleta', 2))} giros de roleta por dia\n"
        f"🎫 {int(cfg('vip_raspadinhas', 2))} raspadinhas por dia\n"
        f"🍀 {float(cfg('vip_chance_mult', 1.5)):g}x mais chances\n"
        f"⭐ {float(cfg('vip_xp_mult', 2)):g}x XP\n"
        f"🪙 +{int(cfg('vip_coins_bonus', 0))} Coins bônus\n"
        f"💎 +{int(cfg('vip_gemas_bonus', 0))} Gemas bônus\n\n"
        f"⏳ <b>Duração: {dias} dias</b>\n"
        f"💰 <b>Valor: R$ {preco_reais:.2f}</b>\n"
    )

    kb = types.InlineKeyboardMarkup()

    if ativo:
        cursor.execute(
            """SELECT expiracao FROM vip_assinaturas
               WHERE usuario_id=? AND status='ATIVO'
               ORDER BY expiracao DESC LIMIT 1""",
            (chat_id,)
        )
        row = cursor.fetchone()
        exp = row[0] if row else "-"

        texto += f"\n🟢 <b>Seu VIP está ativo</b>\n⏳ Expira em: <b>{exp}</b>\n"


        kb.add(types.InlineKeyboardButton("💳 Renovar VIP com Pix", callback_data="vip_comprar_online"))
        kb.add(types.InlineKeyboardButton("🧑‍💻 Falar com Suporte", callback_data="vip_suporte"))
    else:

        kb.add(types.InlineKeyboardButton("💳 COMPRAR VIP COM PIX", callback_data="vip_comprar_online"))
        kb.add(types.InlineKeyboardButton("🧑‍💻 Falar com Suporte", callback_data="vip_suporte"))

    bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=kb)



mp_email_states = {}


def ativar_vip_por_pagamento_mp(bot, usuario_id, pagamento_id, valor, dias):
    """Gera um código VIP de uso único após a confirmação real do pagamento.

    O VIP NÃO é ativado nesta etapa: o usuário ainda precisa resgatar o código
    no botão de código promocional. Isso impede ativação dupla.
    """
    try:
        from codigos import criar_codigo
        validade = (datetime.now() + timedelta(days=7)).date().isoformat()
        ok, codigo = criar_codigo("VIP", dias, 1, validade, 0)
        if not ok:
            print(f"ERRO CRIANDO CODIGO VIP AUTOMATICO: {codigo}")
            return False, None, None
        registrar_historico(usuario_id, "VIP_MP_PAGO", f"Pagamento Mercado Pago {pagamento_id}: R$ {valor:.2f}; código gerado", 0)
        registrar_movimentacao(usuario_id, "VIP", 0, f"Pagamento VIP confirmado: R$ {valor:.2f}")
        criar_notificacao(usuario_id, "💳 Pagamento VIP confirmado", f"Seu código VIP foi gerado: {codigo}")
        return True, codigo, None
    except Exception as erro:
        print(f"ERRO AO GERAR CODIGO VIP MERCADO PAGO: {erro}")
        return False, None, None


vip_admin_states = {}

def registrar(bot):
    preparar_vip()
    preparar_pagamentos_mp()
    iniciar_monitoramento(bot)

    @bot.callback_query_handler(func=lambda c: c.data == "vip_comprar_online")
    def comprar_vip_online(call):
        uid = call.from_user.id
        if cfg("vip_ativo", "1") != "1":
            bot.answer_callback_query(call.id, "VIP indisponível.", show_alert=True)
            return
        preparar_pagamentos_mp()
        bot.answer_callback_query(call.id)
        mp_email_states[uid] = True
        bot.send_message(
            call.message.chat.id,
            "💳 <b>COMPRA VIP POR PIX</b>\n\n"
            "Para gerar sua cobrança segura pelo Mercado Pago, envie seu e-mail.\n\n"
            "📧 Exemplo: voce@gmail.com\n\n"
            "O e-mail é usado somente na criação da cobrança.",
            parse_mode="HTML"
        )

    @bot.message_handler(func=lambda m: mp_email_states.get(m.from_user.id, False))
    def receber_email_vip(message):
        uid = message.from_user.id
        mp_email_states.pop(uid, None)
        email = (message.text or "").strip().lower()
        import re
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            bot.send_message(message.chat.id, "❌ E-mail inválido. Abra o VIP novamente e informe um e-mail válido.")
            return
        if not cfg("vip_ativo", "1") == "1":
            bot.send_message(message.chat.id, "❌ O VIP está indisponível no momento.")
            return
        valor = float(cfg("vip_preco_reais", "9.99"))
        dias = max(1, int(cfg("vip_duracao_dias", "30")))
        ok, retorno = criar_pix(
            usuario_id=uid,
            email=email,
            valor=valor,
            dias=dias,
            descricao=f"{cfg('vip_nome','VIP Premium')} - {dias} dias"
        )
        if not ok:
            bot.send_message(message.chat.id, f"❌ {retorno}")
            return
        qr = retorno["qr_code"]
        ticket = retorno.get("ticket_url")
        texto = (
            "💳 <b>PIX GERADO COM SUCESSO</b>\n\n"
            f"💎 Plano: <b>{cfg('vip_nome','VIP Premium')}</b>\n"
            f"⏳ Duração: <b>{dias} dias</b>\n"
            f"💰 Valor: <b>R$ {valor:.2f}</b>\n\n"
            "📋 <b>Pix Copia e Cola:</b>\n"
            f"<code>{qr}</code>\n\n"
            "Depois de pagar, a confirmação será feita automaticamente pelo Mercado Pago.\n"
            "Você receberá o código VIP aqui no bot."
        )
        kb = types.InlineKeyboardMarkup()
        if ticket:
            kb.add(types.InlineKeyboardButton("🔗 Abrir pagamento", url=ticket))
        kb.add(types.InlineKeyboardButton("🔄 Verificar pagamento", callback_data=f"vip_verificar:{retorno['id']}"))
        bot.send_message(message.chat.id, texto, parse_mode="HTML", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("vip_verificar:"))
    def verificar_vip_mp(call):
        uid = call.from_user.id
        pagamento_id = call.data.split(":", 1)[1]
        from mercadopago_vip import consultar_pagamento, preparar_pagamentos_mp, marcar_aprovado
        preparar_pagamentos_mp()
        cursor.execute("""
            SELECT id,usuario_id,pagamento_id,referencia,email,valor,dias,status,codigo,criado_em
            FROM vip_pagamentos_mp WHERE pagamento_id=? AND usuario_id=?
        """, (pagamento_id, uid))
        row = cursor.fetchone()
        if not row:
            bot.answer_callback_query(call.id, "Pagamento não encontrado.", show_alert=True)
            return
        dados = consultar_pagamento(pagamento_id)
        if not dados:
            bot.answer_callback_query(call.id, "Não consegui consultar o Mercado Pago agora.", show_alert=True)
            return
        status = str(dados.get("status") or "pending")
        if status == "approved":
            marcar_aprovado(bot, row, dados)
            bot.answer_callback_query(call.id, "Pagamento confirmado!", show_alert=True)
        elif status in ("rejected", "cancelled", "refunded", "charged_back"):
            cursor.execute("UPDATE vip_pagamentos_mp SET status=?, atualizado_em=? WHERE pagamento_id=?", (status, data_atual(), pagamento_id))
            conn.commit()
            bot.answer_callback_query(call.id, f"Pagamento: {status}.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Ainda aguardando o pagamento.", show_alert=True)

    @bot.callback_query_handler(func=lambda c: c.data == "vip_suporte")
    def vip_suporte(call):
        from config import SUPORTE
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"🧑‍💻 <b>AQUISIÇÃO PELO SUPORTE</b>\n\n"
            f"Fale com o suporte: <b>{SUPORTE}</b>\n\n"
            "Informe que deseja adquirir ou renovar o VIP. "
            "Após a confirmação, o administrador poderá gerar um código promocional para você resgatar aqui no bot.",
            parse_mode="HTML"
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith('vip_cfg_'))
    def vip_cfg_callback(call):
        if not eh_admin(call.from_user.id):
            bot.answer_callback_query(call.id, 'Sem permissão.', show_alert=True); return
        key = call.data.replace('vip_cfg_', '')
        if key == 'toggle':
            set_cfg('vip_ativo', '0' if cfg('vip_ativo','1') == '1' else '1')
            bot.answer_callback_query(call.id, 'Status alterado.')
            bot.delete_message(call.message.chat.id, call.message.message_id)
            mostrar_admin_vip(bot, call.message.chat.id)
            return

        mapping = {'name':('vip_nome','Nome do VIP'), 'price':('vip_preco_reais','Preço em R$'), 'days':('vip_duracao_dias','Duração em dias'), 'roleta':('vip_giros_roleta','Giros de roleta por dia'), 'rasp':('vip_raspadinhas','Raspadinhas por dia'), 'chance':('vip_chance_mult','Multiplicador de chance'), 'xp':('vip_xp_mult','Multiplicador de XP'), 'coins':('vip_coins_bonus','Coins bônus'), 'gemas':('vip_gemas_bonus','Gemas bônus')}
        if key not in mapping: return
        vip_admin_states[call.from_user.id] = mapping[key]
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f'✏️ <b>{mapping[key][1]}</b>\n\nDigite o novo valor:', parse_mode='HTML')

    @bot.message_handler(func=lambda m: m.from_user.id in vip_admin_states and eh_admin(m.from_user.id))
    def vip_cfg_text(message):
        chave, label = vip_admin_states.pop(message.from_user.id)
        valor = (message.text or '').strip().replace(',', '.')
        try:
            if chave == 'vip_nome':
                if not valor or len(valor) > 32: raise ValueError
            elif chave in ('vip_preco_stars','vip_duracao_dias','vip_giros_roleta','vip_raspadinhas','vip_coins_bonus','vip_gemas_bonus'):
                n = int(float(valor))
                if n < 0 or (chave in ('vip_preco_stars','vip_duracao_dias') and n < 1): raise ValueError
                valor = n
            else:
                n = float(valor)
                if n < 1: raise ValueError
                valor = n
            set_cfg(chave, valor)
            bot.send_message(message.chat.id, f'✅ {label} atualizado para <b>{valor}</b>.', parse_mode='HTML')
        except ValueError:
            bot.send_message(message.chat.id, '❌ Valor inválido. A alteração foi cancelada.')

    @bot.message_handler(commands=['paysupport'])
    def pay_support(message):
        bot.send_message(message.chat.id, "💳 <b>SUPORTE DE PAGAMENTOS</b>\n\nSe houve cobrança e o VIP não foi ativado, envie este comprovante ao suporte junto do horário da compra.", parse_mode='HTML')

def mostrar_admin_vip(bot, chat_id):
    preparar_vip()
    online = bool(MERCADOPAGO_VIP_ATIVO)
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("🟢/🔴 Ativar VIP", callback_data="vip_cfg_toggle"),
        types.InlineKeyboardButton("✏️ Nome", callback_data="vip_cfg_name")
    )
    kb.row(
        types.InlineKeyboardButton("💰 Preço VIP", callback_data="vip_cfg_price"),
        types.InlineKeyboardButton("⏳ Duração", callback_data="vip_cfg_days")
    )
    kb.row(
        types.InlineKeyboardButton("🎰 Giros", callback_data="vip_cfg_roleta"),
        types.InlineKeyboardButton("🎫 Raspadinhas", callback_data="vip_cfg_rasp")
    )
    kb.row(
        types.InlineKeyboardButton("🍀 Chances", callback_data="vip_cfg_chance"),
        types.InlineKeyboardButton("⭐ XP", callback_data="vip_cfg_xp")
    )
    kb.row(
        types.InlineKeyboardButton("🪙 Coins bônus", callback_data="vip_cfg_coins"),
        types.InlineKeyboardButton("💎 Gemas bônus", callback_data="vip_cfg_gemas")
    )

    status = "🟢 ATIVO" if cfg("vip_ativo", "1") == "1" else "🔴 DESATIVADO"

    texto = (
        "💎 <b>CONFIGURAÇÃO VIP</b>\n\n"
        f"Status: {status}\n"
        f"Preço: <b>R$ {float(cfg('vip_preco_reais','9.99')):.2f}</b>\n"
        f"Duração: <b>{cfg('vip_duracao_dias','30')} dias</b>\n"
        f"Roleta: <b>{cfg('vip_giros_roleta','2')}/dia</b>\n"
        f"Raspadinha: <b>{cfg('vip_raspadinhas','2')}/dia</b>\n"
        f"Chance: <b>{cfg('vip_chance_mult','1.5')}x</b>\n"
        f"XP: <b>{cfg('vip_xp_mult','2')}x</b>\n"
        f"Coins bônus: <b>{cfg('vip_coins_bonus','0')}</b>\n"
        f"Gemas bônus: <b>{cfg('vip_gemas_bonus','0')}</b>\n"
        "\n💳 Pagamento: Mercado Pago / Pix automático\n"
    )
    bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=kb)

