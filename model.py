# -*- coding: utf-8 -*-
#########################################################
# python
import traceback
from datetime import datetime
import json
import os

# third-party
from sqlalchemy import or_, and_, func, not_
from sqlalchemy.orm import backref

# sjva 공용
from framework import app, db, path_app_root


# 패키지
from .plugin import logger, package_name
from downloader import ModelDownloaderItem

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))
#########################################################
        
class ModelSetting(db.Model):
    __tablename__ = '%s_setting' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)
 
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    @staticmethod
    def get(key):
        try:
            return db.session.query(ModelSetting).filter_by(key=key).first().value.strip()
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
            
    
    @staticmethod
    def get_int(key):
        try:
            return int(ModelSetting.get(key))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def get_bool(key):
        try:
            return (ModelSetting.get(key) == 'True')
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def set(key, value):
        try:
            item = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
            if item is not None:
                item.value = value.strip()
                db.session.commit()
            else:
                db.session.add(ModelSetting(key, value.strip()))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def to_dict():
        try:
            from framework.util import Util
            return Util.db_list_to_dict(db.session.query(ModelSetting).all())
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())


    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                if key in ['scheduler', 'is_running']:
                    continue
                logger.debug('Key:%s Value:%s', key, value)
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True                  
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            logger.debug('Error Key:%s Value:%s', key, value)
            return False


class ModelBotDownloaderKtvItem(db.Model):
    __tablename__ = '%s_item' % package_name 
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    # 수신받은 데이터 전체
    data = db.Column(db.JSON)

    # 토렌트 정보
    filename = db.Column(db.String)
    magnet = db.Column(db.String)
    file_count = db.Column(db.Integer)
    total_size = db.Column(db.Integer)
    files = db.Column(db.JSON)
    
    # 파일처리 정보
    filename_rule = db.Column(db.String)
    filename_name = db.Column(db.String)
    filename_number = db.Column(db.Integer)
    filename_release = db.Column(db.String)
    filename_date = db.Column(db.String)
    filename_quality = db.Column(db.String)

    # 메타
    daum_genre = db.Column(db.String)
    daum_id = db.Column(db.String)
    daum_title = db.Column(db.String)
    daum_poster_url = db.Column(db.String)

    # 다운로드 정보
    download_status = db.Column(db.String)
    plex_key = db.Column(db.String)
    
    downloader_item_id = db.Column(db.Integer, db.ForeignKey('plugin_downloader_item.id'))
    downloader_item = db.relationship('ModelDownloaderItem')

    # 1 버전 추가
    download_check_time = db.Column(db.DateTime)
    delay_time = db.Column(db.DateTime)

    # 2 버전 추가
    log = db.Column(db.String)

    # 3 버전 추가
    server_id = db.Column(db.Integer)

    def __init__(self):
        self.created_time = datetime.now()
        self.download_status = ''
        
    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        ret['download_check_time'] = self.download_check_time.strftime('%m-%d %H:%M:%S') if self.download_check_time is not None  else None
        ret['delay_time'] = self.delay_time.strftime('%m-%d %H:%M:%S') if self.delay_time is not None  else None
        ret['downloader_item'] = self.downloader_item.as_dict() if self.downloader_item is not None else None
        return ret
    
    
    @staticmethod
    def process_telegram_data(data):
        try:
            magnet = 'magnet:?xt=urn:btih:' + data['hash']
            entity = db.session.query(ModelBotDownloaderKtvItem).filter_by(magnet=magnet).first()
            # 수동 방송은 어떻게 해야할까..
            if data['broadcast_type'] == 'auto':
                if entity is not None:
                    return
            else:
                # 수동 방송 장르가 꼭 있는 걸로 가정
                if entity is not None:
                    if entity.daum_genre == data['daum']['genre']:
                        # 같은 마그넷, 같은 장르라면 패스
                        return
            entity =  ModelBotDownloaderKtvItem()
            entity.server_id = data['server_id']
            entity.data = data

            entity.filename = data['filename']
            entity.magnet = magnet
            entity.file_count = data['file_count']
            entity.total_size = data['total_size']
            entity.files = data['files']
            entity.filename_rule = data['ktv']['filename_rule']
            entity.filename_name = data['ktv']['name']
            entity.filename_number = data['ktv']['number']
            entity.filename_release = data['ktv']['release']
            entity.filename_date =  data['ktv']['date']
            entity.filename_quality = data['ktv']['quality']
            if data['daum'] is not None:
                entity.daum_genre = data['daum']['genre']
                entity.daum_id = data['daum']['daum_id']
                entity.daum_title = data['daum']['title']
                entity.daum_poster_url = data['daum']['poster_url']
            else:
                entity.daum_genre = u'미분류'
            db.session.add(entity)
            db.session.commit()
            return entity
        except Exception as e:
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())   

    @staticmethod
    def make_etc_genre():
        try:
            items = db.session.query(ModelBotDownloaderKtvItem).filter(ModelBotDownloaderKtvItem.daum_genre == None).with_for_update().all()
            logger.debug('Empty genre len :%s', len(items))
            for item in items:
                item.daum_genre = u'미분류'
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())   
        return False
        