import os
import io
import re
import json
from datetime import datetime
from PIL import Image
import qrcode

# Try to import pyzbar with fallback
try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    print("⚠️ pyzbar not available - QR scanning disabled")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

# User sessions
user_sessions = {}
scan_history = {}

# ==================== QR/BARCODE FUNCTIONS ====================
def generate_qr_code(data: str, fill_color: str = "black", back_color: str = "white"):
    """Generate QR code image from data"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color=fill_color, back_color=back_color)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        return img_bytes.read()
    except Exception as e:
        print(f"QR generation error: {e}")
        return None

def scan_qr_code(image_data: bytes):
    """Scan QR code from image using pyzbar"""
    if not PYZBAR_AVAILABLE:
        return None
    
    try:
        # Open image with PIL
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Decode QR codes using pyzbar
        decoded_objects = decode(img)
        
        results = []
        for obj in decoded_objects:
            data = obj.data.decode('utf-8')
            results.append({
                "data": data,
                "type": obj.type,
                "rect": {
                    "left": obj.rect.left,
                    "top": obj.rect.top,
                    "width": obj.rect.width,
                    "height": obj.rect.height
                }
            })
        
        return results if results else None
    except Exception as e:
        print(f"QR scan error: {e}")
        return None

def detect_qr_type(data: str):
    """Detect what type of QR code data is"""
    # URL detection
    if re.match(r'^https?://', data):
        return "URL"
    
    # Wi-Fi detection
    if data.startswith('WIFI:'):
        return "Wi-Fi"
    
    # vCard detection
    if data.startswith('BEGIN:VCARD'):
        return "vCard"
    
    # Geo detection
    if data.startswith('geo:'):
        return "Geo Location"
    
    # Bitcoin/ Crypto
    if data.startswith('bitcoin:') or data.startswith('ethereum:'):
        return "Crypto Address"
    
    # Email
    if re.match(r'^mailto:', data):
        return "Email"
    
    # Phone
    if re.match(r'^tel:', data):
        return "Phone Number"
    
    # JSON
    try:
        json.loads(data)
        return "JSON Data"
    except:
        pass
    
    return "Text"

def parse_wifi_qr(data: str):
    """Parse Wi-Fi QR code data"""
    parts = {}
    for part in data.split(';'):
        if ':' in part:
            key, value = part.split(':', 1)
            parts[key.strip()] = value.strip()
    return parts

def parse_vcard(data: str):
    """Parse vCard data"""
    vcard = {}
    for line in data.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            vcard[key.strip()] = value.strip()
    return vcard

# ==================== KEYBOARD FUNCTIONS ====================
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 Scan QR/Barcode", callback_data="scan")],
        [InlineKeyboardButton("🎨 Generate QR Code", callback_data="generate")],
        [InlineKeyboardButton("📊 Document Analysis", callback_data="document")],
        [InlineKeyboardButton("📋 Scan History", callback_data="history")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_generate_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔗 URL", callback_data="gen_url")],
        [InlineKeyboardButton("📝 Text", callback_data="gen_text")],
        [InlineKeyboardButton("📡 Wi-Fi", callback_data="gen_wifi")],
        [InlineKeyboardButton("👤 vCard", callback_data="gen_vcard")],
        [InlineKeyboardButton("📍 Location", callback_data="gen_geo")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_result_keyboard():
    keyboard = [
        [InlineKeyboardButton("📱 Scan Another", callback_data="scan")],
        [InlineKeyboardButton("🎨 Generate QR", callback_data="generate")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_document_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Analyze Document", callback_data="document")],
        [InlineKeyboardButton("📱 Scan QR", callback_data="scan")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Initialize user session
    user_id = str(user.id)
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    if user_id not in scan_history:
        scan_history[user_id] = []
    
    # Check if scanning is available
    scan_status = "✅ Available" if PYZBAR_AVAILABLE else "❌ Unavailable (Install pyzbar)"
    
    welcome_message = (
        f"🔍 Welcome {user.first_name} to **ScanCraftBot**!\n\n"
        "Your ultimate QR code and document scanning companion!\n\n"
        "**✨ Features:**\n"
        "• 📱 Scan QR codes and barcodes from images\n"
        "• 🎨 Generate QR codes (URLs, text, Wi-Fi, vCard, location)\n"
        "• 📊 Analyze text documents\n"
        "• 📋 View scan history\n"
        "• 🔍 Auto-detect QR code types\n\n"
        f"📊 **QR Scanning Status:** {scan_status}\n\n"
        "**🎯 Quick Start:**\n"
        "• Click 'Scan QR/Barcode' and send an image\n"
        "• Click 'Generate QR Code' to create one\n"
        "• Send any text document for analysis\n\n"
        "⬇️ Start scanning now!"
    )
    
    await update.message.reply_text(
        welcome_message,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 **ScanCraftBot User Guide**\n\n"
        "**📱 Scan QR/Barcode**\n"
        "• Send an image containing a QR code or barcode\n"
        "• I'll decode and show the information\n"
        "• Auto-detects QR code type (URL, Wi-Fi, vCard, etc.)\n\n"
        "**🎨 Generate QR Code**\n"
        "• **URL:** Create a QR code for any website\n"
        "• **Text:** Encode any text message\n"
        "• **Wi-Fi:** Create Wi-Fi login QR codes\n"
        "• **vCard:** Create contact QR codes\n"
        "• **Location:** Create geo-location QR codes\n\n"
        "**📊 Document Analysis**\n"
        "• Send text documents (.txt)\n"
        "• Get word count, character count\n"
        "• Sentence and paragraph analysis\n\n"
        "**Commands**\n"
        "/start - Start the bot\n"
        "/help - Show this help"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command"""
    if not PYZBAR_AVAILABLE:
        await update.message.reply_text(
            "❌ **QR Scanning is currently unavailable**\n\n"
            "The pyzbar library is not installed. Please contact the bot owner.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    await update.message.reply_text(
        "📱 **Ready to scan!**\n\n"
        "Please send me an image containing a QR code or barcode.\n\n"
        "Supported formats: JPG, PNG, WEBP, GIF",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ==================== CALLBACK HANDLERS ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(update.effective_user.id)
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    if data == "scan":
        if not PYZBAR_AVAILABLE:
            await query.edit_message_text(
                "❌ **QR Scanning is currently unavailable**\n\n"
                "The pyzbar library is not installed. Please contact the bot owner.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return
        
        await query.edit_message_text(
            "📱 **Ready to scan!**\n\n"
            "Please send me an image containing a QR code or barcode.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        user_sessions[user_id]["action"] = "scan"
    
    elif data == "generate":
        await query.edit_message_text(
            "🎨 **Generate QR Code**\n\n"
            "Choose what type of QR code you want to create:",
            parse_mode="Markdown",
            reply_markup=get_generate_keyboard()
        )
    
    elif data.startswith("gen_"):
        gen_type = data.replace("gen_", "")
        user_sessions[user_id]["gen_type"] = gen_type
        
        messages = {
            "url": "🔗 **URL QR Code**\n\nPlease enter the URL:\nExample: `https://example.com`",
            "text": "📝 **Text QR Code**\n\nPlease enter the text to encode:",
            "wifi": "📡 **Wi-Fi QR Code**\n\nPlease enter Wi-Fi details in this format:\n`SSID:YourWiFi, Password:YourPassword, Security:WPA`\n\nExample: `SSID:HomeWiFi, Password:Secret123, Security:WPA`",
            "vcard": "👤 **vCard QR Code**\n\nPlease enter contact details in this format:\n`Name:John Doe, Phone:+1234567890, Email:john@example.com`",
            "geo": "📍 **Location QR Code**\n\nPlease enter coordinates in this format:\n`lat,lng`\n\nExample: `40.7128,-74.0060`"
        }
        
        await query.edit_message_text(
            messages.get(gen_type, "Please enter the required information:"),
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        user_sessions[user_id]["action"] = f"gen_{gen_type}"
    
    elif data == "document":
        await query.edit_message_text(
            "📊 **Document Analysis**\n\n"
            "Please send me a text document (.txt) for analysis.\n\n"
            "I'll provide:\n"
            "• Word and character count\n"
            "• Sentence and paragraph count\n"
            "• Readability analysis\n\n"
            "Note: Maximum file size: 1MB",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        user_sessions[user_id]["action"] = "document"
    
    elif data == "history":
        history = scan_history.get(user_id, [])
        if not history:
            await query.edit_message_text(
                "📋 **No scan history yet!**\n\n"
                "Scan a QR code to start building your history.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
            return
        
        history_text = "📋 **Recent Scans**\n\n"
        for i, entry in enumerate(history[-10:], 1):
            timestamp = entry.get("timestamp", "Unknown")
            data_preview = entry.get("data", "")[:50]
            qr_type = entry.get("type", "Unknown")
            history_text += f"{i}. [{qr_type}] {data_preview}...\n"
        
        await query.edit_message_text(
            history_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "back":
        await query.edit_message_text(
            "🏠 **Main Menu**\n\n"
            "What would you like to do?",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        user_sessions[user_id] = {}

# ==================== MESSAGE HANDLERS ====================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    action = user_sessions[user_id].get("action", "")
    
    # Handle QR generation
    if action.startswith("gen_"):
        gen_type = action.replace("gen_", "")
        
        if gen_type == "url":
            if not text.startswith(('http://', 'https://')):
                text = f"https://{text}"
            qr_data = text
            display_name = f"URL: {text[:40]}{'...' if len(text) > 40 else ''}"
        
        elif gen_type == "text":
            qr_data = text
            display_name = f"Text: {text[:40]}{'...' if len(text) > 40 else ''}"
        
        elif gen_type == "wifi":
            # Parse Wi-Fi details
            parts = {}
            for part in text.split(','):
                if ':' in part:
                    key, value = part.split(':', 1)
                    parts[key.strip()] = value.strip()
            
            ssid = parts.get('SSID', 'Unknown')
            password = parts.get('Password', '')
            security = parts.get('Security', 'WPA')
            qr_data = f"WIFI:T:{security};S:{ssid};P:{password};;"
            display_name = f"Wi-Fi: {ssid}"
        
        elif gen_type == "vcard":
            parts = {}
            for part in text.split(','):
                if ':' in part:
                    key, value = part.split(':', 1)
                    parts[key.strip()] = value.strip()
            
            name = parts.get('Name', 'Unknown')
            phone = parts.get('Phone', '')
            email = parts.get('Email', '')
            qr_data = f"BEGIN:VCARD\nVERSION:3.0\nFN:{name}\nTEL:{phone}\nEMAIL:{email}\nEND:VCARD"
            display_name = f"vCard: {name}"
        
        elif gen_type == "geo":
            coords = text.split(',')
            if len(coords) == 2:
                lat, lng = coords[0].strip(), coords[1].strip()
                qr_data = f"geo:{lat},{lng}"
                display_name = f"Location: {lat}, {lng}"
            else:
                await update.message.reply_text(
                    "❌ **Invalid format**\n\n"
                    "Please use: `lat,lng`\n"
                    "Example: `40.7128,-74.0060`",
                    parse_mode="Markdown"
                )
                return
        
        else:
            await update.message.reply_text(
                "❌ **Unknown QR type**",
                parse_mode="Markdown"
            )
            return
        
        # Generate QR code
        processing_msg = await update.message.reply_text(
            "🔄 **Generating QR code...**",
            parse_mode="Markdown"
        )
        
        qr_image = generate_qr_code(qr_data)
        
        if qr_image:
            await processing_msg.delete()
            await update.message.reply_photo(
                photo=io.BytesIO(qr_image),
                caption=f"✅ **QR Code Generated**\n\n"
                       f"📝 **Type:** {gen_type.title()}\n"
                       f"📋 **Content:** {display_name}\n\n"
                       f"💡 Scan this QR code to access the information!",
                parse_mode="Markdown",
                reply_markup=get_result_keyboard()
            )
            user_sessions[user_id]["action"] = None
        else:
            await processing_msg.edit_text(
                "❌ **Failed to generate QR code**\n\n"
                "Please try again with different input.",
                parse_mode="Markdown"
            )
        
        return
    
    # Default response
    await update.message.reply_text(
        "👋 **Use the buttons below!**\n\n"
        "I can:\n"
        "• 📱 Scan QR codes and barcodes\n"
        "• 🎨 Generate QR codes\n"
        "• 📊 Analyze documents\n\n"
        "Send me an image with a QR code to scan!",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image messages for QR scanning"""
    if not PYZBAR_AVAILABLE:
        await update.message.reply_text(
            "❌ **QR Scanning is currently unavailable**\n\n"
            "The pyzbar library is not installed. Please contact the bot owner.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    user_id = str(update.effective_user.id)
    
    try:
        # Get the image
        photo = await update.message.photo[-1].get_file()
        image_data = await photo.download_as_bytearray()
        
        # Process message
        processing_msg = await update.message.reply_text(
            "🔄 **Scanning image...**\n\n"
            "⏳ Analyzing for QR codes and barcodes...",
            parse_mode="Markdown"
        )
        
        # Scan for QR codes
        results = scan_qr_code(image_data)
        
        if results:
            await processing_msg.delete()
            
            # Save to history
            if user_id not in scan_history:
                scan_history[user_id] = []
            
            result_text = "🔍 **QR/Barcode Scan Results**\n\n"
            
            for i, result in enumerate(results, 1):
                data = result["data"]
                qr_type = detect_qr_type(data)
                
                result_text += f"**Result #{i}**\n"
                result_text += f"📋 **Type:** {qr_type}\n"
                result_text += f"📝 **Data:** `{data}`\n"
                
                # Add specific parsing for special types
                if qr_type == "Wi-Fi":
                    wifi_info = parse_wifi_qr(data)
                    result_text += f"   📡 SSID: {wifi_info.get('S', 'Unknown')}\n"
                    result_text += f"   🔑 Password: {wifi_info.get('P', 'N/A')}\n"
                
                elif qr_type == "vCard":
                    vcard_info = parse_vcard(data)
                    result_text += f"   👤 Name: {vcard_info.get('FN', vcard_info.get('N', 'Unknown'))}\n"
                    result_text += f"   📞 Phone: {vcard_info.get('TEL', 'N/A')}\n"
                
                elif qr_type == "URL":
                    result_text += f"   🔗 Link: [Open URL]({data})\n"
                
                result_text += "\n"
                
                # Save to history
                scan_history[user_id].append({
                    "timestamp": datetime.now().isoformat(),
                    "data": data,
                    "type": qr_type
                })
            
            result_text += "💡 Click below to scan another image!"
            
            await update.message.reply_text(
                result_text,
                parse_mode="Markdown",
                reply_markup=get_result_keyboard(),
                disable_web_page_preview=True
            )
        else:
            await processing_msg.edit_text(
                "❌ **No QR codes or barcodes found**\n\n"
                "Please try:\n"
                "• Using a clearer image\n"
                "• Making sure the QR code is fully visible\n"
                "• Taking a photo with better lighting",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
    
    except Exception as e:
        print(f"Image handling error: {e}")
        await update.message.reply_text(
            "❌ **Error processing image**\n\n"
            "Please try again with a different image.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages for analysis"""
    document = update.message.document
    
    if document.mime_type and document.mime_type.startswith("text/"):
        try:
            file = await document.get_file()
            content = await file.download_as_bytearray()
            text = content.decode('utf-8')
            
            # Basic text analysis
            words = len(re.findall(r'\b\w+\b', text))
            chars = len(text)
            chars_no_space = len(re.sub(r'\s', '', text))
            sentences = len([s for s in re.split(r'[.!?]+', text) if s.strip()])
            paragraphs = len([p for p in text.split('\n') if p.strip()])
            avg_words_per_sentence = words / sentences if sentences > 0 else 0
            
            analysis = (
                f"📊 **Document Analysis**\n\n"
                f"📄 File: {document.file_name}\n"
                f"📝 **Words:** {words}\n"
                f"🔤 **Characters:** {chars}\n"
                f"   (Without spaces: {chars_no_space})\n"
                f"📖 **Sentences:** {sentences}\n"
                f"📄 **Paragraphs:** {paragraphs}\n"
                f"📊 **Avg Words/Sentence:** {avg_words_per_sentence:.1f}\n\n"
                f"💡 Send a QR code image to scan or use the buttons below!"
            )
            
            await update.message.reply_text(
                analysis,
                parse_mode="Markdown",
                reply_markup=get_document_keyboard()
            )
        except Exception as e:
            print(f"Document error: {e}")
            await update.message.reply_text(
                "❌ **Error reading document**\n\n"
                "Please make sure it's a valid text file.",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
    else:
        await update.message.reply_text(
            "📄 **Unsupported document type**\n\n"
            "Please send a .txt file for analysis.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

# ==================== MAIN FUNCTION ====================
def main():
    """Start the bot"""
    print("=" * 50)
    print("🔍 Starting ScanCraftBot...")
    print(f"📱 QR Scanning: {'✅ Available' if PYZBAR_AVAILABLE else '❌ Unavailable'}")
    if not PYZBAR_AVAILABLE:
        print("⚠️ Install zbar: apt-get install zbar-tools libzbar-dev")
    print("=" * 50)
    
    # Build application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .build()
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("scan", scan_command))
    
    # Add callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Start the bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("=" * 50)
    application.run_polling()

if __name__ == "__main__":
    main()
