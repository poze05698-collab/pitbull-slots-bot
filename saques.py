from telebot import types

from database import cursor, conn
from utils import (
    registrar_historico,
    saldo_usuario,
    saque_pendente,
    dinheiro
)

from config import (
    VALOR_MINIMO_SAQUE,
    ADMIN_ID
)

# ==========================================
# ESTADOS
# ==========================================

aguardando_pix = {}
aguardando_saque = {}


# ==========================================
# REGISTRAR MÓDULO
# ==========================================

def registrar(bot):

    # ==========================================
    # CADASTRAR PIX
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💳 PIX")
    def pix(message):

        user_id = message.from_user.id

        cursor.execute(
            "SELECT pix FROM usuarios WHERE id=?",
            (user_id,)
        )

        resultado = cursor.fetchone()

        if resultado and resultado[0]:

            bot.send_message(

                message.chat.id,

                f"""
💳 SUA CHAVE PIX

<code>{resultado[0]}</code>

Envie uma nova chave caso queira alterar.
""",

                parse_mode="HTML"

            )

        else:

            bot.send_message(

                message.chat.id,

                """
💳 CADASTRO DE PIX

Envie sua chave PIX.

Ela será utilizada para receber seus saques.
"""

            )

        aguardando_pix[user_id] = True


    # ==========================================
    # RECEBER PIX
    # ==========================================

    @bot.message_handler(func=lambda m: m.from_user.id in aguardando_pix)
    def salvar_pix(message):

        user_id = message.from_user.id

        pix = message.text.strip()

        cursor.execute(

            """
            UPDATE usuarios

            SET pix=?

            WHERE id=?

            """,

            (

                pix,

                user_id

            )

        )

        conn.commit()

        aguardando_pix.pop(user_id)

        registrar_historico(

            user_id,

            "PIX",

            "Chave PIX cadastrada"

        )

        bot.send_message(

            message.chat.id,

            """
✅ PIX salvo com sucesso.
"""

        )


    # ==========================================
    # SOLICITAR SAQUE
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💸 Solicitar Saque")
    def solicitar_saque(message):

        user_id = message.from_user.id

        cursor.execute(

            """
            SELECT pix

            FROM usuarios

            WHERE id=?

            """,

            (user_id,)

        )

        resultado = cursor.fetchone()

        if resultado is None or resultado[0] == "":

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

        if disponivel < VALOR_MINIMO_SAQUE:

            bot.send_message(

                message.chat.id,

                f"""
❌ Você não possui saldo suficiente.

Saldo disponível:

{dinheiro(disponivel)}

Valor mínimo:

{dinheiro(VALOR_MINIMO_SAQUE)}
"""

            )

            return

        aguardando_saque[user_id] = True

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
    # RECEBER VALOR DO SAQUE
    # ==========================================

    @bot.message_handler(func=lambda m: m.from_user.id in aguardando_saque)
    def receber_valor_saque(message):

        user_id = message.from_user.id

        try:
            valor = float(
                message.text.replace(",", ".")
            )

        except ValueError:

            bot.send_message(
                message.chat.id,
                "❌ Digite um valor válido."
            )

            return

        saldo = saldo_usuario(user_id)

        reservado = saque_pendente(user_id)

        disponivel = saldo - reservado

        if valor < VALOR_MINIMO_SAQUE:

            bot.send_message(

                message.chat.id,

                f"""

❌ O valor mínimo para saque é

{dinheiro(VALOR_MINIMO_SAQUE)}

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

        cursor.execute(

            """

            SELECT pix

            FROM usuarios

            WHERE id=?

            """,

            (user_id,)

        )

        pix = cursor.fetchone()[0]

        teclado = types.InlineKeyboardMarkup()

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

💸 CONFIRMAR SAQUE

Valor:

{dinheiro(valor)}

PIX:

<code>{pix}</code>

Deseja continuar?

""",

            parse_mode="HTML",

            reply_markup=teclado

        )

        aguardando_saque.pop(user_id)

      # ==========================================
    # CONFIRMAR SAQUE
    # ==========================================

    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirmar_saque:"))
    def confirmar_saque(call):

        user_id = call.from_user.id

        valor = float(call.data.split(":")[1])

        cursor.execute(
            """
            SELECT pix
            FROM usuarios
            WHERE id=?
            """,
            (user_id,)
        )

        pix = cursor.fetchone()[0]

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
            (?, ?, ?, 'PENDENTE', '', NULL, ?, NULL)
            """,
            (
                user_id,
                valor,
                pix,
                data_atual()
            )
        )

        cursor.execute(
            """
            UPDATE usuarios
            SET saque_pendente = saque_pendente + ?
            WHERE id=?
            """,
            (
                valor,
                user_id
            )
        )

        conn.commit()

        registrar_historico(
            user_id,
            "SAQUE",
            "Solicitação de saque",
            valor
        )

        bot.edit_message_text(

            f"""

✅ Solicitação enviada!

Valor:

{dinheiro(valor)}

Seu saque ficará aguardando aprovação do administrador.

""",

            chat_id=call.message.chat.id,

            message_id=call.message.message_id

        )

        # Avisar administrador

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

💸 NOVA SOLICITAÇÃO DE SAQUE

👤 Usuário:

{usuario}

🆔 ID:

<code>{user_id}</code>

💰 Valor:

{dinheiro(valor)}

""",

            parse_mode="HTML"

        )

        bot.answer_callback_query(call.id)


    # ==========================================
    # CANCELAR SAQUE
    # ==========================================

    @bot.callback_query_handler(func=lambda call: call.data == "cancelar_saque")
    def cancelar_saque(call):

        bot.edit_message_text(

            "❌ Solicitação cancelada.",

            chat_id=call.message.chat.id,

            message_id=call.message.message_id

        )

        bot.answer_callback_query(call.id)


