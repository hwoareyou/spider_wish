# -*- coding: utf-8 -*-
# @Author   : liu
# 加入日志
from selenium.webdriver import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium import webdriver
import time
import json,re,os,urllib.request,datetime,random,requests,sys,socket
from lxml import etree
from mysql_utils.mysql_db import MysqlDb
from baidu_OCR import recognition_character
import threading
from threading import Thread
from queue import Queue
from tengxun_OCR import Ocr
from selenium.webdriver.chrome.options import Options
from log_utils.mylog import Mylog
from PIL import Image
import traceback
import warnings
warnings.filterwarnings('ignore')


class ThreadClawerWish(Thread):

    def __init__(self, i, product_link_queue, product_info_queue, user_id):
        '''
        :param i: 线程编号
        :param product_link_queue:商品链接队列
        :param product_info_queue: 商品信息队列
        :param user_id: 用户id
        '''
        Thread.__init__(self)
        self.user_id = user_id
        self.mysql = MysqlDb()
        self.threadName = '采集线程' + str(i)
        self.product_link_queue = product_link_queue
        self.product_info_queue = product_info_queue

        pass

    # 解析提取商品数据
    def __parseProduct__(self, product_data):
        try:
            product_info = {}
            data = product_data['data']
            # 商品卖家
            seller_name = data['contest']['merchant_info']['title']
            product_info['seller_name'] = seller_name
            # 商品链接
            # web_url = data['app_indexing_data']['web_url']
            web_url = data['contest']['permalink']
            product_info['product_url'] = web_url
            # 商品id
            product_id = data['contest']['id']
            product_info['product_id'] = product_id
            # 商品名称
            name = data['contest']['name']
            product_info['product_name'] = name
            # 商品价格
            # price = str(int(data['contest']['localized_value']['localized_value'])) + data['contest']['localized_value']['currency_code']
            price = str(
                int(data['contest']['commerce_product_info']['variations'][0]['localized_price']['localized_value'])) \
                    + data['contest']['commerce_product_info']['variations'][0]['localized_price']['currency_code']
            product_info['product_price'] = price
            # 商品主图
            contest_page_picture = data['contest']['contest_page_picture']
            product_info['img_url'] = contest_page_picture
            # 商品图片
            extra_photo_urls = data['contest']['extra_photo_urls']
            extra_photo_urls = {item[0]: item[1].replace('small', 'large') for item in extra_photo_urls.items()}
            extra_photo_urls['0'] = contest_page_picture
            product_info['img_urls'] = extra_photo_urls
            # 商品关键词
            keywords = data['contest']['keywords'].split(',')
            product_info['keywords'] = keywords
            # 浏览量
            num_entered = data['contest']['num_entered']
            product_info['num_entered'] = num_entered
            # 商品描述
            description = data['contest']['description']
            product_info['description'] = description
            # 成交量
            num_bought = data['contest']['num_bought']
            product_info['num_bought'] = num_bought
            # 评论数
            comments = int(data['contest']['product_rating']['rating_count'])
            product_info['comments'] = comments
            # 星级
            grade_star = data['contest']['product_rating']['rating']
            product_info['grade_star'] = str(round(grade_star, 1))

            # 商品属性列表
            product_attr_list = data['contest']['commerce_product_info']['variations']
            attr_data_list = []
            for attr_data in product_attr_list:
                try:
                    attr_id = attr_data['variation_id']
                    attr_color = attr_data['color']
                    attr_size = attr_data['size']
                    attr_price = str(int(attr_data['localized_price']['localized_value'])) + attr_data['localized_price']['currency_code']
                    attr_photo_id = attr_data['sequence_id']
                    if str(attr_photo_id) in list(extra_photo_urls.keys()):
                        attr_photo_url = extra_photo_urls[str(attr_photo_id)]
                    else:
                        attr_photo_url = extra_photo_urls['0']
                    attr_data_list.append({'attr_id': attr_id, 'attr_color': attr_color, 'attr_size': attr_size, 'attr_price': attr_price,'attr_photo_url': attr_photo_url})
                except Exception as err:
                    mylog.logs().exception(sys.exc_info())
                    traceback.print_exc()
            product_info['attr_data_list'] = attr_data_list

            print('商品信息：', product_info['product_id'], product_info['product_name'])
            return product_info

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    def __get_proxy__(self):

        # 代理服务器
        proxyHost = "http-dyn.abuyun.com"
        proxyPort = "9020"

        # 代理隧道验证信息
        proxyUser = "HIL217ZFCDHGJ6FD"
        proxyPass = "1375697BCADCD8BB"

        proxyMeta = "http://%(user)s:%(pass)s@%(host)s:%(port)s" % {
            "host": proxyHost,
            "port": proxyPort,
            "user": proxyUser,
            "pass": proxyPass,
        }

        proxies = {
            "http": proxyMeta,
            # "https": proxyMeta,
        }

        return proxies

    # 通过requests请求数据
    def __request__(self, product_link):
        try:
            cid = re.search(r'product/(.+)\?', product_link).group(1)
            headers = {
                "Host": "www.wish.com",
                "Connection": "keep-alive",
                "X-XSRFToken": "2|c48166c9|5f6f2ebb7dc12d445fa95c63cc87a39b|1566265590",
                "Upgrade-Insecure-Requests": "1",
                # "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 OPR/26.0.1656.60",
                "User-Agent": get_useragent(),
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.wish.com",
                "Content-Type": "application/x-www-form-urlencoded",
                # "Referer": "https://www.wish.com/feed/tabbed_feed_latest/product/5cad47469b83af6034a11c5e?&source=tabbed_feed_latest",
                "Referer": product_link,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cookie": "_is_desktop=true; _xsrf=2|c48166c9|5f6f2ebb7dc12d445fa95c63cc87a39b|1566265590; _ga=GA1.2.406530318.1566265597; _gid=GA1.2.67780578.1566265597; _gat_gtag_UA_27166730_24=1; G_ENABLED_IDPS=google; logged_out_locale=en; bsid=3dcfaf071f234207871e133c21937608; _fbp=fb.1.1566265601515.112966423; notice_preferences=2:; notice_gdpr_prefs=0,1,2:; _timezone=8; sweeper_uuid=64d942f1358d4f7ab0f933412ffe588e"
            }

            post_data = {
                "cid": cid,
                "do_not_track": "false",
                "request_sizing_chart_info": "true",
            }

            url = 'https://www.wish.com/api/product/get'

            try:
                res = requests.post(url, headers=headers, data=post_data, verify=False ,timeout=30)
            except:
                count = 1
                while count <= 5:
                    try:
                        res = requests.post(url, headers=headers, data=post_data, verify=False ,timeout=30)
                        break
                    except:
                        err_info = '__request__ reloading for %d time' % count if count == 1 else '__request__ reloading for %d times' % count
                        print(err_info)
                        count += 1
                if count > 5:
                    print("__request__ job failed!")
                    return

            return res.json()

        except:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 查询商品
    def __query_product__(self, product_id):

        sql = 'select id from amazonshop_goods WHERE ASIN = \'%s\' ' % product_id
        res = self.mysql.select(sql)
        if res:
            return True
        else:
            return False
        pass

    # 商品数据采集
    def clawer(self, product_link):
        try:

            print('正在采集商品：', product_link)
            time.sleep(random.randint(1,3))
            data = self.__request__(product_link)
            product_info = self.__parseProduct__(data)
            # 查询库中是否有该商品的数据
            flag = self.__query_product__(product_info['product_id'])
            if not flag:
                product_info = self.__save_img__(product_info)
                self.product_info_queue.put(product_info)
            else:
                print('商品已存在：{product_id:%s}' % product_info['product_id'])

        except:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 保存图片
    def __save_img__(self, product_info):
        try:
            product_id = product_info['product_id']
            # 主体图片
            # product_img = product_info['img_url']
            product_img_list = product_info['img_urls']
            # 变体数据
            att_data_list = product_info['attr_data_list']

            # dir = os.getcwd().replace('spider1', '') + '/static/media/img/'
            dir = os.getcwd().replace('utils','') +  '/amazon1/amazon/amazon/static/media/img/' + str(product_id) + '/'
            if not os.path.exists(dir):
                os.makedirs(dir)

            # 主体
            img_list = []
            # img_list.append({'img_url': product_img, 'img_dir': dir + '0' + '.jpg'})
            for img_i,img_url in product_img_list.items():
                img_dir = dir + img_i + '.jpg'
                img_list.append({'img_url': img_url, 'img_dir': img_dir})

            product_info['img_dir'] = dir + '0' + '.jpg'

            # 变体
            att_img_list = []
            attr_data_list = []
            for img_data in att_data_list:
                attr_id = img_data['attr_id']
                img_dir = dir + attr_id + '.jpg'
                att_imgUrl = img_data['attr_photo_url']
                if att_imgUrl:
                    att_img_list.append({'img_url':att_imgUrl,'img_dir':img_dir})
                img_data['img_dir'] = img_dir
                attr_data_list.append(img_data)

            product_info['attr_data_list'] = attr_data_list

            # 设置超时时间为30s(解决下载不完全问题且避免陷入死循环)
            socket.setdefaulttimeout(30)
            for img_data in (img_list + att_img_list):
                img_url = img_data['img_url']
                img_dir = img_data['img_dir']
                try:
                    urllib.request.urlretrieve(img_url, img_dir)
                except:
                    count = 1
                    while count <= 5:
                        try:
                            urllib.request.urlretrieve(img_url, img_dir)
                            break
                        except:
                            err_info = '__save_img__ reloading for %d time' % count if count == 1 else '__save_img__ reloading for %d times' % count
                            print(err_info)
                            count += 1
                    if count > 5:
                        print("__save_img__ job failed!")
                        print(img_url)

            return product_info

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    def run(self):

        print('启动：', self.threadName)
        while not flag_clawer:
            try:
                product_link = self.product_link_queue.get(timeout=3)
            except:
                time.sleep(3)
                continue
            self.clawer(product_link)
        print('退出：', self.threadName)
        self.mysql.close()


class ThreadParse(Thread):

    def __init__(self, i, user_id, product_info_queue, product_total, url, source):
        Thread.__init__(self)
        self.user_id = user_id
        self.source = source
        self.url = url
        self.product_total = product_total
        self.mysql = MysqlDb()
        self.threadName = '解析线程' + str(i)
        self.product_info_queue = product_info_queue

    # 将商品的排名信息写入排名表
    def __save_categorySalesRank__(self, productId, categorySalesRank, type):
        '''
        :param productId: 商品ID(goods表中id)
        :param categorySalesRank: 商品排名信息，list类型（[(排名1，类别1),(排名2，类别2)...]）
        :return:
        '''
        try:
            if type == 1:
                sql = 'insert ignore into amazonshop_categoryrank (good_id, ranking, sort) values (%s, %s, %s)'
                # sql = 'insert into amazonshop_categoryrank (good_id, ranking, sort) SELECT %s,\'%s\',\'%s\'  FROM  dual' \
                #       ' WHERE  NOT  EXISTS (SELECT id FROM amazonshop_categoryrank WHERE good_id = %s AND sort = \'%s\' )' % ()

            elif type == 2:
                sql = 'insert ignore into amazonshop_attrcategoryrank (good_attr_id, ranking, sort) values (%s, %s, %s)'

            value = []
            for data in categorySalesRank:
                value.append((productId,) + data)
            self.mysql.insert(sql, value)
        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 将属性及属性值信息写入属性表（属性分类表、属性分类值表）
    def __save_dimensions__(self, dimension, dimensionValues):
        '''
        :param dimension: 商品的属性名称（如color、size）,str类型
        :param dimensionValues: 商品的属性值（如color的属性值有red、black、white）,list类型([])
        :return: 返回属性值的id（属性分类值表的id），list类型
        '''
        try:
            if 'Size' in dimension:
                export_name = 'size'
            elif 'Color' in dimension:
                export_name = 'color'
            elif 'Length' in dimension:
                export_name = 'size'
            elif 'Width' in dimension:
                export_name = 'size'
            elif 'Height' in dimension:
                export_name = 'size'
            else:
                export_name = ''

            # 写入属性信息
            sql = 'insert into amazonshop_attrcategory (attr_name,export_name) select \"%s\",\"%s\" from dual WHERE NOT  EXISTS  (SELECT id from amazonshop_attrcategory WHERE attr_name = \"%s\" ) ' % (
                dimension, export_name, dimension)
            cur = self.mysql.mysql.cursor()
            cur.execute(sql)
            cur.execute('commit')

            # 写入属性值信息
            sql = 'SELECT id FROM amazonshop_attrcategory WHERE attr_name = \"%s\" ' % dimension
            attr_id = self.mysql.select(sql)[0]['id']
            value = [(attr_id, dimensionValues)]
            sql = 'insert ignore into amazonshop_attrcategoryvalue (attrcategory_id, attr_value) values (%s,%s)'
            self.mysql.insert(sql, value)
            sql = 'SELECT id FROM amazonshop_attrcategoryvalue WHERE attrcategory_id = \"%s\" AND attr_value = \"%s\" ' % (attr_id, dimensionValues)
            attr_value_id = self.mysql.select(sql)[0]['id']

            # 关闭游标
            cur.close()
            return attr_value_id

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 将属性值组合信息写入商品属性表
    def __save_dimensionValues__(self, productId, product_info):
        '''
        :param productId: 商品ID（goods表中的id）
        :param product_info: 商品变体的信息，dict类型
        :return:
        '''
        try:
            attr_data_list = product_info['attr_data_list']
            for attr_data in attr_data_list:
                img_dir = '/static' + attr_data['img_dir'].split('static')[1]
                attr_tuple = ()
                attr_color = attr_data['attr_color']
                if attr_color:
                    attr_value_id = self.__save_dimensions__('Color', attr_color)
                    attr_tuple += (attr_value_id,)
                attr_size = attr_data['attr_size']
                if attr_size:
                    attr_value_id = self.__save_dimensions__('Size', attr_size)
                    attr_tuple += (attr_value_id,)

                # 将商品的属性值组合信息写入商品属性表
                sql = 'insert ignore into amazonshop_goodsattr (good_attr,good_id,ASIN,brand_name,seller_volume,comment_volume,grade_star,product_name,price,product_description,img_url,img_dir,good_url,source_id) values ' \
                      '(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
                value = [(str(attr_tuple), productId, attr_data['attr_id'],product_info['seller_name'],1,
                          product_info['comments'],product_info['grade_star'], product_info['product_name'],
                          attr_data['attr_price'],product_info['description'],attr_data['attr_photo_url'],
                          img_dir,product_info['product_url'],self.source)]

                self.mysql.insert(sql, value)


        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 将商品信息写入商品表
    def __save_productInfo__(self, product_info, user_id):
            '''
            :param product_info: 商品信息
            :return: 返回商品ID
            '''
            try:
                img_dir = '/static' + product_info['img_dir'].split('static')[1]
                sql = 'insert ignore into amazonshop_goods (ASIN,brand_name,seller_volume,comment_volume,grade_star,product_name,price,product_description,user_id,img_url,img_dir,good_url,source_id) values ' \
                      '(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
                value = [(product_info['product_id'], product_info['seller_name'],1,product_info['comments'],product_info['grade_star'],
                          product_info['product_name'],product_info['product_price'],product_info['description'],
                          user_id,product_info['img_url'],img_dir,product_info['product_url'],self.source)]
                self.mysql.insert(sql, value)

                sql = 'select id from amazonshop_goods WHERE  ASIN = \'%s\' AND  user_id = %s ' % (product_info['product_id'], user_id)
                productId = self.mysql.select(sql)[0]['id']

                return productId

            except Exception as err:
                mylog.logs().exception(sys.exc_info())
                traceback.print_exc()

    # 保存商品数据
    def __save_data__(self, product_info):
        try:
            # 保存主体商品信息，并返回商品id
            productId = self.__save_productInfo__(product_info, self.user_id)

            # 保存变体商品信息
            self.__save_dimensionValues__(productId, product_info)

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    def __save_process__(self, num):

        # 更新数据库的采集进度
        sql = 'update amazonshop_usershopsurl set sum = %s, num = %s WHERE  shop_url = %s'
        self.mysql.update(sql,[(self.product_total, num, self.url)])

        # 更新当前的采集进度（web展示）
        content = {"shop_url":self.url,"total":self.product_total,"number":num,"user_id":self.user_id}
        # file_root = os.getcwd() + '/file/'
        file_root = os.getcwd().replace('utils','') + '/amazon1/amazon/amazon/static/file/'
        if not os.path.exists(file_root):
            os.makedirs(file_root)
        file_path = file_root + 'process.json'
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(content, json_file, ensure_ascii=False)
        pass

    def run(self):

        try:
            print('启动：', self.threadName)
            while not flag_parse:
                try:
                    product_info = self.product_info_queue.get(timeout=3)
                except:
                    time.sleep(3)
                    continue

                # 保存采集进度
                global num
                num += 1
                self.__save_process__(num)
                print('写入商品：', product_info['product_id'],product_info['product_name'])
                self.__save_data__(product_info)

            print('退出：',self.threadName)
            self.mysql.close()

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()


class GetAllProductsLink():

    def __init__(self, url, product_link_queue):
        '''
        :param url: 店铺链接
        :param product_link_queue: 商品链接队列
        '''
        self.url = url
        self.product_link_queue = product_link_queue

    # 采集
    def __clawer__(self, store_url, start):

        try:
            time.sleep(random.randint(1, 3))
            data = self.__request__(store_url, start)
            flag = self.__getProductlink__(data)
            if flag:
                start += 50
                self.__clawer__(store_url, start)
            else:
                return

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 通过requests请求数据
    def __request__(self, store_url, start):
        try:
            query = re.search(r'merchant/(.+)[?]?', store_url).group(1)
            headers = {
                "Host": "www.wish.com",
                "Connection": "keep-alive",
                "X-XSRFToken": "2|4b2588d6|1aa3d7a89c7032fa9cbc4855af130dbf|1566349564",
                "Upgrade-Insecure-Requests": "1",
                # "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 OPR/26.0.1656.60",
                "User-Agent": get_useragent(),
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.wish.com",
                "Content-Type": "application/x-www-form-urlencoded",
                # "Referer": "https://www.wish.com/feed/tabbed_feed_latest/product/5cad47469b83af6034a11c5e?&source=tabbed_feed_latest",
                "Referer": store_url,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cookie": 'cto_lwid=945e9c4b-005f-40f3-b738-dd7ba30ee5d3; notice_preferences=2:; notice_gdpr_prefs=0,1,2:; sweeper_session="2|1:0|10:1566270112|15:sweeper_session|84:ZTFmODIyNDMtNGI3NS00NjU3LWI5ODAtOGJmYTZiZmJlOWI2MjAxOS0wOC0yMCAwMzowMTo0OS4wMjE0MTE=|a7902d7bb960f467a7a344c6315d756eb79b7f1ed812fdd66b68b44cfecf91e8"; sessionRefreshed_5d5a1e062a88498e92d316ea=true; _ga=GA1.2.645152159.1566270177; _gid=GA1.2.2009637231.1566270177; _xsrf=2|4b2588d6|1aa3d7a89c7032fa9cbc4855af130dbf|1566349564; _is_desktop=true; G_ENABLED_IDPS=google; __stripe_sid=c4ce5bc8-85a6-4519-8817-b964880bab89; __stripe_mid=3045ea72-07f3-441b-9a1b-245c6908fd52; bsid=a37cb1fc98023a61fa811c55478da534; _fbp=fb.1.1566267040424.1179357789; _timezone=8; sweeper_uuid=7a9cb4aeb73b4526a88e0968c8026efd'
            }
            post_data = {
                "query": query,
                "start": start,
                "count": "50",
                "transform": "true",
            }
            url = 'https://www.wish.com/api/merchant'
            try:
                res = requests.post(url, headers=headers, data=post_data, verify=False ,timeout=30)
            except:
                count = 1
                while count <= 5:
                    try:
                        res = requests.post(url, headers=headers, data=post_data, verify=False ,timeout=30)
                        break
                    except:
                        err_info = '__request__ reloading for %d time' % count if count == 1 else '__request__ reloading for %d times' % count
                        print(err_info)
                        count += 1
                if count > 5:
                    print("__request__ job failed!")
                    return

            return res.json()

        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    # 获取商品链接
    def __getProductlink__(self, data):
        try:
            data = data['data']
            store_id = data['merchant_info']['id']
            product_datas = data['results']
            if product_datas:
                for product_data in product_datas:
                    product_id = product_data['id']
                    protuct_link = 'https://www.wish.com/merchant/{0}/product/{1}?&source=merchant'.format(store_id,product_id)
                    self.product_link_queue.put(protuct_link)
                return True
            else:
                return False
        except Exception as err:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()

    def run(self):
        '''
        :return: 返回店铺的所有商品链接
        '''
        # 店铺总链接（默认店铺的第一页链接）
        # print('正在采集店铺：', self.url)
        try:
            start = 0
            self.__clawer__(self.url, start)
            print('已获取店铺所有商品的链接！')
        except:
            mylog.logs().exception(sys.exc_info())
            traceback.print_exc()


def update_process():
    # 更新当前的采集进度（web展示）
    content = {}
    file_root = os.getcwd().replace('utils', '') + '/amazon1/amazon/amazon/static/file/'
    if not os.path.exists(file_root):
        os.makedirs(file_root)
    file_path = file_root + 'process.json'
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(content, json_file, ensure_ascii=False)
    pass


def get_useragent():
    useragent_list = [
        "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.133 Safari/534.16",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 OPR/26.0.1656.60",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0.1599.101 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/21.0.1180.71 Safari/537.1 LBBROWSER",
        "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 OPR/26.0.1656.60",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.11 TaoBrowser/2.0 Safari/536.11",
        "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.84 Safari/535.11 SE 2.X MetaSr 1.0",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.122 UBrowser/4.0.3214.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/22.0.1207.1 Safari/537.1",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1092.0 Safari/536.6",
        "Mozilla/5.0 (Windows NT 6.2) AppleWebKit/536.6 (KHTML, like Gecko) Chrome/20.0.1090.0 Safari/536.6",
        "Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.1 (KHTML, like Gecko) Chrome/19.77.34.5 Safari/537.1",
        "Mozilla/5.0 (Windows NT 6.0) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.36 Safari/536.5",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1063.0 Safari/536.3",
        "Mozilla/5.0 (Windows NT 5.1) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1063.0 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.2) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1062.0 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1062.0 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.2) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1061.1 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1061.1 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1061.1 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.2) AppleWebKit/536.3 (KHTML, like Gecko) Chrome/19.0.1061.0 Safari/536.3",
        "Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/535.24 (KHTML, like Gecko) Chrome/19.0.1055.1 Safari/535.24"
    ]
    return random.choice(useragent_list)
    pass


# 采集是否完成的标志
flag_clawer = False
# 解析是否完成的标志
flag_parse = False
# 创建日志
mylog = Mylog('clawer_wish')
# 商品采集数
num = 0


def main(url,user_id,source):

    # 商品链接队列
    product_link_queue = Queue()
    # 商品信息队列
    product_info_queue = Queue()

    # url = 'https://www.wish.com/feed/tabbed_feed_latest/product/5b61581a7b536870e77680d6?&source=tabbed_feed_latest'
    # product_link_queue.put(url)

    get_all_products_link = GetAllProductsLink(url, product_link_queue)
    get_all_products_link.run()


    # 商品总数
    product_total = product_link_queue.qsize()

    if not product_link_queue.empty():

        # 存储3个采集线程的列表集合
        threadcrawl = []
        for i in range(3):
            thread = ThreadClawerWish(i, product_link_queue, product_info_queue, user_id)
            thread.start()
            threadcrawl.append(thread)

        # 存储1个解析线程
        threadparse = []
        for i in range(1):
            thread = ThreadParse(i, user_id, product_info_queue, product_total, url, source)
            thread.start()
            threadparse.append(thread)

        # 等待队列为空，采集完成
        while not product_link_queue.empty():
            pass
        else:
            global flag_clawer
            flag_clawer = True

        for thread in threadcrawl:
            thread.join()

        #等待队列为空，解析完成
        while not product_info_queue.empty():
            pass
        else:
            global flag_parse
            flag_parse = True



        for thread in threadparse:
            thread.join()

        # 更新采集进程，web显示进度
        update_process()

        print('数据采集完成！')
        flag_clawer = False
        flag_parse = False

    else:
        print('数据采集失败！')


if __name__ == '__main__':

    # url = 'https://www.wish.com/merchant/58958f35520a8d4fee49d5c1?&source=merchant'
    url = 'https://www.wish.com/merchant/5533c83986ff95173dc017d0'

    main(url,user_id=1,source=3)

