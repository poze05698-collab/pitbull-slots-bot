from telebot import types

from config import (
    ADMIN_ID,
    STATUS_PENDENTE
)

from database import cursor

from utils import (
    eh_admin,
    dinheiro
)

from indicacoes import (
    aprovar_indicacao,
    rejeitar_indicacao
)

from saques import (
    aprovar_saque,
    rejeitar_saque,
    listar_saques_pendentes
)

from antifraude import (
    banir_usuario,
    desbanir_usuario
)

# ==========================================
# VERIFICAR ADMIN
# ==========================================

def admin_autorizado(user_id):

    return eh_admin(user_id)


# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    # ==========================================
    # PAINEL ADMIN
    # ==========================================

    @bot.message_handler(commands=["admin"])
    def painel_admin(message):

        if not admin_autorizado(message.from_user.id):

            bot.reply_to(

                message,

                "❌ Você não possui permissão."

            )

            return

        teclado = types.ReplyKeyboardMarkup(
            resize_keyboard=True
        )

        teclado.row(
            "🎁 Indicações",
            "💸 Saques"
        )

        teclado.row(
            "👥 Usuários",
            "📊 Estatísticas"
        )

        teclado.row(
            "🚫 Banimentos",
            "⬅️ Menu"
        )

        bot.send_message(

            message.chat.id,

            """
🔐 <b>PAINEL ADMINISTRATIVO</b>

Escolha uma opção.
""",

            parse_mode="HTML",

            reply_markup=teclado

        )

    # ==========================================
    # INDICAÇÕES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎁 Indicações")
    def listar_indicacoes(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT
                i.id,
                u1.nome,
                u2.nome,
                i.valor,
                i.data,
                i.grupo_confirmado
            FROM indicacoes i
            JOIN usuarios u1
                ON u1.id = i.indicador_id
            JOIN usuarios u2
                ON u2.id = i.indicado_id
            WHERE i.status=?
            ORDER BY i.id
            """,
            (STATUS_PENDENTE,)
        )

        lista = cursor.fetchall()

        if not lista:

            bot.send_message(

                message.chat.id,

                "✅ Não existem indicações pendentes."

            )

            return

        for item in lista:

            teclado = types.InlineKeyboardMarkup()

            teclado.row(

                types.InlineKeyboardButton(

                    "✅ Aprovar",

                    callback_data=f"aprovar_indicacao:{item[0]}"

                ),

                types.InlineKeyboardButton(

                    "❌ Rejeitar",

                    callback_data=f"rejeitar_indicacao:{item[0]}"

                )

            )

            grupo = "Sim" if item[5] else "Não"

            bot.send_message(

                message.chat.id,

                f"""
🎁 INDICAÇÃO #{item[0]}

👤 Indicador:

{item[1]}

👤 Indicado:

{item[2]}

💰 Valor:

{dinheiro(item[3])}

👥 Entrou no grupo?

{grupo}

📅 Data:

{item[4]}
""",

                reply_markup=teclado

            )

try:

    membro = bot.get_chat_member(
        GRUPO_ID,
        indicado_id
    )

    if membro.status in (
        "left",
        "kicked"
    ):

        bot.answer_callback_query(
            call.id,
            "❌ O usuário ainda não entrou no grupo."
        )

        return

except Exception:

    bot.answer_callback_query(
        call.id,
        "❌ Não foi possível verificar o grupo."
    )

    return
    
    # ==========================================
    # APROVAR INDICAÇÃO
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("aprovar_indicacao:")
    )
    def callback_aprovar_indicacao(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(

                call.id,

                "Sem permissão.",

                show_alert=True

            )

            return

        indicacao_id = int(call.data.split(":")[1])

        sucesso, retorno = aprovar_indicacao(

            indicacao_id,

            call.from_user.id

        )

        if not sucesso:

            bot.answer_callback_query(

                call.id,

                retorno,

                show_alert=True

            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(

            chat_id=call.message.chat.id,

            message_id=call.message.message_id,

            reply_markup=None

        )

        bot.send_message(

            call.message.chat.id,

            "✅ Indicação aprovada com sucesso."

        )

        try:

            bot.send_message(

                usuario_id,

                """
🎉 Sua indicação foi aprovada!

O valor já está disponível em seu saldo.
"""

            )

        except:

            pass

        bot.answer_callback_query(call.id)


    # ==========================================
    # REJEITAR INDICAÇÃO
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rejeitar_indicacao:")
    )
    def callback_rejeitar_indicacao(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(

                call.id,

                "Sem permissão.",

                show_alert=True

            )

            return

        indicacao_id = int(call.data.split(":")[1])

        motivo = "Rejeitada pelo administrador"

        sucesso, retorno = rejeitar_indicacao(

            indicacao_id,

            call.from_user.id,

            motivo

        )

        if not sucesso:

            bot.answer_callback_query(

                call.id,

                retorno,

                show_alert=True

            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(

            chat_id=call.message.chat.id,

            message_id=call.message.message_id,

            reply_markup=None

        )

        bot.send_message(

            call.message.chat.id,

            "❌ Indicação rejeitada."

        )

        try:

            bot.send_message(

                usuario_id,

                f"""
❌ Sua indicação foi rejeitada.

Motivo:

{motivo}
"""

            )

        except:

            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # SAQUES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💸 Saques")
    def listar_saques(message):

        if not admin_autorizado(message.from_user.id):
            return

        saques = listar_saques_pendentes()

        if not saques:

            bot.send_message(

                message.chat.id,

                "✅ Não existem saques pendentes."

            )

            return

        for saque in saques:

            teclado = types.InlineKeyboardMarkup()

            teclado.row(

                types.InlineKeyboardButton(

                    "✅ Aprovar",

                    callback_data=f"aprovar_saque:{saque[0]}"

                ),

                types.InlineKeyboardButton(

                    "❌ Rejeitar",

                    callback_data=f"rejeitar_saque:{saque[0]}"

                )

            )

            bot.send_message(

                message.chat.id,

                f"""
💸 <b>SAQUE #{saque[0]}</b>

👤 Usuário:

<code>{saque[1]}</code>

💰 Valor:

{dinheiro(saque[2])}

💳 PIX:

<code>{saque[3]}</code>

📅 Data:

{saque[4]}
""",

                parse_mode="HTML",

                reply_markup=teclado

            )


    # ==========================================
    # APROVAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("aprovar_saque:")
    )
    def callback_aprovar_saque(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(

                call.id,

                "Sem permissão.",

                show_alert=True

            )

            return

        saque_id = int(call.data.split(":")[1])

        sucesso, retorno = aprovar_saque(

            saque_id,

            call.from_user.id

        )

        if not sucesso:

            bot.answer_callback_query(

                call.id,

                retorno,

                show_alert=True

            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(

            chat_id=call.message.chat.id,

            message_id=call.message.message_id,

            reply_markup=None

        )

        bot.send_message(

            call.message.chat.id,

            "✅ Saque aprovado com sucesso."

        )

        try:

            bot.send_message(

                usuario_id,

                """
🎉 Seu saque foi aprovado!

Em breve o pagamento será realizado.
"""

            )

        except:

            pass

        bot.answer_callback_query(call.id)


    # ==========================================
    # REJEITAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rejeitar_saque:")
    )
    def callback_rejeitar_saque(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(

                call.id,

                "Sem permissão.",

                show_alert=True

            )

            return

        saque_id = int(call.data.split(":")[1])

        motivo = "Rejeitado pelo administrador"

        sucesso, retorno = rejeitar_saque(

            saque_id,

            call.from_user.id,

            motivo

        )

        if not sucesso:

            bot.answer_callback_query(

                call.id,

                retorno,

                show_alert=True

            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(

            chat_id=call.message.chat.id,

            message_id=call.message.message_id,

            reply_markup=None

        )

        bot.send_message(

            call.message.chat.id,

            "❌ Saque rejeitado."

        )

        try:

            bot.send_message(

                usuario_id,

                f"""
❌ Seu saque foi rejeitado.

Motivo:

{motivo}
"""

            )

        except:

            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # USUÁRIOS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "👥 Usuários")
    def listar_usuarios(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM usuarios
            """
        )

        total = cursor.fetchone()[0]

        bot.send_message(

            message.chat.id,

            f"""
👥 <b>USUÁRIOS</b>

Total de usuários cadastrados:

<b>{total}</b>
""",

            parse_mode="HTML"

        )


    # ==========================================
    # BANIMENTOS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🚫 Banimentos")
    def menu_banimentos(message):

        if not admin_autorizado(message.from_user.id):
            return

        bot.send_message(

            message.chat.id,

            """
🚫 Sistema de banimentos

Esta função será integrada ao módulo antifraude.py.
"""

        )


    # ==========================================
    # ESTATÍSTICAS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📊 Estatísticas")
    def estatisticas(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            "SELECT COUNT(*) FROM usuarios"
        )
        usuarios = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM indicacoes"
        )
        indicacoes = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM saques"
        )
        saques = cursor.fetchone()[0]

        bot.send_message(

            message.chat.id,

            f"""
📊 <b>ESTATÍSTICAS</b>

👥 Usuários:

{usuarios}

🎁 Indicações:

{indicacoes}

💸 Saques:

{saques}
""",

            parse_mode="HTML"

        )
