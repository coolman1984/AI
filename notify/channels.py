"""Sending a message: Telegram bot, e-mail (SMTP), WhatsApp (Meta Cloud API). Standard library only.
A failure raises NotifyError with a clear text; nothing is retried here (the next run tries again)."""
import html
import json
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

CHANNELS = {"inapp": "Only in NERP", "telegram": "Telegram", "email": "E-mail", "whatsapp": "WhatsApp (Meta Business)"}


class NotifyError(Exception):
    pass


def _post_json(url, payload, headers=None, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers=dict({"content-type": "application/json"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise NotifyError("%s answered %d: %s" % (urllib.parse.urlparse(url).netloc, e.code,
                                                  e.read().decode("utf-8", "replace")[:300]))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise NotifyError("No connection to %s (%s)" % (urllib.parse.urlparse(url).netloc, getattr(e, "reason", e)))


def to_html(text):
    """**bold** -> <b>, everything else escaped (Telegram HTML)"""
    out = []
    for i, part in enumerate(html.escape(text).split("**")):
        out.append(("<b>%s</b>" % part) if i % 2 else part)
    return "".join(out)


def plain(text):
    return text.replace("**", "")


def telegram(cfg, chat_id, title, text):
    token = cfg.get("telegram_token")
    if not token:
        raise NotifyError("Telegram bot token is not set (ZNOTIF - settings)")
    body = "<b>%s</b>\n\n%s" % (html.escape(title), to_html(text))
    r = _post_json("https://api.telegram.org/bot%s/sendMessage" % token,
                   {"chat_id": chat_id, "text": body[:4000], "parse_mode": "HTML", "disable_web_page_preview": True})
    if not r.get("ok", False):
        raise NotifyError("Telegram: %s" % r.get("description", r))


def telegram_chats(cfg):
    """the chats that wrote to the bot (to find the chat id: open the bot, press Start, then call this)"""
    token = cfg.get("telegram_token")
    if not token:
        raise NotifyError("Telegram bot token is not set")
    req = urllib.request.Request("https://api.telegram.org/bot%s/getUpdates" % token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError) as e:
        raise NotifyError("No connection to Telegram (%s)" % getattr(e, "reason", e))
    chats = {}
    for u in d.get("result", []):
        c = (u.get("message") or u.get("my_chat_member") or {}).get("chat") or {}
        if c.get("id"):
            chats[c["id"]] = " ".join(x for x in (c.get("first_name"), c.get("last_name"), c.get("title"),
                                                   ("@" + c["username"]) if c.get("username") else None) if x)
    return [{"chat_id": str(k), "name": v} for k, v in chats.items()]


def email(cfg, to, title, text):
    host = cfg.get("smtp_host")
    if not host:
        raise NotifyError("SMTP server is not set (ZNOTIF - settings)")
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = title, cfg.get("smtp_from") or cfg.get("smtp_user") or "nerp@localhost", to
    m.set_content(plain(text))
    try:
        with smtplib.SMTP(host, int(cfg.get("smtp_port") or 587), timeout=20) as s:
            if cfg.get("smtp_tls", "1") == "1":
                s.starttls()
            if cfg.get("smtp_user"):
                s.login(cfg["smtp_user"], cfg.get("smtp_password") or "")
            s.send_message(m)
    except (smtplib.SMTPException, OSError) as e:
        raise NotifyError("E-mail: %s" % e)


def whatsapp(cfg, phone, title, text):
    pid, token = cfg.get("wa_phone_id"), cfg.get("wa_token")
    if not (pid and token):
        raise NotifyError("WhatsApp Business phone number id / token are not set (ZNOTIF - settings)")
    to = "".join(ch for ch in phone if ch.isdigit())
    _post_json("https://graph.facebook.com/v21.0/%s/messages" % pid,
               {"messaging_product": "whatsapp", "to": to, "type": "text",
                "text": {"body": ("*%s*\n\n%s" % (title, text.replace("**", "*")))[:4000]}},
               {"authorization": "Bearer %s" % token})


def send(channel, cfg, address, title, text):
    if channel == "inapp":
        return
    fn = {"telegram": telegram, "email": email, "whatsapp": whatsapp}.get(channel)
    if not fn:
        raise NotifyError("Unknown channel %s" % channel)
    if not (address or "").strip():
        raise NotifyError("No address for %s" % CHANNELS[channel])
    fn(cfg, address.strip(), title, text)
