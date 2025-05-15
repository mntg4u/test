import logging
import asyncio
from collections import defaultdict

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# —— LOGGING (same style as your carbon function) ——
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# —— IN-MEMORY VOTE DATA ——
vote_data = defaultdict(lambda: {
    "yes": set(),
    "no": set(),
    "target_msg": None,
    "chat_id": None
})

# —— START A VOTE BY REPLYING WITH @mn ——
@Client.on_message(filters.reply & filters.regex(r"@mn"))
async def vote_start(client, message):
    logger.info(f"[vote_start] fired in chat {message.chat.id} reply_to={message.reply_to_message and message.reply_to_message.message_id}")
    target = message.reply_to_message
    if not target:
        return

    vote_id = f"{target.chat.id}_{target.message_id}"
    vote_data[vote_id]["target_msg"] = target.message_id
    vote_data[vote_id]["chat_id"] = target.chat.id

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"vote|yes|{vote_id}"),
            InlineKeyboardButton("❌ No",  callback_data=f"vote|no|{vote_id}")
        ]
    ])
    await message.reply("🗳️ Should I delete this message?", reply_markup=markup)
    logger.info(f"[vote_start] created vote_id={vote_id}")

# —— HANDLE VOTE BUTTON CLICKS ——
@Client.on_callback_query(filters.regex(r"^vote\|"))
async def handle_vote(client, callback_query: CallbackQuery):
    data = callback_query.data
    user_id = callback_query.from_user.id
    logger.info(f"[handle_vote] data={data} from_user={user_id}")

    parts = data.split("|", 2)
    if len(parts) != 3:
        logger.warning(f"[handle_vote] malformed data: {data}")
        return
    _, vote_type, vote_id = parts

    # Prevent double voting
    if user_id in vote_data[vote_id]["yes"] or user_id in vote_data[vote_id]["no"]:
        await callback_query.answer("⚠️ You already voted!", show_alert=True)
        logger.info(f"[handle_vote] duplicate vote by {user_id} on {vote_id}")
        return

    vote_data[vote_id][vote_type].add(user_id)
    yes_count = len(vote_data[vote_id]["yes"])
    no_count  = len(vote_data[vote_id]["no"])
    logger.info(f"[handle_vote] counts for {vote_id} — yes: {yes_count}, no: {no_count}")

    # Decision logic
    if yes_count >= 5:
        try:
            await client.delete_messages(vote_data[vote_id]["chat_id"], vote_data[vote_id]["target_msg"])
            logger.info(f"[handle_vote] deleted message {vote_data[vote_id]['target_msg']} in chat {vote_data[vote_id]['chat_id']}")
        except Exception:
            logger.exception("[handle_vote] failed to delete message")
        await callback_query.message.edit_text("✅ Message deleted by vote.")
        vote_data.pop(vote_id, None)

    elif no_count >= 5:
        await callback_query.message.edit_text("❌ Message kept by vote.")
        vote_data.pop(vote_id, None)

    else:
        # update user with current tally
        await callback_query.answer(f"✅ Yes: {yes_count} | ❌ No: {no_count}", show_alert=False)
