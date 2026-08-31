from telebot import types
import threading

from database import conn, cursor
from config import ADMIN_ID
from utils import data_atual
from ia_suporte import responder as responder_ia


# =====================================================
# STATUS
# =====================================================

STATUS_ABERTO = "ABERTO"
STATUS_RESPONDIDO = "RESPONDIDO"
STATUS_FECHADO = "FECHADO"


# =====================================================
# CATEGORIAS
# =====================================================

CATEGORIAS = {
    "saldo": "💰 Problema com saldo",
    "saque": "💸 Problema com saque",
    "indicacao": "🎁 Problema com indicação",
    "pix": "💳 Problema com PIX",
    "convite": "🔗 Problema com convite",
    "outro": "❓ Outro"
}


def preparar_banco():

    # Cria o histórico completo das mensagens.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            remetente TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
    )

    # Migração segura: adiciona as novas colunas somente se ainda não existirem.
    cursor.execute("PRAGMA table_info(tickets)")
    colunas = {linha[1] for linha in cursor.fetchall()}

    novas_colunas = {
        "categoria": "TEXT DEFAULT 'outro'",
        "assumido_por": "INTEGER",
        "assumido_em": "TEXT",
        "ultima_mensagem_em": "TEXT",
        "avaliacao": "INTEGER",
        "avaliacao_comentario": "TEXT"
    }

    for nome, tipo in novas_colunas.items():

        if nome not in colunas:

            cursor.execute(
                f"ALTER TABLE tickets ADD COLUMN {nome} {tipo}"
            )

    conn.commit()


def registrar(bot):

    preparar_banco()

    # Usuário que está escolhendo categoria / digitando a primeira mensagem.
    estados = {}

    # Admin que está respondendo: {ADMIN_ID: ticket_id}
    respostas = {}

    # Usuários que acabaram de avaliar e podem enviar comentário.
    comentarios_avaliacao = {}

    # =====================================================
    # AUXILIARES
    # =====================================================

    def atendimento_ia_em_background(ticket_id, usuario_id, categoria, mensagem):
        """Responde o ticket sem bloquear a thread que recebeu a mensagem."""
        try:
            resposta = responder_ia(usuario_id, ticket_id, categoria, mensagem)
            if not resposta:
                return

            ticket = buscar_ticket(ticket_id)
            if not ticket or ticket[4] == STATUS_FECHADO or ticket[7] is not None:
                return

            registrar_mensagem(
                ticket_id,
                usuario_id,
                "IA",
                resposta
            )

            cursor.execute(
                """UPDATE tickets
                   SET resposta=?, status=?, data_resposta=?
                   WHERE id=? AND status<>? AND assumido_por IS NULL""",
                (resposta, STATUS_RESPONDIDO, data_atual(), ticket_id, STATUS_FECHADO)
            )
            conn.commit()

            bot.send_message(
                usuario_id,
                f"🤖 <b>SUPORTE VIRTUAL — TICKET #{ticket_id}</b>\n\n{resposta}\n\n💬 Se o problema continuar, responda esta mensagem. Se for necessário, nossa equipe humana assumirá o atendimento.",
                parse_mode="HTML"
            )
        except Exception as erro:
            print(f"ERRO NO ATENDIMENTO IA DO TICKET #{ticket_id}: {erro}")

    def iniciar_atendimento_ia(ticket_id, usuario_id, categoria, mensagem):
        threading.Thread(
            target=atendimento_ia_em_background,
            args=(ticket_id, usuario_id, categoria, mensagem),
            daemon=True,
            name=f"ia-ticket-{ticket_id}"
        ).start()

    def ticket_aberto(usuario_id):

        cursor.execute(
            """
            SELECT
                id,
                usuario_id,
                assunto,
                mensagem,
                status,
                data,
                categoria,
                assumido_por,
                ultima_mensagem_em
            FROM tickets
            WHERE usuario_id=?
            AND status IN (?, ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                usuario_id,
                STATUS_ABERTO,
                STATUS_RESPONDIDO
            )
        )

        return cursor.fetchone()

    def buscar_ticket(ticket_id):

        cursor.execute(
            """
            SELECT
                id,
                usuario_id,
                assunto,
                mensagem,
                status,
                data,
                categoria,
                assumido_por,
                ultima_mensagem_em,
                avaliacao,
                avaliacao_comentario
            FROM tickets
            WHERE id=?
            LIMIT 1
            """,
            (ticket_id,)
        )

        return cursor.fetchone()

    def registrar_mensagem(ticket_id, usuario_id, remetente, mensagem):

        cursor.execute(
            """
            INSERT INTO ticket_mensagens
            (
                ticket_id,
                usuario_id,
                remetente,
                mensagem,
                data
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                usuario_id,
                remetente,
                mensagem,
                data_atual()
            )
        )

        cursor.execute(
            """
            UPDATE tickets
            SET ultima_mensagem_em=?
            WHERE id=?
            """,
            (
                data_atual(),
                ticket_id
            )
        )

        conn.commit()

    def teclado_ticket(ticket_id, usuario_id):

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "✉️ RESPONDER",
                callback_data=f"ticket_resp_id_{ticket_id}"
            ),
            types.InlineKeyboardButton(
                "👨‍💼 ASSUMIR",
                callback_data=f"ticket_assumir_{ticket_id}"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "📜 Histórico",
                callback_data=f"ticket_hist_{ticket_id}"
            ),
            types.InlineKeyboardButton(
                "❌ Fechar",
                callback_data=f"ticket_close_id_{ticket_id}"
            )
        )

        return markup

    def texto_ticket(ticket):

        (
            ticket_id,
            usuario_id,
            assunto,
            mensagem,
            status,
            data,
            categoria,
            assumido_por,
            ultima_mensagem,
            avaliacao,
            avaliacao_comentario
        ) = ticket

        categoria_nome = CATEGORIAS.get(
            categoria,
            CATEGORIAS["outro"]
        )

        status_texto = {
            STATUS_ABERTO: "🟡 Aguardando suporte",
            STATUS_RESPONDIDO: "🔵 Em atendimento",
            STATUS_FECHADO: "🔴 Fechado"
        }.get(status, status)

        return f"""
━━━━━━━━━━━━━━━━━━━━
🎫 <b>TICKET #{ticket_id}</b>
━━━━━━━━━━━━━━━━━━━━

👤 Usuário:
<code>{usuario_id}</code>

📂 Categoria:
{categoria_nome}

📊 Status:
{status_texto}

📅 Aberto:
{data}

📝 Primeira mensagem:
{mensagem}
"""

    def notificar_admin_nova_mensagem(
        ticket_id,
        usuario_id,
        mensagem,
        mostrar_botoes=False
    ):

        texto = f"""
💬 <b>NOVA MENSAGEM</b>

🎫 Ticket #{ticket_id}

👤 Usuário:
<code>{usuario_id}</code>

━━━━━━━━━━━━━━━━━━━━

{mensagem}

━━━━━━━━━━━━━━━━━━━━
"""

        if mostrar_botoes:

            bot.send_message(
                ADMIN_ID,
                texto,
                parse_mode="HTML",
                reply_markup=teclado_ticket(
                    ticket_id,
                    usuario_id
                )
            )

        else:

            bot.send_message(
                ADMIN_ID,
                texto,
                parse_mode="HTML"
            )

    # =====================================================
    # ABRIR TICKET
    # =====================================================

    @bot.message_handler(
        func=lambda m: m.text == "🎫 Suporte"
    )
    def abrir_ticket(message):

        user_id = message.from_user.id

        existente = ticket_aberto(user_id)

        if existente:

            bot.send_message(
                message.chat.id,
                f"""
🎫 <b>Você já possui um atendimento aberto.</b>

Ticket: <b>#{existente[0]}</b>

📊 Status:
{"🟡 Aguardando suporte" if existente[4] == STATUS_ABERTO else "🔵 Em atendimento"}

💬 Pode enviar sua próxima mensagem normalmente aqui.

❌ O atendimento só termina quando o administrador fechar o ticket.
""",
                parse_mode="HTML"
            )

            return

        markup = types.InlineKeyboardMarkup()

        for chave, nome in CATEGORIAS.items():

            markup.add(
                types.InlineKeyboardButton(
                    nome,
                    callback_data=f"ticket_cat_{chave}"
                )
            )

        bot.send_message(
            message.chat.id,
            """
🎫 <b>ABRIR ATENDIMENTO</b>

Escolha o motivo do atendimento:

📂 Selecione uma categoria abaixo.
""",
            parse_mode="HTML",
            reply_markup=markup
        )

    # =====================================================
    # ESCOLHER CATEGORIA
    # =====================================================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("ticket_cat_")
    )
    def escolher_categoria(call):

        user_id = call.from_user.id

        if ticket_aberto(user_id):

            bot.answer_callback_query(
                call.id,
                "Você já possui um ticket aberto.",
                show_alert=True
            )

            return

        categoria = call.data.replace(
            "ticket_cat_",
            "",
            1
        )

        if categoria not in CATEGORIAS:
            categoria = "outro"

        estados[user_id] = categoria

        bot.answer_callback_query(
            call.id,
            "Categoria selecionada."
        )

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            f"""
🎫 <b>NOVO ATENDIMENTO</b>

📂 Categoria:
{CATEGORIAS[categoria]}

Agora descreva seu problema.

💬 Depois disso você poderá continuar enviando várias mensagens no mesmo ticket.
""",
            parse_mode="HTML"
        )

    # =====================================================
    # PRIMEIRA MENSAGEM
    # =====================================================

    @bot.message_handler(
        func=lambda m: m.from_user.id in estados
    )
    def receber_primeira_mensagem(message):

        user_id = message.from_user.id
        mensagem = (message.text or "").strip()

        if not mensagem:

            bot.send_message(
                message.chat.id,
                "❌ Envie uma mensagem válida."
            )

            return

        categoria = estados.pop(
            user_id,
            "outro"
        )

        existente = ticket_aberto(user_id)

        if existente:

            bot.send_message(
                message.chat.id,
                f"❌ Você já possui o ticket #{existente[0]} aberto."
            )

            return

        cursor.execute(
            """
            INSERT INTO tickets
            (
                usuario_id,
                assunto,
                mensagem,
                status,
                data,
                categoria,
                ultima_mensagem_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                CATEGORIAS.get(
                    categoria,
                    CATEGORIAS["outro"]
                ),
                mensagem,
                STATUS_ABERTO,
                data_atual(),
                categoria,
                data_atual()
            )
        )

        ticket_id = cursor.lastrowid

        conn.commit()

        registrar_mensagem(
            ticket_id,
            user_id,
            "USUARIO",
            mensagem
        )

        try:

            notificar_admin_nova_mensagem(
                ticket_id,
                user_id,
                mensagem,
                mostrar_botoes=True
            )

        except Exception as erro:

            print(
                f"Erro ao enviar ticket ao admin: {erro}"
            )

        bot.send_message(
            message.chat.id,
            f"""
✅ <b>Ticket #{ticket_id} aberto com sucesso!</b>

📂 Categoria:
{CATEGORIAS.get(categoria, CATEGORIAS["outro"])}

💬 Você pode continuar enviando mensagens normalmente.

Nossa equipe responderá neste mesmo atendimento.
""",
            parse_mode="HTML"
        )

        # A IA começa imediatamente o primeiro atendimento em segundo plano.
        iniciar_atendimento_ia(
            ticket_id,
            user_id,
            categoria,
            mensagem
        )

    # =====================================================
    # MENSAGENS DO USUÁRIO
    # =====================================================

    def usuario_tem_ticket(user_id):

        return ticket_aberto(user_id) is not None

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id != ADMIN_ID
            and m.from_user.id not in estados
            and usuario_tem_ticket(m.from_user.id)
            and m.text != "🎫 Suporte"
        )
    )
    def continuar_conversa_usuario(message):

        user_id = message.from_user.id
        mensagem = (message.text or "").strip()

        if not mensagem:
            return

        ticket = ticket_aberto(user_id)

        if not ticket:
            return

        ticket_id = ticket[0]

        registrar_mensagem(
            ticket_id,
            user_id,
            "USUARIO",
            mensagem
        )

        cursor.execute(
            """
            UPDATE tickets
            SET status=?
            WHERE id=?
            """,
            (
                STATUS_ABERTO,
                ticket_id
            )
        )

        conn.commit()

        try:

            notificar_admin_nova_mensagem(
                ticket_id,
                user_id,
                mensagem,
                mostrar_botoes=False
            )

            bot.send_message(
                user_id,
                "📨 Mensagem enviada ao suporte."
            )

            # Se nenhum administrador assumiu o ticket, a IA tenta responder.
            if ticket[7] is None:
                iniciar_atendimento_ia(
                    ticket_id,
                    user_id,
                    ticket[6],
                    mensagem
                )

        except Exception as erro:

            print(
                f"Erro ao encaminhar mensagem: {erro}"
            )

            bot.send_message(
                user_id,
                "❌ Não foi possível enviar sua mensagem."
            )

    # =====================================================
    # ADMIN: ASSUMIR
    # =====================================================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("ticket_assumir_")
    )
    def assumir_ticket(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        ticket_id = int(
            call.data.replace(
                "ticket_assumir_",
                "",
                1
            )
        )

        ticket = buscar_ticket(ticket_id)

        if not ticket or ticket[4] == STATUS_FECHADO:

            bot.answer_callback_query(
                call.id,
                "Ticket fechado ou inexistente.",
                show_alert=True
            )

            return

        cursor.execute(
            """
            UPDATE tickets
            SET
                assumido_por=?,
                assumido_em=?,
                status=?
            WHERE id=?
            """,
            (
                ADMIN_ID,
                data_atual(),
                STATUS_RESPONDIDO,
                ticket_id
            )
        )

        conn.commit()

        bot.answer_callback_query(
            call.id,
            "✅ Atendimento assumido."
        )

        bot.send_message(
            ADMIN_ID,
            f"""
👨‍💼 <b>ATENDIMENTO ASSUMIDO</b>

🎫 Ticket #{ticket_id}

Agora você é responsável por este atendimento.
""",
            parse_mode="HTML"
        )

    # =====================================================
    # ADMIN: RESPONDER
    # =====================================================

    @bot.callback_query_handler(
        func=lambda c: (
            c.data.startswith("ticket_resp_id_")
            or c.data.startswith("ticket_resp_")
        )
    )
    def iniciar_resposta(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        if call.data.startswith("ticket_resp_id_"):

            ticket_id = int(
                call.data.replace(
                    "ticket_resp_id_",
                    "",
                    1
                )
            )

        else:

            # Compatibilidade com botões antigos.
            usuario_id = int(
                call.data.split("_")[-1]
            )

            ticket = ticket_aberto(usuario_id)

            if not ticket:

                bot.answer_callback_query(
                    call.id,
                    "Ticket não encontrado.",
                    show_alert=True
                )

                return

            ticket_id = ticket[0]

        ticket = buscar_ticket(ticket_id)

        if not ticket or ticket[4] == STATUS_FECHADO:

            bot.answer_callback_query(
                call.id,
                "Este ticket está fechado.",
                show_alert=True
            )

            return

        respostas[ADMIN_ID] = ticket_id

        bot.answer_callback_query(
            call.id,
            "Modo de resposta ativado."
        )

        bot.send_message(
            ADMIN_ID,
            f"""
✍️ <b>RESPONDER TICKET #{ticket_id}</b>

👤 Usuário:
<code>{ticket[1]}</code>

Digite sua resposta.

💬 Você poderá continuar enviando várias respostas.
""",
            parse_mode="HTML"
        )

    # =====================================================
    # ADMIN: RECEBER RESPOSTA
    # =====================================================

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id == ADMIN_ID
            and m.from_user.id in respostas
        )
    )
    def receber_resposta_admin(message):

        resposta = (message.text or "").strip()

        if not resposta:
            return

        ticket_id = respostas.get(
            ADMIN_ID
        )

        if not ticket_id:
            return

        ticket = buscar_ticket(ticket_id)

        if not ticket or ticket[4] == STATUS_FECHADO:

            respostas.pop(
                ADMIN_ID,
                None
            )

            bot.send_message(
                ADMIN_ID,
                "❌ Este ticket já foi fechado."
            )

            return

        usuario_id = ticket[1]

        registrar_mensagem(
            ticket_id,
            ADMIN_ID,
            "ADMIN",
            resposta
        )

        cursor.execute(
            """
            UPDATE tickets
            SET
                resposta=?,
                status=?,
                admin_id=?,
                data_resposta=?
            WHERE id=?
            """,
            (
                resposta,
                STATUS_RESPONDIDO,
                ADMIN_ID,
                data_atual(),
                ticket_id
            )
        )

        conn.commit()

        try:

            bot.send_message(
                usuario_id,
                f"""
📩 <b>SUPORTE — TICKET #{ticket_id}</b>

{resposta}

💬 Você pode responder novamente neste mesmo atendimento.
""",
                parse_mode="HTML"
            )

            bot.send_message(
                ADMIN_ID,
                f"""
✅ Resposta enviada para o ticket #{ticket_id}.

💬 O atendimento continua aberto.
Você pode escrever outra resposta.
""",
                parse_mode="HTML"
            )

        except Exception as erro:

            print(
                f"Erro ao enviar resposta: {erro}"
            )

    # =====================================================
    # ADMIN: HISTÓRICO
    # =====================================================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("ticket_hist_")
    )
    def historico_ticket(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        ticket_id = int(
            call.data.replace(
                "ticket_hist_",
                "",
                1
            )
        )

        ticket = buscar_ticket(ticket_id)

        if not ticket:

            bot.answer_callback_query(
                call.id,
                "Ticket não encontrado.",
                show_alert=True
            )

            return

        cursor.execute(
            """
            SELECT
                remetente,
                mensagem,
                data
            FROM ticket_mensagens
            WHERE ticket_id=?
            ORDER BY id
            """,
            (ticket_id,)
        )

        mensagens = cursor.fetchall()

        if not mensagens:

            texto = "📭 Nenhuma mensagem registrada."

        else:

            partes = []

            for remetente, mensagem, data in mensagens:

                if remetente == "ADMIN":
                    nome = "👨‍💼 SUPORTE"

                else:
                    nome = "👤 USUÁRIO"

                partes.append(
                    f"""
<b>{nome}</b>
📅 {data}

{mensagem}
"""
                )

            texto = "\n━━━━━━━━━━━━━━\n".join(
                partes
            )

        # Divide o histórico para evitar mensagens grandes demais.
        limite = 3500

        blocos = [
            texto[i:i + limite]
            for i in range(
                0,
                len(texto),
                limite
            )
        ]

        for bloco in blocos:

            bot.send_message(
                ADMIN_ID,
                f"""
📜 <b>HISTÓRICO — TICKET #{ticket_id}</b>

{bloco}
""",
                parse_mode="HTML"
            )

        bot.answer_callback_query(
            call.id,
            "Histórico enviado."
        )

    # =====================================================
    # ADMIN: FECHAR TICKET
    # =====================================================

    @bot.callback_query_handler(
        func=lambda c: (
            c.data.startswith("ticket_close_id_")
            or c.data.startswith("ticket_close_")
        )
    )
    def fechar_ticket(call):

        if call.from_user.id != ADMIN_ID:

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        if call.data.startswith("ticket_close_id_"):

            ticket_id = int(
                call.data.replace(
                    "ticket_close_id_",
                    "",
                    1
                )
            )

        else:

            usuario_id = int(
                call.data.split("_")[-1]
            )

            ticket = ticket_aberto(
                usuario_id
            )

            if not ticket:

                bot.answer_callback_query(
                    call.id,
                    "Ticket não encontrado.",
                    show_alert=True
                )

                return

            ticket_id = ticket[0]

        ticket = buscar_ticket(ticket_id)

        if not ticket:

            bot.answer_callback_query(
                call.id,
                "Ticket não encontrado.",
                show_alert=True
            )

            return

        if ticket[4] == STATUS_FECHADO:

            bot.answer_callback_query(
                call.id,
                "Ticket já está fechado.",
                show_alert=True
            )

            return

        cursor.execute(
            """
            UPDATE tickets
            SET
                status=?,
                admin_id=?,
                fechado_em=?
            WHERE id=?
            """,
            (
                STATUS_FECHADO,
                ADMIN_ID,
                data_atual(),
                ticket_id
            )
        )

        conn.commit()

        respostas.pop(
            ADMIN_ID,
            None
        )

        bot.answer_callback_query(
            call.id,
            "✅ Ticket fechado."
        )

        try:

            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )

        except Exception:
            pass

        try:

            bot.send_message(
                ticket[1],
                f"""
✅ <b>Ticket #{ticket_id} encerrado.</b>

Obrigado por entrar em contato com nosso suporte.

⭐ Gostaria de avaliar o atendimento?
""",
                parse_mode="HTML",
                reply_markup=teclado_avaliacao(
                    ticket_id
                )
            )

        except Exception:
            pass

    # =====================================================
    # AVALIAÇÃO
    # =====================================================

    def teclado_avaliacao(ticket_id):

        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton(
                "⭐",
                callback_data=f"ticket_rate_{ticket_id}_1"
            ),
            types.InlineKeyboardButton(
                "⭐⭐",
                callback_data=f"ticket_rate_{ticket_id}_2"
            ),
            types.InlineKeyboardButton(
                "⭐⭐⭐",
                callback_data=f"ticket_rate_{ticket_id}_3"
            )
        )

        markup.row(
            types.InlineKeyboardButton(
                "⭐⭐⭐⭐",
                callback_data=f"ticket_rate_{ticket_id}_4"
            ),
            types.InlineKeyboardButton(
                "⭐⭐⭐⭐⭐",
                callback_data=f"ticket_rate_{ticket_id}_5"
            )
        )

        return markup

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("ticket_rate_")
    )
    def avaliar_ticket(call):

        partes = call.data.split("_")

        ticket_id = int(
            partes[2]
        )

        nota = int(
            partes[3]
        )

        ticket = buscar_ticket(
            ticket_id
        )

        if not ticket:

            bot.answer_callback_query(
                call.id,
                "Ticket não encontrado.",
                show_alert=True
            )

            return

        if ticket[1] != call.from_user.id:

            bot.answer_callback_query(
                call.id,
                "Essa avaliação não pertence a você.",
                show_alert=True
            )

            return

        if ticket[4] != STATUS_FECHADO:

            bot.answer_callback_query(
                call.id,
                "O ticket ainda não foi encerrado.",
                show_alert=True
            )

            return

        cursor.execute(
            """
            UPDATE tickets
            SET avaliacao=?
            WHERE id=?
            """,
            (
                nota,
                ticket_id
            )
        )

        conn.commit()

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.answer_callback_query(
            call.id,
            "Obrigado pela avaliação! ⭐"
        )

        bot.send_message(
            call.from_user.id,
            f"""
⭐ <b>Obrigado!</b>

Sua avaliação do ticket #{ticket_id} foi registrada.

Se quiser, você pode enviar um comentário para ajudar nossa equipe a melhorar.
""",
            reply_markup=types.ForceReply(
                selective=True,
                input_field_placeholder="Digite seu comentário..."
            )
        )

        comentarios_avaliacao[call.from_user.id] = ticket_id

    # =====================================================
    # COMENTÁRIO DA AVALIAÇÃO
    # =====================================================

    @bot.message_handler(
        func=lambda m: m.from_user.id in comentarios_avaliacao
    )
    def receber_comentario_avaliacao(message):

        user_id = message.from_user.id
        ticket_id = comentarios_avaliacao.pop(
            user_id,
            None
        )

        if not ticket_id:
            return

        comentario = (message.text or "").strip()

        if not comentario:
            bot.send_message(
                user_id,
                "❌ Digite um comentário válido."
            )

            comentarios_avaliacao[user_id] = ticket_id
            return

        cursor.execute(
            """
            UPDATE tickets
            SET avaliacao_comentario=?
            WHERE id=?
            AND usuario_id=?
            """,
            (
                comentario,
                ticket_id,
                user_id
            )
        )

        conn.commit()

        bot.send_message(
            user_id,
            "✅ Obrigado pelo comentário!"
        )

        bot.send_message(
            ADMIN_ID,
            f"""
⭐ <b>NOVA AVALIAÇÃO</b>

🎫 Ticket #{ticket_id}

💬 Comentário:
{comentario}
""",
            parse_mode="HTML"
        )

    # =====================================================
    # PAINEL ADMINISTRATIVO DE TICKETS
    # =====================================================

    @bot.message_handler(
        commands=["tickets"]
    )
    def painel_tickets_comando(message):

        if message.from_user.id != ADMIN_ID:
            return

        enviar_painel_tickets()

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id == ADMIN_ID
            and m.text == "🎫 Tickets"
        )
    )
    def painel_tickets_botao(message):

        enviar_painel_tickets()

    def enviar_painel_tickets():

        cursor.execute(
            """
            SELECT
                COUNT(CASE WHEN status=? THEN 1 END),
                COUNT(CASE WHEN status=? THEN 1 END),
                COUNT(CASE WHEN status=? THEN 1 END),
                COUNT(*)
            FROM tickets
            """,
            (
                STATUS_ABERTO,
                STATUS_RESPONDIDO,
                STATUS_FECHADO
            )
        )

        stats = cursor.fetchone()

        aguardando = stats[0] or 0
        atendimento = stats[1] or 0
        fechados = stats[2] or 0
        total = stats[3] or 0

        markup = types.InlineKeyboardMarkup()

        # Atalho direto para responder o ticket ativo mais recente.
        cursor.execute(
            """
            SELECT id
            FROM tickets
            WHERE status IN (?, ?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (STATUS_ABERTO, STATUS_RESPONDIDO)
        )
        ultimo_ticket = cursor.fetchone()

        if ultimo_ticket:
            markup.add(
                types.InlineKeyboardButton(
                    "✉️ Responder ticket",
                    callback_data=f"ticket_resp_id_{ultimo_ticket[0]}"
                )
            )

        markup.add(
            types.InlineKeyboardButton(
                "🟡 Aguardando",
                callback_data="tickets_lista_abertos"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "🔵 Em atendimento",
                callback_data="tickets_lista_atendimento"
            )
        )

        markup.add(
            types.InlineKeyboardButton(
                "📜 Fechados",
                callback_data="tickets_lista_fechados"
            )
        )

        bot.send_message(
            ADMIN_ID,
            f"""
🎫 <b>PAINEL DE TICKETS</b>

━━━━━━━━━━━━━━━━━━━━

🟡 Aguardando: <b>{aguardando}</b>

🔵 Em atendimento: <b>{atendimento}</b>

🔴 Fechados: <b>{fechados}</b>

📊 Total: <b>{total}</b>

━━━━━━━━━━━━━━━━━━━━
""",
            parse_mode="HTML",
            reply_markup=markup
        )

    # =====================================================
    # LISTAS DO PAINEL
    # =====================================================

    @bot.callback_query_handler(
        func=lambda c: c.data.startswith("tickets_lista_")
    )
    def listar_tickets(call):

        if call.from_user.id != ADMIN_ID:
            return

        tipo = call.data.replace(
            "tickets_lista_",
            "",
            1
        )

        if tipo == "abertos":
            status = STATUS_ABERTO
            titulo = "🟡 AGUARDANDO"

        elif tipo == "atendimento":
            status = STATUS_RESPONDIDO
            titulo = "🔵 EM ATENDIMENTO"

        else:
            status = STATUS_FECHADO
            titulo = "🔴 FECHADOS"

        cursor.execute(
            """
            SELECT id, usuario_id, categoria, status, data
            FROM tickets
            WHERE status=?
            ORDER BY id DESC
            LIMIT 30
            """,
            (status,)
        )

        lista = cursor.fetchall()

        if not lista:

            bot.answer_callback_query(
                call.id,
                "Nenhum ticket encontrado.",
                show_alert=True
            )

            return

        bot.send_message(
            ADMIN_ID,
            f"🎫 <b>{titulo}</b>",
            parse_mode="HTML"
        )

        for ticket_id, usuario_id, categoria, status_atual, data in lista:

            markup = types.InlineKeyboardMarkup()

            if status_atual != STATUS_FECHADO:

                # Sempre mostrar Responder em qualquer ticket ativo.
                markup.row(
                    types.InlineKeyboardButton(
                        "✉️ Responder",
                        callback_data=f"ticket_resp_id_{ticket_id}"
                    ),
                    types.InlineKeyboardButton(
                        "👨‍💼 Assumir",
                        callback_data=f"ticket_assumir_{ticket_id}"
                    )
                )

                markup.row(
                    types.InlineKeyboardButton(
                        "📜 Histórico",
                        callback_data=f"ticket_hist_{ticket_id}"
                    ),
                    types.InlineKeyboardButton(
                        "❌ Fechar",
                        callback_data=f"ticket_close_id_{ticket_id}"
                    )
                )

            else:

                markup.add(
                    types.InlineKeyboardButton(
                        "📜 Histórico",
                        callback_data=f"ticket_hist_{ticket_id}"
                    )
                )

            bot.send_message(
                ADMIN_ID,
                f"""
🎫 <b>Ticket #{ticket_id}</b>

👤 Usuário:
<code>{usuario_id}</code>

📂 {CATEGORIAS.get(categoria, CATEGORIAS["outro"])}

📅 {data}

📊 {status_atual}
""",
                parse_mode="HTML",
                reply_markup=markup
            )

        bot.answer_callback_query(
            call.id
        )

    # =====================================================
    # ESTATÍSTICAS / AVALIAÇÃO MÉDIA
    # =====================================================

    @bot.message_handler(
        commands=["ticketstats"]
    )
    def estatisticas_tickets(message):

        if message.from_user.id != ADMIN_ID:
            return

        cursor.execute(
            """
            SELECT
                COUNT(*),
                AVG(avaliacao),
                COUNT(CASE WHEN avaliacao IS NOT NULL THEN 1 END)
            FROM tickets
            WHERE status=?
            """,
            (STATUS_FECHADO,)
        )

        total, media, avaliados = cursor.fetchone()

        media_texto = (
            f"{media:.1f}/5"
            if media is not None
            else "Ainda sem avaliações"
        )

        bot.send_message(
            ADMIN_ID,
            f"""
📊 <b>ESTATÍSTICAS DE SUPORTE</b>

🎫 Tickets fechados:
<b>{total or 0}</b>

⭐ Média das avaliações:
<b>{media_texto}</b>

📝 Tickets avaliados:
<b>{avaliados or 0}</b>
""",
            parse_mode="HTML"
        )
