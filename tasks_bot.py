#!/usr/bin/env python3
# ============================================================
#   بوت إدارة المهام - شركة حوافل الجمال للصناعة
#   النسخة 2.0 - متوافق مع python-telegram-bot 22.x
# ============================================================

import os, json, logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

BOT_TOKEN = "8664520842:AAFcTknBX_gpaE_Jn2eJ5EbcpvHdsEwroh8"
DATA_FILE = "tasks_data.json"

TASK_TITLE, TASK_DESC, TASK_PRIORITY, TASK_ASSIGN, TASK_DEADLINE, COMMENT_TEXT = range(6)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== قاعدة البيانات ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": [], "users": {}, "admins": [], "next_id": 1}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_next_id():
    data = load_data()
    nid = data["next_id"]
    data["next_id"] += 1
    save_data(data)
    return nid

def is_admin(user_id):
    return str(user_id) in load_data().get("admins", [])

def priority_emoji(p):
    return {"عاجل": "🔴", "عادي": "🟡", "منخفض": "🟢"}.get(p, "⚪")

def status_emoji(s):
    return {"جديدة": "🆕", "قيد التنفيذ": "⚙️", "مكتملة": "✅", "ملغاة": "❌"}.get(s, "❓")

def fmt_date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%Y/%m/%d %H:%M")
    except:
        return iso

def task_card(task, show_comments=False):
    p = priority_emoji(task['priority'])
    s = status_emoji(task['status'])
    deadline = f"\n⏰ الموعد: {task.get('deadline','غير محدد')}" if task.get('deadline') else ""
    assigned = ", ".join([f"@{a}" for a in task.get('assigned_usernames', [])]) or "غير محدد"
    txt = (
        f"{p} *المهمة \#{task['id']}: {task['title']}*\n"
        f"{s} الحالة: *{task['status']}*\n"
        f"📋 {task['description']}\n"
        f"👥 المكلفون: {assigned}\n"
        f"📌 الأولوية: {task['priority']}{deadline}\n"
        f"📅 {fmt_date(task['created_at'])}\n"
        f"👤 المنشئ: @{task.get('creator_username','—')}"
    )
    if show_comments and task.get("comments"):
        txt += "\n\n💬 *التعليقات:*"
        for c in task["comments"]:
            txt += f"\n• @{c['username']} : {c['text']}"
    return txt

# ==================== /start ====================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    uid  = str(user.id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "name": user.full_name,
            "username": user.username or user.full_name,
            "id": user.id
        }
    if not data["admins"]:
        data["admins"].append(uid)
    save_data(data)
    badge = "👑 مدير" if is_admin(user.id) else "👤 موظف"
    await update.message.reply_text(
        f"🏢 *نظام مهام حوافل الجمال للصناعة*\n\n"
        f"مرحباً {user.first_name}\! {badge}\n\n"
        f"➕ /newtask — إنشاء مهمة\n"
        f"📋 /tasks — مهامي\n"
        f"📊 /alltasks — كل المهام \(مدير\)\n"
        f"📈 /report — تقرير \(مدير\)\n"
        f"👥 /users — المستخدمون\n"
        f"❓ /help — المساعدة",
        parse_mode="MarkdownV2"
    )

# ==================== إنشاء مهمة ====================
async def new_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("➕ *إنشاء مهمة جديدة*\n\nاكتب *عنوان المهمة:*", parse_mode="Markdown")
    return TASK_TITLE

async def task_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["title"] = update.message.text
    await update.message.reply_text("📝 اكتب *وصف المهمة* (أو أرسل - للتخطي):", parse_mode="Markdown")
    return TASK_DESC

async def task_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["desc"] = update.message.text if update.message.text != "-" else "—"
    kb = [[
        InlineKeyboardButton("🔴 عاجل",   callback_data="pri_عاجل"),
        InlineKeyboardButton("🟡 عادي",   callback_data="pri_عادي"),
        InlineKeyboardButton("🟢 منخفض", callback_data="pri_منخفض"),
    ]]
    await update.message.reply_text("📌 اختر *الأولوية:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    return TASK_PRIORITY

async def task_priority(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["priority"] = query.data.replace("pri_", "")
    data  = load_data()
    users = data["users"]
    if not users:
        await query.edit_message_text("⚠️ لا يوجد مستخدمون!")
        return ConversationHandler.END
    kb = []
    for uid, u in users.items():
        kb.append([InlineKeyboardButton(f"👤 {u['name']}", callback_data=f"assign_{uid}")])
    kb.append([InlineKeyboardButton("✅ تم الاختيار", callback_data="assign_done")])
    ctx.user_data["assigned"] = []
    await query.edit_message_text(
        "👥 اختر *المكلفين* (يمكن اختيار أكثر من شخص)\nثم اضغط ✅ تم الاختيار",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )
    return TASK_ASSIGN

async def task_assign(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "assign_done":
        if not ctx.user_data.get("assigned"):
            await query.answer("⚠️ اختر شخصاً على الأقل!", show_alert=True)
            return TASK_ASSIGN
        await query.edit_message_text("⏰ اكتب *الموعد النهائي* (مثال: 2025-05-01)\nأو أرسل - للتخطي:", parse_mode="Markdown")
        return TASK_DEADLINE
    uid      = query.data.replace("assign_", "")
    assigned = ctx.user_data.get("assigned", [])
    if uid in assigned: assigned.remove(uid)
    else: assigned.append(uid)
    ctx.user_data["assigned"] = assigned
    data  = load_data()
    kb    = []
    for u_id, u in data["users"].items():
        tick = "✅ " if u_id in assigned else ""
        kb.append([InlineKeyboardButton(f"{tick}👤 {u['name']}", callback_data=f"assign_{u_id}")])
    kb.append([InlineKeyboardButton("✅ تم الاختيار", callback_data="assign_done")])
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(kb))
    return TASK_ASSIGN

async def task_deadline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    deadline = update.message.text if update.message.text != "-" else None
    creator  = update.effective_user
    data     = load_data()
    assigned_ids       = ctx.user_data.get("assigned", [])
    assigned_usernames = [data["users"].get(uid, {}).get("username", uid) for uid in assigned_ids]
    task = {
        "id": get_next_id(),
        "title": ctx.user_data["title"],
        "description": ctx.user_data["desc"],
        "priority": ctx.user_data["priority"],
        "status": "جديدة",
        "assigned_ids": assigned_ids,
        "assigned_usernames": assigned_usernames,
        "creator_id": str(creator.id),
        "creator_username": creator.username or creator.full_name,
        "deadline": deadline,
        "created_at": datetime.now().isoformat(),
        "comments": []
    }
    data["tasks"].append(task)
    save_data(data)
    kb = [[
        InlineKeyboardButton("⚙️ بدء التنفيذ", callback_data=f"status_{task['id']}_قيد التنفيذ"),
        InlineKeyboardButton("✅ إنجاز",        callback_data=f"status_{task['id']}_مكتملة"),
    ],[
        InlineKeyboardButton("💬 تعليق",        callback_data=f"comment_{task['id']}"),
        InlineKeyboardButton("👁 تفاصيل",       callback_data=f"detail_{task['id']}"),
    ]]
    for uid in assigned_ids:
        try:
            await ctx.bot.send_message(
                chat_id=int(uid),
                text=f"🔔 *مهمة جديدة مُسندة إليك!*\n\n{task_card(task)}",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Cannot notify {uid}: {e}")
    await update.message.reply_text(
        f"✅ *تم إنشاء المهمة #{task['id']} بنجاح!*\n\n{task_card(task)}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ==================== مهامي ====================
async def my_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    data = load_data()
    my   = [t for t in data["tasks"] if uid in t.get("assigned_ids",[]) or t.get("creator_id")==uid]
    if not my:
        await update.message.reply_text("📭 لا يوجد مهام مرتبطة بك.")
        return
    await update.message.reply_text(f"📋 *مهامك ({len(my)} مهمة):*", parse_mode="Markdown")
    for task in my[-10:]:
        kb = [[
            InlineKeyboardButton("⚙️ قيد التنفيذ", callback_data=f"status_{task['id']}_قيد التنفيذ"),
            InlineKeyboardButton("✅ مكتملة",       callback_data=f"status_{task['id']}_مكتملة"),
        ],[
            InlineKeyboardButton("💬 تعليق",        callback_data=f"comment_{task['id']}"),
            InlineKeyboardButton("👁 تفاصيل",       callback_data=f"detail_{task['id']}"),
        ]]
        await update.message.reply_text(task_card(task), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ==================== كل المهام ====================
async def all_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ للمديرين فقط.")
        return
    data  = load_data()
    kb = [[
        InlineKeyboardButton("🆕 جديدة",       callback_data="filter_جديدة"),
        InlineKeyboardButton("⚙️ قيد التنفيذ", callback_data="filter_قيد التنفيذ"),
    ],[
        InlineKeyboardButton("✅ مكتملة",       callback_data="filter_مكتملة"),
        InlineKeyboardButton("📋 الكل",         callback_data="filter_all"),
    ]]
    await update.message.reply_text(
        f"📊 *إجمالي المهام: {len(data['tasks'])}*\nاختر تصفية:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def filter_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    filt  = query.data.replace("filter_", "")
    data  = load_data()
    tasks = data["tasks"] if filt == "all" else [t for t in data["tasks"] if t["status"] == filt]
    if not tasks:
        await query.edit_message_text("📭 لا يوجد مهام.")
        return
    await query.edit_message_text(f"📋 *{len(tasks)} مهمة:*", parse_mode="Markdown")
    for task in tasks[-10:]:
        kb = [[
            InlineKeyboardButton("⚙️ قيد التنفيذ", callback_data=f"status_{task['id']}_قيد التنفيذ"),
            InlineKeyboardButton("✅ مكتملة",       callback_data=f"status_{task['id']}_مكتملة"),
            InlineKeyboardButton("❌ إلغاء",        callback_data=f"status_{task['id']}_ملغاة"),
        ],[
            InlineKeyboardButton("💬 تعليق",        callback_data=f"comment_{task['id']}"),
            InlineKeyboardButton("👁 تفاصيل",       callback_data=f"detail_{task['id']}"),
        ]]
        await ctx.bot.send_message(
            chat_id=query.message.chat_id,
            text=task_card(task), reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
        )

# ==================== تغيير الحالة ====================
async def change_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts      = query.data.split("_", 2)
    task_id    = int(parts[1])
    new_status = parts[2]
    data  = load_data()
    task  = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        await query.answer("⚠️ المهمة غير موجودة!", show_alert=True)
        return
    old_status     = task["status"]
    task["status"] = new_status
    save_data(data)
    user = update.effective_user
    await query.edit_message_text(
        f"{task_card(task)}\n\n✅ {old_status} ← *{new_status}*", parse_mode="Markdown"
    )
    if task["creator_id"] != str(user.id):
        try:
            await ctx.bot.send_message(
                chat_id=int(task["creator_id"]),
                text=f"🔔 *تحديث مهمة #{task_id}*\n@{user.username or user.full_name} غيّر الحالة إلى: *{new_status}*\nالمهمة: {task['title']}",
                parse_mode="Markdown"
            )
        except: pass

# ==================== التعليقات ====================
async def add_comment_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["comment_task_id"] = int(query.data.replace("comment_", ""))
    await ctx.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"💬 اكتب تعليقك على المهمة #{ctx.user_data['comment_task_id']}:"
    )
    return COMMENT_TEXT

async def save_comment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    task_id = ctx.user_data.get("comment_task_id")
    user    = update.effective_user
    data    = load_data()
    task    = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        await update.message.reply_text("⚠️ المهمة غير موجودة!")
        return ConversationHandler.END
    task["comments"].append({
        "username": user.username or user.full_name,
        "text": update.message.text,
        "time": datetime.now().isoformat()
    })
    save_data(data)
    await update.message.reply_text(f"✅ تم إضافة تعليقك على المهمة #{task_id}")
    notified = set()
    for uid in task.get("assigned_ids", []) + [task["creator_id"]]:
        if uid != str(user.id) and uid not in notified:
            notified.add(uid)
            try:
                await ctx.bot.send_message(
                    chat_id=int(uid),
                    text=f"💬 تعليق جديد على المهمة #{task_id}\n@{user.username or user.full_name}: {update.message.text}"
                )
            except: pass
    return ConversationHandler.END

# ==================== التفاصيل ====================
async def task_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.replace("detail_", ""))
    data    = load_data()
    task    = next((t for t in data["tasks"] if t["id"] == task_id), None)
    if not task:
        await query.answer("⚠️ غير موجودة!", show_alert=True)
        return
    await query.edit_message_text(task_card(task, show_comments=True), parse_mode="Markdown")

# ==================== التقرير ====================
async def report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ للمديرين فقط.")
        return
    data  = load_data()
    tasks = data["tasks"]
    if not tasks:
        await update.message.reply_text("📭 لا يوجد مهام.")
        return
    new_t  = sum(1 for t in tasks if t["status"]=="جديدة")
    in_p   = sum(1 for t in tasks if t["status"]=="قيد التنفيذ")
    done   = sum(1 for t in tasks if t["status"]=="مكتملة")
    cancel = sum(1 for t in tasks if t["status"]=="ملغاة")
    urgent = sum(1 for t in tasks if t["priority"]=="عاجل")
    perf   = {}
    for t in tasks:
        for uid in t.get("assigned_ids", []):
            name = data["users"].get(uid, {}).get("name", uid)
            if name not in perf: perf[name] = {"total":0,"done":0}
            perf[name]["total"] += 1
            if t["status"] == "مكتملة": perf[name]["done"] += 1
    perf_txt = ""
    for name, p in perf.items():
        pct = int(p["done"]/p["total"]*100) if p["total"] else 0
        bar = "█"*(pct//10) + "░"*(10-pct//10)
        perf_txt += f"\n👤 {name}: {p['done']}/{p['total']} [{bar}] {pct}%"
    await update.message.reply_text(
        f"📈 *تقرير المهام*\n━━━━━━━━━━━━\n"
        f"📊 الإجمالي: *{len(tasks)}*\n"
        f"🆕 جديدة: *{new_t}*\n⚙️ قيد التنفيذ: *{in_p}*\n"
        f"✅ مكتملة: *{done}*\n❌ ملغاة: *{cancel}*\n🔴 عاجلة: *{urgent}*\n"
        f"━━━━━━━━━━━━\n👥 *أداء الفريق:*{perf_txt}",
        parse_mode="Markdown"
    )

# ==================== المستخدمون ====================
async def users_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data  = load_data()
    users = data["users"]
    if not users:
        await update.message.reply_text("👥 لا يوجد مستخدمون.\nاطلب من الفريق إرسال /start للبوت @Attar2035_bot")
        return
    txt = "👥 *المستخدمون المسجلون:*\n"
    for uid, u in users.items():
        badge = "👑" if uid in data.get("admins",[]) else "👤"
        txt  += f"\n{badge} {u['name']} (@{u.get('username','—')})"
    txt += f"\n\n💡 رابط التسجيل: @Attar2035_bot"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *المساعدة*\n\n"
        "➕ /newtask — إنشاء مهمة\n📋 /tasks — مهامي\n"
        "📊 /alltasks — كل المهام\n📈 /report — تقرير\n👥 /users — المستخدمون",
        parse_mode="Markdown"
    )

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

# ==================== التشغيل ====================
def main():
    app = Application.builder().token(BOT_TOKEN).updater(None).build()
    task_conv = ConversationHandler(
        entry_points=[CommandHandler("newtask", new_task)],
        states={
            TASK_TITLE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, task_title)],
            TASK_DESC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, task_desc)],
            TASK_PRIORITY: [CallbackQueryHandler(task_priority, pattern="^pri_")],
            TASK_ASSIGN:   [CallbackQueryHandler(task_assign,   pattern="^assign_")],
            TASK_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, task_deadline)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    comment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_comment_start, pattern="^comment_")],
        states={COMMENT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_comment)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("tasks",    my_tasks))
    app.add_handler(CommandHandler("alltasks", all_tasks))
    app.add_handler(CommandHandler("report",   report))
    app.add_handler(CommandHandler("users",    users_list))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(task_conv)
    app.add_handler(comment_conv)
    app.add_handler(CallbackQueryHandler(change_status, pattern="^status_"))
    app.add_handler(CallbackQueryHandler(filter_tasks,  pattern="^filter_"))
    app.add_handler(CallbackQueryHandler(task_detail,   pattern="^detail_"))
    print("🤖 بوت المهام يعمل... اضغط Ctrl+C للإيقاف")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
