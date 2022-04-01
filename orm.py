#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'JoshPaul'

import asyncio,logging,aiomysql

#创建基本日志函数，变量sql出现很多次，但我们还不知道它的作用
def log(sql,args=()):
    logging.info('SQL:%s' % sql)

#创建连接池
#异步IO起手式async，创建连接池函数，pool用法如下：
#https://aiomysql.readthedocs.io/en/latest/pool.html?highlight=create_pool
async def create_pool(loop,**kw):
    logging.info('create database connection pool...')
    #声明__pool为全局变量
    global __pool
    #使用这些基本参数来创建连接池
    #await和async是联动的（异步IO）
    __pool = await aiomysql.create_pool(
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop
    )

#Select
async def select(sql,args,size=None):
    log(sql,args)
    global __pool
    #with-as：可以方便我们执行一些清理工作，如close和exit：
    #https://www.jianshu.com/p/c00df845323c

    #这里的await很多，可能看不懂什么意思，我暂时把它理解为：
    #可以让它后面执行的语句等一会，防止多个程序同时执行，达到异步效果
    with(await __pool) as conn:
        #cursor是游标,conn变量表示建立与数据库的连接。
        #'aiomysql.DictCursor'看似复杂，但它仅仅是要求返回字典格式。
        cur = await conn.cursor(aiomysql.DictCursor)
        #cursor游标实例调用execute来执行一条单独的SQL语句，参考自：
        # https://docs.python.org/zh-cn/3.8/library/sqlite3.html?highlight=execute#cursor-objects
        # 这里的 cur 来自上面的 conn.cursor ，然后执行后面的 sql ，具体sql干了啥先不管
        await cur.execute(sql.replace('?','%s'),args or())
        #size为空时为False,上面定义了初始值为None,具体得看传入的参数有没有定义size
        if size:
            #fetchmany可以获取行数为size的多行查询结果集，返回一个列表
            rs = await cur.fetchmany(size)
        else:
            #fetchall可以获取一个查询结果的所有(剩余)行,返回一个列表
            rs = await cur.fetchall()
        #close(),立即关闭cursor,从这一时刻起该cursor将不再可用
        await cur.close()
        #日志:提示返回了多少行
        logging.info('rows returned: %s' % len(rs))
        #现在终于知道了,select函数给我们从SQL返回了一个列表
        return rs

#Execute
async def execut(sql,args):
    log(sql)
    global __pool
    with (await __pool) as conn:
        try:
            cur = await conn.cursor()
            await cur.execute(sql.replace('?','%s'),args)
            #rowcount获取行数,应该表示的是该函数影响的行数
            affected = cur.rowcount
            await cur.close()
        except BaseException as e:
        #源码 except BaseException as e :反正不用这个e,改掉就不报错
            #将错误抛出,BaseException是异常不用管
            raise
        #返回行数
        return affected

#考虑如何定义一个User对象,然后通过数据库表users和它关联起来。
from orm import Model,StringField,IntegerField

class User(Model):
    __table__ = 'users'
    #注意,定义在User类中的__tabel__、id和name是类的属性,不是实例的属性!!所以，
    #在类级别上定义的属性用来描述User对象和表的映射关系，
    #而实例属性必须通过__init__()方法去初始化，所以两者互不干扰：
    id = IntegerField(primary_key=True)
    name = StringField()

#创建实例:
user = User(id=123,name = 'Josh')
#存入数据库:
user.insert()
#查询所有User对象
users = User.findAll()

#这个函数只在下面的 Model元类中被调用， 作用好像是加数量为 num 的'?'
def create_args_string(num):
    L = []
    for _ in range(num):
    # 源码是 for n in range(num):  我看着反正 n 也不会用上，改成这个就不报错了
        L.append('?')
    return ', '.join(L)


#Model只是一个基类,所以先定义ModelMetaclass,再在定义Model时使用metaclass参数
#关于元类,教程在https://www.liaoxuefeng.com/wiki/1016959663602400/1017592449371072
class ModelMetaclass(type):
    # __new__()方法接收到的参数依次是：
    # cls：当前准备创建的类的对象 class
    # name：类的名字 str
    # bases：类继承的父类集合 Tuple
    # attrs：类的方法集合
    def __new__(cls,name,bases,attrs):
        #排队Model类本身,返回它自己
        if name=='Model':
            return type.__new__(cls,name,bases,attrs)
        #获取table名称
        tableName = attrs.get('__table__',None) or name
        #日志:找到名为name的model
        logging.info('found model:%s (table:%s)' % (name,tableName))
        #获取 所有的Field和主键名
        mappings = dict()
        fields = []
        primaryKey = None
        #attrs.items 取决于__new__传入的attrs参数
        for k,v in attrs.items():
            #isinstance函数:如果v和Field类型相同则返回True,不相同则False
            if isinstance(v,Field):
                logging.info('found mapping :%s ==>%s' % (k,v))
                mappings[k] = v
                #这里的v.primary_key我理解为:只要primary_key为True则field为主键
                if v.primary_key:
                    #找到主键,如果主键primaryKey有值时,返回一个错误
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field:%s' % k)
                    #然后直接给主键赋值
                    primaryKey = k
                else:
                    #没找到主键,直接在fields里加上k
                    fields.append(k)
        if not primaryKey:
            #如果主键为None就报错
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            # pop : 如果 key 存在于字典中则将其移除并返回其值,否则返回default
            attrs.pop(k)
        escape_fields = list(map(lambda f: '`%s`' % f,fields))
        attrs['__mappings__'] = mappings # 保存属性和列的映射关系
        attrs['__table__'] = tableName # table 名
        attrs['__primary_key__'] = primaryKey # 主键属性名
        attrs['__fields__'] = fields # 除主键外的属性名
        # 构造默认的 SELECT, INSERT, UPDAT E和 DELETE 语句
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)






