# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback

# third-party
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify, session, send_from_directory 
from flask_socketio import SocketIO, emit, send
from flask_login import login_user, logout_user, current_user, login_required

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, path_data, socketio, check_api
from framework.util import Util
from system.logic import SystemLogic
from framework.common.torrent.process import TorrentProcess
from system.model import ModelSetting as SystemModelSetting

# 패키지
# 로그
package_name = __name__.split('.')[0]
logger = get_logger(package_name)

from .model import ModelSetting, ModelBotDownloaderKtvItem
from .logic import Logic
from .logic_normal import LogicNormal

#########################################################


#########################################################
# 플러그인 공용                                       
#########################################################
blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

menu = {
    'main' : [package_name, '봇 다운로드 - TV'],
    'sub' : [
        ['setting', '설정'], ['list', '목록'], ['log', '로그']
    ],
    'category' : 'torrent'
}

plugin_info = {
    'version' : '0.1.0.0',
    'name' : 'bot_downloader_ktv',
    'category_name' : 'torrent',
    'developer' : 'soju6jan',
    'description' : '텔레그램 봇으로 수신한 정보로 TV 다운로드',
    'home' : 'https://github.com/soju6jan/bot_downloader_ktv',
    'more' : '',
}

def plugin_load():
    Logic.plugin_load()

def plugin_unload():
    Logic.plugin_unload()

def process_telegram_data(data):
    LogicNormal.process_telegram_data(data)



#########################################################
# WEB Menu 
#########################################################
@blueprint.route('/')
def home():
    return redirect('/%s/list' % package_name)

@blueprint.route('/<sub>')
@login_required
def first_menu(sub): 
    logger.debug('DETAIL %s %s', package_name, sub)
    if sub == 'setting':
        arg = ModelSetting.to_dict()
        arg['package_name']  = package_name
        arg['scheduler'] = str(scheduler.is_include(package_name))
        arg['is_running'] = str(scheduler.is_running(package_name))
        from system.model import ModelSetting as SystemModelSetting
        ddns = SystemModelSetting.get('ddns')
        arg['rss_api'] = '%s/%s/api/rss' % (ddns, package_name)
        if SystemModelSetting.get_bool('auth_use_apikey'):
            arg['rss_api'] += '?apikey=%s' % SystemModelSetting.get('auth_apikey')
        
        return render_template('%s_setting.html' % package_name, sub=sub, arg=arg)
    elif sub == 'list':
        arg = {'package_name' : package_name}
        arg['is_torrent_info_installed'] = False
        try:
            import torrent_info
            arg['is_torrent_info_installed'] = True
        except Exception as e: 
            pass
        return render_template('%s_list.html' % package_name, arg=arg)
    elif sub == 'log':
        return render_template('log.html', package=package_name)
    return render_template('sample.html', title='%s - %s' % (package_name, sub))

#########################################################
# For UI 
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
@login_required
def ajax(sub):
    try:
        # 설정 저장
        if sub == 'setting_save':
            ret = ModelSetting.setting_save(request)
            return jsonify(ret)
        elif sub == 'scheduler':
            go = request.form['scheduler']
            logger.debug('scheduler :%s', go)
            if go == 'true':
                Logic.scheduler_start()
            else:
                Logic.scheduler_stop()
            return jsonify(go)
        elif sub == 'reset_db':
            LogicNormal.reset_last_index()
            ret = Logic.reset_db()
            return jsonify(ret)
        elif sub == 'one_execute':
            ret = Logic.one_execute()
            return jsonify(ret)
        
        elif sub == 'reset_last_index':
            ret = LogicNormal.reset_last_index()
            return jsonify(ret)
        elif sub == 'list':
            ret = ModelBotDownloaderKtvItem.filelist(request)
            ret['plex_server_hash'] = None
            try:
                import plex
                ret['plex_server_hash'] = plex.Logic.get_server_hash()
            except Exception, e:
                logger.error('not import plex')
            return jsonify(ret)
        elif sub == 'add_program':
            ret = LogicNormal.add_program(request)
            return jsonify(ret)
        elif sub == 'add_download':
            ret = LogicNormal.add_download(request)
            return jsonify(ret)
        elif sub == 'plex_refresh':
            ret = LogicNormal.plex_refresh(request.form['id'])
            return jsonify(ret)
        elif sub == 'remove':
            ret = ModelBotDownloaderKtvItem.remove(request.form['id'])
            return jsonify(ret)
        
        # 봇 검색
        elif sub == 'torrent_info':
            try:
                from torrent_info import Logic as TorrentInfoLogic
                data = request.form['hash']
                logger.debug(data)
                if data.startswith('magnet'):
                    ret = TorrentInfoLogic.parse_magnet_uri(data)
                else:
                    ret = TorrentInfoLogic.parse_torrent_url(data)
                return jsonify(ret)
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        elif sub == 'make_etc_genre':
            return jsonify(ModelBotDownloaderKtvItem.make_etc_genre())


    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())  
        return jsonify('fail')   


#########################################################
# API
#########################################################
@blueprint.route('/api/<sub>', methods=['GET', 'POST'])
@check_api
def api(sub):
    try:
        if sub == 'add_download':
            ret = LogicNormal.add_download_api(request)
            return jsonify(ret)
        elif sub == 'rss':
            ret = ModelBotDownloaderKtvItem.itemlist_by_api(request)
            data = []
            for t in ret:
                item = {}
                item['title'] = t.filename
                item['link'] = t.magnet
                item['created_time'] = t.created_time
                data.append(item)
            from framework.common.rss import RssUtil
            xml = RssUtil.make_rss(package_name, data)
            return Response(xml, mimetype='application/xml')

    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())