# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
import threading

# third-party

# sjva 공용
from framework import db, scheduler, path_app_root
from framework.job import Job
from framework.util import Util

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelBotDownloaderKtvItem
from .logic_normal import LogicNormal
#########################################################

class Logic(object):
    db_default = {
        'interval' : '30',
        'auto_start' : 'False',
        'web_page_size': '20',
        'torrent_program' : '0',
        'path' : '',
        'download_mode' : '1',  #블랙, 화이트
        'except_program' : '',
        'whitelist_program' : '',
        'whitelist_first_episode_download' : 'True', 

        'use_plex_data' : 'True',
        'one_episode_multifile' : 'False',
        
        'telegram_invoke_action' : '1', 

        #'send_telegram' : 'True', 
        'receive_info_send_telegram' : 'False', 
        'download_start_send_telegram' : 'False',
        'condition_quality' : '720|1080',
        'whitelist_genre' : '',
        'except_genre' : '',
        'condition_duplicate_download' : '0', #off, on, 화질 향상시
        'use_wait_1080' : 'Fasle',
        'use_wait_1080_time' : '300',
        'condition_include_keyword' : '',
        'condition_except_keyword' : '', 
        'last_id' : '-1', 
        'db_version' : '2', 
        'delay_time' : '0'

    }

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
            
            Logic.migration()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        
    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            Logic.db_init()
            if ModelSetting.query.filter_by(key='auto_start').first().value == 'True':
                Logic.scheduler_start()
            # 편의를 위해 json 파일 생성
            from plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def scheduler_start():
        try:
            logger.debug('%s scheduler_start' % package_name)
            job = Job(package_name, package_name, ModelSetting.get('interval'), Logic.scheduler_function, u"Bot 다운로드 - TV", False)
            scheduler.add_job_instance(job)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def scheduler_stop():
        try:
            logger.debug('%s scheduler_stop' % package_name)
            scheduler.remove_job(package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
           

    @staticmethod
    def scheduler_function():
        try:
            LogicNormal.scheduler_function()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def reset_db():
        try:
            db.session.query(ModelBotDownloaderKtvItem).delete()
            db.session.commit()
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False


    @staticmethod
    def one_execute():
        try:
            if scheduler.is_include(package_name):
                if scheduler.is_running(package_name):
                    ret = 'is_running'
                else:
                    scheduler.execute_job(package_name)
                    ret = 'scheduler'
            else:
                def func():
                    time.sleep(2)
                    Logic.scheduler_function()
                threading.Thread(target=func, args=()).start()
                ret = 'thread'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret


    @staticmethod
    def process_telegram_data(data):
        try:
            logger.debug(data)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def migration():
        try:
            db_version = ModelSetting.get('db_version')
            if db_version is None:
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_item ADD download_check_time DATETIME' % (package_name)
                cursor.execute(query)
                query = 'ALTER TABLE %s_item ADD delay_time DATETIME' % (package_name)
                cursor.execute(query)
                connection.close()
                db.session.add(ModelSetting('db_version', '1'))
                db.session.commit()
                db.session.flush()
            if ModelSetting.get('db_version') == '1':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                query = 'ALTER TABLE %s_item ADD log VARCHAR' % (package_name)
                cursor.execute(query)
                connection.close()
                ModelSetting.set('db_version', '2')
                db.session.flush()
            
            # db_version 이 아예 없으면 2로 들어가 버린다. 당분간만
            if ModelSetting.get('db_version') == '2':
                import sqlite3
                db_file = os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name)
                connection = sqlite3.connect(db_file)
                cursor = connection.cursor()
                change = False
                try:
                    query = 'ALTER TABLE %s_item ADD download_check_time DATETIME' % (package_name)
                    cursor.execute(query)
                    query = 'ALTER TABLE %s_item ADD delay_time DATETIME' % (package_name)
                    cursor.execute(query)
                    change = True
                except:
                    pass

                try:
                    query = 'ALTER TABLE %s_item ADD log VARCHAR' % (package_name)
                    cursor.execute(query)
                    change = True
                except:
                    pass
                connection.close()
               
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())