from telebot import types

from database import conn, cursor

from config import (
    ADMIN_ID,
    VALOR_MINIMO_SAQUE,
    STATUS_PENDENTE,
    STATUS_APROVADO,
    STATUS_REJEITADO
)

from utils import (
    dinheiro,
    data_atual,
    buscar_pix,
    saldo_usuario,
    saque_pendente,
    adicionar_saque_pendente,
    remover_saque_pendente,
    remover_saldo,
    registrar_historico,
    valor_minimo_saque_atual,
    criar_notificacao,
    registrar_movimentacao
)

from antifraude import usuario_banido


# ==========================================
# ESTADOS
# ==========================================

aguardando_pix = {}

aguardando_valor = {}


# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    # ==========================================
    # CADASTRAR PIX
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💳 PIX")
    def cadastrar_pix(message):

        user_id = message.from_user.id

        if usuario_banido(user_id):

            bot.send_message(

                message.chat.id,

                "❌ Sua conta está bloqueada."

            )

            return

        pix = buscar_pix(user_id)

        if pix != "":

            bot.send_message(

                message.chat.id,

                f"""
💳 SUA CHAVE PIX

<code>{pix}</code>

Envie uma nova chave para alterá-la.
""",

                parse_mode="HTML"

            )

        else:

            bot.send_message(

                message.chat.id,

                """
💳 CADASTRO DE PIX

Envie sua chave PIX.

Pode ser:

• CPF

• Telefone

• Email

• Chave Aleatória
"""

            )

        aguardando_pix[user_id] = True


    # ==========================================
    # RECEBER PIX
    # ==========================================

    @bot.message_handler(func=lambda m: m.from_user.id in aguardando_pix)
    def receber_pix(message):

        user_id = message.from_user.id

        if usuario_banido(user_id):

            aguardando_pix.pop(user_id, None)

            bot.send_message(

                message.chat.id,

                "❌ Sua conta está bloqueada."

            )

            return

        chave = message.text.strip()

        if len(chave) < 5:

            bot.send_message(

                message.chat.id,

                "❌ Chave PIX inválida."

            )

            return

        cursor.execute(
            """
            UPDATE usuarios
            SET pix=?
            WHERE id=?
            """,
            (
                chave,
                user_id
            )
        )

        conn.commit()

        aguardando_pix.pop(user_id, None)

        registrar_historico(
            user_id,
            "PIX",
            "Chave PIX cadastrada"
        )

        bot.send_message(

            message.chat.id,

            f"""
✅ Chave PIX salva com sucesso.

Sua chave:

<code>{chave}</code>
""",

            parse_mode="HTML"

        )


    # ==========================================
    # SOLICITAR SAQUE
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💸 Solicitar Saque")
    def solicitar_saque(message):

        valor_minimo = valor_minimo_saque_atual()

        user_id = message.from_user.id

        if usuario_banido(user_id):

            bot.send_message(

                message.chat.id,

                "❌ Sua conta está bloqueada."

            )

            return

        pix = buscar_pix(user_id)

        if pix == "":

            bot.send_message(

                message.chat.id,

                """
❌ Você precisa cadastrar sua chave PIX primeiro.
"""

            )

            return

        saldo = saldo_usuario(user_id)

        reservado = saque_pendente(user_id)

        disponivel = saldo - reservado

        if disponivel < valor_minimo:

            bot.send_message(

                message.chat.id,

                f"""
❌ Saldo insuficiente.

Disponível:

{dinheiro(disponivel)}

Valor mínimo:

{dinheiro(valor_minimo)}
"""

            )

            return

        aguardando_valor[user_id] = True

        bot.send_message(

            message.chat.id,

            f"""
💸 SOLICITAÇÃO DE SAQUE

Saldo disponível:

{dinheiro(disponivel)}

Digite o valor que deseja sacar.
"""

        )


    # ==========================================
    # RECEBER VALOR
    # ==========================================

    @bot.message_handler(func=lambda m: m.from_user.id in aguardando_valor)
    def receber_valor(message):

        valor_minimo = valor_minimo_saque_atual()

        user_id = message.from_user.id

        if usuario_banido(user_id):

            aguardando_valor.pop(user_id, None)

            bot.send_message(

                message.chat.id,

                "❌ Sua conta está bloqueada."

            )

            return

        try:

            valor = float(
                message.text.replace(",", ".")
            )

        except:

            bot.send_message(

                message.chat.id,

                "❌ Digite um valor válido."

            )

            return

        saldo = saldo_usuario(user_id)

        reservado = saque_pendente(user_id)

        disponivel = saldo - reservado

        if valor < valor_minimo:

            bot.send_message(

                message.chat.id,

                f"""
❌ O valor mínimo para saque é

{dinheiro(valor_minimo)}
"""

            )

            return

        if valor > disponivel:

            bot.send_message(

                message.chat.id,

                f"""
❌ Você possui apenas

{dinheiro(disponivel)}

disponíveis.
"""

            )

            return

        pix = buscar_pix(user_id)

        teclado = types.InlineKeyboardMarkup(row_width=2)

        teclado.add(

            types.InlineKeyboardButton(

                "✅ Confirmar",

                callback_data=f"confirmar_saque:{valor}"

            ),

            types.InlineKeyboardButton(

                "❌ Cancelar",

                callback_data="cancelar_saque"

            )

        )

        bot.send_message(

            message.chat.id,

            f"""
💸 <b>CONFIRMAR SAQUE</b>

💰 Valor:

{dinheiro(valor)}

💳 PIX:

<code>{pix}</code>

Deseja confirmar?
""",

            parse_mode="HTML",

            reply_markup=teclado

        )

        aguardando_valor.pop(user_id, None)

    # ==========================================
    # CONFIRMAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("confirmar_saque:")
    )
    def confirmar_saque(call):

        user_id = call.from_user.id

        if usuario_banido(user_id):

            bot.answer_callback_query(
                call.id,
                "Sua conta está bloqueada.",
                show_alert=True
            )

            return

        valor = float(call.data.split(":")[1])

        pix = buscar_pix(user_id)

        cursor.execute(

            """
            INSERT INTO saques
            (
                usuario_id,
                valor,
                pix,
                status,
                motivo_rejeicao,
                admin_id,
                data,
                data_aprovacao
            )

            VALUES

            (?, ?, ?, ?, '', NULL, ?, NULL)

            """,

            (

                user_id,

                valor,

                pix,

                STATUS_PENDENTE,

                data_atual()

            )

        )

        saque_id = cursor.lastrowid

        conn.commit()

        adicionar_saque_pendente(

            user_id,

            valor

        )

        registrar_historico(

            user_id,

            "SAQUE",

            "Solicitação de saque",

            valor

        )

        bot.edit_message_text(

            f"""
✅ Solicitação enviada!

💰 Valor:

{dinheiro(valor)}

Agora aguarde a aprovação do administrador.
""",

            chat_id=call.message.chat.id,

            message_id=call.message.message_id

        )

        cursor.execute(

            """
            SELECT nome
            FROM usuarios
            WHERE id=?
            """,

            (user_id,)

        )

        usuario = cursor.fetchone()[0]

        bot.send_message(

            ADMIN_ID,

            f"""
💸 <b>NOVA SOLICITAÇÃO DE SAQUE</b>

👤 Usuário:

{usuario}

🆔 ID:

<code>{user_id}</code>

💰 Valor:

{dinheiro(valor)}

💳 PIX:

<code>{pix}</code>

Utilize o painel administrativo para aprovar ou rejeitar este saque.
""",

            parse_mode="HTML"

        )

        bot.answer_callback_query(call.id)


    # ==========================================
    # CANCELAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data == "cancelar_saque"
    )
    def cancelar_saque(call):

        bot.edit_message_text(

            "❌ Solicitação cancelada.",

            chat_id=call.message.chat.id,

            message_id=call.message.message_id

        )

        bot.answer_callback_query(call.id)

# ==========================================
# APROVAR SAQUE
# ==========================================

def aprovar_saque(saque_id, admin_id):

    cursor.execute(
        """
        SELECT usuario_id, valor, status
        FROM saques
        WHERE id=?
        """,
        (saque_id,)
    )

    saque = cursor.fetchone()

    if saque is None:
        return False, "Saque não encontrado."

    usuario_id, valor, status = saque

    if status != STATUS_PENDENTE:
        return False, "Este saque já foi processado."

    cursor.execute(
        """
        UPDATE saques
        SET
            status=?,
            admin_id=?,
            data_aprovacao=?
        WHERE id=?
        """,
        (
            STATUS_APROVADO,
            admin_id,
            data_atual(),
            saque_id
        )
    )

    conn.commit()

    remover_saque_pendente(
        usuario_id,
        valor
    )

    remover_saldo(
        usuario_id,
        valor
    )

    registrar_historico(
        usuario_id,
        "SAQUE",
        "Saque aprovado",
        valor
    )

    registrar_movimentacao(
        usuario_id,
        "SAQUE_APROVADO",
        -valor,
        f"Saque #{saque_id} aprovado"
    )

    criar_notificacao(
        usuario_id,
        "🎉 Saque aprovado",
        f"Seu saque de R$ {valor:.2f} foi aprovado."
    )

    return True, usuario_id


# ==========================================
# REJEITAR SAQUE
# ==========================================

def rejeitar_saque(saque_id, admin_id, motivo):

    cursor.execute(
        """
        SELECT usuario_id, valor, status
        FROM saques
        WHERE id=?
        """,
        (saque_id,)
    )

    saque = cursor.fetchone()

    if saque is None:
        return False, "Saque não encontrado."

    usuario_id, valor, status = saque

    if status != STATUS_PENDENTE:
        return False, "Este saque já foi processado."

    cursor.execute(
        """
        UPDATE saques
        SET
            status=?,
            motivo_rejeicao=?,
            admin_id=?,
            data_aprovacao=?
        WHERE id=?
        """,
        (
            STATUS_REJEITADO,
            motivo,
            admin_id,
            data_atual(),
            saque_id
        )
    )

    conn.commit()

    remover_saque_pendente(
        usuario_id,
        valor
    )

    registrar_historico(
        usuario_id,
        "SAQUE",
        f"Saque rejeitado: {motivo}",
        valor
    )

    registrar_movimentacao(
        usuario_id,
        "SAQUE_REJEITADO",
        0,
        f"Saque #{saque_id} rejeitado: {motivo}"
    )

    criar_notificacao(
        usuario_id,
        "❌ Saque rejeitado",
        f"Seu saque de R$ {valor:.2f} foi rejeitado. Motivo: {motivo}"
    )

    return True, usuario_id


# ==========================================
# LISTAR SAQUES PENDENTES
# ==========================================

def listar_saques_pendentes():

    cursor.execute(
        """
        SELECT
            id,
            usuario_id,
            valor,
            pix,
            data
        FROM saques
        WHERE status=?
        ORDER BY id
        """,
        (STATUS_PENDENTE,)
    )

    return cursor.fetchall()
