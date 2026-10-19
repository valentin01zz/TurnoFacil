"""Email identity: one canonical form per mailbox, so aliases cannot open extra accounts."""

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def canonical_email(email):
    """Lowercase, drop any "+tag" and, for Gmail, ignore dots (they all reach the same mailbox).

    ana.perez+prueba@Gmail.com -> anaperez@gmail.com ; ana+x@empresa.com -> ana@empresa.com
    """
    local, _, domain = email.strip().lower().rpartition("@")
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local = local.replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"
