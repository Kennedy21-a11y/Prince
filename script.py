import os
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters

# === Variables Globales ===
clients = {}       # {user_id: [list des clients]}
progression = {}   # {user_id: {nom_client: nb_cases_cochees}}

CHOOSING, COCHAGE, RECHARGING = range(3)


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
def trouver_centres(mask_path="ir.png"):
    mask = Image.open(mask_path).convert("L")  # gris
    arr = np.array(mask)

    # Seuil pour considérer un pixel blanc
    thresh = 200
    white_pixels = np.argwhere(arr > thresh)

    # Si pas de points blancs → retourne vide
    if white_pixels.size == 0:
        return []

    # Grouper par proximité : ici simplifié → kmeans pas nécessaire
    # On prend chaque point blanc et fait la moyenne par "tâche"
    from scipy.ndimage import label, center_of_mass

    # Créer carte binaire
    binary = (arr > thresh).astype(int)

    # Étiqueter chaque tâche
    labels, nb = label(binary)

    # Calculer barycentre de chaque tâche
    centres = center_of_mass(binary, labels, range(1, nb + 1))

    # Convertir en tuples (x, y)
    centres_xy = [(int(c[1]), int(c[0])) for c in centres]

    return centres_xy


# === Génération Carte avec ton image ===
# === Génération Carte avec ton image ===
def generer_carte(nom_client: str, cases_cochees: int = 0) -> BytesIO:
    fond = Image.open("re.png").convert("RGBA")
    draw = ImageDraw.Draw(fond)
    font_titre = load_font(40)
    font_normal = load_font(60)

    # === Position automatique du texte (via masque texte.png) ===
    pos_texte = trouver_centres("texte.png")
    if pos_texte:
        # prendre le premier point trouvé
        x_t, y_t = pos_texte[0]
        draw.text((x_t, y_t), f"Carte fidélité - {nom_client}", font=font_titre, fill="white", anchor="mm")
    else:
        # fallback si pas de masque
        draw.text((40, 40), f"Carte fidélité - {nom_client}", font=font_titre, fill="white")

    # === Récup coordonnées des cases à cocher (via ir.png) ===
    positions = trouver_centres("ir.png")

    # Trier pour garantir un ordre cohérent (haut → bas, gauche → droite)
    positions = sorted(positions, key=lambda p: (p[1], p[0]))

    # === Coche ✅ en fonction du nombre demandé ===
    for idx, (x, y) in enumerate(positions):
        if idx < cases_cochees:
            draw.text((x, y), "✓", font=font_normal, fill="green", anchor="mm")


    # Sauvegarde
    image_io = BytesIO()
    fond.save(image_io, format="PNG")
    image_io.seek(0)
    return image_io



# === Commandes Bot ===
def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    keyboard = []

    if user_id in clients and clients[user_id]:
        keyboard = [
            [InlineKeyboardButton("➕ Enregistrer un client", callback_data="nouveau")],
            [InlineKeyboardButton("🎟️ Retirer une carte", callback_data="recharge")]
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

    if query.data == "nouveau":
        query.message.reply_text("Entrez le nom du nouveau client :")
        return CHOOSING

    elif query.data == "recharge":
        user_id = query.from_user.id
        if user_id not in clients or not clients[user_id]:
            query.message.reply_text("Aucun client enregistré.")
            return ConversationHandler.END

        noms = clients[user_id]
        keyboard = [[InlineKeyboardButton(nom, callback_data=f"carte_{nom}")] for nom in noms]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text("Choisissez un client :", reply_markup=reply_markup)
        return RECHARGING


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
        progression[user_id][nom_client] += nb
        if progression[user_id][nom_client] > 9:
            progression[user_id][nom_client] = 9

        cases = progression[user_id][nom_client]
        image = generer_carte(nom_client, cases)
        update.message.reply_photo(photo=image, caption=f"✅ {cases}/9 cases cochées pour {nom_client}.")
    else:
        update.message.reply_text("⚠️ Erreur : client introuvable.")

    return ConversationHandler.END


# === Main ===
def main():
    TOKEN =os.getenv("8457419998:AAEEdd9G9oqal74JIYcFd7omaoJWcpPGWCM")
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choix_nom)],
            RECHARGING: [CallbackQueryHandler(choisir_carte, pattern="^carte_")],
            COCHAGE: [MessageHandler(Filters.text & ~Filters.command, cocher_cases)],
        },
        fallbacks=[],
    )

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()

