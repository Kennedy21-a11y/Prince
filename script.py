import os
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters

# === Variables Globales ===
clients = {}       # {user_id: [list des clients]}
progression = {}   # {user_id: {nom_client: nb_cases_cochees}}

CHOOSING, COCHAGE, RECHARGING, DELETING = range(4)

# === Charger police compatible emoji ===
def load_font(size):
    fonts = ["seguiemj.ttf", "seguiemj", "Segoe UI Emoji", "arial.ttf"]
    for f in fonts:
        try:
            return ImageFont.truetype(f, size)
        except:
            continue
    return ImageFont.load_default()

# === Trouver centres automatiquement via masque ===
def trouver_centres(mask_path):
    path = os.path.join("assets", mask_path)  # Images dans dossier assets/
    mask = Image.open(path).convert("L")
    arr = np.array(mask)

    thresh = 200
    white_pixels = np.argwhere(arr > thresh)
    if white_pixels.size == 0:
        return []

    from scipy.ndimage import label, center_of_mass
    binary = (arr > thresh).astype(int)
    labels, nb = label(binary)
    centres = center_of_mass(binary, labels, range(1, nb + 1))
    centres_xy = [(int(c[1]), int(c[0])) for c in centres]

    return centres_xy

# === Génération Carte ===
def generer_carte(nom_client: str, cases_cochees: int = 0) -> BytesIO:
    fond = Image.open(os.path.join("assets", "re.png")).convert("RGBA")
    draw = ImageDraw.Draw(fond)
    font_titre = load_font(40)
    font_normal = load_font(60)

    pos_texte = trouver_centres("texte.png")
    if pos_texte:
        x_t, y_t = pos_texte[0]
        draw.text((x_t, y_t), f"Carte fidélité - {nom_client}", font=font_titre, fill="white", anchor="mm")
    else:
        draw.text((40, 40), f"Carte fidélité - {nom_client}", font=font_titre, fill="white")

    positions = trouver_centres("ir.png")
    positions = sorted(positions, key=lambda p: (p[1], p[0]))

    for idx, (x, y) in enumerate(positions):
        if idx < cases_cochees:
            draw.text((x, y), "✓", font=font_normal, fill="green", anchor="mm")

    image_io = BytesIO()
    fond.save(image_io, format="PNG")
    image_io.seek(0)
    return image_io

# === Commandes Bot ===
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id in clients and clients[user_id]:
        keyboard = [
            [InlineKeyboardButton("➕ Enregistrer un client", callback_data="nouveau")],
            [InlineKeyboardButton("🎟️ Retirer une carte", callback_data="recharge")],
            [InlineKeyboardButton("🗑️ Supprimer un client", callback_data="delete")]
        ]
    else:
        keyboard = [[InlineKeyboardButton("➕ Enregistrer un client", callback_data="nouveau")]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Bienvenue sur *Ryan Recharge Express* ⚡\nQue souhaitez-vous faire ?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if query.data == "nouveau":
        query.message.reply_text("Entrez le nom du nouveau client :")
        return CHOOSING

    elif query.data == "recharge":
        if user_id not in clients or not clients[user_id]:
            query.message.reply_text("Aucun client enregistré.")
            return ConversationHandler.END

        noms = clients[user_id]
        keyboard = [[InlineKeyboardButton(nom, callback_data=f"carte_{nom}")] for nom in noms]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Choisissez un client :", reply_markup=reply_markup)
        return RECHARGING

    elif query.data == "delete":
        if user_id not in clients or not clients[user_id]:
            query.message.reply_text("⚠️ Aucun client à supprimer.")
            return ConversationHandler.END

        noms = clients[user_id]
        keyboard = [[InlineKeyboardButton(f"❌ {nom}", callback_data=f"delete_{nom}")] for nom in noms]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Quel client souhaitez-vous supprimer ?", reply_markup=reply_markup)
        return DELETING

def choix_nom(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    nom_client = update.message.text

    if user_id not in clients:
        clients[user_id] = []
    clients[user_id].append(nom_client)

    if user_id not in progression:
        progression[user_id] = {}
    progression[user_id][nom_client] = 0

    image = generer_carte(nom_client, 0)
    update.message.reply_photo(photo=image, caption=f"🎉 Carte créée pour {nom_client} !")

    return ConversationHandler.END

def choisir_carte(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    nom_client = query.data.replace("carte_", "")
    user_id = query.from_user.id
    context.user_data["client_actuel"] = nom_client
    query.message.reply_text(f"Combien de cases dois-je cocher pour {nom_client} ?")
    return COCHAGE

def cocher_cases(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    nom_client = context.user_data.get("client_actuel")
    try:
        nb = int(update.message.text)
    except ValueError:
        update.message.reply_text("⚠️ Merci d’entrer un nombre valide.")
        return COCHAGE

    if user_id in progression and nom_client in progression[user_id]:
        progression[user_id][nom_client] = min(9, progression[user_id][nom_client] + nb)
        cases = progression[user_id][nom_client]
        image = generer_carte(nom_client, cases)
        update.message.reply_photo(photo=image, caption=f"✅ {cases}/9 cases cochées pour {nom_client}.")
    else:
        update.message.reply_text("⚠️ Erreur : client introuvable.")

    return ConversationHandler.END

def supprimer_client(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    nom_client = query.data.replace("delete_", "")
    user_id = query.from_user.id

    if user_id in clients and nom_client in clients[user_id]:
        clients[user_id].remove(nom_client)
        if nom_client in progression.get(user_id, {}):
            del progression[user_id][nom_client]
        query.message.reply_text(f"🗑️ Client *{nom_client}* supprimé avec succès ✅", parse_mode="Markdown")
    else:
        query.message.reply_text("⚠️ Ce client n’existe plus.")

    return ConversationHandler.END

# === Main ===
def main():
    TOKEN = os.getenv("BOT_TOKEN")  # 🔥 Token via variable d'environnement
    if not TOKEN:
        raise ValueError("⚠️ TELEGRAM_TOKEN non défini. Ajoute-le dans Render Environment Variables.")

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choix_nom)],
            RECHARGING: [CallbackQueryHandler(choisir_carte, pattern="^carte_")],
            COCHAGE: [MessageHandler(Filters.text & ~Filters.command, cocher_cases)],
            DELETING: [CallbackQueryHandler(supprimer_client, pattern="^delete_")]
        },
        fallbacks=[],
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
