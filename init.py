import discord
import os
from openai import OpenAI
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

# Load sensitive data from environment variables
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MONGODB_URI = os.getenv('MONGODB_URI')

# Initialize OpenAI Client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize MongoDB Client
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client.milo
votes_collection = db.image_votes
posts_collection = db.image_posts
messages_collection = db.incoming_messages  # Collection for storing messages

# Replace with the ID of the channel you want to listen to
FOOD_CHANNEL_ID = 1197403586645213244  

# Discord Bot Setup
intents = discord.Intents.all()
intents.messages = True
bot = discord.Bot(intents=intents)

class VotingView(discord.ui.View):
    def __init__(self, message_id, image_url):
        super().__init__(timeout=432000)
        self.message_id = message_id
        self.image_url = image_url

    async def refresh_vote_count(self):
        self.yum_votes = votes_collection.count_documents({"message_id": self.message_id, "vote_type": "Yum"})
        self.meh_votes = votes_collection.count_documents({"message_id": self.message_id, "vote_type": "Meh"})
        self.ew_votes = votes_collection.count_documents({"message_id": self.message_id, "vote_type": "Ew"})
        self.children[0].label = f"Yum! ({self.yum_votes} votes)"  # Yum button
        self.children[1].label = f"Meh.. ({self.meh_votes} votes)"  # Yum button
        self.children[2].label = f"Ew! ({self.ew_votes} votes)"  # Ew button

    async def handle_vote(self, interaction, vote_type):
        user_id = str(interaction.user.id)
        vote = {"vote_type": vote_type}
        votes_collection.update_one({"message_id": self.message_id, "user_id": user_id}, {"$set": vote}, upsert=True)
        print(interaction)
        await self.refresh_vote_count()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Yum! (0 votes)", style=discord.ButtonStyle.green, emoji="😋", custom_id="yum_vote")
    async def handle_yum(self, button, interaction):
        await self.handle_vote(interaction, "Yum")

    @discord.ui.button(label="Meh.. (0 votes)", style=discord.ButtonStyle.primary, emoji="😐", custom_id="meh_vote")
    async def handle_meh(self, button, interaction):
        await self.handle_vote(interaction, "Meh")

    @discord.ui.button(label="Ew! (0 votes)", style=discord.ButtonStyle.red, emoji="🤢", custom_id="ew_vote")
    async def handle_ew(self, button, interaction):
        await self.handle_vote(interaction, "Ew")

    @discord.ui.button(label="Show Results", style=discord.ButtonStyle.grey, custom_id="show_results")
    async def show_results(self, button, interaction):
        votes = votes_collection.find({"message_id": self.message_id})
        results = []
        for vote in votes:
            user = await bot.fetch_user(vote['user_id'])
            username = user.name  # or user.display_name for nickname
            vote_emoji = '😋' if vote['vote_type'] == 'Yum' else '🤢' if vote['vote_type'] == 'Ew' else '😐'
            results.append(f"{username}: {vote_emoji}")

        result_str = "\n".join(results)
        await interaction.response.send_message(f"Current Votes\n{result_str}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user or str(message.channel.id) != str(FOOD_CHANNEL_ID):
        return

    image_attachment = next((attachment for attachment in message.attachments if attachment.content_type and attachment.content_type.startswith('image/')), None)
    if image_attachment:
        posts_collection.update_one(
            {"message_id": str(message.id)},
            {"$set": {"user_id": str(message.author.id), "image_url": image_attachment.url}},
            upsert=True
        )
        user_mention = message.author.mention
        view = VotingView(message_id=str(message.id), image_url=image_attachment.url)
        await message.channel.send(f"Rate {user_mention}'s food!", view=view)


bot.run(DISCORD_TOKEN)