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


        # Suporte permanece disponível mesmo com pagamento online.
        kb.add(types.InlineKeyboardButton(
            "🧑‍💻 Renovar pelo Suporte",
            callback_data="vip_suporte"
        ))
    else:

        # Se o pagamento online estiver desligado, este é o caminho de compra.
        kb.add(types.InlineKeyboardButton(
            "🧑‍💻 Adquirir pelo Suporte",
            callback_data="vip_suporte"
        ))

    bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=kb)


vip_admin_states = {}

def registrar(bot):
    preparar_vip()

    @bot.callback_query_handler(func=lambda c: c.data == "vip_comprar")
    def comprar_vip(call):
        uid = call.from_user.id
        if cfg("vip_ativo", "1") != "1":
            bot.answer_callback_query(call.id, "VIP indisponível.", show_alert=True)
            return
        # Compra/renovação é permitida mesmo com VIP ativo.
        # O período pago será somado ao vencimento atual.
        stars = max(1, int(cfg("vip_preco_stars", 100)))
        dias = max(1, int(cfg("vip_duracao_dias", 30)))
        payload = f"vip:{uid}:{stars}:{dias}:{int(_agora().timestamp())}"
        prices = [types.LabeledPrice(label=cfg("vip_nome", "VIP Premium"), amount=stars)]
        try:
            bot.send_invoice(
                call.message.chat.id,
                title=cfg("vip_nome", "VIP Premium")[:32],
                description=f"Acesso VIP por {dias} dias"[:255],
                invoice_payload=payload,
                provider_token="",
                currency="XTR",
                prices=prices,
                start_parameter="vip-pagamento"
            )
            bot.answer_callback_query(call.id, "Pagamento aberto.")
        except Exception as erro:
            print(f"ERRO AO GERAR INVOICE VIP: {erro}")
            bot.answer_callback_query(call.id, "Não foi possível gerar o pagamento agora.", show_alert=True)

    @bot.pre_checkout_query_handler(func=lambda q: q.invoice_payload.startswith("vip:"))
    def vip_pre_checkout(query):
        try:
            partes = query.invoice_payload.split(":")
            if len(partes) != 5:
                bot.answer_pre_checkout_query(query.id, ok=False, error_message="Pedido VIP inválido.")
                return
            uid = int(partes[1]); stars = int(partes[2]); dias = int(partes[3])
            if uid != query.from_user.id or stars != int(query.total_amount) or dias <= 0:
                bot.answer_pre_checkout_query(query.id, ok=False, error_message="Pedido VIP inválido ou alterado.")
                return
            if not int(cfg("vip_ativo", "1")):
                bot.answer_pre_checkout_query(query.id, ok=False, error_message="O VIP está indisponível no momento.")
                return
            # Renovação permitida: o período será somado ao vencimento atual.
            bot.answer_pre_checkout_query(query.id, ok=True)
        except Exception:
            bot.answer_pre_checkout_query(query.id, ok=False, error_message="Não foi possível validar o pedido.")

    @bot.message_handler(content_types=['successful_payment'])
    def vip_pagamento(message):
        sp = message.successful_payment
        payload = sp.invoice_payload or ""
        if not payload.startswith("vip:"):
            return
        uid = message.from_user.id
        try:
            partes = payload.split(":")
            if len(partes) != 5 or int(partes[1]) != uid:
                return
            stars = int(partes[2]); dias = int(partes[3]); charge = sp.telegram_payment_charge_id
            if sp.currency != "XTR" or int(sp.total_amount) != stars or dias <= 0:
                print("PAGAMENTO VIP REJEITADO: dados incompatíveis")
                return
            cursor.execute("SELECT 1 FROM vip_pagamentos WHERE charge_id=? OR payload=?", (charge, payload))
            if cursor.fetchone():
                return
            inicio = _agora()
            cursor.execute("""INSERT INTO vip_pagamentos(usuario_id,payload,charge_id,valor_stars,data)
                            VALUES(?,?,?,?,?)""", (uid,payload,charge,stars,data_atual()))

            cursor.execute("""SELECT id, expiracao FROM vip_assinaturas
                              WHERE usuario_id=? AND status='ATIVO'
                              ORDER BY expiracao DESC LIMIT 1""", (uid,))
            atual = cursor.fetchone()

            if atual:
                base = _parse_dt(atual[1])
                if not base or base <= inicio:
                    base = inicio
                expiracao = base + timedelta(days=dias)
                cursor.execute(
                    "UPDATE vip_assinaturas SET expiracao=?, status='ATIVO', charge_id=?, payload=?, preco_stars=? WHERE id=?",
                    (expiracao.isoformat(timespec='seconds'), charge, payload, stars, atual[0])
                )
                acao = "RENOVADO"
            else:
                expiracao = inicio + timedelta(days=dias)
                cursor.execute("""INSERT INTO vip_assinaturas(usuario_id,plano,preco_stars,inicio,expiracao,status,charge_id,payload,criado_em)
                                VALUES(?,?,?,?,?,'ATIVO',?,?,?)""",
                               (uid,cfg('vip_nome','VIP Premium'),stars,
                                inicio.isoformat(timespec='seconds'),
                                expiracao.isoformat(timespec='seconds'),
                                charge,payload,data_atual()))
                acao = "ATIVADO"

            conn.commit()
            registrar_historico(uid, "VIP_COMPRA", f"Compra de {cfg('vip_nome','VIP Premium')} por {stars} Stars", 0)
            registrar_movimentacao(uid, "VIP", 0, f"Compra VIP: {stars} Stars")
            criar_notificacao(uid, "💎 VIP ativado", f"Seu VIP foi ativado por {dias} dias.")
            bot.send_message(uid, f"🎉 <b>VIP {acao} COM SUCESSO!</b>\n\n💎 {cfg('vip_nome','VIP Premium')}\n⏳ Expira em: <b>{expiracao.strftime('%d/%m/%Y %H:%M')}</b>\n\n🎰 {int(cfg('vip_giros_roleta',2))} giros/dia\n🎫 {int(cfg('vip_raspadinhas',2))} raspadinhas/dia\n🍀 {float(cfg('vip_chance_mult',1.5)):g}x chances", parse_mode='HTML')
        except Exception as erro:
            conn.rollback()
            print(f"ERRO AO ATIVAR VIP APÓS PAGAMENTO: {erro}")

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
    online = cfg("vip_pagamento_online", "1") == "1"
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
        "\n🧑‍💻 A aquisição e renovação são feitas exclusivamente pelo suporte.\n"
    )
    bot.send_message(chat_id, texto, parse_mode="HTML", reply_markup=kb)

