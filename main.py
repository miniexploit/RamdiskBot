import discord
from discord.ext import commands
import shutil
from m1n1Exception import *
import requests
import patcher
from utils import create_embed
import utils
from discord.ui import Button, View
import asyncio
import nest_asyncio
nest_asyncio.apply()
#_import__('IPython').embed()

client = discord.Bot()
'''debug_guilds=[1005348893413867601]'''

DEBUG = 0


@client.event
async def on_ready():
	print("Bot is ready!")

@client.slash_command(name="hi", description="Say hi!")
async def hi(ctx):
	await ctx.respond("Hey!")

@client.slash_command(name="patch", description="Patch ramdisk for tethered downgrading")
async def patch(ctx, identifier, version):
	try:
		ipsw_api = requests.get(f'https://api.ipsw.me/v4/device/{identifier}?type=ipsw').json()
	except:
		embed = create_embed("Error", f"`{identifier}`is not a valid device identifier")
		await ctx.respond(embed=embed)
		return
	
	if not any(firm['version'] == version for firm in ipsw_api['firmwares']):
		embed = create_embed("Error", f"`{version}`is not a valid iOS version")
		await ctx.respond(embed=embed)
		return

	embed = create_embed("Patching ramdisk in progress", "Please be patient")
	await ctx.respond(embed=embed)
	channel = client.get_channel(debugchannelid)
	dbginfo = f"Requested by {ctx.author.mention}\n```\n{identifier}, iOS {version} ramdisk patch progress (DEBUG LOG)\n```"
	dbgmsg = await channel.send(dbginfo)
	async def debug(msg):
		nonlocal dbginfo
		# convert dbginfo into array
		arr = dbginfo.splitlines()
		# insert msg before ```
		arr.insert(len(arr)-1, msg)
		dbginfo = "\n".join(arr)
		await dbgmsg.edit(dbginfo)

	maker = patcher.ramdiskMaker(identifier, version, callback=debug)
	if (url := maker.isOutExists()):
		embed = create_embed(f"Hey! {ctx.author.mention}", f"The ramdisk of the iOS version you're requesting has already been uploaded!\n{url}")
		await ctx.send(embed=embed)
		return
	url_ret = maker.getFirmwareUrl()
	if url_ret[1]: # url_ret is json
		async def button_callback(interaction):
			print("button_callback() running")
			#print(interaction)
			await interaction.response.send_message(f"BuildID selected: `{interaction.custom_id}`", ephemeral=True)
			for button in buttons:
				button.disabled = True
			#await interaction.
			await msg.edit(embed=create_embed("Multiple BuildIDs", "BuildID selected by user"), view=view)
			maker.setFirmwareUrl(url_ret[0][interaction.custom_id])
			await debug("Firmware URL set!")
		buttons = []
		view = View()
		for buildid in url_ret[0].keys():
			buttons.append(Button(label=buildid, style=discord.ButtonStyle.secondary, custom_id=buildid))
		for button in buttons:
			button.callback = button_callback
			view.add_item(button)
		msg = await ctx.send(embed=create_embed("Multiple BuildIDs", "There're multiple BuildIDs for this iOS version, please select one from below"), view=view)
		await client.wait_for("interaction")
	else:
		maker.setFirmwareUrl(url_ret[0])
	await asyncio.sleep(5)
	# extract
	ramdiskPath = maker.extractRamdisk()
	# patch
	outPath = maker.patchRamdisk(ramdiskPath)
	url = maker.uploadRamdisk(outPath)
	embed = create_embed(f"Ramdisk uploaded!",f"Download it here:\n{url}")
	await ctx.send(embed=embed)
	maker.cleanUp()
	print("done!")

if not DEBUG:
	@patch.error
	async def patch_error(ctx, error):
		print("patch_error() running")
		embed = create_embed(f"Error during patching ramdisk",f"An exception was raised during the patching process:\n`{error.__cause__}`")
		await ctx.send(ctx.author.mention, embed=embed)

client.run(os.environ["BOT_TOKEN"])

