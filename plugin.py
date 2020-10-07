# -*- coding: utf-8 -*-
# python
import os, traceback
# third-party
from flask import Blueprint
# sjva 공용
from framework import app, path_data, SystemModelSetting
from framework.logger import get_logger
from framework.util import Util
from framework.common.plugin import get_model_setting, Logic, default_route
# 패키지
#########################################################

class P(object):
    package_name = __name__.split('.')[0]
    logger = get_logger(package_name)
    blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
    menu = { 
        'main' : [package_name, '봇 다운로드 - TV'],
        'sub' : [
            ['torrent', '토렌트'], ['vod', 'VOD'], ['log', '로그']
        ], 
        'category' : 'torrent',
        'sub2' : {
            'torrent' : [
                ['setting', '설정'], ['list', '목록']
            ],
            'vod' : [
                ['setting', '설정'], ['list', '목록']
            ]
        }
    }  
    plugin_info = {
        'version' : '0.2.0.0',
        'name' : 'bot_downloader_ktv',
        'category_name' : 'torrent',
        'developer' : 'soju6jan',
        'description' : '텔레그램 봇으로 수신한 정보로 TV 다운로드',
        'home' : 'https://github.com/soju6jan/bot_downloader_ktv',
        'more' : '',
    }
    ModelSetting = get_model_setting(package_name, logger)
    logic = None
    module_list = None
    home_module = 'torrent'
    
    


def initialize():
    try:
        app.config['SQLALCHEMY_BINDS'][P.package_name] = 'sqlite:///%s' % (os.path.join(path_data, 'db', '{package_name}.db'.format(package_name=P.package_name)))
        from framework.util import Util
        Util.save_from_dict_to_json(P.plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))
        ###############################################
        from .logic_torrent_ktv import LogicTorrentKTV
        P.module_list = [LogicTorrentKTV(P)]
        if app.config['config']['level'] < 5:
            del P.menu['sub'][1]
        else:
            from .logic_vod import LogicVod
            P.module_list.append(LogicVod(P))
        ###############################################
        P.logic = Logic(P)
        default_route(P)
    except Exception as e: 
        P.logger.error('Exception:%s', e)
        P.logger.error(traceback.format_exc())

initialize()
