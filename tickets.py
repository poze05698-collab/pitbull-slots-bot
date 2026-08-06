from telebot import types

from database import conn, cursor

from config import ADMIN_ID

from utils import data_atual

STATUS_ABERTO = "ABERTO"
STATUS_RESPONDIDO = "RESPONDIDO"
STATUS_FECHADO = "FECHADO"


def registrar(bot):

    estados = {}

    respostas = {}


    # ==========================================
    # ABRIR TICKET
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎫 Suporte")
    def abrir_ticket(message):

        if message.from_user.id in estados:

            bot.send_message(
                message.chat.id,
                "❌ Você já possui um atendimento em andamento."
            )

            return

        estados[message.from_user.id] = True

        bot.send_message(
            message.chat.id,
            """
🎫 <b>SUPORTE</b>

Descreva seu problema.

Nossa equipe responderá o mais rápido possível.
""",
            parse_mode="HTML"
        )

    # ==========================================
    # RECEBER TICKET
    # ==========================================

    @bot.message_handler(func=lambda m: m.from_user.id in estados)
    def receber_ticket(message):

        user_id = message.from_user.id

        mensagem = message.text.strip()

        estados.pop(user_id)

        cursor.execute(
            """
            INSERT INTO tickets
            (
                usuario_id,
                mensagem,
                status,
                data
            )
            VALUES
            (?, ?, ?, ?)
            """,
            (
                user_id,
                mensagem,
                STATUS_ABERTO,
                data_atual()
            )
        )

        conn.commit()


    # ==========================================
    # ENVIAR PARA O ADMIN
    # ==========================================

        markup = types.InlineKeyboardMarkup()

        markup.row(

            types.InlineKeyboardButton(
                "✉️ Responder",
                callback_data=f"ticket_resp_{user_id}"
            ),

            types.InlineKeyboardButton(
                "❌ Fechar",
                callback_data=f"ticket_close_{user_id}"
            )

        )

        try:

            bot.send_message(

                ADMIN_ID,

                f"""
🎫 <b>NOVO TICKET</b>

👤 Usuário:
<code>{user_id}</code>

📝 Mensagem:

{mensagem}
""",

                parse_mode="HTML",

                reply_markup=markup

            )

        except Exception as erro:

            print(f"Erro ao enviar ticket: {erro}")

        bot.send_message(

            message.chat.id,

            """
✅ Seu ticket foi enviado.

Nossa equipe responderá em breve.
""",

            parse_mode="HTML"

        )


    # ==========================================
    # RESPONDER TICKET
    # ==========================================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("ticket_resp_")
    )
    def responder_ticket(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão."
            )

            return

        usuario_id = int(
            call.data.split("_")[-1]
        )

        respostas[ADMIN_ID] = usuario_id

        bot.answer_callback_query(
            call.id,
            "Digite a resposta para o usuário."
        )

        bot.send_message(

            ADMIN_ID,

            f"""
✍️ Responda o ticket.

Usuário:
<code>{usuario_id}</code>
""",

            parse_mode="HTML"

        )

    # ==========================================
    # RECEBER RESPOSTA
    # ==========================================

    @bot.message_handler(
        func=lambda m: m.from_user.id in respostas
    )
    def receber_resposta(message):

        if message.from_user.id != ADMIN_ID:
            return

        usuario_id = respostas.pop(ADMIN_ID)

        resposta = message.text.strip()

        cursor.execute(
            """
            UPDATE tickets
            SET
                resposta=?,
                status=?,
                admin_id=?,
                data_resposta=?
            WHERE usuario_id=?
            AND status=?
            """,
            (
                resposta,
                STATUS_RESPONDIDO,
                ADMIN_ID,
                data_atual(),
                usuario_id,
                STATUS_ABERTO
            )
        )

        conn.commit()

        bot.send_message(

            usuario_id,

            f"""
📩 <b>Resposta do Suporte</b>

{resposta}
""",

            parse_mode="HTML"

        )

        bot.send_message(
            ADMIN_ID,
            "✅ Resposta enviada."
        )


    # ==========================================
    # FECHAR TICKET
    # ==========================================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("ticket_close_")
    )
    def fechar_ticket(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão."
            )

            return

        usuario_id = int(
            call.data.split("_")[-1]
        )

        cursor.execute(
            """
            UPDATE tickets
            SET
                status=?,
                admin_id=?,
                data_fechamento=?
            WHERE usuario_id=?
            AND status IN (?, ?)
            """,
            (
                STATUS_FECHADO,
                ADMIN_ID,
                data_atual(),
                usuario_id,
                STATUS_ABERTO,
                STATUS_RESPONDIDO
            )
        )

        conn.commit()

        bot.answer_callback_query(
            call.id,
            "✅ Ticket fechado."
        )

        try:

            bot.send_message(

                usuario_id,

                """
📩 Seu ticket foi encerrado.

Se precisar de ajuda novamente,
abra um novo ticket pelo menu.
"""

            )

        except Exception:
            pass

        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except Exception:
            pass
