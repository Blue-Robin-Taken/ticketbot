import discord
from discord.ext import commands
from discord.ui import View
from discord.ui import Button
from PIL import ImageColor
import chat_exporter
import io
import json
import os

with open(os.path.relpath('config.json'), 'r') as config_file:
    settings = json.loads(config_file.read())

testing_servers = settings['other_settings']['testing_servers']
OTHER_ROLE_ID = settings['other_settings']['OTHER_ROLE_ID']
TRANSCRIPT_CHANNEL = settings['other_settings']['TRANSCRIPT_CHANNEL']
PAYMENT_CATEGORIES = settings['allowed_payment_methods']
print(testing_servers, OTHER_ROLE_ID, TRANSCRIPT_CHANNEL, PAYMENT_CATEGORIES)


async def permissions_error_ctx(ctx):
    await ctx.respond("You don't have the required permissions to complete this task", ephemeral=True)


async def permissions_error_interaction(interaction):
    await interaction.response.send_message("You don't have the required permissions to complete this task",
                                            ephemeral=True)


class TicketMessageView(View):
    def __init__(self, ):
        super().__init__(timeout=None)
        self.add_item(self.CloseTicket())
        self.add_item(self.Claim())

    # noinspection PyProtectedMember
    class CloseTicket(Button):
        def __init__(self, ):
            super().__init__(label='Close', emoji='🔒', style=discord.ButtonStyle.danger, custom_id='close_ticket')

        async def callback(self, interaction):
            """
            This command disables the view the ticket is in. It also removes the user from the ticket.
            """
            if interaction.user.guild_permissions.administrator or await interaction.guild._fetch_role(
                    role_id=OTHER_ROLE_ID) in interaction.user.roles:

                transcript = await chat_exporter.export(interaction.channel)
                transcript_file = discord.File(
                    io.BytesIO(transcript.encode()),
                    filename=f"transcript-{interaction.channel.name}.html",
                )

                transcript_channel = await interaction.guild.fetch_channel(TRANSCRIPT_CHANNEL)
                message = await transcript_channel.send(file=transcript_file)
                link = await chat_exporter.link(message)
                embed = discord.Embed(
                    title=f'Below is the link to the transcript online',
                    description=f'[Here]({link})',
                    color=discord.Color.random()
                )
                await transcript_channel.send(embed=embed)
                await interaction.response.send_message(f'Channel closed by {interaction.user.mention}')
                await interaction.channel.delete(reason='Ticket Closed')
            else:
                await permissions_error_interaction(interaction)

    class Claim(Button):
        def __init__(self, ):
            super().__init__(label='Claim', emoji='🙋‍♂️', style=discord.ButtonStyle.green, custom_id='claim_ticket')

        # noinspection PyProtectedMember
        async def callback(self, interaction):
            if interaction.user.guild_permissions.administrator or await interaction.guild._fetch_role(
                    role_id=OTHER_ROLE_ID) in interaction.user.roles:
                await interaction.response.send_message(f'This ticket has been claimed by {interaction.user.mention}.')
            else:
                await permissions_error_interaction(interaction)


class TicketCreateModal(discord.ui.Modal):
    """
    Given to user when the user creates a ticket from the button attached to the ticket message.
    """

    def __init__(self, button_custom_id):

        super().__init__(title='Ticket Info', timeout=None)
        self.button_custom_id = button_custom_id
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label='Username'))  # Index 0
        self.add_item(
            discord.ui.InputText(style=discord.InputTextStyle.short, label='Coin Amount (Int value) in m'))  # Index 1

    async def callback(self, interaction):
        if int(self.children[1].value) >= 200:
            select_category = None  # Used later to change category perms
            c = None  # The channel used
            print(self.button_custom_id)
            for category in interaction.guild.categories:
                if category.name == str(self.button_custom_id).lower():
                    c = await category.create_text_channel(
                        name=f'{str(self.button_custom_id)}-{self.children[1].value}')
                    select_category = category
                    # await category.set_permissions(overwrite=c.overwrites)
                    break
            if c is None:
                category = await interaction.guild.create_category(name=str(self.button_custom_id).lower())
                c = await category.create_text_channel(name=f'{str(self.button_custom_id)}-{self.children[1].value}')
                select_category = category
            # https://docs.pycord.dev/en/stable/api/data_classes.html#discord.Permissions
            overwrite_perms = discord.PermissionOverwrite(send_messages=False, read_messages=False,
                                                          view_channel=False)
            await c.set_permissions(interaction.guild.default_role, overwrite=overwrite_perms)  # Set permissions for @everyone
            await c.set_permissions(interaction.user, overwrite=overwrite_perms)  # Set perms for user
            if 200 <= int(self.children[1].value) <= 300:  # Junior sellers for specific money amounts
                await c.set_permissions(
                    await discord.utils.get_or_fetch(interaction.guild, 'role', id=OTHER_ROLE_ID),
                    send_messages=True, read_messages=True,
                    view_channel=True)  # Set perms for the specific role
            print(c.overwrites)
            for target in c.overwrites:
                try:
                    await select_category.set_permissions(target, overwrite=c.overwrites[target])
                except KeyError:
                    pass
            embed = discord.Embed(
                title=f'Ticket by: {self.children[0].value}',
                description=f'Payment Method: {str(self.button_custom_id)} \n Coin Amount: {self.children[1].value} \n Stats: https://sky.shiiyu.moe/stats/{self.children[0].value}',
                color=discord.Color.random()
            )
            await c.send(embed=embed, view=TicketMessageView())
            await interaction.response.send_message(f'Created a new ticket!', ephemeral=True)
        else:
            return "Invalid Coin Amount"


class TicketButtons(View):
    def __init__(self, initialization):
        super().__init__(timeout=None)
        # max_buttons = 5
        if initialization:
            with open('store.json') as f:
                data = json.load(f)
                for id_ in data['LoadIds']:
                    self.add_item(self.NormalButton('', 'loadLabel', custom_id=id_))
                f.close()

    class NormalButton(Button):
        def __init__(self, emoji, label, custom_id):
            super().__init__(emoji=emoji, label=label, custom_id=custom_id)

        async def callback(self, interaction):
            await interaction.response.send_modal(TicketCreateModal(self.custom_id))


class TicketChannelModal(discord.ui.Modal):
    """
    This modal is used for creating a new button on the ticket message.
    """

    def __init__(self, m, bot):
        super().__init__(title='Options for Ticket Options', timeout=None)

        self.add_item(
            discord.ui.InputText(label='Emoji', style=discord.InputTextStyle.short, min_length=1))
        self.add_item(discord.ui.InputText(label='Title', style=discord.InputTextStyle.singleline,
                                           min_length=1, max_length=255))
        self.add_item(
            discord.ui.InputText(label='Description', style=discord.InputTextStyle.long, min_length=1)
        )
        self.add_item(
            discord.ui.InputText(label='Category', style=discord.InputTextStyle.short, min_length=1)
        )
        self.m = m
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        self.m = await discord.utils.get_or_fetch(self.bot, 'message',
                                                  self.m.id)  # https://docs.pycord.dev/en/stable/api/utils.html#discord.utils.get_or_fetch
        new_view = discord.ui.View.from_message(self.m)
        new_view.timeout = None
        button_add = TicketButtons.NormalButton(emoji=self.children[0].value, label=self.children[1].value,
                                                custom_id=self.children[3].value)
        new_view.add_item(
            button_add
        )
        # -- Saving the view to store.json --
        with open('store.json', 'r+') as store:
            data = json.load(store)
            data['LoadIds'].append(str(self.children[3].value))
            store.seek(0)
            json.dump(obj=data, fp=store)
        new_embed: discord.Embed = self.m.embeds[0]
        new_embed.add_field(name=self.children[1].value + f' {self.children[0].value}', value=self.children[2].value,
                            inline=False)
        await self.m.edit(view=new_view, embed=new_embed)
        await interaction.response.send_message(str(self.children))

    async def on_error(self, error: Exception, interaction):
        print('Err: \n' + str(error) + '\n at ' + interaction.channel.name)


class AddModalTicketCreate(discord.ui.View):
    def __init__(self, m: discord.Message, bot):
        super().__init__(timeout=None)
        self.m = m  # m is the message of the embed_output
        self.bot = bot

    # noinspection PyUnusedLocal
    @discord.ui.button(label='Add Option', style=discord.ButtonStyle.green)
    async def callback(self, button, interaction):
        modal = TicketChannelModal(self.m, self.bot)
        await interaction.response.send_modal(modal)


# --- Main Cog ---
# noinspection PyProtectedMember
class Ticketing(commands.Cog):
    def __init__(self, bot):  # init m8
        self.bot = bot

    # -- Subgroups --
    ticket_group = discord.commands.SlashCommandGroup('ticket')
    ticket_create_group = ticket_group.create_subgroup('channel')

    @staticmethod
    def hex_to_rgb(h: str):  # https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
        return ImageColor.getcolor('#' + h.replace('#', ''), "RGB")

    @ticket_create_group.command(guild_ids=testing_servers)
    async def create(self, ctx, title: str, description: str,
                     channel: discord.Option(discord.TextChannel, channel_types=[
                         discord.ChannelType.text,
                         discord.ChannelType.news,
                         discord.ChannelType.public_thread]),
                     r: discord.Option(int, max_value=250, min_value=0, required=False) = None,
                     g: discord.Option(int, max_value=250, min_value=0, required=False) = None,
                     b: discord.Option(int, max_value=250, min_value=0, required=False) = None,
                     hex_color: discord.Option(str, required=False) = None):
        if ctx.author.guild_permissions.administrator or await ctx.guild._fetch_role(
                role_id=OTHER_ROLE_ID) in ctx.author.roles:
            # -- Color Handling --
            color = discord.Color.random()
            if hex_color is not None:
                color = self.hex_to_rgb(hex_color)
                color = discord.Colour.from_rgb(color[0], color[1], color[2])
            elif (r is not None) and (g is not None) and (b is not None):
                color = discord.Colour.from_rgb(r, g, b)

            # -- Embed Handling --
            embed_output = discord.Embed(
                title=title,
                description=description,
                color=color
            )
            embed_response = discord.Embed(
                title='Embed sent successfully.',
                description='*Press the button to add an option to the ticket sent.*',
                color=discord.Color.random()
            )

            # -- Output Handling --
            m = await channel.send(embed=embed_output)  # Send embed output
            await ctx.channel.send(
                embed=embed_response, view=AddModalTicketCreate(m,
                                                                self.bot))  # Send the response embed indicating the embed was successfully sent
            await ctx.send_modal(modal=TicketChannelModal(m, self.bot))  # Ask a modal for embed_output options
        else:
            await permissions_error_ctx(ctx)

    @ticket_group.command(title='close', description='Closes the ticket the command is run in.',
                          testing_servers=testing_servers)
    async def close(self, ctx):
        """
        This command disables the view the ticket is in. It also removes the user from the ticket.
        """
        if ctx.author.guild_permissions.administrator or await ctx.guild._fetch_role(
                role_id=OTHER_ROLE_ID) in ctx.author.roles:

            transcript = await chat_exporter.export(ctx.channel)
            transcript_file = discord.File(
                io.BytesIO(transcript.encode()),
                filename=f"transcript-{ctx.channel.name}.html",
            )

            transcript_channel = await ctx.guild.fetch_channel(TRANSCRIPT_CHANNEL)
            message = await transcript_channel.send(file=transcript_file)
            link = await chat_exporter.link(message)
            embed = discord.Embed(
                title=f'Below is the link to the transcript online',
                description=f'[Here]({link})',
                color=discord.Color.random()
            )
            await transcript_channel.send(embed=embed)
            await ctx.respond(f'Channel closed by {ctx.author.mention}')
            await ctx.channel.delete(reason='Ticket Closed')
        else:
            await permissions_error_ctx(ctx)

    @ticket_group.command(title='add', description='Add a user to the ticket.', testing_servers=testing_servers)
    async def add(self, ctx, user: discord.Option(discord.User, required=True)):
        if ctx.author.guild_permissions.administrator or await ctx.guild._fetch_role(
                role_id=OTHER_ROLE_ID) in ctx.author.roles:
            await ctx.channel.set_permissions(user, send_messages=True, read_messages=True,
                                              view_channel=True)
            await ctx.respond(f"{ctx.author.mention} added {user.mention}")
        else:
            await permissions_error_ctx(ctx)

    # --- Error handling ---
    @create.error  # If there is permission error (or anything else), this will respond
    async def create_err(self, ctx, error):
        await ctx.channel.send(f'Error: ```\n {error} \n```')

    @add.error
    async def add_err(self, ctx, error):
        await ctx.channel.send(f'Error: ```\n {error} \n```')

    @close.error
    async def close_err(self, ctx, error):
        await ctx.channel.send(f'Error: ```\n {error} \n```')


"""
All of the following code above was created by BlueRobin_. Please do not remove this line until the purchase is complete.
"""
