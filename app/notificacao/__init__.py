"""Notificação ao aluno — envio de e-mail (`T-180`).

Separado de `app/http/` de propósito: notificar não é servir requisição, e
nenhuma rota deveria importar `smtplib` diretamente. O contrato é
`EnviadorDeEmail`; o adaptador concreto é decisão de quem monta a
aplicação.
"""
