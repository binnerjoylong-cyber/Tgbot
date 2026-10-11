import os
import re
import json
import asyncio
import subprocess
import requests
import shutil
import static_ffmpeg

try:
    static_ffmpeg.add_paths()
except Exception as e:
    print("Static FFmpeg setup warning:", e)

FFMPEG_PATH = shutil.which("ffmpeg")

from threading import Thread
from urllib.parse import quote
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    BotCommand
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

import yt_dlp

# ============================================================
# FLASK WEB SERVER
# ============================================================

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 6753546651))
FORCE_CHANNEL = "@mame_posts"
FORCE_CHANNEL_LINK = "https://t.me/mame_posts"

# ============================================================
# DATABASE MANAGEMENT
# ============================================================

DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save Error:", e)

def record_user_activity(user_id):
    data = load_data()
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"msg_count": 0, "started": True, "lang": None}
    data[uid_str]["msg_count"] = data[uid_str].get("msg_count", 0) + 1
    data[uid_str]["started"] = True
    save_data(data)

def set_user_language(user_id, lang_code):
    data = load_data()
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"msg_count": 1, "started": True, "lang": lang_code}
    else:
        data[uid_str]["lang"] = lang_code
    save_data(data)

def get_user_language(user_id):
    data = load_data()
    return data.get(str(user_id), {}).get("lang", None)

def get_user_stats(user_id):
    data = load_data()
    uid_str = str(user_id)
    total_users = len(data)
    user_msg_count = data.get(uid_str, {}).get("msg_count", 0)
    return total_users, user_msg_count

# ============================================================
# TRANSLATIONS
# ============================================================

TRANSLATIONS = {
    "am": {
        "btn_add": "ቦቱን ወደ ቻትዎ ለመጨመር",
        "btn_order": "ማስታወቂያ ለማሰራት",
        "btn_price": "Price | ዋጋ",
        "btn_payment": "Payment Method",
        "btn_status": "My Status & Stats",
        "btn_lang": "Language | ቋንቋ",
        "btn_support": "Support | ድጋፍ",
        "btn_back": "Back to Menu",
        "done_msg": "✅ <b>ተጠናቋል! ቋንቋዎ ተስተካክሏል።</b>",
        "loading": '⏳ <b>Loading|ይጠብቁ...</b>',
        "video_converted": '🎵 <b>Extracted Audio</b>\n\n✅ <b>Converted with</b> @{bot_username} & @mame_posts',
        "size_limit": "⚠️ <b>ቪዲዮው ከ 50MB በላይ ስለሆነ በቴሌግራም መላክ አይቻልም!</b>",
        "fail_download": "💔 <b>የፈለጉትን File ማግኘት አልቻልኩም! እባክዎ እንደገና ይሞክሩ።</b>",
        "photo_download": '📸 <b>Downloaded Thumbnail/Photo</b>\n\n✅ <b>Downloaded with</b> @{bot_username}',
        "welcome": 'Hello 🚨\n\n<b>ከሁሉም Social Media ቪዲዮ ማውረድ ይችላሉ!</b>',
        "price": '💰 12 Hours: በስምምነት | 24 Hours: 500 ETB',
        "order": '📢 @mame_posts ላይ ማስታወቂያ ለማሰራት ፖስት ይላኩ።',
        "payment": '💳 CBE: <code>1000528274394</code> | Telebirr: <code>+251963266849</code>',
        "support": '💬 እርዳታ ከፈለጉ መልእክት ይላኩ።'
    },
    "en": {
        "btn_add": "Add bot to group",
        "btn_order": "Advertise",
        "btn_price": "Rates",
        "btn_payment": "Payment Method",
        "btn_status": "My Status",
        "btn_lang": "Language",
        "btn_support": "Help & Support",
        "btn_back": "Back to Menu",
        "done_msg": "✅ <b>Done! Language updated.</b>",
        "loading": '⏳ <b>Loading, please wait...</b>',
        "video_converted": '🎵 <b>Extracted Audio</b>\n\n✅ <b>Converted with</b> @{bot_username}',
        "size_limit": "⚠️ <b>File exceeds Telegram 50MB limit!</b>",
        "fail_download": "💔 <b>Could not download the file! Please verify the link.</b>",
        "photo_download": '📸 <b>Thumbnail Downloaded</b>\n\n✅ @{bot_username}',
        "welcome": 'Hello 🚨\n\n<b>Send any social media link to download videos, audio & photos!</b>',
        "price": '💰 24 Hours: 500 ETB | 48 Hours: 700 ETB',
        "order": '📢 Send your promo post to advertise on @mame_posts.',
        "payment": '💳 CBE: <code>1000528274394</code> | Telebirr: <code>+251963266849</code>',
        "support": '💬 Send your links directly here.'
    },
    "ar": {
        "btn_add": "إضافة للمجموعة",
        "btn_order": "طلب إعلان",
        "btn_price": "الأسعار",
        "btn_payment": "طرق الدفع",
        "btn_status": "إحصائياتي",
        "btn_lang": "اللغة",
        "btn_support": "الدعم",
        "btn_back": "العودة",
        "done_msg": "✅ <b>تم ضبط اللغة بنجاح.</b>",
        "loading": '⏳ <b>جاري التحميل...</b>',
        "video_converted": '🎵 <b>الصوت المستخرج</b>\n\n✅ @{bot_username}',
        "size_limit": "⚠️ <b>حجم الملف أكبر من 50MB!</b>",
        "fail_download": "💔 <b>تعذر تحميل الرابط!</b>",
        "photo_download": '📸 <b>الصورة المصغرة</b>',
        "welcome": 'مرحباً! أرسل أي رابط لتحميل الفيديو والموسيقى مباشرة.',
        "price": '💰 24 ساعة: 500 ETB',
        "order": '📢 للإعلان على @mame_posts',
        "payment": '💳 CBE: <code>1000528274394</code>',
        "support": '💬 أرسل الرابط للتحميل.'
    }
}

def get_trans(user_id, key):
    lang = get_user_language(user_id)
    if not lang or lang not in TRANSLATIONS:
        lang = "am"
    return TRANSLATIONS.get(lang, TRANSLATIONS["am"]).get(key, "")

def get_bot_username(context):
    return context.bot.username or "mame_posts_bot"

def get_main_menu_keyboard(bot_username, user_id):
    keyboard = [
        [InlineKeyboardButton(get_trans(user_id, "btn_add"), url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton(get_trans(user_id, "btn_order"), callback_data="cmd_order")],
        [
            InlineKeyboardButton(get_trans(user_id, "btn_price"), callback_data="cmd_price"),
            InlineKeyboardButton(get_trans(user_id, "btn_payment"), callback_data="cmd_payment")
        ],
        [
            InlineKeyboardButton(get_trans(user_id, "btn_status"), callback_data="cmd_status"),
            InlineKeyboardButton(get_trans(user_id, "btn_lang"), callback_data="cmd_change_lang")
        ],
        [InlineKeyboardButton(get_trans(user_id, "btn_support"), callback_data="cmd_support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_language_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇪🇹 አማርኛ", callback_data="lang_am"), InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")]
    ])

def get_back_keyboard(user_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton(get_trans(user_id, "btn_back"), callback_data="cmd_back")]])

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("menu", "Main menu"),
        BotCommand("status", "Check status"),
        BotCommand("rate", "Advertising rates"),
        BotCommand("payment", "Payment methods"),
        BotCommand("help", "Help and support")
    ])

async def is_joined(update, context):
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL, user_id=update.effective_user.id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return True

async def show_force_join(update, context):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_join")]
    ]
    await update.message.reply_text("🔒 <b>Please join our channel first!</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# ============================================================
# COMMAND HANDLERS
# ============================================================

async def start(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)

    if not get_user_language(user_id):
        await update.message.reply_text("<b>Please select your language / ቋንቋ ይምረጡ:</b>", reply_markup=get_language_keyboard(), parse_mode="HTML")
        return

    await update.message.reply_text("🏠", reply_markup=ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True))
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=get_trans(user_id, "welcome"),
        reply_markup=get_main_menu_keyboard(get_bot_username(context), user_id),
        parse_mode="HTML"
    )

async def rates_command(update, context):
    if update.message:
        await update.message.reply_text(get_trans(update.effective_user.id, "price"), parse_mode="HTML")

async def payment_command(update, context):
    if update.message:
        await update.message.reply_text(get_trans(update.effective_user.id, "payment"), parse_mode="HTML")

async def help_command(update, context):
    if update.message:
        await update.message.reply_text(get_trans(update.effective_user.id, "support"), parse_mode="HTML")

async def status_command(update, context):
    if not update.message:
        return
    user = update.effective_user
    total_users, user_msg_count = get_user_stats(user.id)
    msg = f"👤 <b>Username:</b> @{user.username or 'None'}\n🆔 <b>ID:</b> <code>{user.id}</code>\n💬 <b>Messages:</b> {user_msg_count}\n👥 <b>Total Users:</b> {total_users}"
    await update.message.reply_text(msg, parse_mode="HTML")

async def broadcast_command(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    data = load_data()
    count = 0
    reply = update.message.reply_to_message
    for uid in data.keys():
        try:
            if reply:
                await reply.copy(chat_id=int(uid))
            else:
                await context.bot.send_message(chat_id=int(uid), text=" ".join(context.args))
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

# ============================================================
# ROBUST DOWNLOAD ENGINE
# ============================================================

def clean_target_url(raw_url: str) -> str:
    url = re.sub(r'(\?|&)si=[^&]+', '', raw_url)
    url = re.sub(r'(\?|&)feature=[^&]+', '', url)
    shorts = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', url)
    if shorts:
        return f"https://www.youtube.com/watch?v={shorts.group(1)}"
    return url

def download_via_cobalt(url: str, output_path: str) -> bool:
    """Alternative API that completely bypasses YouTube Datacenter bot-check."""
    try:
        api_endpoints = [
            "https://api.cobalt.tools/api/json",
            "https://cobalt-api.kwiatekm.tokyo/api/json"
        ]
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0"
        }
        payload = {
            "url": url,
            "vQuality": "720",
            "filenamePattern": "basic"
        }

        for ep in api_endpoints:
            try:
                res = requests.post(ep, json=payload, headers=headers, timeout=15)
                data = res.json()
                video_url = data.get("url")
                if video_url:
                    r = requests.get(video_url, stream=True, timeout=60)
                    if r.status_code == 200:
                        with open(output_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                            return True
            except Exception:
                continue
    except Exception as e:
        print("Cobalt fallback failed:", e)
    return False

def download_via_ytdlp(url: str, output_template: str):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'outtmpl': output_template,
        'writethumbnail': True,
        'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
        'merge_output_format': 'mp4'
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

async def handle_url_download(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_url: str):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_username = get_bot_username(context)

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    status_msg = await update.message.reply_text(get_trans(user_id, "loading"), parse_mode="HTML")

    clean_url = clean_target_url(raw_url)
    prefix = f"media_{user_id}_{update.message.message_id}"
    video_out = f"{prefix}.mp4"
    audio_out = f"audio_{user_id}_{update.message.message_id}.mp3"
    thumb_out = f"{prefix}.jpg"

    downloaded = False

    # 1. YouTube specific: Try Cobalt API first to avoid 152-18 Bot Detection
    if any(d in clean_url.lower() for d in ["youtube.com", "youtu.be"]):
        downloaded = await asyncio.to_thread(download_via_cobalt, clean_url, video_out)

    # 2. If not YouTube or Cobalt failed, fallback to yt-dlp
    if not downloaded:
        try:
            await asyncio.to_thread(download_via_ytdlp, clean_url, f"{prefix}.%(ext)s")
            for f in os.listdir('.'):
                if f.startswith(prefix) and not f.endswith(('.part', '.temp')):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ['.mp4', '.mkv', '.webm']:
                        video_out = f
                        downloaded = True
                    elif ext in ['.jpg', '.jpeg', '.webp']:
                        thumb_out = f
        except Exception as e:
            print("yt-dlp general error:", e)

    # Check and Send Output
    sent_any = False
    ffmpeg_bin = FFMPEG_PATH or "ffmpeg"

    if os.path.exists(video_out) and os.path.getsize(video_out) > 0:
        # Generate thumbnail from video if not already present
        if not os.path.exists(thumb_out):
            thumb_gen = f"{prefix}_thumb.jpg"
            subprocess.run([ffmpeg_bin, "-y", "-ss", "00:00:01", "-i", video_out, "-vframes", "1", thumb_gen], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(thumb_gen):
                thumb_out = thumb_gen

        # Send Thumbnail
        if os.path.exists(thumb_out):
            try:
                with open(thumb_out, "rb") as tf:
                    await update.message.reply_photo(photo=tf, caption=get_trans(user_id, "photo_download").format(bot_username=bot_username), parse_mode="HTML")
            except Exception:
                pass

        # Send Video
        if os.path.getsize(video_out) <= 50 * 1024 * 1024:
            try:
                with open(video_out, "rb") as vf:
                    await update.message.reply_video(
                        video=vf,
                        caption=f"🚀 <b>Downloaded with</b> @{bot_username} & @mame_posts\n\n✅ <b>Enjoy!</b>",
                        parse_mode="HTML",
                        supports_streaming=True
                    )
                sent_any = True
            except Exception:
                with open(video_out, "rb") as vf:
                    await update.message.reply_document(document=vf, caption=f"🚀 @{bot_username}", parse_mode="HTML")
                sent_any = True

            # Extract and Send Audio
            subprocess.run([ffmpeg_bin, "-y", "-i", video_out, "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(audio_out) and os.path.getsize(audio_out) > 0:
                with open(audio_out, "rb") as af:
                    await update.message.reply_audio(audio=af, caption=f"🎧 <b>Extracted Audio</b>\n\n✅ @{bot_username}", parse_mode="HTML")
        else:
            await status_msg.edit_text(get_trans(user_id, "size_limit"), parse_mode="HTML")
            return

    # Clean Up Files
    for f in os.listdir('.'):
        if f.startswith(prefix) or f.startswith(f"audio_{user_id}_{update.message.message_id}"):
            try:
                os.remove(f)
            except Exception:
                pass

    if sent_any:
        try:
            await status_msg.delete()
        except Exception:
            pass
    else:
        try:
            await status_msg.edit_text(get_trans(user_id, "fail_download"), parse_mode="HTML")
        except Exception:
            pass

# ============================================================
# CALLBACKS & MESSAGES
# ============================================================

async def button_callback(update, context):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    bot_username = get_bot_username(context)

    if data.startswith("lang_"):
        set_user_language(user_id, data.split("_", 1)[1])
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(user_id, "done_msg"),
            reply_markup=ReplyKeyboardMarkup([["🏠 Menu"]], resize_keyboard=True),
            parse_mode="HTML"
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=get_trans(user_id, "welcome"),
            reply_markup=get_main_menu_keyboard(bot_username, user_id),
            parse_mode="HTML"
        )
        return

    if data == "cmd_change_lang":
        await query.answer()
        await query.edit_message_text("<b>Select language:</b>", reply_markup=get_language_keyboard(), parse_mode="HTML")
        return

    if data == "cmd_back":
        await query.answer()
        await query.edit_message_text(get_trans(user_id, "welcome"), reply_markup=get_main_menu_keyboard(bot_username, user_id), parse_mode="HTML")
        return

    for k in ["price", "order", "payment", "support"]:
        if data == f"cmd_{k}":
            await query.answer()
            await query.edit_message_text(get_trans(user_id, k), reply_markup=get_back_keyboard(user_id), parse_mode="HTML")
            return

    if data == "cmd_status":
        await query.answer()
        total, count = get_user_stats(user_id)
        msg = f"👤 @{query.from_user.username or 'None'}\n🆔 <code>{user_id}</code>\n💬 Messages: {count}\n👥 Users: {total}"
        await query.edit_message_text(msg, reply_markup=get_back_keyboard(user_id), parse_mode="HTML")
        return

async def check_join(update, context):
    query = update.callback_query
    if await is_joined(update, context):
        await query.answer()
        await query.edit_message_text("✅ <b>Joined! Resend your link.</b>", parse_mode="HTML")
    else:
        await query.answer("❌ Join the channel first!", show_alert=True)

SUPPORTED = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "twitter.com", "x.com", "facebook.com", "reddit.com", "pinterest.com", "pin.it"]

async def handle_user_messages(update, context):
    if not update.message:
        return
    user_id = update.effective_user.id
    record_user_activity(user_id)

    text = update.message.text or update.message.caption or ""
    if text.strip() == "🏠 Menu":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_trans(user_id, "welcome"),
            reply_markup=get_main_menu_keyboard(get_bot_username(context), user_id),
            parse_mode="HTML"
        )
        return

    if any(d in text.lower() for d in SUPPORTED):
        if not await is_joined(update, context):
            await show_force_join(update, context)
            return
        m = re.search(r"https?://[^\s]+", text)
        target = m.group(0).rstrip(".,!?)]}") if m else text.strip()
        await handle_url_download(update, context, target)
        return

    # Forward other messages to Admin
    try:
        header = f"📩 <b>New User Message</b>\n👤 Name: {update.effective_user.full_name}\n🆔 ID: <code>{user_id}</code>"
        h_msg = await context.bot.send_message(chat_id=ADMIN_ID, text=header, parse_mode="HTML")
        f_msg = await update.message.forward(chat_id=ADMIN_ID)
        if "user_mapping" not in context.bot_data:
            context.bot_data["user_mapping"] = {}
        context.bot_data["user_mapping"][str(h_msg.message_id)] = user_id
        context.bot_data["user_mapping"][str(f_msg.message_id)] = user_id
        await update.message.reply_text("✅ መልዕክትዎ ተቀብለናል።")
    except Exception:
        pass

async def admin_reply(update, context):
    if not update.message or update.effective_user.id != ADMIN_ID:
        return
    r_msg = update.message.reply_to_message
    if not r_msg:
        return
    mapping = context.bot_data.get("user_mapping", {})
    uid = mapping.get(str(r_msg.message_id))
    if uid:
        try:
            await update.message.copy(chat_id=uid)
            await update.message.reply_text("✅ Sent.")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    # Ignore polling conflict in console to prevent spamming
    if "Conflict: terminated by other getUpdates request" not in str(context.error):
        print("❌ ERROR:", context.error)

# ============================================================
# MAIN
# ============================================================

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing!")

    keep_alive()

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rates", rates_command))
    application.add_handler(CommandHandler("rate", rates_command))
    application.add_handler(CommandHandler("payment", payment_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))

    application.add_handler(CallbackQueryHandler(check_join, pattern=r"^check_join$"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern=r"^(cmd_|lang_)"))

    admin_filter = filters.User(user_id=ADMIN_ID) & filters.REPLY & ~filters.COMMAND
    application.add_handler(MessageHandler(admin_filter, admin_reply))

    type_filter = (filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VOICE | filters.AUDIO | filters.Sticker.ALL) & ~filters.COMMAND
    application.add_handler(MessageHandler(type_filter, handle_user_messages))

    application.add_error_handler(error_handler)

    print("🤖 Mame Posts Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
