# -*- coding: utf-8 -*-
#########################################################
# python
import traceback
from datetime import datetime
import json
import os

# third-party
from sqlalchemy import or_, and_, func, not_, desc
from sqlalchemy.orm import backref

# sjva 공용
from framework import app, db, path_app_root
from framework.util import Util


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
    
    # 3 버전 추가
    folderid = db.Column(db.String)

    # 4 버전 추가
    folderid_time = db.Column(db.DateTime)
    # 5 버전 추가
    share_copy_time = db.Column(db.DateTime)

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
        ret['folderid_time'] = self.folderid_time.strftime('%m-%d %H:%M:%S') if self.folderid_time is not None  else None
        ret['share_copy_time'] = self.share_copy_time.strftime('%m-%d %H:%M:%S') if self.share_copy_time is not None  else None
        return ret
    
    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


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
            # 2020-08-03 동일 파일명 수신하지 않음.
            entity = db.session.query(ModelBotDownloaderKtvItem).filter_by(filename=data['filename']).first()
            if entity is not None:
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

    @staticmethod
    def filelist(req):
        try:
            ret = {}
            page = 1
            page_size = ModelSetting.get_int('web_page_size')
            job_id = ''
            search = ''
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'search_word' in req.form:
                search = req.form['search_word']
            option = req.form['option']
            order = req.form['order'] if 'order' in req.form else 'desc'

            query = ModelBotDownloaderKtvItem.make_query(search, option, order)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            logger.debug('ModelBotDownloaderKtvItem count:%s', count)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def make_query(search, option, order, genre=None, server_id_mod=None):
        query = db.session.query(ModelBotDownloaderKtvItem)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(ModelBotDownloaderKtvItem.filename.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(ModelBotDownloaderKtvItem.filename.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(or_(ModelBotDownloaderKtvItem.filename.like('%'+search+'%'), ModelBotDownloaderKtvItem.daum_title == search))

        if genre is not None and genre != '':
            if genre.find('|') != -1:
                tmp = genre.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(ModelBotDownloaderKtvItem.daum_genre.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif genre.find(',') != -1:
                tmp = genre.split(',')
                for tt in tmp:
                    if tt != '':
                        query = query.filter(ModelBotDownloaderKtvItem.daum_genre.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(or_(ModelBotDownloaderKtvItem.daum_genre.like('%'+genre+'%'), ModelBotDownloaderKtvItem.daum_genre == genre))

        
        if option == 'request_True':
            query = query.filter(ModelBotDownloaderKtvItem.download_status.like('True%'))
        elif option == 'request_False':
            query = query.filter(ModelBotDownloaderKtvItem.download_status.like('False%'))
        elif option == 'by_plex_on':
            query = query.filter(ModelBotDownloaderKtvItem.plex_key != None)
        elif option == 'by_plex_off':
            query = query.filter(ModelBotDownloaderKtvItem.plex_key == None)
        elif option == 'by_plex_episode_off':
            query = query.filter(ModelBotDownloaderKtvItem.plex_key != None)
            query = query.filter(not_(ModelBotDownloaderKtvItem.plex_key.like('E%')))
        if order == 'desc':
            query = query.order_by(desc(ModelBotDownloaderKtvItem.id))
        else:
            query = query.order_by(ModelBotDownloaderKtvItem.id)

        if server_id_mod is not None and server_id_mod != '':
            tmp = server_id_mod.split('_')
            if len(tmp) == 2:
                query = query.filter(ModelBotDownloaderKtvItem.server_id % int(tmp[0]) == int(tmp[1]))


        return query


            
    @staticmethod
    def itemlist_by_api(req):
        try:
            search = req.args.get('search')
            logger.debug(search)
            option = req.args.get('option')
            order = 'desc'
            genre = req.args.get('genre')
            count = req.args.get('count')
            if count is None or count == '':
                count = 100
            server_id_mod = req.args.get('server_id_mod')
            query = ModelBotDownloaderKtvItem.make_query(search, option, order, genre=genre, server_id_mod=server_id_mod)
            query = query.limit(count)
            lists = query.all()
            return lists
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def remove(db_id):
        try:
            entity = db.session.query(ModelBotDownloaderKtvItem).filter(ModelBotDownloaderKtvItem.id == db_id).first()
            db.session.delete(entity)
            db.session.commit()
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def receive_share_data(data):
        try:
            query = db.session.query(ModelBotDownloaderKtvItem).filter(ModelBotDownloaderKtvItem.server_id == int(data['server_id']))
            query = query.filter(ModelBotDownloaderKtvItem.magnet.like('%'+ data['magnet_hash']))
            entity = query.with_for_update().first()
            
            if entity is not None:
                #logger.debug(entity)
                if entity.folderid != '':
                    return True
                entity.folderid = data['folderid']
                entity.folderid_time = datetime.now()
                db.session.commit()
                from .logic_normal import LogicNormal
                LogicNormal.process_gd(entity)
                return True
            return False
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
    
