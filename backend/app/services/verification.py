import hashlib
import io
import random
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.header import Header
from email.mime.text import MIMEText

import jwt
from PIL import Image, ImageDraw, ImageFont

from app.config import settings

CAPTCHA_CHARS = "abcdefghjkmnpqrstuvwxyz23456789"
CAPTCHA_TTL_MINUTES = 5
EMAIL_CODE_TTL_MINUTES = 10

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "arialbd.ttf",
]

_font_cache = {}


def _load_font(size):
    if size in _font_cache:
        return _font_cache[size]
    for path in FONT_CANDIDATES:
        try:
            font = ImageFont.truetype(path, size)
            _font_cache[size] = font
            return font
        except OSError:
            continue
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_captcha_code(length: int = 4) -> str:
    return "".join(secrets.choice(CAPTCHA_CHARS) for _ in range(length))


def render_captcha_image(code: str) -> bytes:
    w, h = 140, 46
    img = Image.new("RGB", (w, h), (242, 245, 251))
    draw = ImageDraw.Draw(img)
    for _ in range(6):
        draw.line(
            [(random.randint(0, w), random.randint(0, h)), (random.randint(0, w), random.randint(0, h))],
            fill=(188, 199, 216), width=1,
        )
    for i, ch in enumerate(code):
        font = _load_font(random.randint(26, 30))
        color = (random.randint(20, 90), random.randint(50, 120), random.randint(140, 200))
        x = 14 + i * 30 + random.randint(-3, 3)
        y = random.randint(4, 10)
        char_img = Image.new("RGBA", (36, 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(char_img)
        d.text((4, 2), ch, font=font, fill=color)
        char_img = char_img.rotate(random.randint(-22, 22), expand=True, resample=Image.BICUBIC)
        img.paste(char_img, (x, y), char_img)
    for _ in range(80):
        draw.point((random.randint(0, w - 1), random.randint(0, h - 1)), fill=(120, 135, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.lower().encode()).hexdigest()


def issue_captcha() -> tuple[str, bytes]:
    """返回 (captcha_token, png)。token 是包含验证码哈希、5 分钟有效的 JWT。"""
    code = generate_captcha_code()
    payload = {
        "code_hash": _hash_code(code),
        "type": "captcha",
        "exp": utcnow() + timedelta(minutes=CAPTCHA_TTL_MINUTES),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, render_captcha_image(code)


def verify_captcha(captcha_token: str, answer: str) -> bool:
    try:
        payload = jwt.decode(captcha_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "captcha":
            return False
        return secrets.compare_digest(payload["code_hash"], _hash_code(answer.strip()))
    except jwt.InvalidTokenError:
        return False


def issue_email_code(email: str, code: str) -> str:
    payload = {
        "email": email.lower(),
        "code_hash": _hash_code(code),
        "type": "email_code",
        "exp": utcnow() + timedelta(minutes=EMAIL_CODE_TTL_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_email_code(email_token: str, email: str, code: str) -> bool:
    try:
        payload = jwt.decode(email_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "email_code":
            return False
        if payload.get("email") != email.strip().lower():
            return False
        return secrets.compare_digest(payload["code_hash"], _hash_code(code.strip()))
    except jwt.InvalidTokenError:
        return False


def new_email_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def send_email(to: str, subject: str, body: str):
    if not settings.smtp_host or not settings.smtp_user:
        raise RuntimeError("SMTP 未配置，请联系管理员配置邮件服务")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context) as server:
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg["From"], [to], msg.as_string())


def send_verification_email(to: str, code: str):
    send_email(
        to,
        "Official Domain Registry 邮箱验证码",
        f"你的邮箱验证码是：{code}\n\n验证码 10 分钟内有效，请勿泄露给他人。\n"
        "如果不是你本人操作，请忽略本邮件。\n\nOfficial Domain Registry",
    )
