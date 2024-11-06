import requests
from telegram import Update
import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import json
import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Set up logging
load_dotenv()  # Load environment variables from .env file

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your Telegram bot token and CryptoPanic API key
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')

def fetch_metadata(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Get title
    title = soup.find("meta", property="og:title")
    title = title["content"] if title else "No Title Available"

    # Get description
    description = soup.find("meta", property="og:description")
    description = description["content"] if description else "No description available."

    # Get image
    image = soup.find("meta", property="og:image")
    image_url = image["content"] if image else None

    return {"title": title, "description": description, "image_url": image_url}

# Function to get latest crypto news from CryptoPanic API
# Function to get latest crypto news with summaries and images
def get_latest_news():
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&public=true"
    response = requests.get(url)
    data = response.json()
    
    logger.info(f"Fetched news data: {data}")  # Log the fetched data
    
    news_items = data.get("results", [])
    latest_news = []
    
    for item in news_items[:5]:  # Fetch top 5 news items
        title = item["title"]
        link = item["url"]
        summary = item.get("description") or "No summary available."
        image = item.get("source", {}).get("domain") + "/favicon.ico"
        
        latest_news.append({"title": title, "link": link, "summary": summary, "image": image})
    
    return latest_news

# Load sent news links from a file
def load_sent_news_links():
    if os.path.exists('sent_news_links.json'):
        with open('sent_news_links.json', 'r') as f:
            return set(json.load(f))
    return set()

# Save sent news links to a file
def save_sent_news_links(sent_links):
    with open('sent_news_links.json', 'w') as f:
        json.dump(list(sent_links), f)

# Initialize a set to keep track of sent news links
sent_news_links = load_sent_news_links()

# Function to get previously sent news
def get_previous_news():
    if os.path.exists('sent_news_links.json'):
        with open('sent_news_links.json', 'r') as f:
            sent_links = json.load(f)
            return "\n\n".join(sent_links)  # Format the previous news for display
    return "No previous news available."

# Function to send news item to a chat and a channel
async def send_news_item(context, chat_id, CHANNEL_USERNAME, news_item):
    link = news_item["link"]
    if link not in sent_news_links:  # Check if the link has already been sent
        metadata = fetch_metadata(link)
        title = metadata["title"]
        description = metadata["description"]
        image_url = metadata["image_url"]
        airdrop_channel_url = "https://t.me/magical_alpha"
        
        message = f"📰 {title}\n\n{description}\n\n[Read More]({link}) | [Airdrop Channel]({airdrop_channel_url})" 

        try:
            if image_url:
                # Send message with image
                await context.bot.send_photo(chat_id=chat_id, photo=image_url, caption=message, parse_mode='Markdown')
                await context.bot.send_photo(chat_id=CHANNEL_USERNAME, photo=image_url, caption=message, parse_mode='Markdown')
            else:
                # Send only text without link preview
                await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown', disable_web_page_preview=True)
                await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=message, parse_mode='Markdown', disable_web_page_preview=True)

            # Mark the link as sent and save to prevent duplication
            sent_news_links.add(link)
            save_sent_news_links(sent_news_links)

        except telegram.error.BadRequest as e:
            logger.error(f"Failed to send message: {e}")

# Update the send_news_update function
async def send_news_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Send news update command triggered")
    chat_id = update.effective_chat.id
    news_list = get_latest_news()
 
    for news_item in news_list:
        await send_news_item(context, chat_id, CHANNEL_USERNAME, news_item)
        break  # Exit after sending one news item

# New command to get previous news
async def previous_news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Previous news command triggered")  # Debugging output
    previous_news = get_previous_news()
    await update.message.reply_text("Previous News:\n" + previous_news)

# Command to start monitoring price and news
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("Hello! I'll keep you updated on Bitcoin price alerts and the latest crypto news.")

    # Schedule the job to send news every hour (3600 seconds)
    context.application.job_queue.run_repeating(
        send_news_update, interval=30, first=1, context=context
    )

# Function to show available commands
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Help command triggered")  # Debugging output
    commands = (
        "/start - Start the bot and receive updates.",
        "/help - Show this help message.",
        "/news - Get the latest news.",
        "/previous_news - Get the Previous news.",
        "/test_auto_post - Test auto post.",
        "/price <coin_name> - Get price"
    )
    await update.message.reply_text("Available commands:\n" + "\n".join(commands))

# Function to format volume values
def format_volume(volume):
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.1f}B"
    elif volume >= 1_000_000:
        return f"{volume / 1_000_000:.1f}M"  # Format as millions
    elif volume >= 1_000:
        return f"{volume / 1_000:.1f}K"  # Format as thousands
    return str(volume)  # Return as is if less than 1000

# Function to get the price and additional data of a specified coin
def get_coin_data(coin_name):
    url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={coin_name}&price_change_percentage=1h"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        coin_data = data[0] if data else {}  # Access the first element of the list
        return {
            "price": coin_data.get("current_price", "Price not available."),  # Updated to use current_price
            "volume_1h": coin_data.get("total_volume", 0),  # Default to 0 if not available
            "price_change_percentage_24h": coin_data.get("price_change_percentage_24h", "Change percentage not available."),
            "price_change_percentage_1h": coin_data.get("price_change_percentage_1h_in_currency", "Change percentage not available."),
            "market_cap": coin_data.get("market_cap", "Market cap not available."),
            "fdv": coin_data.get("fully_diluted_valuation", "FDV not available."),  # Updated to use fully_diluted_valuation
            "high_24h": coin_data.get("high_24h", "High not available."),
            "low_24h": coin_data.get("low_24h", "Low not available."),
            "symbol": coin_name.upper()  # Assuming the coin name is the symbol
        }
    return "Error fetching data."

# New command to get the price and volume of a specified coin
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Price command triggered")  # Debugging output
    if context.args:
        coin_name = context.args[0].lower()  # Get the coin name from the command arguments
        
        # Mapping of common abbreviations to full names
        coin_mapping = {
            "eth": "ethereum",
            "btc": "bitcoin",
            "ltc": "litecoin",
            # Add more mappings as needed
        }
        
        # Use the mapping if the coin name is an abbreviation
        if coin_name in coin_mapping:
            coin_name = coin_mapping[coin_name]
        
        coin_data = get_coin_data(coin_name)
        
        if isinstance(coin_data, str):  # Check if an error message was returned
            await update.message.reply_text(coin_data)
        else:
            price = coin_data["price"]
            volume_1h = format_volume(coin_data["volume_1h"])  # Format the volume
            price_change_percentage_24h = f"{coin_data['price_change_percentage_24h']:.2f}"
            price_change_percentage_1h = f"{coin_data['price_change_percentage_1h']:.2f}"  # Format to 2 decimal places
            high_24h = coin_data["high_24h"]
            low_24h = coin_data["low_24h"]
            market_cap = coin_data["market_cap"]
            fdv = coin_data["fdv"]
            symbol = coin_data["symbol"]

            # Format the output
            response_message = (
                f"{symbol}\n"  
                f"H|L: {high_24h}|{low_24h}\n"
                f"1h {price_change_percentage_1h}   😕\n"
                f"24h {price_change_percentage_24h}   💸\n"
                f"Cap: {market_cap} | {fdv}\n"
                f"Vol: {volume_1h}"
            )
            await update.message.reply_text(response_message)
    else:
        await update.message.reply_text("Please provide a coin name. Usage: /price <coin_name>")
# Function to automatically post new news to the channel
async def auto_post_news(context: ContextTypes.DEFAULT_TYPE):
    news_list = get_latest_news()  # Fetch the latest news
    for news_item in news_list:
        link = news_item.get("link")  # Ensure we get the link safely
        
        if link and link not in sent_news_links:  # Check if the link is valid and not already sent
            metadata = fetch_metadata(link)
            title = metadata["title"]
            description = metadata["description"]
            image_url = metadata["image_url"]
            airdrop_channel_url = "https://t.me/magical_alpha"
            
            # Format the message
            message = f"📰 {title}\n\n{description}\n\n[Read More]({link}) | [Airdrop Channel]({airdrop_channel_url})"
            
            try:
                if image_url:  # Check if image_url is not None
                    # Send message with image
                    await context.bot.send_photo(chat_id=CHANNEL_USERNAME, photo=image_url, caption=message, parse_mode='Markdown')
                else:
                    # Send only text without link preview
                    await context.bot.send_message(chat_id=CHANNEL_USERNAME, text=message, parse_mode='Markdown', disable_web_page_preview=True)
                
                # Add to sent news links to avoid duplicates
                sent_news_links.add(link)
                save_sent_news_links(sent_news_links)
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

async def test_auto_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await auto_post_news(context)

# Main function to set up the bot and handlers
def main():
    # Create the Application with your bot token
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.job_queue.run_repeating(auto_post_news, interval=300, first=1)
    # Command to start the bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("news", send_news_update))
    application.add_handler(CommandHandler("previous_news", previous_news_command))  # New command handler
    application.add_handler(CommandHandler("price", price_command))  # Add the command handler for the /price command
    application.add_handler(CommandHandler("test_auto_post", test_auto_post))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
