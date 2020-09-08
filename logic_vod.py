# -*- coding: utf-8 -*-
#########################################################
# python
import os, sys, traceback, re, json, threading, urllib, datetime, time
# third-party
import requests
# third-party
from flask import request, render_template, jsonify, Response
from sqlalchemy import or_, and_, func, not_, desc
# sjva 공용
from framework import app, db, scheduler, path_data, socketio, SystemModelSetting
from framework.util import Util
from framework.common.plugin import LogicModuleBase
# 패키지
from .plugin import P
sub_name = 'vod'
#########################################################
class LogicVod(LogicModuleBase):
    db_default = {
        'vod_db_version' : '1',
        'vod_download_mode' : '0', #Nothing, 모두받기, 블랙, 화이트
        'vod_blacklist_genre' : '',
        'vod_blacklist_program' : '',
        'vod_whitelist_genre' : '',
        'vod_whitelist_program' : '',
        'vod_remote_path' : '',
    }
    
    def __init__(self, P):
        super(LogicVod, self).__init__(P, 'setting')
        self.name = sub_name


    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        arg['sub'] = self.name
        if sub == 'setting':
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        elif sub == 'list':
            return render_template('{package_name}_{module_name}_{sub}.html'.format(package_name=P.package_name, module_name=self.name, sub=sub), arg=arg)
        return render_template('sample.html', title='%s - %s' % (P.package_name, sub))


    def process_ajax(self, sub, req):
        if sub == 'reset_last_index':
            P.ModelSetting.set('last_id', '-1')
            return jsonify(True)
        elif sub == 'web_list':
            ret = ModelBotDownloaderKtvVodItem.web_list(request)
            return jsonify(ret)
        elif sub == 'option_process':
            mode = req.form['mode']
            value = req.form['value']
            value_list = P.ModelSetting.get_list('vod_%s' % mode, '|')
            if value in value_list:
                ret = 'already'
            else:
                if len(value_list) == 0:
                    P.ModelSetting.set('vod_%s' % mode, value)
                else:
                    P.ModelSetting.set('vod_%s' % mode, P.ModelSetting.get('vod_%s' % mode) + ' | ' + value)
                ret = 'success'
            return jsonify(ret)
        elif sub == 'share_copy':
            db_id = req.form['id']
            item = ModelBotDownloaderKtvVodItem.get_by_id(db_id)
            ret = self.share_copy(item)
            if item is not None:
                item.save()
            return jsonify(ret)


    def process_telegram_data(self, data, target=None):
        try:
            if target is None:
                return
            item = ModelBotDownloaderKtvVodItem.process_telegram_data(data)
            if item is None:
                return
            flag_download = self.condition_check_download_mode(item)
            if flag_download:
                self.share_copy(item)
        except Exception as e:
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        finally:
            if item is not None:
                item.save()


    def condition_check_download_mode(self, item):
        try:
            vod_download_mode = P.ModelSetting.get('vod_download_mode')
            if vod_download_mode == '0':
                return False
            
            if vod_download_mode == '1':
                flag_download = True
                if item.daum_title is None:
                    item.log += u'Daum 정보 없음. 다운:On'
                    return flag_download
                vod_blacklist_genre = P.ModelSetting.get_list('vod_blacklist_genre', '|')
                vod_blacklist_program = P.ModelSetting.get_list('vod_blacklist_program', '|')

                if len(vod_blacklist_genre) > 0 and item.daum_genre in vod_blacklist_genre:
                    flag_download = False
                    item.log += u'제외 장르. 다운:Off'

                if flag_download:
                    for program_name in vod_blacklist_program:
                        if item.daum_title.replace(' ', '').find(program_name.replace(' ', '')) != -1:
                            flag_download = False
                            item.log += u'제외 프로그램. 다운:Off'
                            break
                if flag_download:
                    item.log += u'블랙리스트 모드. 다운:On'
            else:
                flag_download = False
                if item.daum_title is None:
                    item.log += u'Daum 정보 없음. 다운:Off'
                    return flag_download
                vod_whitelist_genre = P.ModelSetting.get_list('vod_whitelist_genre', '|')
                vod_whitelist_program = P.ModelSetting.get_list('vod_whitelist_program', '|')

                if len(vod_whitelist_genre) > 0 and item.daum_genre in vod_whitelist_genre:
                    flag_download = True
                    item.log += u'포함 장르. 다운:On'
                if flag_download == False:
                    for program_name in vod_whitelist_program:
                        if item.daum_title.replace(' ', '').find(program_name.replace(' ', '')) != -1:
                            flag_download = True
                            item.log += u'포함 프로그램. 다운:On'
                            break
                if not flag_download:
                    item.log += u'화이트리스트 모드. 다운:Off'
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
        return flag_download


    def share_copy(self, item):
        try:
            vod_remote_path = P.ModelSetting.get('vod_remote_path')
            if vod_remote_path == '':
                return 'no_remote_path'
            try:
                from gd_share_client.logic_user import LogicUser
            except:
                return 'no_gd_share_client'
            ret = LogicUser.vod_copy(item.fileid, vod_remote_path)
            item.share_request_time = datetime.datetime.now()
            return 'request'
        except Exception as e:
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
    


class ModelBotDownloaderKtvVodItem(db.Model):
    __tablename__ = '%s_%s_item' % (P.package_name, sub_name)
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = P.package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    share_request_time = db.Column(db.DateTime)
    share_completed_time = db.Column(db.DateTime)
    data = db.Column(db.JSON)
    fileid = db.Column(db.String)
    filename = db.Column(db.String)
    size = db.Column(db.Integer)
    filename_name = db.Column(db.String)
    filename_number = db.Column(db.Integer)
    filename_release = db.Column(db.String)
    filename_filename_rule = db.Column(db.String)
    filename_date = db.Column(db.String)
    filename_quality = db.Column(db.String)
    daum_genre = db.Column(db.String)
    daum_id = db.Column(db.String)
    daum_title = db.Column(db.String)
    daum_poster_url = db.Column(db.String)
    log = db.Column(db.String)


    def __init__(self):
        self.created_time = datetime.datetime.now()
        self.log = ''
        
    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S') 
        ret['share_request_time'] = self.share_request_time.strftime('%m-%d %H:%M:%S') if self.share_request_time is not None  else None
        ret['share_completed_time'] = self.share_completed_time.strftime('%m-%d %H:%M:%S') if self.share_completed_time is not None  else None
        return ret
    
    def save(self):
        try:
            db.session.add(self)
            db.session.commit()
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())

    @classmethod
    def process_telegram_data(cls, data):
        try:
            entity = db.session.query(cls).filter_by(filename=data['f']).first()
            if entity is not None:
                return
            entity =  ModelBotDownloaderKtvVodItem()
            entity.data = data
            entity.fileid = data['id']
            entity.filename = data['f']
            entity.size = data['s']

            entity.filename_name = data['ktv']['name']
            entity.filename_number = data['ktv']['number']
            entity.filename_release = data['ktv']['release']
            entity.filename_rule = data['ktv']['filename_rule']
            entity.filename_date =  data['ktv']['date']
            entity.filename_quality = data['ktv']['quality']

            if data['daum'] is not None:
                entity.daum_genre = data['daum']['genre']
                entity.daum_id = data['daum']['daum_id']
                entity.daum_title = data['daum']['title']
                entity.daum_poster_url = data['daum']['poster_url']
            else:
                entity.daum_genre = u'미분류'
            #entity.save()
            return entity
        except Exception as e:
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())   

    @classmethod
    def web_list(cls, req):
        try:
            ret = {}
            page = 1
            page_size = 30
            search = ''
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'search_word' in req.form:
                search = req.form['search_word']
            option = req.form['option'] if 'option' in req.form else None
            order = req.form['order'] if 'order' in req.form else 'desc'
            query = cls.make_query(search, option, order)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception, e:
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
    
    @classmethod
    def make_query(cls, search, option, order):
        query = db.session.query(cls)
        if search is not None and search != '':
            if search.find('|') != -1:
                tmp = search.split('|')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        conditions.append(cls.filename.like('%'+tt.strip()+'%') )
                        conditions.append(cls.daum_title.like('%'+tt.strip()+'%') )
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                tmp = search.split(',')
                conditions = []
                for tt in tmp:
                    if tt != '':
                        query = query.filter(or_(cls.filename.like('%'+tt.strip()+'%'), cls.daum_title.like('%'+tt.strip()+'%')))
            else:
                query = query.filter(or_(cls.filename.like('%'+search+'%'), cls.daum_title.like('%'+search+'%')))

        if option == 'request_true':
            query = query.filter(cls.share_request_time != None)
        elif option == 'request_false':
            query = query.filter(cls.share_request_time == None)
        
        if order == 'desc':
            query = query.order_by(desc(cls.id))
        else:
            query = query.order_by(cls.id)
        return query

    @classmethod
    def remove(cls, db_id):
        try:
            entity = db.session.query(cls).filter(cls.id == db_id).first()
            db.session.delete(entity)
            db.session.commit()
            return True
        except Exception as e: 
            P.logger.error('Exception:%s', e)
            P.logger.error(traceback.format_exc())
            return False

    @classmethod
    def get_by_id(cls, id):
        return db.session.query(cls).filter_by(id=id).first()
