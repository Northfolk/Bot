#! python3
# -*- coding: utf-8 -*-

import configparser
import discord
import random
import feedparser
import requests
import bs4
import sqlite3
import asyncio
from PIL import Image
from io import BytesIO
from urllib import request
import os
import time
import logging
import sys
from . import models


def loadConfigFromDB(setting_model):
    '''
    Load params from DB
    e.g.: loadConfigFromDB(models.BasicSettings)
    :param setting_model:
    :return: res: dict()
    '''
    bot_token = setting_model.objects.all()[1].bot_token
    cosplay_ch = setting_model.objects.all()[1].cosplay_ch
    eso_news_ch = setting_model.objects.all()[1].eso_news_ch
    eso_status_ch = setting_model.objects.all()[1].eso_status_ch
    eso_status_msg = setting_model.objects.all()[1].eso_status_msg
    delay = setting_model.objects.all()[1].delay

    res = {
        'bot_token': bot_token,
        'cosplay_ch': cosplay_ch,
        'eso_news_ch': eso_news_ch,
        'eso_status_ch': eso_status_ch,
        'eso_status_msg': eso_status_msg,
        'delay': delay
           }

    return res


def loadConfigFromFile(path):
    '''
    Load or create config file
    :param path: string
    :return: list of settings
    '''
    cfg = configparser.ConfigParser()
    if not os.path.exists(path):
        logging.error('INI file not found. Creating INI file...')
        cfg.add_section('Discord')
        cfg.set('Discord', 'DISCORD BOT TOKEN', 'Your bot token')
        cfg.set('Discord', 'COSPLAY CHANNEL', 'Cosplay channel id')
        cfg.set('Discord', 'ESO NEWS CHANNEL', 'ESO news channel id')
        cfg.set('Discord', 'ESO STATUS CHANNEL', 'Eso status channel id')
        cfg.set('Discord', 'ESO STATUS MESSAGE', 'Eso status pin-message id')
        cfg.set('Discord', 'DELAY BETWEEN NEWS', '3600')
        cfg.add_section('URL')
        cfg.set('URL', 'COSPLAY URL', 'https://www.deviantart.com/tag/sexycosplay')
        cfg.set('URL', 'ESO NEWS URL', 'http://files.elderscrollsonline.com/rss/en-us/eso-rss.xml')
        cfg.set('URL', 'ESO SERVER STATUS URL', 'https://esoserverstatus.net/')
        cfg.set('URL', 'ESO PLEDGE URL', 'https://www.esoleaderboards.com/')
        cfg.add_section('Database')
        cfg.set('Database settings', 'DB path', 'db.sqlite')
        with open(path, "w") as config_file:
            cfg.write(config_file)
        logging.info('INI file created. Please input your settings.')
        sys.exit('Please input your settings')

    logging.info('INI file found. Loading settings.')
    cfg.read(path)
    return cfg


class NewsParser(object):
    '''
    RSS-parsing with image addition
    '''

    def __init__(self, rss_link):
        self.link = rss_link
        self.news = []

    def refresh(self):
        self.news = []

        # парсим новостную ленту
        data = feedparser.parse(self.link)

        # парсим картинку для новости
        s = requests.session()
        r = s.get('https://www.elderscrollsonline.com/en-gb/agegate')
        s.post(r.url, {'month': 4, 'day': 13, 'year': 1989})
        for i in data['entries'][0:-1]:
            r = s.get(i['link'])
            soup = bs4.BeautifulSoup(r.text, 'lxml')
            img_link = 'http:' + soup.find('img').attrs['src']
            self.news.append([i['title'], i['link'], i['summary'], img_link])
        s.close()


class NewsOperator(object):
    '''
    write into DB
    '''
    def __init__(self, db, table):
        # looking for BD, if not -> error
        self.db = db
        self.tb = table
        if not os.path.exists(self.db):
            conn = sqlite3.connect(self.db)
            c = conn.cursor()
            try:
                c.execute('CREATE TABLE {} (Title, Summary, Link, Img)'.format(self.tb))
            except Exception as e:
                logging.error('Error while creating new table ' + self.tb + ': {}\n'.format(e))
            conn.commit()
            conn.close()

    def write(self, data):
        # DB write
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        try:
            for i in data:
                c.execute('INSERT INTO {} VALUES (?, ?, ?, ?)'.format(self.tb), i)
        except Exception as e:
            logging.error('Error while inserting values in table: {}'.format(e))
        conn.commit()
        conn.close()

    def in_table(self, data):
        # check entry for existing
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('SELECT Title from {}'.format(self.tb))
        row = c.fetchall()
        res = []
        for i in row:
            res.append(i[0])
        temp = []
        for i in data:
            if i[0] not in res:
                temp.append(i)
        conn.close()
        return temp


class EntertainmentBot(discord.Client):
    def __init__(self, cfg):
        self.cfg = cfg
        discord.Client.__init__(self)

    async def eso_check_status(self, channel_id, message_id, send=True):
        '''
        1. Check ESO server status
        2. Send message in 'channel_id'-channel
        3. Edit 'message_id'-message
        '''
        ch_id = self.get_channel(channel_id)  # get channel
        msg_to_edit = await self.get_message(ch_id, message_id)  # get message to edit
        try:
            # get servers status
            r = requests.get(self.cfg['URL']['eso server status'])
            soup = bs4.BeautifulSoup(r.text, 'lxml')
            servers = [i.text.strip() for i in soup.findAll('h4')]
            status = [i.text.strip() for i in soup.findAll('span')]
            msg = 'Статус серверов:\n'  # temp variable for output message
            s = ''
            if 'Offline' in status:
                s = soup.findAll('h3')
                s = s[1].text.strip()
                msg = s.replace('\t', '').replace('\r', '').replace('Maintenance is ongoing', '') \
                          .replace('·', ':tools:').replace(' \x96', '.') + '\n'
            for i in range(0, len(servers)):
                if status[i] == 'Online':
                    s = ':white_check_mark: ' + servers[i]
                else:
                    s = ':x: ' + servers[i]
                msg += s + '\n'
            # send messages
            if send:
                await self.send_message(ch_id, msg)
            await self.edit_message(msg_to_edit, msg)

        except Exception as e:
            logging.error('Error while checking ESO servers status:\n{}'.format(e))
            await self.send_message(ch_id, 'Error while checking ESO servers status')

    async def on_ready(self):
        logging.info('Logged in as:\nName: {}; Id: {}'.format(self.user.name, self.user.id))

    async def on_message(self, message):
        # messages in cosplay channel
        ch_id = self.cfg['Discord']['cosplay channel']
        if message.content.lower() == '!хочу косплей' and message.channel.id == ch_id:
            name = message.content[len('$name'):].strip()
            msg = await self.send_message(self.get_channel(ch_id), (
                'Подожди секунду {}, сейчас найдем что-нибудь для тебя...'.format(str(message.author).split('#')[0])))
            url = ['https://www.deviantart.com/tag/sexycosplay?offset={}',
                   'https://www.deviantart.com/tag/cosplayfemale?offset={}']
            r = requests.get(url[random.randint(0, 1)].format(random.randrange(0, 2400, 24)))
            try:
                soup = bs4.BeautifulSoup(r.text, 'lxml')
                l = soup.findAll('span', attrs={'data-super-full-img': True})
                cosplay = [[i.attrs['data-super-alt'], i.attrs['data-super-full-img']] for i in l]
                i = random.randint(0, len(cosplay) - 1)
                f_name = cosplay[i][1].split('/')[-1]
                request.urlretrieve(cosplay[i][1], f_name)
                await self.send_file(self.get_channel(ch_id), f_name)
                await self.edit_message(msg, cosplay[i][0])
                os.remove(f_name)
            except Exception as e:
                logging.error('Error while stealing some cosplay image: {}'.format(e))
                await self.send_message(self.get_channel(ch_id), 'Что-то пошло не так...')

        # messages in eso status channel
        ch_id = self.cfg['Discord']['eso status channel']
        msg_id = self.cfg['Discord']['eso status message']
        if message.content.lower() == '!статус' and message.channel.id == ch_id:
            await self.eso_check_status(ch_id, msg_id)

        if message.content.lower() == '!обеты' and message.channel.id == ch_id:
            r = requests.get(self.cfg['URL']['eso pledge'])
            soup = bs4.BeautifulSoup(r.text, 'lxml')
            table = soup.find('table', attrs={'class': 'score_table'})
            h = table.findAll('th')
            h = [i.text.strip() for i in h]
            row = table.findAll('td')
            row = [i.text.strip() for i in row]
            row = row[5:8]
            next_pledge = '\n:exclamation:' + h[-1] + ':exclamation:'
            h = h[2:5]
            output = ''
            for i in range(0, len(row)):
                output += ':small_blue_diamond: ' + h[i] + ': ' + row[i] + '\n'
            output += next_pledge
            await self.send_message(self.get_channel(ch_id), output)

    async def background_loop(self):
        await self.wait_until_ready()
        while not self.is_closed:
            # checking news
            teso_news = NewsParser(self.cfg['URL']['eso news'])
            writer = NewsOperator(self.cfg['Database']['db path'], 'TESO')
            ch_id = self.cfg['Discord']['eso news channel']
            teso_news.refresh()
            news_to_print = writer.in_table(teso_news.news)
            for news in news_to_print[::-1]:
                logging.info(news)
                response = requests.get(news[3])
                img = Image.open(BytesIO(response.content))
                img.save('temp_news.jpg')
                await self.send_file(self.get_channel(ch_id), 'temp_news.jpg')
                await self.send_message(self.get_channel(ch_id), '**' + news[0] + '**\n' + news[1] + '\n' + news[2])
                os.remove('temp_news.jpg')
                await asyncio.sleep(15)
            writer.write(news_to_print)

            # checking ESO server status
            await self.eso_check_status(self.cfg['Discord']['eso status channel'],
                                        self.cfg['Discord']['eso status message'], send=False)

            # waiting till next check
            await asyncio.sleep(int(self.cfg['Discord']['delay between news']))

    def bot_start(self, *args, **kwargs):
        while True:
            try:
                token = self.cfg['Discord']['discord bot token']
                self.loop.create_task(self.background_loop())
                self.loop.run_until_complete(self.start(token, *args, **kwargs))
            except Exception as e:
                print("Error", e)
                logging.error('Error while bot starting: \n {}'.format(e))
            logging.info("Waiting until restart")
            time.sleep(60)  # trying to restart


# main part
def run():
    logging.basicConfig(format='%(asctime)s %(message)s', filename='logs.log', filemode='w', level=logging.INFO)
    ini_path = 'Settings.ini'
    cfg = loadConfigFromFile(ini_path)
    bot = EntertainmentBot(cfg)
    bot.bot_start()
