from database import cursor, conn
from utils import data_atual, registrar_historico


def abrir_ticket(usuario_id, assunto, mensagem):

    cursor.execute(
        """
        INSERT INTO tickets
        (
            usuario_id,
            assunto,
            mensagem,
            resposta,
            status,
            admin_id,
            data,
            data_resposta
        )
        VALUES (?, ?, ?, '', 'ABERTO', NULL, ?, NULL)
        """,
        (
            usuario_id,
            assunto,
            mensagem,
            data_atual()
        )
    )

    conn.commit()

    registrar_historico(
        usuario_id,
        "TICKET",
        f"Ticket aberto: {assunto}"
    )

    return cursor.lastrowid


# ==========================================
# BUSCAR TICKET
# ==========================================

def buscar_ticket(ticket_id):

    cursor.execute(
        """
        SELECT *
        FROM tickets
        WHERE id=?
        """,
        (ticket_id,)
    )

    return cursor.fetchone()


# ==========================================
# LISTAR TICKETS ABERTOS
# ==========================================

def listar_tickets():

    cursor.execute(
        """
        SELECT *
        FROM tickets
        WHERE status='ABERTO'
        ORDER BY id
        """
    )

    return cursor.fetchall()


# ==========================================
# RESPONDER TICKET
# ==========================================

def responder_ticket(ticket_id, admin_id, resposta):

    cursor.execute(
        """
        UPDATE tickets
        SET

        resposta=?,

        status='RESPONDIDO',

        admin_id=?,

        data_resposta=?

        WHERE id=?
        """,
        (
            resposta,
            admin_id,
            data_atual(),
            ticket_id
        )
    )

    conn.commit()


# ==========================================
# FECHAR TICKET
# ==========================================

def fechar_ticket(ticket_id):

    cursor.execute(
        """
        UPDATE tickets
        SET status='FECHADO'
        WHERE id=?
        """,
        (ticket_id,)
    )

    conn.commit()
