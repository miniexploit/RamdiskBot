import discord
import json


# class MultipleBuildIDsView(discord.ui.view):
#     def __init__(self, buildidsJSON):
#         self.buildidsJSON = buildidsJSON
#     @discord.ui.button(label="There are multiple BuildIDs for this iOS version. Please pick the right one below")

def create_embed(toptext, bodytext):
    embed = discord.Embed(title=toptext, description=bodytext, color=0x0000ff)
    embed.set_author(
        name="RamdiskBot",
        icon_url=
        "https://cdn.discordapp.com/attachments/949660529109123152/1005324036336799744/images.jpeg"
    )
    return embed


# JSON manager

def read_json():
    with open("url.json", "rb") as f:
        p = json.loads(f.read())
    return p

def write_json(p: dict):
    with open("url.json", "w") as f:
        f.write(json.dumps(p))

def read_key(key):
    p = read_json()
    return p[key]

def write_key(key, value):
    p = read_json()
    p[key] = value
    write_json(p)
    return p[key]