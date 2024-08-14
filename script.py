from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import time
from random import randrange
from multiprocessing import Pool

# Installation automatique de chromedriver
chromedriver_autoinstaller.install()

def watch_video(video_url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.get(video_url)

    # Mettre la vidéo en plein écran
    fullScreen(driver)
    time.sleep(randrange(15, 30))  # Temps d'attente réduit
    skipAd(driver)
    time.sleep(randrange(15, 30))
    forwardVideo(driver)

    # Attendre encore un peu pour simuler un utilisateur qui regarde la vidéo
    time.sleep(randrange(15, 30))

    driver.quit()

def fullScreen(driver):
    try:
        full_screen_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button.ytp-fullscreen-button'))
        )
        full_screen_button.click()
    except Exception as error:
        print("Plein écran non activé :", error)

def skipAd(driver):
    try:
        skip_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'ytp-ad-skip-button'))
        )
        skip_button.click()
    except Exception as error:
        print("Pas de publicité à passer ou erreur :", error)

def forwardVideo(driver):
    try:
        progress_bar = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'ytp-progress-bar'))
        )
        progress_bar.click()
    except Exception as error:
        print("Impossible d'avancer la vidéo :", error)

def start(update: Update, context) -> None:
    keyboard = [
        [InlineKeyboardButton("Ajouter des vues", callback_data='add_views')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Bienvenue! Que voulez-vous faire?', reply_markup=reply_markup)

def button(update: Update, context) -> None:
    query = update.callback_query
    query.answer()

    if query.data == 'add_views':
        query.edit_message_text(text="Veuillez envoyer le lien de votre vidéo YouTube.")

def receive_link(update: Update, context) -> None:
    video_url = update.message.text
    update.message.reply_text("Merci! L'ajout de vues est en cours...")

    # Lancer plusieurs processus en parallèle pour obtenir plusieurs vues
    pool = Pool(processes=10)  # 10 processus en parallèle
    pool.map(watch_video, [video_url] * 10)  # Lancer 10 instances de Selenium

    pool.close()
    pool.join()
    
    update.message.reply_text("Succès! 10 vues ont été ajoutées en 1 minute.")

def main() -> None:
    updater = Updater("7219580952:AAFMg1fmQvZXjhpOIYsloth3zNhATVApTyU", use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, receive_link))

    # Démarrer le bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
