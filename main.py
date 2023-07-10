# --- Important Imports ---
import discord
import os

# --- Cog Imports ---
import ticketing

bot = discord.Bot()  # Create bot
# --- Load Cogs ---
cogs = [
    ticketing.Ticketing
]  # Is a list of type cog with the parameter of the bot

print('test')


def load_cogs():  # Load all cogs
    for cog in cogs:
        bot.add_cog(cog(bot))
    print('Cogs loaded')


@bot.listen()
async def on_connect():
    print('Connected')  # Print on connection


@bot.listen()
async def on_ready():  # Print on ready
    bot.add_view(ticketing.TicketButtons(True))
    bot.add_view(ticketing.TicketMessageView())
    print('Ready!')


load_cogs()  # Load all cogs before the bot is connected
bot.run(str(os.getenv('DISCORD')))  # Start the bot

"""
All of the following code above was created by BlueRobin_. Please do not remove this line until the purchase is complete.
"""
