# -*- coding: utf-8 -*-
#########################################################
# python
import os
import datetime
import traceback
import urllib

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_

# sjva 공용
from framework import app, db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util
from framework.common.torrent.process import TorrentProcess
from system.model import ModelSetting as SystemModelSetting

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelBotDownloaderKtvItem


#########################################################
class LogicNormal(object):
    @staticmethod
    def process_telegram_data(data):
        try:
            ret = ModelBotDownloaderKtvItem.process_telegram_data(data)
            #logger.debug(ret)
            if ret is not None:
                if ModelSetting.get_bool('receive_info_send_telegram'):
                    msg = '😉 TV 정보 수신\n'
                    msg += '제목 : %s\n' % data['filename']
                    if ret is None:
                        msg += '중복 마그넷입니다.'
                        #TelegramHandle.sendMessage(msg)
                    else:
                        url = '%s/%s/api/add_download?url=%s' % (SystemModelSetting.get('ddns'), package_name, ret.magnet)
                        if SystemModelSetting.get_bool('auth_use_apikey'):
                            url += '&apikey=%s' % SystemModelSetting.get('auth_apikey')
                        if app.config['config']['is_sjva_server']:
                            msg += '\n' + ret.magnet + '\n'
                        else:
                            msg += '\n➕ 다운로드 추가\n<%s>\n' % url
                        try:
                            if ret.daum_id is not None:
                                url = 'https://search.daum.net/search?w=tv&q=%s&irk=%s&irt=tv-program&DA=TVP' % (urllib.quote(ret.daum_title.encode('utf8')), ret.daum_id)
                                msg += '\n● Daum 정보\n%s' % url
                        except Exception as e: 
                            logger.error('Exception:%s', e)
                            logger.error(traceback.format_exc())  
                    import framework.common.notify as Notify
                    Notify.send_message(msg, image_url=ret.daum_poster_url, message_id='bot_downloader_ktv_receive')
                LogicNormal.invoke()
                TorrentProcess.receive_new_data(ret, package_name)
        except Exception, e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())


    @staticmethod
    def invoke():
        try:
            logger.debug('invoke')
            telegram_invoke_action = ModelSetting.get('telegram_invoke_action')
            if telegram_invoke_action == '0':
                return False
            elif telegram_invoke_action == '1':
                if scheduler.is_include(package_name):
                    if scheduler.is_running(package_name):
                        return False
                    else:
                        scheduler.execute_job(package_name)
                        return True
            elif telegram_invoke_action == '2':
                from .logic import Logic
                Logic.one_execute()
                return True
            else:
                return False
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def reset_last_index():
        try:
            ModelSetting.set('last_id', '-1')
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    

    @staticmethod
    def scheduler_function():
        try:
            #logger.debug('%s scheduler_function', package_name)
            last_id = ModelSetting.get_int('last_id')

            except_program = ModelSetting.get('except_program')
            except_programs = [x.strip().replace(' ', '').strip() for x in except_program.replace('\n', '|').split('|')]
            except_programs = Util.get_list_except_empty(except_programs)

            whitelist_program = ModelSetting.get('whitelist_program')
            whitelist_programs = [x.strip().replace(' ', '').strip() for x in whitelist_program.replace('\n', '|').split('|')]
            whitelist_programs = Util.get_list_except_empty(whitelist_programs)

            except_genre = ModelSetting.get('except_genre')
            except_genres = [x.strip() for x in except_genre.replace('\n', '|').split('|')]
            except_genres = Util.get_list_except_empty(except_genres)

            whitelist_genre = ModelSetting.get('whitelist_genre')
            whitelist_genres = [x.strip() for x in whitelist_genre.replace('\n', '|').split('|')]
            whitelist_genres = Util.get_list_except_empty(whitelist_genres)
            
            # rssbot에서 데이터를 가져온다.
            flag_first = False
            if last_id == -1:
                flag_first = True
                # 최초 실행은 -1로 판단하고, 봇을 설정안했다면 0으로
                query = db.session.query(ModelBotDownloaderKtvItem) \
                    .filter(ModelBotDownloaderKtvItem.created_time > datetime.datetime.now() + datetime.timedelta(days=-1))
                items = query.all()
            else:
                condition = []
                tmp = datetime.datetime.now() - datetime.timedelta(minutes=ModelSetting.get_int('delay_time'))
                #condition.append( and_(ModelBotDownloaderKtvItem.id > last_id, (ModelBotDownloaderKtvItem.created_time + datetime.timedelta(minutes=ModelSetting.get_int('delay_time'))) < datetime.datetime.now() ))
                condition.append( and_( ModelBotDownloaderKtvItem.id > last_id, ModelBotDownloaderKtvItem.created_time < tmp ))
                condition.append( and_(ModelBotDownloaderKtvItem.download_status.like('Delay'), ModelBotDownloaderKtvItem.delay_time < datetime.datetime.now() ))
                query = db.session.query(ModelBotDownloaderKtvItem)
                query = query.filter(or_(*condition))
                items = query.all()

            # 하나씩 판단....
            logger.debug('XXX %s count :%s', last_id, len(items))
            for item in items:
                try:
                    flag_download = False
                    item.download_status = ''
                    item.downloader_item_id = None
                    item.log = ''
                    logger.debug('title:%s daum:%s date:%s no:%s', item.daum_title, item.daum_id, item.filename_date, item.filename_number) 
                    option_auto_download = ModelSetting.get('option_auto_download')

                    if option_auto_download == '0':
                        item.download_status = 'no'
                    else:
                        if item.daum_genre is None:
                            item.download_status = 'False_no_meta'
                        else:
                            LogicNormal.search_plex_data(item)
                            # PLEX
                            if ModelSetting.get_bool('use_plex_data'):
                                flag_download = LogicNormal.condition_check_plex(item)

                            if not flag_download and not item.download_status.startswith('False'):
                                flag_download = LogicNormal.condition_check_download_mode(item, except_genres, whitelist_genres, except_programs, whitelist_programs)

                            if flag_download:
                                flag_download = LogicNormal.condition_check_duplicate(item)

                            if flag_download:
                                flag_download = LogicNormal.condition_check_filename(item)

                            if flag_download:
                                flag_download = LogicNormal.condition_check_delay(item)
                                if flag_download == False and item.download_status == 'Delay':
                                    continue

                            #다운로드
                            if flag_download:
                                if option_auto_download == '1':
                                    import downloader
                                    logger.debug(u'다운로드 요청')
                                    downloader_item_id = downloader.Logic.add_download2(item.magnet, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='', server_id='%s_%s_%s' % (item.server_id, item.file_count, item.total_size))['downloader_item_id']
                                    item.downloader_item_id = downloader_item_id
                                else:
                                    item.download_status = 'True_only_status'
                            else:
                                if option_auto_download == '1':
                                    item.download_status = 'False'
                                else:
                                    item.download_status = 'False_only_status'
                                    
                            if ModelSetting.get_bool('download_start_send_telegram'):
                                flag_notify = True
                                if ModelSetting.get_bool('download_start_send_telegram_only_true'):
                                    if item.download_status != 'True':
                                        flag_notify = False
                                if flag_notify:
                                    LogicNormal.send_telegram_message(item)
                    item.download_check_time =  datetime.datetime.now()                         
                    db.session.add(item)
                except Exception as e: 
                    logger.error('Exception:%s', e)
                    logger.error(traceback.format_exc())

            new_last_id = last_id
            if flag_first and len(items) == 0:
                new_last_id = '0'
            else:
                if len(items) > 0:
                    new_last_id = '%s' % items[len(items)-1].id
            if new_last_id != last_id:
                ModelSetting.set('last_id', str(new_last_id))
            db.session.commit()

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def search_plex_data(item):
        try:
            import plex
            plex_videos = plex.Logic.library_search_show(item.daum_title, item.daum_id)
            if plex_videos is not None and len(plex_videos) > 0:
                for plex_video in plex_videos:
                    item.plex_key = 'P' + plex_video.key
                    episodes = plex_video.episodes()
                    for e in episodes:
                        if e.originallyAvailableAt is not None:
                            tmp = e.originallyAvailableAt.strftime('%Y%m%d')[2:]
                            if tmp == item.filename_date:
                                logger.debug('Episdoe Data:%s %s %s %s', tmp, item.filename_date, e.index, item.filename_number )
                                if (e.index is None and item.filename_number == -1) or (e.index is not None and e.index == item.filename_number):
                                    item.plex_key = 'E' + e.key 
                                    break
            else:
                logger.debug('not exist in PLEX')
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def condition_check_plex(item):
        try:
            flag_download = False
            if item.plex_key is not None:
                if item.plex_key.startswith('E'):
                    logger.debug('PLEX에 에피소드 있음')
                    if ModelSetting.get_bool('one_episode_multifile'):
                        flag_download = True
                        item.download_status = 'True_by_plex_in_lib_multi_epi'
                        item.log += u'PLEX 에피소드 중복 허용으로 다운:On'
                    else:
                        item.download_status = 'False_by_plex_in_one_epi'
                else:
                    logger.debug('PLEX에 에피소드 없음')
                    flag_download = True
                    item.download_status = 'True_by_plex_in_lib_no_epi'
                    item.log += u'PLEX 에피소드 없음으로 다운:On'
            else:
                logger.debug('not exist program in plex')
            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    
    @staticmethod
    def condition_check_download_mode(item, except_genres, whitelist_genres, except_programs, whitelist_programs):
        try:
            if ModelSetting.get('download_mode') == '0':
                flag_download = True
                if len(except_genres) > 0 and item.daum_genre in except_genres:
                    flag_download = False
                    item.download_status = 'False_except_genre'
                    item.log += u'제외 장르. 다운:Off'
                if flag_download:
                    item.download_status = 'True_blacklist'
                    item.log += u'블랙리스트 모드. 다운:On'
                    for program_name in except_programs:
                        if item.daum_title.replace(' ', '').find(program_name) != -1:
                            item.download_status = 'False_except_program'
                            flag_download = False
                            item.log += u'제외 프로그램. 다운:Off'
                            break
            else:
                flag_download = False
                logger.debug(whitelist_genres)
                logger.debug(item.daum_genre)
                if len(whitelist_genres) > 0 and item.daum_genre in whitelist_genres:
                    flag_download = True
                    item.download_status = 'True_whitelist_genre'
                    item.log += u'포함 장르. 다운:On'
                if flag_download == False:
                    item.download_status = 'False_whitelist'
                    item.log += u'화이트리스트 모드. 다운:Off'
                    for program_name in whitelist_programs:
                        if item.daum_title.replace(' ', '').find(program_name) != -1:
                            item.download_status = 'True_whitelist_program'
                            flag_download = True
                            item.log += u'포함 프로그램. 다운:On'
                            break
                if not flag_download and ModelSetting.get_bool('whitelist_first_episode_download'):
                    if item.filename_number is not None and item.filename_number != '':
                        if item.filename_number == 1:
                            if len(whitelist_genres) == 0 or item.daum_genre in whitelist_genres:
                                flag_download = True
                                item.download_status = 'True_whitelist_first_epi'
                                item.log += u'1회차 다운로드 허용. 다운:On'

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download


    @staticmethod
    def condition_check_duplicate(item):
        try:
            # off, on, 화질 향상시
            condition_duplicate_download = ModelSetting.get('condition_duplicate_download')
            if condition_duplicate_download == '1':
                item.log += '\n중복 허용 - 다운:On'
                return True
            query = db.session.query(ModelBotDownloaderKtvItem)
            query = query.filter( \
                ModelBotDownloaderKtvItem.daum_id == item.daum_id, \
                ModelBotDownloaderKtvItem.filename_number == item.filename_number, \
                ModelBotDownloaderKtvItem.filename_date == item.filename_date, \
                ModelBotDownloaderKtvItem.id < item.id)
                # 20-01-31
                # 지연.. 이 후 1080 받음.. 이전데이터는 없기 때문에 받아버림.
                #ModelBotDownloaderKtvItem.id < item.id)
            lists = query.all()
            if len(lists) == 0:
                item.log += '\n중복 에피소드 DB에 없음.'
                return True
            else:
                item.log += '\n중복 에피소드 DB에 있음. count:%s' % len(lists)
            if condition_duplicate_download == '0':
                for tmp in lists:
                    #if tmp.downloader_item_id is not None:
                    if tmp.download_status.startswith('True'):
                        item.download_status = 'False_not_allow_duplicate_episode'
                        item.log += u'\n이미 받은 에피소드가 있음. 다운:Off'
                        return False
                item.log += u'\n이미 받은 에피소드가 없음. 다운:On'
                return True
            elif condition_duplicate_download == '2':
                if item.filename_quality == '':
                    item.log += u'\n화질 정보 없어서 판단하지 않음.'
                    return True
                download_quality_list = []
                for tmp in lists:
                    #if tmp.downloader_item_id is not None:
                    if tmp.download_status.startswith('True'):
                        if tmp.filename_quality not in download_quality_list:
                            download_quality_list.append(tmp.filename_quality)

                download_flag = True
                for t in download_quality_list:
                    if int(item.filename_quality) <=  int(t):
                        download_flag = False
                        break
                if download_flag:
                    item.log += u'\n화질 향상에 의해 다운:On. 받은 화질:%s' % ','.join(download_quality_list)
                    return True
                else:
                    item.download_status = 'False_exist_download_quality'
                    item.log += u'\n화질 향상 없음. 다운:Off. 받은 화질:%s' % ','.join(download_quality_list)
                    return False
           
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return True

    @staticmethod
    def condition_check_filename(item):
        try:
            condition_quality = ModelSetting.get('condition_quality')
            if condition_quality != '' and condition_quality is not None:
                condition_qualitys = [x.strip().replace(' ', '').strip() for x in condition_quality.replace(',', '|').split('|')]
                condition_qualitys = Util.get_list_except_empty(condition_qualitys)
                if item.filename_quality not in condition_qualitys:
                    item.download_status = 'False_not_match_condition_quality'
                    item.log += u'\n화질 조건에 맞지 않음. 다운:Off. 조건:%s' % ','.join(condition_qualitys)
                    return False
            
            condition_include_keyword = ModelSetting.get('condition_include_keyword')
            if condition_include_keyword != '' and condition_include_keyword is not None:
                condition_include_keywords = [x.strip().replace(' ', '').strip() for x in condition_include_keyword.replace('\n', '|').split('|')]
                condition_include_keywords = Util.get_list_except_empty(condition_include_keywords)
                download_flag = False
                for t in condition_include_keywords:
                    if item.filename.find(t) != -1:
                        item.log += u'\n단어 포함 조건 만족 : %s' % t
                        download_flag = True
                        break
                if download_flag == False:
                    item.download_status = 'False_not_match_condition_include_keyword'
                    item.log += u'\n단어 포함 조건에 맞지 않음. 다운:Off. 조건:%s' % ','.join(condition_include_keywords)
                    return False
            
            condition_except_keyword = ModelSetting.get('condition_except_keyword')
            if condition_except_keyword != '' and condition_except_keyword is not None:
                condition_except_keywords = [x.strip().replace(' ', '').strip() for x in condition_except_keyword.replace('\n', '|').split('|')]
                condition_except_keywords = Util.get_list_except_empty(condition_except_keywords)
                for t in condition_except_keywords:
                    if item.filename.find(t) != -1:
                        item.download_status = 'False_match_condition_except_keyword'    
                        item.log += u'\n단어 제외 조건. 다운:Off. 조건:%s' % t
                        return False
                item.log += u'\n단어 제외 조건 해당사항 없음.'

            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return True


    @staticmethod
    def condition_check_delay(item):
        try:
            if ModelSetting.get_bool('use_wait_1080'):
                if item.filename_quality != '1080':
                    if item.created_time + datetime.timedelta(minutes=ModelSetting.get_int('use_wait_1080_time')) > datetime.datetime.now():
                        item.download_status = 'Delay'
                        #item.delay_time = datetime.datetime.now() + datetime.timedelta(minutes=ModelSetting.get_int('use_wait_1080_time'))
                        item.delay_time = item.created_time + datetime.timedelta(minutes=ModelSetting.get_int('use_wait_1080_time'))
                        item.log += u'\n다운로드 지연. 다음 판단시간 : %s' % item.delay_time
                        return False
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return flag_download

    





    @staticmethod
    def send_telegram_message(item):
        try:
            telegram_log = '😉 봇 다운로드 - TV\n'
            telegram_log += '정보 : %s (%s), %s회, %s\n' % (item.daum_title, item.daum_genre, item.filename_number, item.filename_date)
            
            if item.download_status.startswith('True'):
                status_str = '✔요청 '
            elif item.download_status.startswith('False'):
                status_str = '⛔패스 '
            else:
                status_str = '🕛대기 '
            if item.plex_key is not None:
                if item.plex_key.startswith('P'):
                    status_str += '(PLEX 프로그램⭕ 에피소드❌) '
                elif item.plex_key.startswith('E'):
                    status_str += '(PLEX 프로그램⭕ 에피소드⭕) '
            else:
                status_str += '(PLEX 프로그램❌) '
                
            if item.download_status == 'True_by_plex_in_lib_multi_epi':
                status_str += '에피소드 멀티파일'
            elif item.download_status == 'False_by_plex_in_one_epi':
                status_str += '에피소드 이미 있음'
            elif item.download_status == 'True_by_plex_in_lib_no_epi':
                status_str += '에피소드 없음'
            elif item.download_status == 'True_blacklist':
                status_str += '블랙리스트에 없음'
            elif item.download_status == 'False_whitelist':
                status_str += '화이트리스트에 없음'
            elif item.download_status == 'False_except_program':
                status_str += '블랙리스트'
            elif item.download_status == 'True_whitelist_program':
                status_str += '화이트리스트'
            elif item.download_status == 'True_whitelist_first_epi':
                status_str += '첫번째 에피소드'
            elif item.download_status == 'False_no_meta':
                status_str += 'Daum 검색 실패'
            elif item.download_status == 'False_except_genre':
                status_str += '블랙리스트 장르'
            elif item.download_status == 'True_whitelist_genre':
                status_str += '화이트리스트 장르'
            elif item.download_status == 'False_not_allow_duplicate_episode':
                status_str += '중복 제외'
            elif item.download_status == 'False_exist_download_quality':
                status_str += '동일 화질 받음'
            elif item.download_status == 'False_not_match_condition_quality':
                status_str += '화질 조건 불일치'
            elif item.download_status == 'False_not_match_condition_include_keyword':
                status_str += '단어 포함 조건'
            elif item.download_status == 'False_match_condition_except_keyword':
                status_str += '단어 제외 조건'

            telegram_log += '결과 : %s\n' % status_str
            telegram_log += '파일명 : %s\n' % item.filename
            telegram_log += '%s/%s/list\n' % (SystemModelSetting.get('ddns'), package_name)
            #telegram_log += item.download_status + '\n'
            telegram_log += '로그\n' + item.log

            import framework.common.notify as Notify
            Notify.send_message(telegram_log, message_id='bot_downloader_ktv_result')

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())



    @staticmethod
    def add_program(req):
        try:
            except_program = req.form['except_program'].strip() if 'except_program' in req.form else None
            whitelist_program = req.form['whitelist_program'].strip() if 'whitelist_program' in req.form else None
            if except_program is not None:
                entity = db.session.query(ModelSetting).filter_by(key='except_program').with_for_update().first()
                target = except_program
            else:
                entity = db.session.query(ModelSetting).filter_by(key='whitelist_program').with_for_update().first()
                target = whitelist_program
            entity_list = [x.strip().replace(' ', '') for x in entity.value.replace('\n', '|').split('|')]
            logger.debug('except value:%s', entity.value)
            #if entity.value.find(target) != -1:
            if target.replace(' ', '') in entity_list:
                db.session.commit() 
                return 0
            else:
                if entity.value != '':
                    entity.value += '|'
                entity.value += target
                db.session.commit() 
                return 1
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return -1
        finally:
            pass


    @staticmethod
    def add_download(req):
        try:
            import downloader
            db_id = req.form['id']
            item = db.session.query(ModelBotDownloaderKtvItem).filter_by(id=db_id).with_for_update().first()
            downloader_item_id = downloader.Logic.add_download2(item.magnet, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='', server_id='%s_%s_%s' % (item.server_id, item.file_count, item.total_size))['downloader_item_id']
            item.downloader_item_id = downloader_item_id
            item.download_status = 'True_manual_%s' % item.download_status
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    # SJVA.me 웹, 텔레그램
    @staticmethod
    def add_download_api(req):
        ret = {}
        try:
            import downloader
            url = req.args.get('url')
            result = downloader.Logic.add_download2(url, ModelSetting.get('torrent_program'), ModelSetting.get('path'), request_type=package_name, request_sub_type='api')
            return result
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret['ret'] = 'exception'
            ret['log'] = str(e)
        return ret
    
    

    
            
    @staticmethod
    def plex_refresh(db_id):
        try:
            import plex
            item = db.session.query(ModelBotDownloaderKtvItem).filter(ModelBotDownloaderKtvItem.id == db_id).with_for_update().first()
            plex_videos = plex.Logic.library_search_show(item.daum_title, item.daum_id)
            plex_key = item.plex_key
            if plex_videos:
                for plex_video in plex_videos:
                    plex_key = 'P' + plex_video.key
                    episodes = plex_video.episodes()
                    flag_plex_exist_episode = False
                    for e in episodes:
                        if e.originallyAvailableAt is not None:
                            tmp = e.originallyAvailableAt.strftime('%Y%m%d')[2:]
                            if tmp == item.filename_date:
                                logger.debug('Episdoe Data:%s %s %s %s', tmp, item.filename_date, e.index, item.filename_number )
                                if (e.index is None and item.filename_number == -1) or (e.index is not None and e.index == item.filename_number):
                                    logger.debug('flag_plex_exist_episode is True')
                                    flag_plex_exist_episode = True
                                    plex_key = 'E' + e.key 
                                    break
                                else:
                                    logger.debug('flag_plex_exist_episode is False')
                    if flag_plex_exist_episode:
                        break
            logger.debug('item.key :%s, plex_key:%s', item.plex_key, plex_key)
            if plex_key != item.plex_key:
                item.plex_key = plex_key
                db.session.commit()
                return True
            else:
                return False
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'



    @staticmethod
    def share_copy(req):
        try:
            import downloader
            db_id = req.form['id']
            item = db.session.query(ModelBotDownloaderKtvItem).filter_by(id=db_id).with_for_update().first()

            try:
                from gd_share_client.logic_user import LogicUser
            except:
                return {'ret':'fail', 'log':u'구글 드라이브 공유 플러그인이 설치되어 있지 않습니다.'}
            my_remote_path = ModelSetting.get('remote_path')
            if my_remote_path == '':
                return {'ret':'fail', 'log':u'리모트 경로가 설정되어 있지 않습니다.'}
            
            # 백그라운드
            ret = LogicUser.torrent_copy(item.folderid, '', '', my_remote_path=my_remote_path)
            item.download_status = 'True_manual_gd_%s' % item.download_status
            db.session.commit()
            return {'ret':'success'}
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    

    
    