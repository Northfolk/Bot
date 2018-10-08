from django.db import models


class BasicSettings(models.Model):
    '''
    Main settings for bot
    '''
    # Fields
    bot_token = models.CharField(max_length=100, help_text='Введите токен бота')
    cosplay_ch = models.CharField(max_length=100, help_text='Введите id канала для постинга косплей-фото')
    eso_news_ch = models.CharField(max_length=100, help_text='Введите id канала для новостей по ESO')
    eso_status_ch = models.CharField(max_length=100, help_text='Введите id канала для статуса ESO-серверов')
    eso_status_msg = models.CharField(max_length=100,
                                      help_text='Введите id заглавного-сообщения для статуса ESO-серверов')
    delay = models.IntegerField(default=900)

